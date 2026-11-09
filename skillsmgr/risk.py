"""Advisory risk evidence over a skill's text and bundled files.

``risk_scan`` explains heuristic signals (shell idioms, credential paths,
hidden Unicode, dynamic code, over-broad triggers, ...).  Every finding is
advisory: it is never a safety verdict and never gates a commit.  The scan
reads only what the caller hands it; ``risk_file_listing`` is the one place a
staged tree is turned into that input.
"""

from __future__ import annotations

import ast
import itertools
import re
import unicodedata
from pathlib import Path

from .sidecar_binding import MANAGER_SIDECARS

__all__ = ["MAX_RISK_FINDINGS", "SCRIPT_SCAN_POLICY", "risk_file_listing", "risk_scan"]

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



def _require_record(record: object, label: str) -> dict:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be a record dict")
    return record


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


# A credential path is only high-risk when the same line acts on it. Measured
# on a real 1,764-instance library on 2026-11-07, bare mentions such as "put
# the key in .env" were 172 of 240 credential findings, all reported high.
# A bare "|" is not an access signal: regex alternation in a detector pattern
# looks the same, and a real pipe always has a command the verb list catches.
_CREDENTIAL_ACCESS_RE = re.compile(
    r"\b(?:cat|less|more|head|tail|read|open|load|source|cp|copy|scp|rsync|"
    r"mv|curl|wget|upload|send|post|exfiltrat\w*|base64|tar|zip|grep|print|"
    r"dump|export|echo)\b|<\s*(?:$|[~$.\w])",
    re.IGNORECASE,
)
_CREDENTIAL_MENTION_NOTE = (
    "; the path is only mentioned here, with no command acting on it on the "
    "same line, so it is kept at low severity"
)


_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
_EVIDENCE_CONTEXT = 60


def _match_severity(kind: str, severity: str, why: str, line: str,
                    matched: str, prefix: str) -> tuple[str, str]:
    """Return the severity and reason for one match on *line*."""
    if _warning_context(prefix):
        return "low", why + _WARNING_CONTEXT_NOTE
    if kind == "credential-path":
        residual = line.replace(matched, " ", 1)
        if not _CREDENTIAL_ACCESS_RE.search(residual):
            return "low", why + _CREDENTIAL_MENTION_NOTE
    return severity, why


def _warning_context(prefix: str) -> bool:
    """Say whether the text *before* a match on its line warns about it.

    Only the prefix counts. A trailing "# never mind" after ``curl … | sh``
    must not downgrade it, and the match itself is excluded, so a suppression
    phrase such as ``never refuse`` is not mistaken for a warning word.
    """
    lowered = prefix.lower()
    return any(phrase in lowered for phrase in _WARNING_CONTEXT_PHRASES)


def _match_evidence(label: str, line: str, start: int, end: int) -> str:
    """Bounded evidence around one match: slice first, then escape."""
    window = line[max(0, start - _EVIDENCE_CONTEXT):end + _EVIDENCE_CONTEXT]
    return _bounded_evidence(f"{label}{window.strip()}")


def _record_match(findings: list[dict], by_token: dict, token: str,
                  finding: dict) -> bool:
    """Keep one finding per token, at the highest severity seen for it.

    Returns False when a new token arrives after the finding bound.
    """
    index = by_token.get(token)
    if index is not None:
        old = findings[index]
        if _SEVERITY_RANK[finding["severity"]] > _SEVERITY_RANK[old["severity"]]:
            findings[index] = finding
        return True
    if len(findings) >= MAX_RISK_FINDINGS:
        return False
    by_token[token] = len(findings)
    findings.append(finding)
    return True


def _pattern_findings(text: str, label: str, pattern: re.Pattern,
                      kind: str, severity: str, why: str) -> list[dict]:
    """Build one finding per distinct bounded match, downgrading warned text.

    The same token repeated through a document is reported once, at the
    highest severity any of its occurrences earned, so an earlier harmless
    mention cannot hide a later dangerous line. Evidence is the text around the
    match rather than the bare token, so a reviewer can judge it.
    """
    findings: list[dict] = []
    by_token: dict[str, int] = {}
    truncated = False
    for match in itertools.islice(pattern.finditer(text),
                                 MAX_RISK_FINDINGS * 4 + 1):
        matched = match.group(0)
        line_start = text.rfind("\n", 0, match.start()) + 1
        line = _match_line(text, match.start(), match.end())
        start, end = match.start() - line_start, match.end() - line_start
        level, reason = _match_severity(kind, severity, why, line, matched,
                                        line[:start])
        finding = {
            "kind": kind,
            "severity": level,
            "evidence": _match_evidence(label, line, start, end),
            "confidence": "heuristic",
            "why": reason,
        }
        if not _record_match(findings, by_token, matched.lower(), finding):
            truncated = True
            break
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
            findings.extend(_dynamic_calls(tree, path))
        # A hostile file can exhaust the parser's recursion or memory (deep
        # attribute chains, a 100k-term expression). That is a skipped file,
        # never an exception escaping the scan.
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            skipped["syntax"] = skipped.get("syntax", 0) + 1
            continue
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
    """Render a dotted attribute chain (``os.path``) for a call target.

    Iterative, so an attribute chain thousands deep cannot recurse.
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


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



_RISK_SCRIPT_SUFFIXES = frozenset({
    ".py", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".psm1", ".bat", ".cmd",
    ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".php",
})
_RISK_LISTING_FILES = 256
_RISK_TEXT_FILES = 50
_RISK_TEXT_BYTES = 256 * 1024
_LISTING_SKIPPED = frozenset({"SKILL.md", "SKILL.md.disabled", *MANAGER_SIDECARS})


def _risk_entry(root: Path, path: Path, texts_read: int) -> dict:
    """One bundled-file entry; script text is attached only within budget."""
    entry: dict = {"path": path.relative_to(root).as_posix()}
    if (path.suffix.lower() in _RISK_SCRIPT_SUFFIXES and texts_read < _RISK_TEXT_FILES
            and path.stat().st_size <= _RISK_TEXT_BYTES):
        try:
            entry["contents"] = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            pass
    return entry


def risk_file_listing(root: str | Path) -> list[dict]:
    """Bounded ``{path, contents?}`` listing of a staged candidate for risk_scan.

    Symlinks are skipped, never followed. ``SKILL.md`` (scanned as the body) and
    manager sidecars are left out. Script-like files up to 256 KiB carry their
    UTF-8 text so the bundled-script and ``ast`` checks can run; every other
    file, ``.pyc`` included, is listed by path only and never read.
    """
    root = Path(root).expanduser()
    if not root.is_dir() or root.is_symlink():
        return []
    entries: list[dict] = []
    texts_read = 0
    try:
        for path in sorted(root.rglob("*")):
            if len(entries) >= _RISK_LISTING_FILES:
                break
            if path.is_symlink() or not path.is_file() or path.name in _LISTING_SKIPPED:
                continue
            entry = _risk_entry(root, path, texts_read)
            texts_read += "contents" in entry
            entries.append(entry)
    except OSError:
        return entries
    return entries
