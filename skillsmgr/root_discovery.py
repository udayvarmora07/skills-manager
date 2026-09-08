"""Internal root discovery and observation helpers for scope adapters."""

from __future__ import annotations

import os
from pathlib import Path


def resolved_root(scope) -> Path:
    """Return the physical root identity used for deduplication."""
    return scope.base.expanduser().resolve()


def unique_physical_scopes(scopes: list) -> list:
    """Keep the first descriptor for each resolved physical root."""
    seen: set[Path] = set()
    unique: list = []
    for scope in scopes:
        root = resolved_root(scope)
        if root in seen:
            continue
        seen.add(root)
        unique.append(scope)
    return unique


def availability(scope) -> str:
    """Classify a root as writable, read-only, missing, or unsupported."""
    if not scope.supported:
        return "unsupported"
    if not scope.base.is_dir():
        return "missing"
    if not scope.writable or not os.access(scope.base, os.W_OK):
        return "read-only"
    return "writable"


def annotate_instance_states(records: list[dict]) -> list[dict]:
    """Add observed states without making precedence/effective-state claims."""
    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(record["name"], []).append(record)
    for record in records:
        group = groups[record["name"]]
        states: list[str] = []
        if record.get("malformed"):
            states.append("invalid")
        if record.get("disabled"):
            states.append("disabled")
        if len(group) > 1:
            states.append("duplicated")
            descriptions = {(item.get("description") or "").strip() for item in group}
            if len(descriptions) > 1:
                states.append("divergent")
        if record.get("consumer") is None and record.get("scope") != "global":
            states.append("unmanaged")
        if not states:
            states.append("active")
        record["instance_states"] = states
        record["instance_state"] = states[0]
        record["effective_state"] = "unresolved"
    return records


def project_scope_specs() -> tuple[tuple[str, str, bool, str | None], ...]:
    """Return project-local scope descriptors and discovery capabilities."""
    return (
        ("Project .agents", ".agents/skills", True, "shared-agent-skills"),
        ("Project .claude", ".claude/skills", False, "claude-code"),
        ("Project .cursor", ".cursor/skills", True, "cursor"),
        ("Project .opencode", ".opencode/skills", True, "opencode"),
        ("Project skills", "skills", False, None),
    )