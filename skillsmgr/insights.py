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

import copy
import difflib
import re
from typing import Callable

from .validator import validate_skill_name

__all__ = [
    "MAX_BODY_DIFF_LINES",
    "MAX_REGISTRY_SEGMENT",
    "REGISTRY_AUDIT_PROVIDERS",
    "REGISTRY_BASE_URL",
    "REGISTRY_PREVIEW_POLICY",
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

_SCRIPT_RE = re.compile(
    r"(?i)\b(rm\s+-rf|curl\b.{0,40}\|\s*sh|wget\b.{0,40}\|\s*sh|"
    r"powershell\b.{0,20}-(?:enc|hidden)|chmod\s+\+x|sudo\s+)"
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
    """Explainable static scan over body, links, tools, and phrases."""
    _require_record(record, "record")
    findings: list[dict] = []
    body = str(record.get("body") or "")
    findings.extend(_scan_script_patterns(body))
    findings.extend(_scan_link_targets(body))
    findings.extend(_scan_tool_grants(record))
    findings.extend(_scan_suspicious_phrases(body))
    findings.extend(_scan_extension_keys(record))
    findings.extend(_scan_bare_urls(body, findings))
    return findings


def _scan_script_patterns(body: str) -> list[dict]:
    """Match shell/destructive command patterns in instruction text."""
    return [{"kind": "script", "severity": "high",
             "evidence": match.group(0).strip()[:120],
             "why": "shell/destructive command pattern in skill "
                    "instructions; review before trusting"}
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


def registry_preview(entry: dict, trust_confirmed: bool = False) -> dict:
    """Offline registry dry-run: preview without download or install."""
    _require_record(entry, "entry")
    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError("registry entry must carry a valid skill name")
    name = validate_skill_name(raw_name.strip())
    blockers: list[str] = []
    if not trust_confirmed:
        blockers.append("trust not confirmed: review source preview and "
                        "provenance, then confirm explicitly")
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
        "may_install": not blockers,
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


def install_argv(source: str, runner: str = "npx", scope: str = "global",
                 agents=None, skills=None, copy: bool = False,
                 list_only: bool = False) -> list[str]:
    """Render the ecosystem-runner argv for one install request."""
    if not isinstance(source, str) or not _INSTALL_VALUE_RE.fullmatch(source) \
            or source.startswith("-"):
        raise ValueError(f"invalid install source {source!r}")
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
            if not isinstance(value, str) or not _INSTALL_VALUE_RE.fullmatch(value) \
                    or value.startswith("-"):
                raise ValueError(f"invalid {label} value {value!r}")
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
    blockers: list[str] = []
    if not trust_confirmed:
        blockers.append("trust not confirmed: review the source and audit "
                        "links, then confirm explicitly")
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
        "hash_status": "provided" if content_hash else "not-provided",
        "hash_use": "compare the registry hash with a stored value to detect "
                    "upstream change without re-fetching files",
        "target_scope": scope,
        "runner": runner,
        "install_command": command,
        "steps": [
            "preview (offline): reference parsed, audit links and hash shown",
            f"dry-run: {command}",
            "confirm trust explicitly (advisory gate)",
            f"run: {command} (set DISABLE_TELEMETRY=1 to opt out of runner telemetry)",
            "validate the installed copy with `validate`",
            "store the registry hash to detect later upstream change",
        ],
        "may_install": not blockers,
        "trust_confirmed": bool(trust_confirmed),
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
