"""Read-only source locks and whole-tree update previews.

This module deliberately stops at evidence.  It never writes a managed skill,
snapshot, provenance sidecar, cache, or SQLite row.  A future approved update
surface can consume the JSON-safe preview after an explicit target review.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .atomic_io import atomic_write_text, mutation_lock
from .insights import risk_scan
from .validator import validate_text


MAX_SOURCE_FILES = 256
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 16 * 1024 * 1024
MAX_SOURCE_PATH_DEPTH = 16
MAX_DIFF_LINES = 200
MAX_TOTAL_DIFF_LINES = 1000
_PROVENANCE_FILENAME = ".skillsmgr-provenance.json"
SOURCE_LOCK_FILENAME = ".skillsmgr-source-lock.json"
MAX_SOURCE_LOCK_BYTES = 32 * 1024
_SOURCE_KINDS = frozenset({"local", "git", "archive", "registry"})
_SOURCE_STATES = frozenset({"local-only", "known-verified", "known-unverified"})
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class SourceLockError(ValueError):
    """Raised when a candidate source cannot be inspected safely."""


def _source_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceLockError(f"{label} must be a non-empty string")
    value = value.strip()
    if len(value) > 2048 or "\x00" in value:
        raise SourceLockError(f"{label} is too long or contains a NUL byte")
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        raise SourceLockError(f"{label} cannot contain credentials")
    if parsed.query or parsed.fragment:
        raise SourceLockError(f"{label} cannot contain query or fragment data")
    return value


def source_identity(kind: str, value: str, *, revision: str | None = None,
                    digest: str | None = None) -> dict:
    """Return a bounded, credential-free source identity record."""
    if kind not in _SOURCE_KINDS:
        raise SourceLockError(f"unsupported source kind {kind!r}")
    identity = {"kind": kind, "value": _source_text(value, "source")}
    if revision is not None:
        identity["revision"] = _source_text(revision, "revision")
    if digest is not None:
        digest = _source_text(digest, "digest")
        if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            raise SourceLockError("digest must be a SHA-256 hex string")
        identity["digest"] = digest.lower()
    return identity


def _relative_file(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SourceLockError("source file escapes its root") from exc
    parts = relative.split("/")
    if not relative or any(part in {"", ".", ".."} for part in parts):
        raise SourceLockError("source file path is not canonical")
    if len(parts) > MAX_SOURCE_PATH_DEPTH or relative.startswith("/") or "\\" in relative:
        raise SourceLockError("source file path exceeds safety bounds")
    return relative


def local_manifest(root: str | Path) -> dict:
    """Read a bounded regular-file manifest without following symlinks."""
    root = Path(root).expanduser()
    try:
        if not root.exists():
            raise SourceLockError("source is missing")
        if not root.is_dir() or root.is_symlink():
            raise SourceLockError("source is inaccessible")
        files = []
        total = 0
        for path in sorted(root.rglob("*")):
            if path.name in {_PROVENANCE_FILENAME, SOURCE_LOCK_FILENAME}:
                continue
            if path.is_symlink():
                raise SourceLockError(f"source contains a symlink: {_relative_file(root, path)}")
            if not path.is_file():
                continue
            relative = _relative_file(root, path)
            raw = path.read_bytes()
            if len(raw) > MAX_SOURCE_FILE_BYTES:
                raise SourceLockError(f"source file exceeds {MAX_SOURCE_FILE_BYTES} bytes: {relative}")
            total += len(raw)
            if total > MAX_SOURCE_TOTAL_BYTES:
                raise SourceLockError(f"source exceeds {MAX_SOURCE_TOTAL_BYTES} bytes")
            files.append({
                "path": relative,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "_raw": raw,
            })
            if len(files) > MAX_SOURCE_FILES:
                raise SourceLockError(f"source has more than {MAX_SOURCE_FILES} files")
    except SourceLockError:
        raise
    except (OSError, UnicodeError) as exc:
        raise SourceLockError(f"source is inaccessible: {exc}") from exc
    if not any(item["path"] in {"SKILL.md", "SKILL.md.disabled"} for item in files):
        raise SourceLockError("source does not contain SKILL.md or SKILL.md.disabled")
    public = [{key: item[key] for key in ("path", "bytes", "sha256")} for item in files]
    digest = hashlib.sha256()
    for item in files:
        encoded_path = item["path"].encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(item["_raw"])
    return {"root": str(root), "files": files, "public_files": public, "sha256": digest.hexdigest()}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SourceLockError(f"source-lock value is not JSON-safe: {exc}") from exc


def _lock_path(skill_dir: str | Path) -> Path:
    return Path(skill_dir).expanduser() / SOURCE_LOCK_FILENAME


def _lock_source(value: object) -> dict:
    if not isinstance(value, dict):
        raise SourceLockError("source-lock source must be an object")
    kind = value.get("kind")
    source_value = value.get("value")
    revision = value.get("revision")
    digest = value.get("digest")
    normalized = source_identity(kind, source_value, revision=revision, digest=digest)
    return normalized


def _lock_target(value: object) -> dict:
    if not isinstance(value, dict):
        raise SourceLockError("source-lock target must be an object")
    physical_path = value.get("physical_path")
    if not isinstance(physical_path, str) or not physical_path.strip():
        raise SourceLockError("source-lock target physical_path is required")
    target = {
        "scope": value.get("scope"),
        "physical_root": value.get("physical_root"),
        "physical_path": physical_path,
        "contained": bool(value.get("contained")),
    }
    for key in ("scope", "physical_root"):
        if target[key] is not None and not isinstance(target[key], str):
            raise SourceLockError(f"source-lock target {key} must be text or null")
    return target


def _validate_lock(value: object) -> dict:
    if not isinstance(value, dict) or value.get("version") != 1:
        raise SourceLockError("source-lock must be a version-1 object")
    source = _lock_source(value.get("source"))
    target = _lock_target(value.get("target"))
    content_hash = value.get("content_hash")
    if not isinstance(content_hash, str) or len(content_hash) != 64 or not _HEX64.fullmatch(content_hash):
        raise SourceLockError("source-lock content_hash must be a SHA-256 hex string")
    checked_at = value.get("checked_at")
    if not isinstance(checked_at, str) or not checked_at.strip() or len(checked_at) > 64:
        raise SourceLockError("source-lock checked_at is invalid")
    state = value.get("state", "local-only")
    if state not in _SOURCE_STATES:
        raise SourceLockError("source-lock state is invalid")
    result = {
        "version": 1,
        "source": source,
        "content_hash": content_hash.lower(),
        "checked_at": checked_at,
        "state": state,
        "target": target,
    }
    if value.get("review_id") is not None:
        review_id = value["review_id"]
        if not isinstance(review_id, str) or not review_id or len(review_id) > 128:
            raise SourceLockError("source-lock review_id is invalid")
        result["review_id"] = review_id
    return result


def source_lock_record(source: dict, content_hash: str, target: dict, *,
                       state: str = "local-only", review_id: str | None = None) -> dict:
    """Build a bounded filesystem-owned source-lock record."""
    value = {
        "version": 1,
        "source": source,
        "content_hash": content_hash,
        "checked_at": _iso_now(),
        "state": state,
        "target": target,
    }
    if review_id is not None:
        value["review_id"] = review_id
    return _validate_lock(value)


def read_source_lock(skill_dir: str | Path) -> dict | None:
    """Read a validated source-lock sidecar, if present."""
    root = Path(skill_dir).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise SourceLockError("source-lock skill directory does not exist safely")
    path = _lock_path(root)
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        raise SourceLockError("source-lock sidecar cannot be a symlink")
    try:
        if path.stat().st_size > MAX_SOURCE_LOCK_BYTES:
            raise SourceLockError("source-lock sidecar is too large")
        return _validate_lock(json.loads(path.read_text(encoding="utf-8")))
    except SourceLockError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise SourceLockError(f"could not read source-lock sidecar: {exc}") from exc


def write_source_lock(skill_dir: str | Path, lock: dict) -> Path:
    """Atomically persist a validated source-lock sidecar beside a skill."""
    root = Path(skill_dir).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise SourceLockError("source-lock skill directory does not exist safely")
    normalized = _validate_lock(lock)
    encoded = _json_bytes(normalized).decode("utf-8") + "\n"
    if len(encoded.encode("utf-8")) > MAX_SOURCE_LOCK_BYTES:
        raise SourceLockError("source-lock sidecar is too large")
    destination = _lock_path(root)
    with mutation_lock(destination):
        if os.path.lexists(destination) and destination.is_symlink():
            raise SourceLockError("source-lock sidecar cannot be a symlink")
        try:
            atomic_write_text(destination, encoded)
            os.chmod(destination, 0o600)
        except OSError as exc:
            raise SourceLockError(f"could not write source-lock sidecar: {exc}") from exc
    return destination


def source_lock_status(skill_dir: str | Path) -> dict:
    """Compare a persisted lock with the current whole-tree content."""
    root = Path(skill_dir).expanduser()
    try:
        lock = read_source_lock(root)
    except SourceLockError as exc:
        return {"state": "inaccessible", "error": str(exc), "lock": None}
    if lock is None:
        return {"state": "missing", "error": None, "lock": None}
    try:
        current = local_manifest(root)
    except SourceLockError as exc:
        return {"state": "inaccessible", "error": str(exc), "lock": lock}
    state = lock["state"] if lock["content_hash"] == current["sha256"] else "changed"
    return {
        "state": state,
        "error": None,
        "lock": lock,
        "content_hash": current["sha256"],
    }


def _line_ending_only(left: bytes, right: bytes) -> bool:
    return left != right and left.replace(b"\r\n", b"\n") == right.replace(b"\r\n", b"\n")


def _looks_binary(raw: bytes) -> bool:
    """Treat NUL/control-bearing payloads as binary, even when UTF-8 decodes."""
    return b"\x00" in raw or any(
        byte < 0x09 or byte in (0x0B, 0x0C, 0x7F) or 0x0E <= byte < 0x20
        for byte in raw
    )


def _text_diff(left: bytes, right: bytes) -> tuple[list[str], bool]:
    if _looks_binary(left) or _looks_binary(right):
        return ["binary content differs; inspect the raw file hashes and sizes"], False
    try:
        before = left.decode("utf-8").splitlines(keepends=True)
        after = right.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        lines = ["binary content differs; inspect the raw file hashes and sizes"]
        return lines, False
    lines = list(difflib.unified_diff(before, after, "current", "candidate"))
    truncated = len(lines) > MAX_DIFF_LINES
    return [line.rstrip("\n") for line in lines[:MAX_DIFF_LINES]], truncated


def _compare_manifests(current: dict, candidate: dict) -> dict:
    old = {item["path"]: item for item in current["files"]}
    new = {item["path"]: item for item in candidate["files"]}
    changes = []
    diff_lines_returned = 0
    diff_total_truncated = False
    for path in sorted(set(old) | set(new)):
        before = old.get(path)
        after = new.get(path)
        if before is None:
            changes.append({
                "path": path,
                "status": "added",
                "candidate": after["sha256"],
                "bytes": after["bytes"],
                "diff_truncated": False,
            })
            continue
        if after is None:
            changes.append({
                "path": path,
                "status": "removed",
                "current": before["sha256"],
                "bytes": before["bytes"],
                "diff_truncated": False,
            })
            continue
        if before["sha256"] == after["sha256"]:
            continue
        diff, per_file_truncated = _text_diff(before["_raw"], after["_raw"])
        line_ending_only = (
            not _looks_binary(before["_raw"])
            and not _looks_binary(after["_raw"])
            and _line_ending_only(before["_raw"], after["_raw"])
        )
        remaining = max(0, MAX_TOTAL_DIFF_LINES - diff_lines_returned)
        if len(diff) > remaining:
            diff = diff[:remaining]
            diff_total_truncated = True
            diff_truncated = True
        else:
            diff_truncated = per_file_truncated
        diff_lines_returned += len(diff)
        changes.append({
            "path": path,
            "status": "changed",
            "current": before["sha256"],
            "candidate": after["sha256"],
            "current_bytes": before["bytes"],
            "candidate_bytes": after["bytes"],
            "line_ending_only": line_ending_only,
            "explanation": (
                "only CRLF/LF line endings differ"
                if line_ending_only
                else "raw file content differs"
            ),
            "diff": diff,
            "diff_truncated": diff_truncated,
        })
    return {
        "changed_files": changes,
        "added": [item["path"] for item in changes if item["status"] == "added"],
        "removed": [item["path"] for item in changes if item["status"] == "removed"],
        "changed": [item["path"] for item in changes if item["status"] == "changed"],
        "line_ending_only": [item["path"] for item in changes if item.get("line_ending_only")],
        "diff_lines_returned": diff_lines_returned,
        "diff_total_truncated": diff_total_truncated,
    }


def _target_summary(target: object, current: Path) -> dict:
    if not isinstance(target, dict):
        return {
            "required": True,
            "scope": None,
            "physical_root": None,
            "physical_path": None,
            "exists": False,
            "writable": False,
            "contained": False,
        }
    physical_path = target.get("physical_path")
    if not isinstance(physical_path, str) or not physical_path.strip():
        raise SourceLockError("target physical_path is required")
    return {
        "required": True,
        "scope": target.get("scope"),
        "physical_root": target.get("physical_root"),
        "physical_path": physical_path,
        "exists": bool(target.get("exists", current.exists())),
        "writable": bool(target.get("writable", os.access(current, os.W_OK))),
        "contained": bool(target.get("contained", False)),
    }


def _validation_evidence(source: Path, name: str) -> tuple[dict, list[dict]]:
    document = source / "SKILL.md"
    if not document.is_file():
        document = source / "SKILL.md.disabled"
    text = document.read_text(encoding="utf-8")
    result = validate_text(text, name=name, skill_dir=source)
    validation = {
        "valid": result.valid,
        "errors": [{"level": item.level, "key": item.key, "message": item.message} for item in result.errors],
        "warnings": [{"level": item.level, "key": item.key, "message": item.message} for item in result.warnings],
    }
    record = {"name": name, "body": result.body, "allowed_tools": result.data.get("allowed-tools")}
    return validation, risk_scan(record)


def preview_local_update(current: str | Path, candidate: str | Path, *, target: dict | None = None,
                         provenance: dict | None = None, name: str | None = None) -> dict:
    """Return a JSON-safe, no-mutation preview for a local candidate tree."""
    current = Path(current).expanduser()
    candidate = Path(candidate).expanduser()
    target_info = _target_summary(target, current)
    name = name or current.name
    if target is None:
        return {
            "review_state": "target-required",
            "source_state": "local-only",
            "source": source_identity("local", str(candidate)),
            "target": target_info,
            "commit_allowed": False,
            "staged": False,
        }
    try:
        current_manifest = local_manifest(current)
    except SourceLockError as exc:
        return {
            "review_state": "target-unavailable",
            "source_state": "inaccessible",
            "source_error": str(exc),
            "target": target_info,
            "commit_allowed": False,
        }
    try:
        candidate_manifest = local_manifest(candidate)
    except SourceLockError as exc:
        message = str(exc)
        state = "missing" if message == "source is missing" else "inaccessible"
        return {
            "review_state": "source-unavailable",
            "source_state": state,
            "source_error": message,
            "source": source_identity("local", str(candidate)),
            "target": target_info,
            "commit_allowed": False,
            "guidance": "relink the source or inspect it before requesting another preview",
        }
    comparison = _compare_manifests(current_manifest, candidate_manifest)
    source_state = "local-only"
    if isinstance(provenance, dict):
        expected = provenance.get("local_snapshot_hash") or provenance.get("content_hash")
        source_state = "known-verified" if provenance.get("hash_verified") else "known-unverified"
        if expected and str(expected).lower() != current_manifest["sha256"]:
            source_state = "changed"
    try:
        validation, risks = _validation_evidence(candidate, name)
    except (OSError, UnicodeError, SourceLockError) as exc:
        validation = {"valid": False, "errors": [{"level": "error", "key": "source", "message": str(exc)}], "warnings": []}
        risks = []
    has_changes = bool(comparison["changed_files"])
    review_state = "blocked" if not validation["valid"] else "review-required" if has_changes else "no-change"
    return {
        "review_state": review_state,
        "source_state": source_state,
        "source": source_identity("local", str(candidate)),
        "current_hash": current_manifest["sha256"],
        "candidate_hash": candidate_manifest["sha256"],
        "comparison": comparison,
        "validation": validation,
        "risk": {"policy": "advisory-only; heuristic evidence is not a safety or trust verdict", "findings": risks},
        "target": target_info,
        "commit_allowed": False,
        "snapshot_required_before_commit": has_changes,
        "staged": False,
    }


def _review_id(preview: dict) -> str:
    evidence = {
        "candidate_hash": preview.get("candidate_hash"),
        "current_hash": preview.get("current_hash"),
        "comparison": preview.get("comparison"),
        "source": preview.get("source"),
        "target": preview.get("target"),
    }
    return hashlib.sha256(_json_bytes(evidence)).hexdigest()


def review_local_update(current: str | Path, candidate: str | Path, *, target: dict,
                        provenance: dict | None = None, name: str | None = None,
                        source: dict | None = None) -> dict:
    """Prepare a review token without staging or mutating the managed tree."""
    current = Path(current).expanduser()
    candidate = Path(candidate).expanduser()
    preview = preview_local_update(
        current, candidate, target=target, provenance=provenance, name=name
    )
    expected_target = str(current.resolve())
    actual_target = preview.get("target", {}).get("physical_path")
    if actual_target != expected_target:
        preview.update({
            "review_state": "target-mismatch",
            "commit_allowed": False,
            "target_error": "target physical_path does not identify the current managed directory",
        })
    elif target.get("contained") is not True:
        preview.update({
            "review_state": "target-unconfirmed",
            "commit_allowed": False,
            "target_error": "target containment must be explicitly confirmed",
        })
    if source is not None:
        preview["source"] = _lock_source(source)
    if preview.get("review_state") == "review-required":
        preview["review_id"] = _review_id(preview)
        preview["approval"] = {
            "required": True,
            "summary": "review the full candidate diff, validation, risks, target, and rollback snapshot before applying",
        }
    else:
        preview["review_id"] = None
    preview["commit_allowed"] = False
    preview["staged"] = False
    return preview


def _copy_tree_without_manager_sidecars(source: Path, destination: Path) -> None:
    """Copy a validated candidate tree without carrying manager evidence forward."""
    try:
        local_manifest(source)
        shutil.copytree(source, destination, symlinks=False)
        for filename in (SOURCE_LOCK_FILENAME, _PROVENANCE_FILENAME):
            (destination / filename).unlink(missing_ok=True)
    except SourceLockError:
        raise
    except (OSError, shutil.Error) as exc:
        raise SourceLockError(f"could not stage source tree: {exc}") from exc


def _snapshot_tree(source: Path, snapshot_root: Path) -> Path:
    source_resolved = source.resolve()
    snapshot_root = snapshot_root.expanduser()
    try:
        snapshot_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(snapshot_root, 0o700)
        if snapshot_root.resolve() == source_resolved or source_resolved.is_relative_to(snapshot_root.resolve()):
            raise SourceLockError("snapshot root cannot contain the managed skill")
        snapshot_id = f"{_iso_now().replace(':', '').replace('-', '')}-{hashlib.sha256(str(source_resolved).encode()).hexdigest()[:12]}"
        destination = snapshot_root / snapshot_id
        temporary = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}-", dir=snapshot_root))
        try:
            local_manifest(source)
            shutil.copytree(source, temporary / source.name, symlinks=False)
            os.replace(temporary / source.name, destination)
            temporary.rmdir()
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return destination
    except SourceLockError:
        raise
    except OSError as exc:
        raise SourceLockError(f"could not create rollback snapshot: {exc}") from exc


def commit_local_update(current: str | Path, candidate: str | Path, *, target: dict,
                        review: dict, approve: bool = False, snapshot_root: str | Path | None = None,
                        provenance: dict | None = None, name: str | None = None,
                        source: dict | None = None) -> dict:
    """Apply one previously reviewed candidate with a recoverable snapshot.

    The review is re-run while holding the same cross-process mutation lock used
    by the replacement.  A changed target or candidate therefore cannot be
    smuggled in between review and commit.  ``approve=True`` and an explicit
    snapshot root are both mandatory to make the mutation intentional.
    """
    if approve is not True:
        raise SourceLockError("source update requires explicit approve=True")
    if not isinstance(review, dict) or not isinstance(review.get("review_id"), str):
        raise SourceLockError("a review result with review_id is required")
    if snapshot_root is None:
        raise SourceLockError("snapshot_root is required before committing a source update")
    current = Path(current).expanduser()
    candidate = Path(candidate).expanduser()
    if not current.is_dir() or current.is_symlink():
        raise SourceLockError("managed source target is not an accessible directory")
    with mutation_lock(current):
        fresh = review_local_update(
            current, candidate, target=target, provenance=provenance,
            name=name, source=source,
        )
        if fresh.get("review_id") != review["review_id"]:
            raise SourceLockError("source review is stale; inspect the candidate again")
        if fresh.get("review_state") != "review-required":
            raise SourceLockError(f"source review is not committable: {fresh.get('review_state')}")
        snapshot = _snapshot_tree(current, Path(snapshot_root))
        stage = Path(tempfile.mkdtemp(prefix=f".{current.name}-source-", dir=current.parent))
        backup = current.parent / f".{current.name}-rollback-{review['review_id'][:12]}"
        try:
            _copy_tree_without_manager_sidecars(candidate, stage / current.name)
            staged_root = stage / current.name
            lock_source = source or fresh["source"]
            state = "known-verified" if isinstance(lock_source, dict) and lock_source.get("digest") else "known-unverified"
            lock = source_lock_record(
                lock_source, fresh["candidate_hash"],
                fresh["target"], state=state, review_id=review["review_id"],
            )
            write_source_lock(staged_root, lock)
            if backup.exists() or backup.is_symlink():
                raise SourceLockError("rollback staging path already exists")
            os.replace(current, backup)
            try:
                os.replace(staged_root, current)
            except OSError:
                os.replace(backup, current)
                raise
            stage.rmdir()
            shutil.rmtree(backup)
        except SourceLockError:
            shutil.rmtree(stage, ignore_errors=True)
            if backup.exists() and not current.exists():
                os.replace(backup, current)
            raise
        except OSError as exc:
            shutil.rmtree(stage, ignore_errors=True)
            if backup.exists() and not current.exists():
                os.replace(backup, current)
            raise SourceLockError(f"could not commit source update: {exc}") from exc
    return {
        "committed": True,
        "review_id": review["review_id"],
        "path": str(current),
        "content_hash": fresh["candidate_hash"],
        "source_lock": lock,
        "snapshot": str(snapshot),
        "rollback_available": True,
    }


def restore_source_snapshot(current: str | Path, snapshot: str | Path, *, approve: bool = False) -> dict:
    """Restore one source-lock snapshot after explicit approval."""
    if approve is not True:
        raise SourceLockError("snapshot restore requires explicit approve=True")
    current = Path(current).expanduser()
    snapshot = Path(snapshot).expanduser()
    if not snapshot.is_dir() or snapshot.is_symlink():
        raise SourceLockError("rollback snapshot is not an accessible directory")
    with mutation_lock(current):
        local_manifest(snapshot)
        stage = Path(tempfile.mkdtemp(prefix=f".{current.name}-restore-", dir=current.parent))
        try:
            shutil.copytree(snapshot, stage / current.name, symlinks=False)
            if current.exists():
                backup = current.parent / f".{current.name}-restore-backup"
                if backup.exists():
                    shutil.rmtree(backup)
                os.replace(current, backup)
            else:
                backup = None
            try:
                os.replace(stage / current.name, current)
            except OSError:
                if backup is not None:
                    os.replace(backup, current)
                raise
            stage.rmdir()
            if backup is not None:
                shutil.rmtree(backup)
        except OSError as exc:
            shutil.rmtree(stage, ignore_errors=True)
            raise SourceLockError(f"could not restore source snapshot: {exc}") from exc
    return {"restored": True, "path": str(current), "snapshot": str(snapshot)}


__all__ = [
    "MAX_SOURCE_FILES", "MAX_TOTAL_DIFF_LINES", "SOURCE_LOCK_FILENAME", "SourceLockError",
    "commit_local_update",
    "local_manifest", "preview_local_update", "read_source_lock", "restore_source_snapshot",
    "review_local_update", "source_identity", "source_lock_record", "source_lock_status",
    "write_source_lock",
]
