"""Reviewed batch operations over exact physical skill instances.

A preview resolves each requested target against the current scope rows and
binds the plan id to every target's content hash, enabled state and (for
sync and remove) whole-tree hash.  Execution recomputes the plan and refuses a
stale one, then applies each target independently and reports per-item
results; a batch is never atomic.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from . import scopes
from .catalog import plan_hash
from .errors import StoreError

OPERATIONS = ("enable", "disable", "remove", "sync")

def _batch_target_inputs(item: object) -> tuple[str, str, str]:
    if not isinstance(item, dict):
        raise StoreError("each batch target must be an object")
    name = item.get("name")
    scope = item.get("scope")
    if not isinstance(name, str) or not name.strip() or not isinstance(scope, str) or not scope.strip():
        raise StoreError("each batch target needs a name and scope")
    return name.strip(), scope.strip(), str(item.get("physical_path") or item.get("path") or "")

def _batch_target_candidates(
    name: str, scope: str, physical: str, records: list[dict]
) -> list[dict]:
    candidates = [row for row in records if row.get("name") == name and row.get("scope") == scope]
    if physical:
        candidates = [
            row for row in candidates
            if str(row.get("physical_path") or row.get("path") or "") == physical
        ]
    return candidates

def _batch_file_digest(entry: Path, total: int) -> tuple[bytes, int]:
    fd = os.open(entry, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise StoreError("batch skill tree contains a non-regular file")
        size = 0
        file_hash = hashlib.sha256()
        while chunk := stream.read(65536):
            size += len(chunk)
            total += len(chunk)
            if size > 4 * 1024 * 1024 or total > 16 * 1024 * 1024:
                raise StoreError("batch skill tree exceeds the size limit")
            file_hash.update(chunk)
        return file_hash.digest(), total

def _batch_tree_hash(path: object) -> str:
    """Hash at most 256 entries, depth 16, 4 MiB per file and 16 MiB total."""
    root = Path(str(path or ""))
    digest = hashlib.sha256()
    count = total = 0
    try:
        if root.is_symlink() or not root.is_dir():
            raise StoreError("batch skill tree is unavailable or a symlink")
        for base, dirs, files in os.walk(root, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
            dirs.sort()
            files.sort()
            for name in dirs + files:
                entry = Path(base) / name
                relative = entry.relative_to(root)
                count += 1
                if count > 256 or len(relative.parts) > 16:
                    raise StoreError("batch skill tree exceeds the entry or depth limit")
                info = entry.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise StoreError("batch skill tree contains a symlink")
                encoded = str(relative).encode("utf-8")
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
                if stat.S_ISDIR(info.st_mode):
                    digest.update(b"D")
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise StoreError("batch skill tree contains a non-regular file")
                digest.update(b"F")
                file_digest, total = _batch_file_digest(entry, total)
                digest.update(file_digest)
        return digest.hexdigest()
    except (OSError, UnicodeError, ValueError) as exc:
        raise StoreError(f"could not inspect batch skill tree: {exc}") from exc

def _batch_rooted_path(value: object, scope, base: Path) -> Path:
    path = Path(os.path.abspath(str(value or "")))
    alias = Path(os.path.abspath(scope.base))
    try:
        return base / path.relative_to(alias)
    except ValueError:
        return path

def _batch_tree_evidence(row: dict) -> str:
    """Validate the named scope entry before reading any tree bytes."""

    if row.get("read_only") or row.get("instance_state") in {"link_escape", "link_followed"}:
        raise StoreError("batch skill is not a writable scope entry")
    scope = scopes.scope_by_id(row.get("scope"))
    if scope is None:
        raise StoreError("batch skill scope is unavailable")
    base = scope.base.resolve()
    named = _batch_rooted_path(row.get("path"), scope, base)
    try:
        relative = named.relative_to(base)
    except ValueError as exc:
        raise StoreError("batch skill path is outside its scope") from exc
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise StoreError("batch skill path contains a symlink")
    safe = scopes.safe_scope_skill_path(scope, row.get("name"))
    observed = row.get("physical_path") or row.get("path")
    if named != safe.resolve() or named != _batch_rooted_path(observed, scope, base):
        raise StoreError("batch skill path does not match the named scope entry")
    return _batch_tree_hash(named)

def _batch_optional_tree(row: dict, include_tree: bool) -> str | None:
    return _batch_tree_evidence(row) if include_tree else None

def _batch_destination(row: dict) -> dict:
    return {"scope": row.get("scope"), "physical_path": row.get("physical_path") or row.get("path"),
            "content_hash": row.get("content_hash"), "disabled": bool(row.get("disabled")),
            "tree_hash": _batch_tree_evidence(row)}

def resolve_target(item: object, records: list[dict], seen: set[tuple[str, str, str]], *, include_tree: bool = True) -> dict:
    name, scope, physical = _batch_target_inputs(item)
    candidates = _batch_target_candidates(name, scope, physical, records)
    if not candidates:
        raise StoreError(f"batch target is no longer present: {scope}/{name}")
    if len(candidates) > 1:
        raise StoreError(f"batch target is ambiguous; include its physical_path: {scope}/{name}")
    row = candidates[0]
    path = str(row.get("physical_path") or row.get("path") or "")
    key = (scope, name, path)
    if key in seen:
        raise StoreError(f"duplicate batch target: {scope}/{name}")
    seen.add(key)
    return {
        "name": name,
        "scope": scope,
        "scope_label": row.get("scope_label", scope),
        "path": row.get("path"),
        "physical_path": row.get("physical_path") or row.get("path"),
        "disabled": bool(row.get("disabled")),
        "instance_state": row.get("instance_state", "unresolved"),
        "content_hash": row.get("content_hash"),
        "tree_hash": _batch_optional_tree(row, include_tree),
    }

def _sync_destinations(name: str, data: dict, records: list[dict]) -> list[dict]:
    """The destination copies a sync would overwrite, as observed at preview."""
    wanted = set(requested_scopes(data))
    return sorted(
        (
            _batch_destination(row)
            for row in records
            if row.get("name") == name and row.get("scope") in wanted
        ),
        key=lambda item: (str(item["scope"]), str(item["physical_path"])),
    )

def _with_sync_destinations(targets: list[dict], data: dict, records: list[dict]) -> list[dict]:
    if data.get("operation") == "sync":
        for target in targets:
            target["destinations"] = _sync_destinations(target["name"], data, records)
    return targets

def _resolve_targets(data: dict) -> list[dict]:
    """Validate and resolve an exact physical target selection."""
    raw = data.get("targets")
    if not isinstance(raw, list) or not raw or len(raw) > 500:
        raise StoreError("targets must be a non-empty list of at most 500 items")

    records = scopes.list_all()
    seen: set[tuple[str, str, str]] = set()
    targets = [resolve_target(item, records, seen, include_tree=data.get("operation") in {"remove", "sync"}) for item in raw]
    return _with_sync_destinations(targets, data, records)

def requested_scopes(data: dict, name: str = "to_scopes") -> list[str]:
    """Return a validated list of scope ids, or raise a clean 400.

    ``/api/sync`` validated nothing: ``to_scopes: [123]`` answered 200 and
    reflected the integer back as an "unknown scope", and ``to_scopes:
    "global"`` answered 200 by iterating the string's *characters* -- six
    "unknown scope" entries, one per letter of "global" (docs/24 §D3-8).
    """
    raw = data.get(name)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise StoreError(f"{name} must be a list of scope ids")
    scopes: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            raise StoreError(f"{name} entries must be scope id strings, got {entry!r}")
        trimmed = entry.strip()
        if not trimmed:
            raise StoreError(f"{name} entries must not be empty")
        scopes.append(trimmed)
    return scopes

def plan(operation: str, targets: list[dict], data: dict) -> dict:
    options = {
        "force": bool(data.get("force")),
        "to_scopes": sorted(set(requested_scopes(data))),
    }
    return {
        "operation": operation,
        "targets": targets,
        "target_count": len(targets),
        "atomic": False,
        "partial_failure": True,
        "recovery": "remove creates per-item trash snapshots; other actions report each item",
        "options": options,
        "plan_id": plan_hash(operation, targets, options),
    }


def _operation(data: dict) -> str:
    operation = data.get("operation")
    if operation not in OPERATIONS:
        raise StoreError("batch operation must be enable, disable, remove, or sync")
    return operation


def preview(data: dict) -> dict:
    """Resolve the requested targets and return the plan to approve."""
    operation = _operation(data)
    if operation == "sync" and not isinstance(data.get("to_scopes"), list):
        raise StoreError("sync batch plans require a to_scopes list")
    return plan(operation, _resolve_targets(data), data)


def _apply(operation: str, target: dict, options: dict) -> dict:
    if operation in ("enable", "disable"):
        desired = operation == "enable"
        if target["disabled"] == (not desired):
            return {"result": "already-set"}
        return scopes.toggle_skill(target["scope"], target["name"], enable=desired)
    if operation == "remove":
        return scopes.remove_skill(target["scope"], target["name"], purge=False)
    return scopes.sync_skill(target["name"], target["scope"], options["to_scopes"], force=bool(options["force"]))


def execute(data: dict) -> dict:
    """Apply an approved plan, refusing one the current state no longer matches."""
    operation = _operation(data)
    targets = _resolve_targets(data)
    current = plan(operation, targets, data)
    if data.get("plan_id") != current["plan_id"]:
        raise StoreError("batch preview is stale; review the current targets again")
    if operation == "sync" and not current["options"]["to_scopes"]:
        raise StoreError("sync batch plans require at least one target scope")
    results: list[dict] = []
    for target in targets:
        item = {"name": target["name"], "scope": target["scope"], "status": "ok"}
        try:
            item.update(_apply(operation, target, current["options"]))
        except (StoreError, OSError, ValueError) as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
        results.append(item)
    failures = [item for item in results if item["status"] == "failed"]
    return {
        "operation": operation,
        "plan_id": current["plan_id"],
        "target_count": len(targets),
        "results": results,
        "ok": not failures,
        "partial": bool(failures) and len(failures) < len(results),
    }
