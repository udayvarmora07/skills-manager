"""Compatibility API for advisory, read-only insight helpers.

Risk scanning, registry parsing, and install rendering are owned by their
respective domain modules. The legacy entry points retain their strict input
contract while delegating those operations.
"""
from __future__ import annotations

import copy
import difflib
from typing import Callable

from .validator import validate_skill_name
from .risk import MAX_RISK_FINDINGS, SCRIPT_SCAN_POLICY, risk_scan
from .registry import MAX_REGISTRY_SEGMENT, REGISTRY_AUDIT_PROVIDERS, REGISTRY_BASE_URL, registry_reference
from .install import REGISTRY_PREVIEW_POLICY, RUNNERS, offline_registry_gate, install_value
from .errors import StoreError

__all__ = [
    "MAX_BODY_DIFF_LINES", "MAX_REGISTRY_SEGMENT", "MAX_RISK_FINDINGS",
    "REGISTRY_AUDIT_PROVIDERS", "REGISTRY_BASE_URL", "REGISTRY_PREVIEW_POLICY",
    "SCRIPT_SCAN_POLICY", "consumer_view", "diff_skills", "diff_three_way",
    "install_argv", "install_command_line", "ownership_states",
    "provenance_summary", "update_preview", "quarantine_plan", "risk_scan",
    "registry_bridge_plan", "registry_preview", "registry_reference",
    "eval_plan", "eval_score", "bundle_policy",
]

MAX_BODY_DIFF_LINES = 200
_QUARANTINE_SCOPE = "quarantine"
_RESOLUTION_NOTE = "unresolved-precedence-approval-gated"

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

def registry_preview(entry: dict, trust_confirmed: bool = False) -> dict:
    """Offline registry dry-run: preview without download or install."""
    _require_record(entry, "entry")
    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError("registry entry must carry a valid skill name")
    name = validate_skill_name(raw_name.strip())
    gate = offline_registry_gate(trust_confirmed, entry.get("content_hash"))
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

def _safe_install_value(value: object, label: str) -> str:
    """Keep the legacy strict string contract around the shared value guard."""
    if not isinstance(value, str) or value != value.strip():
        raise ValueError(f"invalid {label} value {value!r}")
    try:
        return install_value(label, value)
    except StoreError:
        raise ValueError(f"invalid {label} value {value!r}") from None


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

def install_argv(source: str, runner: str = "npx", scope: str = "global",
                 agents=None, skills=None, copy: bool = False,
                 list_only: bool = False) -> list[str]:
    """Render an install command with the original strict argument contract."""
    from .install import install_argv as render

    source = _safe_install_value(source, "install source")
    if runner not in tuple(RUNNERS):
        raise ValueError(f"unsupported runner {runner!r}")
    safe_agents = [_safe_install_value(value, "agent") for value in agents or []]
    safe_skills = [_safe_install_value(value, "skill") for value in skills or []]
    return render(source, runner, scope, safe_agents, safe_skills, copy, list_only)


def install_command_line(source: str, runner: str = "npx", scope: str = "global",
                         agents=None, skills=None, copy: bool = False,
                         list_only: bool = False) -> str:
    """Render the strictly validated command as a display string."""
    return " ".join(install_argv(source, runner, scope, agents, skills, copy, list_only))


def registry_bridge_plan(spec: str, runner: str = "npx", scope: str = "global",
                         agents=None, skills=None, copy: bool = False,
                         list_only: bool = False, trust_confirmed: bool = False,
                         description: str | None = None,
                         content_hash: str | None = None) -> dict:
    """Create an offline plan while retaining the legacy strict input rules."""
    from .install import registry_bridge_plan as plan

    reference = registry_reference(spec)
    scope = _require_optional_str(scope, "scope") or "global"
    content_hash = _require_optional_str(content_hash, "content_hash")
    targets = list(skills or []) or ([reference["slug"]] if reference["slug"] else [])
    agent_values = list(agents or [])
    install_argv(reference["source"], runner, scope, agent_values, targets, copy, list_only)
    return plan(spec, runner, scope, agent_values, targets, copy, list_only,
                trust_confirmed, description, content_hash)
