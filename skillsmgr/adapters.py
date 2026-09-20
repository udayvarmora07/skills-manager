"""Read-only consumer adapter catalog and contained project observations."""

from __future__ import annotations

from pathlib import Path

from . import effective

VERIFIED_ON = "2026-09-09"
_RELOAD = {
    "claude-code": "live change detection is documented",
    "cursor": "startup discovery is documented; refresh behavior is unknown",
    "gemini": "use /skills reload",
    "opencode": "runtime loads the winning definition; cross-root refresh is undocumented",
    "codex": "restart when auto-detection misses a change",
    "commandcode": "live discovery and edits are documented",
}


def _root_record(root: dict) -> dict:
    known = bool(root.get("scope") or root.get("rel") or root.get("path"))
    return {
        "scope": root.get("scope"),
        "relative_path": root.get("rel"),
        "absolute_path": root.get("path"),
        "path_known": known,
        "recursive": bool(root.get("recursive") or root.get("nested")),
        "nested": bool(root.get("nested")),
    }


def catalog() -> list[dict]:
    """Return adapter records derived from the primary-source inventory."""
    records: list[dict] = []
    for adapter_id, spec in effective.CONSUMERS.items():
        roots: list[dict] = []
        tiers: list[dict] = []
        for tier in spec.get("tiers", ()):
            tier_roots = [_root_record(root) for root in tier.get("roots", ())]
            roots.extend(tier_roots)
            tiers.append({
                "id": tier.get("id"),
                "label": tier.get("label"),
                "roots": tier_roots,
                "note": tier.get("note", ""),
            })
        policy = spec.get("policy", "undocumented")
        records.append({
            "id": adapter_id,
            "label": spec.get("label", adapter_id),
            "tier": "verified" if policy == "ordered" else "experimental",
            "status": "verified" if policy == "ordered" else "unknown-precedence",
            "candidate_roots": roots,
            "tiers": tiers,
            "precedence": {
                "policy": policy,
                "status": "documented" if policy == "ordered" else "unknown",
                "evidence": spec.get("source"),
                "notes": spec.get("notes", ""),
            },
            "reload": _RELOAD.get(adapter_id, "reload behavior is undocumented"),
            "platform_support": "portable path rules; availability is observed at runtime",
            "last_verified": VERIFIED_ON,
        })
    return records


def _under_any(path: Path, roots: list[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def project_observation(project: str | Path | None, allowed_roots: list[Path] | None = None) -> dict:
    if project is None or not str(project).strip():
        return {"status": "not-requested", "path": None, "skills_roots": []}
    candidate = Path(str(project)).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError:
        return {"status": "inaccessible", "path": "<redacted>", "skills_roots": []}
    roots = [Path(root).resolve() for root in (allowed_roots or [])]
    if roots and not _under_any(resolved, roots):
        return {
            "status": "outside-managed-roots",
            "path": "<redacted>",
            "skills_roots": [],
            "paths_redacted": True,
        }
    if not resolved.is_dir():
        return {"status": "missing", "path": str(resolved), "skills_roots": []}
    candidates = []
    for rel in (".claude/skills", ".cursor/skills", ".gemini/skills", ".opencode/skills", ".commandcode/skills", ".agents/skills"):
        root = resolved / rel
        candidates.append({"path": str(root), "exists": root.is_dir(), "relative": rel})
    return {"status": "accepted", "path": str(resolved), "skills_roots": candidates, "paths_redacted": False}


def workspaces_payload(project: str | None = None, allowed_roots: list[Path] | None = None) -> dict:
    return {
        "adapters": catalog(),
        "project": project_observation(project, allowed_roots),
        "model": "read-only adapter evidence; effective_state remains unresolved",
    }
