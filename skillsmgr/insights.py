"""Read-only Milestone 9 insight helpers (pure functions, stdlib only).

These helpers answer the "what would happen" questions behind Milestone 9
without changing any locked surface: no new CLI commands or flags, no new
``Store`` public methods, no SQLite schema change, no runtime dependency, no
network access, and no disk mutation. They operate on plain record dicts that
the existing public seams already return (``scopes.list_all``,
``scopes.find_duplicates``, ``loader.load_skill`` observations, and
``Store.history`` rows), so CLI/REST/UI callers can adopt them later through
an approved contract change without re-deriving the policy here.

Every function is pure: inputs are never mutated, results are JSON-safe
dicts/lists of strings, and precedence-aware effective resolution stays
explicitly ``unresolved`` per ADR-002 until the approval-gated
``ConsumerRootBinding`` model lands.
"""

from __future__ import annotations

import ast
import copy
import difflib
import itertools
import re
import unicodedata
from typing import Callable

from .validator import validate_skill_name

__all__ = [
    "MAX_BODY_DIFF_LINES",
    "MAX_REGISTRY_SEGMENT",
    "MAX_RISK_FINDINGS",
    "REGISTRY_AUDIT_PROVIDERS",
    "REGISTRY_BASE_URL",
    "REGISTRY_PREVIEW_POLICY",
    "SCRIPT_SCAN_POLICY",
    "consumer_view",
    "diff_skills",
    "diff_three_way",
    "install_argv",
    "install_command_line",
    "ownership_states",
    "provenance_summary",
    "update_preview",
    "quarantine_plan",
    "risk_scan",
    "registry_bridge_plan",
    "registry_preview",
    "registry_reference",
    "eval_plan",
    "eval_score",
    "bundle_policy",
]

MAX_BODY_DIFF_LINES = 200

# Registry bridge (offline half only).  The skills.sh catalog API needs a
# Vercel OIDC bearer token, so no product code performs a registry request;
# these helpers turn a registry reference into an offline preview plus the
# exact ecosystem-runner command the existing ``install`` surface would run.
REGISTRY_BASE_URL = "https://skills.sh"
# Documented partner slugs on the per-skill security page
# (``/owner/repo/skill/security/{slug}``).
REGISTRY_AUDIT_PROVIDERS = ("agent-trust-hub", "socket", "snyk")
REGISTRY_PREVIEW_POLICY = (
    "offline-only: no registry request, cache write, or credential use; "
    "install stays delegated to the ecosystem runner (npx skills add)"
)
MAX_REGISTRY_SEGMENT = 96

_REGISTRY_SEGMENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_REGISTRY_HOSTS = ("skills.sh", "www.skills.sh")
_INSTALL_VALUE_RE = re.compile(r"[A-Za-z0-9_@./:+-]+")
_INSTALL_RUNNERS = ("npx", "pnpm", "yarn", "bunx", "bun")

_QUARANTINE_SCOPE = "quarantine"
_RESOLUTION_NOTE = "unresolved-precedence-approval-gated"

SCRIPT_SCAN_POLICY = (
    "advisory-only: text-pattern matches are heuristic signals, not proof "
    "of execution, safety, or trust; review and validate independently"
)

_SCRIPT_RE = re.compile(
    r"""
    (?:
        \brm\s+(?:(?:-[a-z]*[rf]|--(?:recursive|force))\s+)+[^\n;`]*
        |\b(?:curl|wget)\b[^\n|]{0,160}\|\s*(?:sh|bash)\b
        |\bbase64\b[^\n|]{0,160}\|\s*(?:sh|bash)\b
        |\bpowershell\b[^\n]{0,80}\s-(?:enc|encodedcommand|hidden)\b
        |\bchmod\s+(?:\+x|[0-7]{3,4})\b
        |\bsudo\s+
        |\bshell\s*=\s*true\b
        |\beval\s*(?:\(|\b)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_URL_RE = re.compile(r"https?://[^\s)`\"']+")
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_TOOL_SPLIT_RE = re.compile(r"[\s,]+")
_RISKY_TOOLS = frozenset(
    {"bash", "shell", "exec", "rm", "curl", "wget", "ssh", "sudo", "powershell"}
)
_SUSPICIOUS_PHRASES = (
    "ignore previous instructions",
    "disable safety",
    "exfiltrate",
    "send credentials",
    "bypass approval",
)

# --- Phase B single-purpose static checks --------------------------------
#
# Written fresh for this project.  The ideas overlap a third-party scanner's
# (SkillSpector, Apache-2.0) categories, but no pattern, id or wording is
# copied from it.  Every check below runs only over data the caller already
# supplied -- the record's body, its description, and an optional bundled-file
# listing -- so this module still reads no filesystem, imports and executes no
# bundled code, and establishes no safety verdict.

MAX_RISK_FINDINGS = 200
PADDING_SPACE_RUN = 200
PADDING_BLANK_LINES = 30
MAX_SCANNED_SCRIPT_FILES = 50
MAX_SCANNED_SCRIPT_CHARS = 256 * 1024

_WARNING_CONTEXT_PHRASES = (
    "do not", "don't", "never", "avoid", "instead of", "unsafe",
)
_WARNING_CONTEXT_NOTE = (
    " Recorded at the lowest severity because the match sits in a warning or "
    "negation context; confirm the surrounding sentence."
)

_REMOTE_EXEC_RE = re.compile(
    r"\b(?:curl|wget)\b[^\n|]{0,160}\|\s*(?:sh|bash|zsh)\b"
    r"|\biex\s*\(\s*iwr\b[^)\n]{0,200}\)"
    r"|\bInvoke-Expression\s*\(\s*Invoke-WebRequest\b",
    re.IGNORECASE,
)
_DECODED_EXEC_RE = re.compile(
    r"\bbase64\b[^\n|]{0,160}\|\s*(?:sh|bash|zsh)\b"
    r"|\beval\s*\(\s*atob\s*\("
    r"|\bexec\s*\(\s*(?:base64\.)?b64decode\s*\("
    r"|\bexec\s*\(\s*codecs\.decode\s*\(",
    re.IGNORECASE,
)
_CREDENTIAL_RE = re.compile(
    r"(?:~/|\$HOME/)?\.ssh(?:/[^\s`\"']*)?"
    r"|(?<!\.ssh/)\bid_rsa\b"
    r"|(?:~/|\$HOME/)?\.aws/credentials\b"
    r"|(?<![\w.])\.netrc\b"
    r"|(?<![\w.-])\.env(?![\w-])(?!\.\w)"
    r"|\bsecurity\s+find-generic-password\b"
    r"|(?:~/|\$HOME/)?\.config/gcloud\b"
    r"|(?:~/|\$HOME/)?\.kube/config\b"
    r"|(?<![\w.])\.npmrc\b",
    re.IGNORECASE,
)
_SUPPRESSION_RE = re.compile(
    r"\bnever\s+refuse\b"
    r"|\bignore\s+(?:all\s+)?previous\s+instructions\b"
    r"|\bdo\s+not\s+mention\s+this\s+skill\b"
    r"|\bwithout\s+warning\s+the\s+user\b"
    r"|\bdo(?:n['\u2019]t|\s+not)\s+tell\s+the\s+user\b",
    re.IGNORECASE,
)
_PERSISTENCE_RE = re.compile(
    r"\bcrontab\b"
    r"|\bsystemctl\s+--user\b"
    r"|(?:~/|\$HOME/)\.config/systemd/user/"
    r"|(?:>>?|\btee\s+(?:-a\s+)?)[^\n]{0,40}"
    r"(?:\.bashrc|\.zshrc|\.bash_profile|\.zprofile|\.profile)\b"
    r"|\bLaunchAgents\b"
    r"|\blaunchctl\s+(?:load|bootstrap)\b",
    re.IGNORECASE,
)
_PADDING_SPACE_RE = re.compile(r"[ \t]{200,}")
_PADDING_BLANK_RE = re.compile(r"(?:\n[ \t]*){31,}")
_BROAD_TRIGGER_RE = re.compile(
    r"\buse\s+for\s+any\b"
    r"|\buse\s+for\s+all\s+tasks\b"
    r"|\balways\s+use\s+this\s+skill\b"
    r"|\buse\s+whenever\b",
    re.IGNORECASE,
)
_BUILTIN_COMMAND_NAMES = frozenset({
    "help", "clear", "compact", "init", "review", "config", "doctor",
    "login", "logout",
})
_DYNAMIC_BUILTINS = frozenset({"exec", "eval", "compile", "__import__"})
_SUBPROCESS_SHELL_CALLS = frozenset({
    "run", "call", "check_call", "check_output", "Popen",
})

_REMOTE_EXEC_WHY = (
    "remote script piped into a shell; the bytes are not reviewed before "
    "execution"
)
_DECODED_EXEC_WHY = (
    "encoded payload is decoded and executed; the executed text is not "
    "visible in this document"
)
_CREDENTIAL_WHY = (
    "credential or secret path; reading it can expose keys the user did not "
    "intend to share"
)
_SUPPRESSION_WHY = (
    "instruction asks the model to withhold warnings or refusals from the "
    "user; English phrases only, so translated equivalents are not detected"
)
_PERSISTENCE_WHY = (
    "persistence mechanism; the change outlives the session and can run later "
    "without the user present"
)
_BYTECODE_WHY = (
    "shipped bytecode is opaque, platform-specific, and unnecessary in a "
    "skill tree"
)
_PADDING_WHY = (
    "long whitespace runs can push hidden text out of view in a rendered "
    "document; the threshold is stated in the evidence"
)
_BROAD_TRIGGER_WHY = (
    "description claims an almost-universal trigger, so the skill can "
    "activate outside the task it was written for"
)
_SHADOW_WHY = (
    "the skill name equals a built-in command, so it can be confused with the "
    "command the user meant"
)
_DYNAMIC_CODE_WHY = (
    "bundled Python builds or runs code dynamically; parsed with ast and "
    "never imported or executed here"
)
_SKIPPED_WHY = (
    "bounded static analysis skipped this file; a missing finding is not "
    "evidence of safety"
)

_SHELL_CHECKS = (
    (_REMOTE_EXEC_RE, "remote-exec", "high", _REMOTE_EXEC_WHY),
    (_DECODED_EXEC_RE, "decoded-exec", "high", _DECODED_EXEC_WHY),
    (_CREDENTIAL_RE, "credential-path", "high", _CREDENTIAL_WHY),
    (_PERSISTENCE_RE, "persistence", "medium", _PERSISTENCE_WHY),
)
_WORDING_CHECKS = (
    (_SUPPRESSION_RE, "suppression", "medium", _SUPPRESSION_WHY),
)


def _canonical_name(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a skill-name string")
    return validate_skill_name(value.strip())


def _require_record(record: object, label: str) -> dict:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be a record dict")
    return record


def _require_records(records: object, label: str) -> list:
    if not isinstance(records, list):
        raise ValueError(f"{label} must be a list of record dicts")
    return records


def _require_optional_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string when present")
    return value


def _record_copy(record: dict) -> dict:
    return copy.deepcopy({key: record.get(key)
                          for key in sorted(record.keys())})


def _coerce_tokens(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
        return None
    return None


def consumer_view(records: list[dict], consumer: str) -> dict:
    """Group one consumer's visible instances without resolving precedence."""
    _require_records(records, "records")
    if not isinstance(consumer, str):
        raise ValueError("consumer must be a string")
    visible = [
        _record_copy(record)
        for record in records
        if isinstance(record, dict) and record.get("consumer") == consumer
    ]
    visible.sort(key=lambda item: str(item.get("name", "")))
    return {
        "consumer": consumer,
        "visible": visible,
        "count": len(visible),
        "resolution": _RESOLUTION_NOTE,
        "note": "Precedence-aware shadowing stays approval-gated (ADR-002); "
        "this view lists observed instances only.",
    }


def _compared_fields(left: dict, right: dict) -> list[str]:
    fields = ["description", "body", "version", "compatibility",
              "allowed_tools", "category", "license"]
    return [field for field in fields
            if (left.get(field) or "") != (right.get(field) or "")]


def diff_skills(old: dict, new: dict) -> dict:
    """Two-way field/body diff between two skill record dicts."""
    _require_record(old, "old")
    _require_record(new, "new")
    changed = _compared_fields(old, new)
    old_body = str(old.get("body") or "").splitlines()
    new_body = str(new.get("body") or "").splitlines()
    lines = list(difflib.unified_diff(
        old_body, new_body, fromfile="current", tofile="incoming",
        lineterm="", n=3,
    )) if "body" in changed else []
    truncated = len(lines) > MAX_BODY_DIFF_LINES
    body_diff = lines[:MAX_BODY_DIFF_LINES] if truncated else lines
    return {
        "name": old.get("name", new.get("name")),
        "changed_fields": changed,
        "body_diff": body_diff,
        "body_diff_truncated": truncated,
    }


def diff_three_way(base: dict, left: dict, right: dict) -> dict:
    """Three-way merge preview: non-conflicting sides win, conflicts hold base."""
    _require_record(base, "base")
    _require_record(left, "left")
    _require_record(right, "right")
    fields = ["description", "body", "version", "compatibility",
              "allowed_tools", "category", "license"]
    merged = {"name": base.get("name", left.get("name", right.get("name")))}
    conflicts: list[str] = []
    sides: dict[str, str] = {}
    for field in fields:
        base_value = base.get(field) or ""
        left_value = left.get(field) or ""
        right_value = right.get(field) or ""
        if left_value == right_value:
            merged[field] = left_value
            sides[field] = "agree"
        elif left_value == base_value:
            merged[field] = right_value
            sides[field] = "right"
        elif right_value == base_value:
            merged[field] = left_value
            sides[field] = "left"
        else:
            merged[field] = base_value
            conflicts.append(field)
            sides[field] = "conflict-holds-base"
    return {"merged": merged, "conflicts": conflicts, "sides": sides}


from .validator import validate_skill_name


def _record_invalid(record: dict) -> bool:
    """Fail-closed invalid check over loader and validator signals.

    ``record["body"]`` is the document body only (frontmatter already
    split by the loader), so it must never be re-validated as a full
    SKILL.md document. ``invalid`` therefore means exactly one of:
    the loader ``malformed`` flag, or ``validator.validate_skill()``
    errors against the record's real skill directory.
    """
    if record.get("malformed"):
        return True
    path = record.get("path")
    name = record.get("name")
    if not isinstance(path, str) or not path or not isinstance(name, str):
        return False
    try:
        from pathlib import Path

        from .validator import validate_skill

        candidate = Path(path)
        skill_dir = candidate if candidate.is_dir() else candidate.parent
        return bool(validate_skill(name, skill_dir).errors)
    except Exception:
        return True


def _ownership_of(record: dict) -> str:
    if _record_invalid(record):
        return "invalid"
    if record.get("scope") == _QUARANTINE_SCOPE:
        return "quarantined"
    if record.get("adopted_from"):
        return "adopted"
    if record.get("consumer") is None and record.get("scope") != "global":
        return "unmanaged"
    return "managed"


def ownership_states(records: list[dict]) -> list[dict]:
    """Classify each record into one of the five ownership states."""
    _require_records(records, "records")
    states = []
    for record in records:
        _require_record(record, "record")
        states.append({"name": record.get("name"),
                       "scope": record.get("scope"),
                       "ownership": _ownership_of(record)})
    return states


def provenance_summary(record: dict) -> dict:
    """Split known provenance/hashes from explicit unknowns."""
    _require_record(record, "record")
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return {"name": record.get("name"), "provenance_status": "unknown",
                "content_hash": record.get("content_hash"),
                "metadata_hash": record.get("metadata_hash"),
                "observed_at": record.get("observed_at")}
    return {
        "name": record.get("name"),
        "provenance_status": "known",
        "provenance": {"path": provenance.get("path"),
                       "scope": provenance.get("scope"),
                       "consumer": provenance.get("consumer")},
        "content_hash": record.get("content_hash"),
        "metadata_hash": record.get("metadata_hash"),
        "observed_at": record.get("observed_at"),
    }


def update_preview(current: dict, incoming: dict,
                   snapshots: list[str] | None = None) -> dict:
    """Preview an update: changed files, token risk, and rollback status."""
    _require_record(current, "current")
    _require_record(incoming, "incoming")
    if snapshots is None:
        snapshots = []
    elif not isinstance(snapshots, list):
        raise ValueError("snapshots must be a list of snapshot ids")
    for item in snapshots:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("snapshots must be a list of snapshot ids")
    snapshots = list(snapshots)
    diff = diff_skills(current, incoming)
    risks: list[str] = []
    old_tokens = _coerce_tokens(current.get("tokens"))
    new_tokens = _coerce_tokens(incoming.get("tokens"))
    if old_tokens is not None and new_tokens is not None and new_tokens > old_tokens:
        risks.append(f"token footprint grows {old_tokens} -> {new_tokens}; "
                     "verify the context budget before syncing")
    if "body" in diff["changed_fields"]:
        risks.append("instruction body changes; re-validate portability "
                     "before activating")
    if diff["changed_fields"] and not snapshots:
        risks.append("no snapshots available; capture one before overwriting")
    return {
        "name": current.get("name", incoming.get("name")),
        "changed_files": diff["changed_fields"],
        "body_diff": diff["body_diff"],
        "risks": risks,
        "rollback_available": bool(snapshots),
        "snapshots": snapshots,
    }


def quarantine_plan(name: str, source: str = "unknown") -> dict:
    """Return a stage-only quarantine plan; performs zero disk mutation."""
    canonical = _canonical_name(name, "name")
    if not isinstance(source, str):
        raise ValueError("source must be a string")
    return {
        "name": canonical,
        "source": source,
        "action": "stage-only",
        "staged_path": f"<data>/quarantine/{canonical}/SKILL.md",
        "activated": False,
        "next_step": "human reviews staged copy, then an approved adopt "
                     "operation moves it into a writable scope",
    }


def risk_scan(record: dict) -> list[dict]:
    """Return explainable, advisory-only signals over a skill record.

    These findings are not an authority decision: the scan cannot determine
    whether an instruction will execute or whether a skill is safe.
    """
    _require_record(record, "record")
    findings: list[dict] = []
    body = str(record.get("body") or "")
    findings.extend(_scan_script_patterns(body))
    findings.extend(_scan_link_targets(body))
    findings.extend(_scan_tool_grants(record))
    findings.extend(_scan_suspicious_phrases(body))
    findings.extend(_scan_extension_keys(record))
    findings.extend(_scan_bare_urls(body, findings))
    findings.extend(_scan_hidden_unicode(record))
    findings.extend(_phase_b_findings(record, body))
    return [dict(finding, advisory=True, authority="advisory")
            for finding in findings]


def _scan_hidden_unicode(record: dict) -> list[dict]:
    """Report bounded, escaped format-control evidence in known text fields."""
    counts: dict[tuple[str, str], int] = {}
    omitted = 0
    for field in ("name", "description", "body", "compatibility", "allowed_tools", "allowed-tools"):
        value = record.get(field)
        if not isinstance(value, str):
            continue
        for char in value:
            if not (unicodedata.category(char) == "Cf" or
                    0xE0000 <= ord(char) <= 0xE007F or
                    unicodedata.bidirectional(char) in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}):
                continue
            key = (field, char)
            if key in counts or len(counts) < 32:
                counts[key] = counts.get(key, 0) + 1
            else:
                omitted += 1
    if not counts:
        return []
    evidence = "; ".join(
        f"{field}: U+{ord(char):04X} {unicodedata.name(char, 'UNNAMED')} ({count} occurrences)"
        for (field, char), count in sorted(counts.items())
    )
    if omitted:
        evidence += f"; {omitted} additional occurrences omitted"
    return [{"kind": "unicode", "severity": "medium", "evidence": evidence,
             "why": "Format, bidirectional, or tag characters can hide or reorder text; review the named fields and code points. This scan is advisory and does not establish safety."}]


def _scan_script_patterns(body: str) -> list[dict]:
    """Match advisory shell/destructive patterns in instruction text."""
    return [{"kind": "script", "severity": "high",
             "evidence": match.group(0).strip()[:120],
             "confidence": "heuristic",
             "why": SCRIPT_SCAN_POLICY}
            for match in _SCRIPT_RE.finditer(body)]


def _scan_link_targets(body: str) -> list[dict]:
    """Classify markdown link targets as external or out-of-root."""
    findings: list[dict] = []
    for target in _LINK_RE.findall(body):
        target = target.strip()
        if target.startswith(("http://", "https://")):
            findings.append({"kind": "link", "severity": "medium",
                             "evidence": target[:160],
                             "why": "external URL; confirm the destination is "
                                    "expected before loading"})
        elif target.startswith("..") or target.startswith("/"):
            findings.append({"kind": "link", "severity": "medium",
                             "evidence": target[:160],
                             "why": "out-of-root relative/absolute link; may "
                                    "escape the skill directory"})
    return findings


def _scan_tool_grants(record: dict) -> list[dict]:
    """Flag broad/destructive tool grants in string tool fields."""
    tools = record.get("allowed_tools") or record.get("allowed-tools") or ""
    if not isinstance(tools, str):
        return []
    return [{"kind": "tool", "severity": "medium",
             "evidence": tool.strip()[:80],
             "why": "broad/destructive tool grant; prefer the "
                    "narrowest tool the skill needs"}
            for tool in _TOOL_SPLIT_RE.split(tools)
            if tool.strip().lower() in _RISKY_TOOLS]


def _scan_suspicious_phrases(body: str) -> list[dict]:
    """Flag untrusted instruction phrases in body text."""
    lowered = body.lower()
    return [{"kind": "pattern", "severity": "high",
             "evidence": phrase,
             "why": "suspicious instruction pattern; treat as "
                    "untrusted until reviewed"}
            for phrase in _SUSPICIOUS_PHRASES if phrase in lowered]


def _scan_extension_keys(record: dict) -> list[dict]:
    """Note consumer-specific frontmatter keys preserved verbatim."""
    extensions = record.get("frontmatter_extensions")
    if not isinstance(extensions, dict) or not extensions:
        return []
    return [{"kind": "pattern", "severity": "low",
             "evidence": ",".join(sorted(extensions))[:160],
             "why": "consumer-specific frontmatter extensions are "
                    "preserved verbatim; confirm they are safe"}]


def _scan_bare_urls(body: str, findings: list[dict]) -> list[dict]:
    """Flag bare external URLs not already covered by link findings."""
    known = {finding["evidence"] for finding in findings
             if finding["kind"] == "link"}
    return [{"kind": "link", "severity": "low",
             "evidence": url[:160],
             "why": "bare external URL outside markdown link "
                    "syntax; confirm before loading"}
            for url in _URL_RE.findall(body) if url[:160] not in known]


def _phase_b_findings(record: dict, body: str) -> list[dict]:
    """Run the Phase B checks over caller-supplied text and file listings."""
    entries = _bundled_entries(record)
    texts = [("", body)] + _script_texts(entries)
    findings: list[dict] = []
    findings.extend(_scan_text_checks(texts, _SHELL_CHECKS))
    wording_texts = list(texts)
    description = record.get("description")
    if isinstance(description, str) and description:
        wording_texts.append(("description: ", description))
    findings.extend(_scan_text_checks(wording_texts, _WORDING_CHECKS))
    findings.extend(_scan_padding(body))
    findings.extend(_scan_description_triggers(record))
    findings.extend(_scan_shipped_bytecode(entries))
    findings.extend(_scan_dynamic_code(entries))
    return _limit_new_findings(findings)


def _bounded_evidence(text: str, limit: int = 160) -> str:
    """Escape non-printable characters and bound one evidence string."""
    escaped = "".join(
        char if char.isprintable() else f"\\u{ord(char):04X}"
        for char in text
    )
    return escaped[:limit]


def _match_line(text: str, start: int, end: int) -> str:
    """Return the line containing ``text[start:end]``."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    return text[line_start:line_end]


def _warning_context(line: str, matched: str) -> bool:
    """Say whether the surrounding line warns about the matched text.

    The matched text itself is removed first, so a suppression phrase such as
    ``never refuse`` is not mistaken for the word "never" that marks a warning.
    """
    residual = line.replace(matched, " ", 1).lower()
    return any(phrase in residual for phrase in _WARNING_CONTEXT_PHRASES)


def _pattern_findings(text: str, label: str, pattern: re.Pattern,
                      kind: str, severity: str, why: str) -> list[dict]:
    """Build one finding per bounded match, downgrading warned-about text."""
    findings: list[dict] = []
    truncated = False
    for match in itertools.islice(pattern.finditer(text),
                                 MAX_RISK_FINDINGS + 1):
        if len(findings) >= MAX_RISK_FINDINGS:
            truncated = True
            break
        matched = match.group(0)
        warns = _warning_context(
            _match_line(text, match.start(), match.end()), matched)
        findings.append({
            "kind": kind,
            "severity": "low" if warns else severity,
            "evidence": _bounded_evidence(f"{label}{matched}"),
            "confidence": "heuristic",
            "why": why + _WARNING_CONTEXT_NOTE if warns else why,
        })
    if truncated:
        last = dict(findings[-1])
        last["evidence"] = (
            f"{last['evidence']}; further matches omitted at the "
            f"{MAX_RISK_FINDINGS}-finding bound"
        )
        findings[-1] = last
    return findings


def _scan_text_checks(texts: list[tuple[str, str]],
                      checks: tuple[tuple[re.Pattern, str, str, str], ...]
                      ) -> list[dict]:
    """Apply single-purpose text checks to labelled body/file chunks."""
    findings: list[dict] = []
    for label, text in texts:
        for pattern, kind, severity, why in checks:
            findings.extend(
                _pattern_findings(text, label, pattern, kind, severity, why))
    return findings


def _bundled_entries(record: dict) -> list[dict]:
    """Return the optional bundled-file listing the caller supplied.

    The accepted shape is the registry snapshot's: a list of mappings carrying
    ``path`` and, when the bytes are already in memory, ``contents``.  A
    record without a listing yields no entries, and nothing is read from disk.
    """
    entries = record.get("files")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _entry_path(entry: dict) -> str:
    path = entry.get("path")
    return path if isinstance(path, str) else ""


def _entry_text(entry: dict) -> str:
    for key in ("contents", "content", "text"):
        value = entry.get(key)
        if isinstance(value, str):
            return value
    return ""


def _script_texts(entries: list[dict]) -> list[tuple[str, str]]:
    """Label in-memory bundled text for the pattern checks, bounded."""
    texts: list[tuple[str, str]] = []
    for entry in entries:
        if len(texts) >= MAX_SCANNED_SCRIPT_FILES:
            break
        text = _entry_text(entry)
        if text and len(text) <= MAX_SCANNED_SCRIPT_CHARS:
            texts.append((f"{_entry_path(entry) or '<bundled>'}: ", text))
    return texts


def _scan_padding(body: str) -> list[dict]:
    """Report padding runs long enough to hide text off screen."""
    findings: list[dict] = []
    for match in itertools.islice(_PADDING_SPACE_RE.finditer(body),
                                 MAX_RISK_FINDINGS):
        findings.append({
            "kind": "padding", "severity": "low",
            "evidence": f"{len(match.group(0))} consecutive spaces/tabs "
                        f"(threshold {PADDING_SPACE_RUN})",
            "confidence": "heuristic",
            "why": _PADDING_WHY,
        })
    for match in itertools.islice(_PADDING_BLANK_RE.finditer(body),
                                 MAX_RISK_FINDINGS):
        blank_lines = match.group(0).count("\n") - 1
        findings.append({
            "kind": "padding", "severity": "low",
            "evidence": f"{blank_lines} consecutive blank lines "
                        f"(threshold {PADDING_BLANK_LINES})",
            "confidence": "heuristic",
            "why": _PADDING_WHY,
        })
    return findings


def _scan_description_triggers(record: dict) -> list[dict]:
    """Flag over-broad triggers and built-in command name collisions."""
    findings: list[dict] = []
    description = record.get("description")
    if isinstance(description, str):
        for match in itertools.islice(_BROAD_TRIGGER_RE.finditer(description),
                                     MAX_RISK_FINDINGS):
            findings.append({
                "kind": "broad-trigger", "severity": "low",
                "evidence": _bounded_evidence(match.group(0)),
                "confidence": "heuristic",
                "why": _BROAD_TRIGGER_WHY,
            })
    name = record.get("name")
    if isinstance(name, str) and name.strip().lower() in _BUILTIN_COMMAND_NAMES:
        findings.append({
            "kind": "broad-trigger", "severity": "low",
            "evidence": _bounded_evidence(
                f"name '{name.strip()}' equals a built-in command"),
            "confidence": "heuristic",
            "why": _SHADOW_WHY,
        })
    return findings


def _scan_shipped_bytecode(entries: list[dict]) -> list[dict]:
    """Report ``__pycache__``/``.pyc`` entries from the listing only."""
    findings: list[dict] = []
    for entry in entries:
        if len(findings) >= MAX_RISK_FINDINGS:
            break
        path = _entry_path(entry)
        parts = path.replace("\\", "/").split("/")
        if not path or not ("__pycache__" in parts or path.endswith(".pyc")):
            continue
        findings.append({
            "kind": "bytecode", "severity": "low",
            "evidence": _bounded_evidence(path),
            "confidence": "heuristic",
            "why": _BYTECODE_WHY,
        })
    return findings


def _scan_dynamic_code(entries: list[dict]) -> list[dict]:
    """Parse bundled ``.py`` sources with ``ast``; never import or execute."""
    findings: list[dict] = []
    skipped: dict[str, int] = {}
    scanned = 0
    for entry in entries:
        path = _entry_path(entry)
        if not path.endswith(".py"):
            continue
        if scanned >= MAX_SCANNED_SCRIPT_FILES:
            skipped["count"] = skipped.get("count", 0) + 1
            continue
        text = _entry_text(entry)
        if len(text) > MAX_SCANNED_SCRIPT_CHARS:
            skipped["size"] = skipped.get("size", 0) + 1
            continue
        scanned += 1
        try:
            tree = ast.parse(text, filename=path)
        except (SyntaxError, ValueError):
            skipped["syntax"] = skipped.get("syntax", 0) + 1
            continue
        findings.extend(_dynamic_calls(tree, path))
    findings.extend(_skipped_notes(skipped))
    return findings


def _dynamic_calls(tree: ast.AST, path: str) -> list[dict]:
    """Report dynamic-execution call sites in one parsed file."""
    findings: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        label = _dynamic_call_label(node)
        if label is None:
            continue
        findings.append({
            "kind": "dynamic-code", "severity": "medium",
            "evidence": _bounded_evidence(f"{path}:{node.lineno} {label}"),
            "confidence": "heuristic",
            "why": _DYNAMIC_CODE_WHY,
        })
        if len(findings) >= MAX_RISK_FINDINGS:
            break
    return findings


def _dynamic_call_label(node: ast.Call) -> str | None:
    """Name one dynamic-execution call, or return ``None`` for anything else."""
    func = node.func
    if isinstance(func, ast.Name) and func.id in _DYNAMIC_BUILTINS:
        return f"{func.id}(...)"
    if not isinstance(func, ast.Attribute):
        return None
    owner = _dotted_name(func.value)
    if owner == "os" and func.attr in {"system", "popen"}:
        return f"os.{func.attr}(...)"
    if (owner == "subprocess" and func.attr in _SUBPROCESS_SHELL_CALLS
            and _has_shell_true(node)):
        return f"subprocess.{func.attr}(..., shell=True)"
    return None


def _dotted_name(node: ast.AST) -> str:
    """Render a dotted attribute chain (``os.path``) for a call target."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else ""
    return ""


def _has_shell_true(node: ast.Call) -> bool:
    for keyword in node.keywords:
        value = keyword.value
        if (keyword.arg == "shell" and isinstance(value, ast.Constant)
                and value.value is True):
            return True
    return False


def _skipped_notes(skipped: dict[str, int]) -> list[dict]:
    """Report bounded-analysis skips so a missing finding is not silent."""
    reasons = (
        ("syntax", "a syntax error"),
        ("size", f"over the {MAX_SCANNED_SCRIPT_CHARS} character scan limit"),
        ("count", f"past the {MAX_SCANNED_SCRIPT_FILES}-file scan limit"),
    )
    return [{
        "kind": "dynamic-code", "severity": "low",
        "evidence": f"{skipped[key]} bundled Python file(s) not analyzed: "
                    f"{reason}",
        "confidence": "heuristic",
        "why": _SKIPPED_WHY,
    } for key, reason in reasons if skipped.get(key)]


def _limit_new_findings(findings: list[dict]) -> list[dict]:
    """Bound the Phase B findings and say how many were omitted."""
    if len(findings) <= MAX_RISK_FINDINGS:
        return findings
    kept = findings[:MAX_RISK_FINDINGS]
    omitted = len(findings) - MAX_RISK_FINDINGS
    last = dict(kept[-1])
    last["evidence"] = f"{last['evidence']}; {omitted} additional matches omitted"
    kept[-1] = last
    return kept


def registry_preview(entry: dict, trust_confirmed: bool = False) -> dict:
    """Offline registry dry-run: preview without download or install."""
    _require_record(entry, "entry")
    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError("registry entry must carry a valid skill name")
    name = validate_skill_name(raw_name.strip())
    gate = _offline_registry_gate(trust_confirmed, entry.get("content_hash"))
    blockers: list[str] = list(gate["blockers"])
    description = entry.get("description")
    if not isinstance(description, str) or not description.strip():
        blockers.append("entry has no description; provenance is incomplete")
        description = description if isinstance(description, str) else ""
    source = entry.get("source", "unknown")
    _require_optional_str(source, "source")
    target_scope = entry.get("scope", "global")
    _require_optional_str(target_scope, "scope")
    content_hash = _require_optional_str(entry.get("content_hash"),
                                         "content_hash")
    steps = ["download", "validate", "stage", "activate"]
    return {
        "name": name,
        "source": source,
        "description": description,
        "content_hash": content_hash,
        "target_scope": target_scope,
        "dry_run": steps,
        "may_install": gate["may_install"],
        "trust_confirmed": gate["trust_confirmed"],
        "trust_requested": gate["trust_requested"],
        "trust_status": gate["trust_status"],
        "trust_verified": gate["trust_verified"],
        "eligibility_status": gate["eligibility_status"],
        "hash_status": gate["hash_status"],
        "hash_verified": gate["hash_verified"],
        "blockers": blockers,
    }


def _offline_registry_gate(trust_requested: object,
                           content_hash: object) -> dict:
    """Describe what an offline preview can and cannot establish.

    The legacy fields are retained for payload compatibility.  In offline
    mode, ``trust_confirmed`` and ``may_install`` deliberately never become
    true, while caller intent and a supplied hash remain observable through
    explicitly unverified fields.
    """
    requested = bool(trust_requested)
    supplied_hash = isinstance(content_hash, str) and bool(content_hash)
    blockers = []
    if not requested:
        blockers.append("trust not confirmed: review source preview and "
                        "provenance, then confirm explicitly")
    blockers.append("install eligibility is unverified: offline preview did "
                    "not fetch or authenticate registry metadata")
    return {
        "may_install": False,
        "trust_confirmed": False,
        "trust_requested": requested,
        "trust_status": "unverified-offline" if requested else "not-confirmed",
        "trust_verified": False,
        "eligibility_status": "unverified-offline",
        "hash_status": "unverified-provided" if supplied_hash else "not-provided",
        "hash_verified": False,
        "blockers": blockers,
    }


def _registry_segment(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} segment must be a non-empty string")
    if len(value) > MAX_REGISTRY_SEGMENT:
        raise ValueError(f"{label} segment is too long (max {MAX_REGISTRY_SEGMENT})")
    if not _REGISTRY_SEGMENT_RE.fullmatch(value):
        raise ValueError(f"unsafe {label} segment: {value!r}")
    return value


def _registry_segments(path_text: str, label: str) -> list[str]:
    if not path_text or path_text.startswith("/") or path_text.endswith("/") or "//" in path_text:
        raise ValueError(f"unsupported registry reference: {path_text!r}")
    return [_registry_segment(part, label) for part in path_text.split("/")]


def registry_audit_links(source: str, slug: str | None,
                         providers=REGISTRY_AUDIT_PROVIDERS) -> list[dict]:
    """Linkable per-skill audit pages (never fetched by this tool)."""
    if not slug:
        return []
    base = f"{REGISTRY_BASE_URL}/{source}/{slug}/security"
    return [{"provider": _registry_segment(provider, "provider"),
             "url": f"{base}/{provider}"} for provider in providers]


def _registry_result(source: str, slug: str | None, spec: str) -> dict:
    registry_id = f"{source}/{slug}" if slug else None
    return {
        "spec": spec,
        "form": "skill" if slug else "source",
        "source": source,
        "slug": slug,
        "registry_id": registry_id,
        "page_url": f"{REGISTRY_BASE_URL}/{registry_id}" if registry_id else None,
        "audit_links": registry_audit_links(source, slug),
    }


def _registry_from_url(spec: str) -> dict:
    match = re.match(r"https?://([^/\s?#]+)([^\s?#]*)", spec)
    if match is None:
        raise ValueError(f"unsupported registry URL: {spec!r}")
    host = match.group(1).lower()
    # A URL path always carries a leading separator; the bare-reference form
    # must not, so strip it here instead of loosening the shared rule.
    path_text = match.group(2)[1:] if match.group(2).startswith("/") else match.group(2)
    if host in ("github.com", "www.github.com"):
        segments = _registry_segments(path_text, "source")
        if len(segments) < 2:
            raise ValueError(f"unsupported GitHub URL: {spec!r}")
        return _registry_result("/".join(segments[:2]), None, spec)
    if host not in _REGISTRY_HOSTS:
        raise ValueError(f"unsupported registry host: {host!r}")
    segments = _registry_segments(path_text, "registry")
    if len(segments) == 1:
        return _registry_result(segments[0], None, spec)
    # A skills.sh page path is always ``{source}/{slug}``, so the final
    # segment is the skill slug (``mintlify.com/mintlify`` = well-known
    # source, ``vercel-labs/skills/find-skills`` = GitHub source + slug).
    return _registry_result("/".join(segments[:-1]), segments[-1], spec)


def registry_reference(spec: str) -> dict:
    """Parse a registry reference offline (no request, no cache, no token).

    Accepted forms: ``owner/repo`` (a source), ``owner/repo/slug`` (a skill id
    in ``{source}/{slug}`` form), ``https://skills.sh/{source}/{slug}``, and
    ``https://github.com/owner/repo`` (the documented ``installUrl`` form).
    """
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("registry reference must be a non-empty string")
    raw = spec.strip()
    if len(raw) > 512:
        raise ValueError("registry reference is too long (max 512 characters)")
    if "://" in raw:
        return _registry_from_url(raw)
    segments = _registry_segments(raw, "registry")
    if len(segments) <= 2:
        return _registry_result("/".join(segments), None, raw)
    if len(segments) == 3:
        return _registry_result("/".join(segments[:2]), segments[2], raw)
    raise ValueError(f"unsupported registry reference: {raw!r}")


def _safe_install_value(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) > 256 or not _INSTALL_VALUE_RE.fullmatch(value):
        raise ValueError(f"invalid {label} value {value!r}")
    normalized = value.replace("\\", "/")
    segments = normalized.split("/")
    if (
        value.startswith("-")
        or value.startswith("/")
        or value in {".", ".."}
        or any(segment in {".", ".."} for segment in segments)
        or (len(value) >= 2 and value[1] == ":")
    ):
        raise ValueError(f"invalid {label} value {value!r}")
    return value


def install_argv(source: str, runner: str = "npx", scope: str = "global",
                 agents=None, skills=None, copy: bool = False,
                 list_only: bool = False) -> list[str]:
    """Render the ecosystem-runner argv for one install request."""
    source = _safe_install_value(source, "install source")
    if runner not in _INSTALL_RUNNERS:
        raise ValueError(f"unsupported runner {runner!r}")
    parts = {
        "npx": ["npx", "skills", "add", source],
        "pnpm": ["pnpm", "dlx", "skills", "add", source],
        "yarn": ["yarn", "dlx", "skills", "add", source],
    }.get(runner, ["bunx", "skills", "add", source])
    if scope == "global":
        parts.append("-g")
    for label, values, flag in (("agent", agents, "-a"), ("skill", skills, "-s")):
        for value in values or []:
            value = _safe_install_value(value, label)
            parts.extend([flag, value])
    if copy:
        parts.append("--copy")
    if list_only:
        parts.append("-l")
    return parts


def install_command_line(source: str, runner: str = "npx", scope: str = "global",
                         agents=None, skills=None, copy: bool = False,
                         list_only: bool = False) -> str:
    """Render one install request as the printed command line."""
    return " ".join(install_argv(source, runner, scope, agents, skills, copy,
                                 list_only))


def registry_bridge_plan(spec: str, runner: str = "npx", scope: str = "global",
                         agents=None, skills=None, copy: bool = False,
                         list_only: bool = False, trust_confirmed: bool = False,
                         description: str | None = None,
                         content_hash: str | None = None) -> dict:
    """Offline registry→install bridge plan (no network, no execution).

    Maps a registry reference to the command the existing ``install`` surface
    would run, and surfaces the audit links plus registry hash used to review
    provenance and to detect upstream change without re-fetching files.
    """
    reference = registry_reference(spec)
    scope = _require_optional_str(scope, "scope") or "global"
    content_hash = _require_optional_str(content_hash, "content_hash")
    targets = list(skills or []) or ([reference["slug"]] if reference["slug"] else [])
    command = install_command_line(reference["source"], runner, scope, agents,
                                   targets, copy, list_only)
    gate = _offline_registry_gate(trust_confirmed, content_hash)
    blockers: list[str] = list(gate["blockers"])
    has_description = isinstance(description, str) and bool(description.strip())
    return {
        "spec": reference["spec"],
        "form": reference["form"],
        "source": reference["source"],
        "slug": reference["slug"],
        "registry_id": reference["registry_id"],
        "page_url": reference["page_url"],
        "audit_links": reference["audit_links"],
        "description": description if has_description else "",
        "description_status": "provided" if has_description else "not-provided",
        "provenance_note": "registry metadata (description, installs) needs an "
                           "authenticated catalog read; supply it manually when "
                           "you have it, otherwise provenance stays incomplete",
        "content_hash": content_hash,
        "hash_status": gate["hash_status"],
        "hash_verified": gate["hash_verified"],
        "hash_use": "compare a supplied hash only after an authenticated "
                    "registry read; this offline preview performs no comparison",
        "target_scope": scope,
        "runner": runner,
        "install_command": command,
        "steps": [
            "preview (offline): reference parsed, audit links and hash shown",
            f"dry-run: {command}",
            "record caller trust intent (still unverified offline)",
            "obtain an authenticated registry read before deciding install eligibility",
            f"run: {command} (set DISABLE_TELEMETRY=1 to opt out of runner telemetry)",
            "validate the installed copy with `validate`",
            "store the registry hash to detect later upstream change",
        ],
        "may_install": gate["may_install"],
        "trust_confirmed": gate["trust_confirmed"],
        "trust_requested": gate["trust_requested"],
        "trust_status": gate["trust_status"],
        "trust_verified": gate["trust_verified"],
        "eligibility_status": gate["eligibility_status"],
        "blockers": blockers,
        "network": "deferred: no registry API request, cache, or credential is used",
        "policy": REGISTRY_PREVIEW_POLICY,
    }


def eval_plan(skill: str, cases: list[dict]) -> dict:
    """Provider-neutral eval plan: deterministic cases, stdlib-only runner."""
    name = _canonical_name(skill, "skill")
    if not isinstance(cases, list) or not cases:
        raise ValueError("eval cases must be a non-empty list")
    normalized = []
    for case in cases:
        if not isinstance(case, dict) or "input" not in case or "expect" not in case:
            raise ValueError("each eval case must be a dict with input/expect")
        normalized.append({"input": str(case.get("input", "")),
                           "expect": str(case.get("expect", ""))})
    return {"skill": name, "runner": "stdlib-only", "cases": normalized,
            "policy": "advisory-only: scores never block installs"}


def eval_score(plan: dict, outputs: list[str],
               scorer: Callable[[str, str], bool]) -> dict:
    """Score eval outputs with a caller-supplied deterministic scorer."""
    _require_record(plan, "plan")
    cases = plan.get("cases")
    if not isinstance(cases, list):
        raise ValueError("plan cases must be a list")
    if not isinstance(outputs, list):
        raise ValueError("outputs must align one-to-one with plan cases")
    if not callable(scorer):
        raise ValueError("scorer must be a callable")
    if len(outputs) != len(cases):
        raise ValueError("outputs must align one-to-one with plan cases")
    passed = sum(1 for case, output in zip(cases, outputs)
                 if scorer(str(output), str(case.get("expect", ""))))
    return {"skill": plan.get("skill"), "passed": passed,
            "total": len(cases),
            "advisory": "score informs trust; it does not auto-install"}


def bundle_policy() -> dict:
    """Signed/team bundle position: deferred until trust foundations mature."""
    return {
        "signatures": "deferred",
        "required_before_signing": [
            "single-user trust model is explicit",
            "quarantine workflow is approved and tested",
            "provenance and content hashes are persisted",
            "recovery and rollback behavior is verified",
        ],
        "note": "Team sharing and key distribution need a dedicated "
                "threat-model review (TODO issue #11); no bundle format is "
                "specified here.",
    }
