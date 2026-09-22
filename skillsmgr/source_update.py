"""Filesystem-owned orchestration for safe local source updates.

The source-lock module owns tree comparison and atomic replacement.  This
module owns only the review and recovery envelope around that operation:
resolving one observed scope instance, staging a private candidate, persisting
an expiring review, and translating low-level failures into stable domain
errors.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import scopes
from .atomic_io import atomic_write_text, mutation_lock
from . import frontmatter
from .path_safety import mkdir_private
from .source_lock import (
    SOURCE_LOCK_FILENAME,
    SourceLockError,
    commit_local_update,
    local_manifest,
    review_local_update,
    source_identity,
)
from .store import Store, StoreError
from .validator import validate_skill_name


_PROVENANCE_FILENAME = ".skillsmgr-provenance.json"
_REVIEW_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SCOPE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_REVIEW_TTL = 24 * 60 * 60
_MAX_REVIEW_BYTES = 2 * 1024 * 1024
_SNAPSHOT_KEEP = 5
_PRIMARY_DOCUMENTS = ("SKILL.md", "SKILL.md.disabled")
_REVIEW_STATUSES = frozenset({"pending", "committed", "cancelled", "expired"})


class SourceUpdateError(StoreError):
    """A clean, stable error from the local source-update service."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        self.status = {
            "review-not-found": 404,
            "snapshot-not-found": 404,
            "snapshot-unavailable": 404,
            "target-not-found": 404,
            "target-changed": 409,
            "review-candidate-changed": 409,
            "candidate-too-large": 413,
        }.get(code, 400)
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict:
        return {"code": self.code, "error": self.message}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _data_path(data_dir: str | Path) -> Path:
    return Path(data_dir).expanduser().resolve()


def _root(data_dir: Path, name: str) -> Path:
    path = data_dir / name
    if path.exists() and path.is_symlink():
        raise SourceUpdateError("commit-failed", "manager-owned update storage is not safe")
    try:
        mkdir_private(path)
        os.chmod(path, 0o700)
    except (OSError, ValueError) as exc:
        raise SourceUpdateError("commit-failed", "manager-owned update storage is unavailable") from exc
    return path


def _valid_review_id(review_id: str) -> str:
    if not isinstance(review_id, str) or not _REVIEW_ID_RE.fullmatch(review_id):
        raise SourceUpdateError("invalid-review-id", "review id must be 32 lowercase hexadecimal characters")
    return review_id


def _valid_scope(scope: str) -> str:
    if not isinstance(scope, str) or scope == "all" or not _SCOPE_ID_RE.fullmatch(scope):
        raise SourceUpdateError("target-not-found", "a concrete writable scope is required")
    return scope


def _review_dir(data_dir: Path, review_id: str) -> Path:
    root = _root(data_dir, "source-update-reviews")
    directory = root / _valid_review_id(review_id)
    if directory.exists() and directory.is_symlink():
        raise SourceUpdateError("review-not-found", "update review is unavailable")
    try:
        if not directory.resolve().is_relative_to(root.resolve()):
            raise SourceUpdateError("review-not-found", "update review is unavailable")
    except AttributeError:  # pragma: no cover - Python 3.10 fallback
        if not str(directory.resolve()).startswith(str(root.resolve()) + os.sep):
            raise SourceUpdateError("review-not-found", "update review is unavailable")
    return directory


def _write_record(directory: Path, record: dict) -> None:
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if len(encoded.encode("utf-8")) > _MAX_REVIEW_BYTES:
        raise SourceUpdateError("candidate-unsafe", "review evidence exceeds the persistent size limit")
    path = directory / "review.json"
    atomic_write_text(path, encoded)
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        raise SourceUpdateError("commit-failed", "could not protect update review evidence") from exc


def _load_record(data_dir: Path, review_id: str) -> tuple[Path, dict]:
    directory = _review_dir(data_dir, review_id)
    path = directory / "review.json"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_REVIEW_BYTES:
            raise ValueError
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        raise SourceUpdateError("review-not-found", "update review is unavailable")
    if (
        not isinstance(record, dict)
        or record.get("version") != 1
        or record.get("review_id") != review_id
        or record.get("status") not in _REVIEW_STATUSES
    ):
        raise SourceUpdateError("review-not-found", "update review is unavailable")
    return directory, record


def _expired(record: dict) -> bool:
    try:
        return float(record["expires_epoch"]) <= _now().timestamp()
    except (KeyError, TypeError, ValueError):
        return True


def _mark_expired(directory: Path, record: dict) -> None:
    record["status"] = "expired"
    record["expired_at"] = _iso(_now())
    try:
        _write_record(directory, record)
        candidate = directory / "candidate"
        if candidate.exists() and not candidate.is_symlink():
            shutil.rmtree(candidate)
    except (OSError, SourceUpdateError):
        pass


def _copy_public_preview(record: dict, *, status: str | None = None) -> dict:
    preview = copy.deepcopy(record.get("preview", {}))
    state = status or record.get("status", "pending")
    result = {
        "review_id": record.get("review_id"),
        "review_expires_at": record.get("review_expires_at"),
        "review_state": state,
        "target": copy.deepcopy(record.get("target", preview.get("target", {}))),
        "source": copy.deepcopy(record.get("source", preview.get("source", {}))),
        "current_hash": preview.get("current_hash"),
        "candidate_hash": preview.get("candidate_hash"),
        "comparison": copy.deepcopy(preview.get("comparison", {})),
        "validation": copy.deepcopy(preview.get("validation", {})),
        "risk": copy.deepcopy(preview.get("risk", {})),
        "activation_preserved": bool(record.get("activation_preserved")),
        "resulting_disabled": bool(record.get("resulting_disabled")),
        "snapshot_required_before_commit": bool(preview.get("snapshot_required_before_commit")),
        "commit_allowed": False,
        "staged": state == "pending",
        "rollback_from_snapshot": record.get("rollback_from_snapshot"),
        "source_review": copy.deepcopy(record.get("source_review", {})),
        "source_lock_preview": preview,
    }
    if record.get("committed_at"):
        result["committed_at"] = record["committed_at"]
    if record.get("snapshot_id"):
        result["snapshot_id"] = record["snapshot_id"]
    return result


@contextmanager
def _scope_store(data_dir: Path, scope: str):
    previous = scopes._GLOBAL_STORE.get()
    if scope == "global":
        scopes.set_global_store(Store(data_dir=data_dir))
    try:
        yield
    finally:
        scopes.set_global_store(previous)


def _resolved(path: str | Path) -> Path:
    try:
        return Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SourceUpdateError("target-mismatch", "target path is not an observed directory") from exc


def _has_write_access(path: Path) -> bool:
    try:
        mode = path.stat().st_mode
        if not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            return False
        return os.access(path, os.W_OK | os.X_OK)
    except OSError:
        return False


def _target_writable(path: Path, root: Path, record: dict) -> bool:
    return (
        record.get("root_availability", "writable") == "writable"
        and path.is_dir()
        and not path.is_symlink()
        and _has_write_access(path)
        and _has_write_access(path.parent)
        and _has_write_access(root)
    )


def _target_record(record: dict, scope: str, name: str, ambiguous: bool) -> dict:
    try:
        physical_root = _resolved(record["physical_root"])
        physical_path = _resolved(record.get("physical_path") or record["path"])
    except (KeyError, SourceUpdateError):
        raise SourceUpdateError("target-not-found", "the observed target is unavailable")
    try:
        contained = physical_path != physical_root and physical_path.is_relative_to(physical_root)
    except AttributeError:  # pragma: no cover - Python 3.10 fallback
        contained = physical_path != physical_root and str(physical_path).startswith(str(physical_root) + os.sep)
    if not contained:
        raise SourceUpdateError("target-mismatch", "the observed target is outside its scope root")
    if not _target_writable(physical_path, physical_root, record):
        raise SourceUpdateError("target-not-writable", "the observed target is not writable")
    return {
        "name": name,
        "scope": scope,
        "consumer": record.get("consumer"),
        "physical_root": str(physical_root),
        "physical_path": str(physical_path),
        "contained": True,
        "exists": True,
        "writable": True,
        "disabled": bool(record.get("disabled")),
        "ambiguous": ambiguous,
    }


def _resolve_target(data_dir: Path, name: str, scope: str, target_path: str | Path | None) -> dict:
    try:
        validate_skill_name(name)
    except ValueError as exc:
        raise SourceUpdateError("target-not-found", "the requested skill name is not addressable") from exc
    scope = _valid_scope(scope)
    try:
        with _scope_store(data_dir, scope):
            records = [row for row in scopes.scan_scope(scope) if row.get("name") == name]
    except (StoreError, OSError, ValueError) as exc:
        raise SourceUpdateError("target-not-found", "the requested scope or skill is unavailable") from exc
    if not records:
        raise SourceUpdateError("target-not-found", "the requested skill instance was not observed")
    ambiguous = len(records) > 1
    if ambiguous and target_path is None:
        raise SourceUpdateError("target-ambiguous", "target_path is required for multiple observed instances")
    chosen = records[0]
    if target_path is not None:
        requested = _resolved(target_path)
        matches = [row for row in records if _record_path(row) == requested]
        if not matches:
            raise SourceUpdateError("target-mismatch", "target_path is not an observed skill instance")
        chosen = matches[0]
    return _target_record(chosen, scope, name, ambiguous)


def _record_path(record: dict) -> Path:
    try:
        return Path(record.get("physical_path") or record["path"]).expanduser().resolve(strict=True)
    except (KeyError, OSError, RuntimeError):
        return Path("/").joinpath("__unavailable-target__")


def _reject_unsafe_tree(source: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise SourceUpdateError("candidate-unsafe", "candidate source must be a real directory")
    pending = [source]
    try:
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        raise SourceUpdateError("candidate-unsafe", "candidate contains a symlink")
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif not entry.is_file(follow_symlinks=False):
                        raise SourceUpdateError("candidate-unsafe", "candidate contains a non-regular file")
    except OSError as exc:
        raise SourceUpdateError("candidate-invalid", "candidate source is inaccessible") from exc


def _primary_document(source: Path) -> str:
    present = [name for name in _PRIMARY_DOCUMENTS if (source / name).is_file()]
    if len(present) != 1:
        code = "candidate-invalid" if not present else "candidate-unsafe"
        raise SourceUpdateError(code, "candidate must contain exactly one skill document")
    return present[0]


def _manifest(source: Path) -> dict:
    _reject_unsafe_tree(source)
    try:
        return local_manifest(source)
    except SourceLockError as exc:
        raise SourceUpdateError("candidate-unsafe", "candidate source failed safety checks") from exc


def _strip_sidecars(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.name not in {_PROVENANCE_FILENAME, SOURCE_LOCK_FILENAME}:
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            raise SourceUpdateError("candidate-unsafe", "candidate manager sidecar could not be removed") from exc


def _stage_candidate(source: Path, review_dir: Path, disabled: bool) -> dict:
    before = _manifest(source)
    primary = _primary_document(source)
    candidate = review_dir / "candidate"
    try:
        # Preserve links during the defensive copy so a link introduced after
        # the pre-scan is rejected by the candidate manifest rather than
        # followed into an arbitrary filesystem tree.
        shutil.copytree(source, candidate, symlinks=True)
    except (OSError, shutil.Error) as exc:
        raise SourceUpdateError("candidate-invalid", "candidate source could not be staged") from exc
    _strip_sidecars(candidate)
    desired = "SKILL.md.disabled" if disabled else "SKILL.md"
    if primary != desired:
        try:
            os.replace(candidate / primary, candidate / desired)
        except OSError as exc:
            raise SourceUpdateError("candidate-invalid", "candidate activation could not be normalized") from exc
    after = _manifest(source)
    if before["sha256"] != after["sha256"]:
        raise SourceUpdateError("candidate-invalid", "candidate source changed while it was being staged")
    staged = _manifest(candidate)
    if _primary_document(candidate) != desired:
        raise SourceUpdateError("candidate-invalid", "candidate activation could not be preserved")
    return staged


def _new_review_id() -> str:
    return secrets.token_hex(16)


def _candidate_summary(manifest: dict) -> dict:
    return {
        "content_hash": manifest["sha256"],
        "file_count": len(manifest["files"]),
        "total_bytes": sum(item["bytes"] for item in manifest["files"]),
    }


def _frontmatter_matches(candidate: Path, name: str) -> bool:
    document = candidate / ("SKILL.md.disabled" if (candidate / "SKILL.md.disabled").is_file() else "SKILL.md")
    try:
        data, _ = frontmatter.parse_frontmatter(document.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, frontmatter.FrontmatterError):
        return False
    return data.get("name") == name


def _unpersisted_preview(preview: dict, target: dict, source: dict, disabled: bool) -> dict:
    record = {
        "review_id": None,
        "review_expires_at": None,
        "status": preview.get("review_state", "blocked"),
        "target": target,
        "source": source,
        "preview": preview,
        "activation_preserved": True,
        "resulting_disabled": disabled,
        "source_review": {},
        "rollback_from_snapshot": None,
    }
    result = _copy_public_preview(record, status=preview.get("review_state", "blocked"))
    result["staged"] = False
    return result


def _prepare_from_source(
    data_dir: Path,
    name: str,
    scope: str,
    source: Path,
    target_path: str | Path | None,
    *,
    source_record: dict,
    rollback_from_snapshot: str | None = None,
) -> dict:
    target = _resolve_target(data_dir, name, scope, target_path)
    try:
        source_identity("local", source_record["value"])
    except (KeyError, SourceLockError) as exc:
        raise SourceUpdateError("candidate-unsafe", "source identity is not safe to retain") from exc
    review_id = _new_review_id()
    reviews_root = _root(data_dir, "source-update-reviews")
    directory = reviews_root / review_id
    try:
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)
        staged_manifest = _stage_candidate(source, directory, target["disabled"])
        staged = directory / "candidate"
        source_review = review_local_update(
            target["physical_path"],
            staged,
            target=target,
            name=name,
            source=source_record,
        )
        if not _frontmatter_matches(staged, name):
            source_review = copy.deepcopy(source_review)
            source_review["review_state"] = "blocked"
            source_review["review_id"] = None
            source_review["validation"] = {
                "valid": False,
                "errors": [{
                    "level": "error",
                    "key": "name",
                    "message": "frontmatter name does not match the target skill name",
                }],
                "warnings": source_review.get("validation", {}).get("warnings", []),
            }
        review_state = source_review.get("review_state")
        if review_state != "review-required" or not source_review.get("review_id"):
            result = _unpersisted_preview(source_review, target, source_record, target["disabled"])
            shutil.rmtree(directory, ignore_errors=True)
            return result
        created = _now()
        candidate_summary = _candidate_summary(staged_manifest)
        candidate_summary["current_hash"] = source_review.get("current_hash")
        record = {
            "version": 1,
            "review_id": review_id,
            "status": "pending",
            "created_at": _iso(created),
            "expires_epoch": created.timestamp() + _REVIEW_TTL,
            "review_expires_at": _iso(datetime.fromtimestamp(created.timestamp() + _REVIEW_TTL, timezone.utc)),
            "target": target,
            "source": source_record,
            "candidate": candidate_summary,
            "source_review": {
                "review_id": source_review["review_id"],
                "current_hash": source_review.get("current_hash"),
                "candidate_hash": source_review.get("candidate_hash"),
            },
            "preview": source_review,
            "activation_preserved": True,
            "resulting_disabled": target["disabled"],
            "rollback_from_snapshot": rollback_from_snapshot,
        }
        _write_record(directory, record)
        return _copy_public_preview(record)
    except SourceUpdateError:
        if directory.exists() and directory.is_dir() and not directory.is_symlink():
            shutil.rmtree(directory, ignore_errors=True)
        raise
    except (OSError, ValueError, SourceLockError) as exc:
        if directory.exists() and directory.is_dir() and not directory.is_symlink():
            shutil.rmtree(directory, ignore_errors=True)
        raise SourceUpdateError("candidate-invalid", "candidate review could not be prepared") from exc


def prepare_local_update(
    data_dir: str | Path,
    name: str,
    scope: str,
    source_dir: str | Path,
    *,
    target_path: str | Path | None = None,
    source_value: str | None = None,
) -> dict:
    """Stage and preview one local candidate without changing the target."""
    data = _data_path(data_dir)
    source = Path(source_dir).expanduser()
    try:
        value = source_value if source_value is not None else str(source)
        source_record = source_identity("local", value)
    except (SourceLockError, OSError) as exc:
        raise SourceUpdateError("candidate-unsafe", "source identity is not safe to retain") from exc
    return _prepare_from_source(data, name, scope, source, target_path, source_record=source_record)


def _path_digest(target: dict) -> str:
    return hashlib.sha256(target["physical_path"].encode("utf-8")).hexdigest()[:32]


def _snapshot_base(data_dir: Path, target: dict) -> Path:
    try:
        validate_skill_name(target["name"])
        if not _SCOPE_ID_RE.fullmatch(target["scope"]):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceUpdateError("snapshot-unavailable", "snapshot target identity is invalid") from exc
    base = _root(data_dir, "source-update-snapshots") / target["scope"] / target["name"] / _path_digest(target)
    try:
        mkdir_private(base)
        os.chmod(base, 0o700)
    except (OSError, ValueError) as exc:
        raise SourceUpdateError("snapshot-unavailable", "snapshot storage is unavailable") from exc
    return base


def _snapshot_folder(data_dir: Path, target: dict, snapshot_id: str) -> Path:
    base = _snapshot_base(data_dir, target)
    folder = base / _valid_review_id(snapshot_id)
    if folder.is_symlink() or not folder.is_dir():
        raise SourceUpdateError("snapshot-not-found", "recovery snapshot was not found")
    try:
        if not folder.resolve().is_relative_to(base.resolve()):
            raise SourceUpdateError("snapshot-unavailable", "recovery snapshot is outside managed storage")
    except AttributeError:  # pragma: no cover - Python 3.10 fallback
        pass
    children = [item for item in folder.iterdir() if item.is_dir() and not item.is_symlink()]
    for child in sorted(children, reverse=True):
        if (child / "SKILL.md").is_file() or (child / "SKILL.md.disabled").is_file():
            return child
    raise SourceUpdateError("snapshot-unavailable", "recovery snapshot is malformed or unreadable")


def _snapshot_entries(data_dir: Path, target: dict) -> list[dict]:
    base = _snapshot_base(data_dir, target)
    if not base.exists():
        return []
    entries = []
    for folder in sorted(base.iterdir(), key=lambda item: item.name, reverse=True):
        if folder.is_symlink() or not folder.is_dir() or not _REVIEW_ID_RE.fullmatch(folder.name):
            continue
        try:
            created_at = _iso(datetime.fromtimestamp(folder.stat().st_mtime, timezone.utc))
        except OSError:
            entries.append({
                "snapshot_id": folder.name,
                "source_review_id": folder.name,
                "created_at": None,
                "tree_hash": None,
                "activation_state": "unknown",
                "readable": False,
                "available": False,
                "error": "snapshot is unreadable or malformed",
            })
            continue
        item = {
            "snapshot_id": folder.name,
            "source_review_id": folder.name,
            "created_at": created_at,
            "tree_hash": None,
            "activation_state": "unknown",
            "readable": False,
            "available": False,
        }
        try:
            snapshot = _snapshot_folder(data_dir, target, folder.name)
            manifest = local_manifest(snapshot)
            item["tree_hash"] = manifest["sha256"]
            item["activation_state"] = "disabled" if (snapshot / "SKILL.md.disabled").is_file() else "active"
            item["readable"] = True
            item["available"] = True
        except (OSError, SourceLockError, SourceUpdateError, ValueError):
            item["error"] = "snapshot is unreadable or malformed"
        entries.append(item)
    return sorted(entries, key=lambda item: (item["created_at"] or "", item["snapshot_id"]), reverse=True)


def _active_rollback_ids(data_dir: Path, target: dict) -> set[str]:
    root = _root(data_dir, "source-update-reviews")
    protected = set()
    if not root.exists():
        return protected
    for directory in root.iterdir():
        if directory.is_symlink() or not directory.is_dir() or not _REVIEW_ID_RE.fullmatch(directory.name):
            continue
        try:
            _, record = _load_record(data_dir, directory.name)
        except SourceUpdateError:
            continue
        if record.get("status") != "pending" or _expired(record):
            continue
        if record.get("rollback_from_snapshot") and _same_target(record.get("target", {}), target):
            protected.add(record["rollback_from_snapshot"])
    return protected


def _same_target(left: dict, right: dict) -> bool:
    return (
        left.get("scope") == right.get("scope")
        and left.get("name") == right.get("name")
        and left.get("physical_path") == right.get("physical_path")
    )


def _prune_snapshots(data_dir: Path, target: dict) -> None:
    entries = _snapshot_entries(data_dir, target)
    protected = _active_rollback_ids(data_dir, target)
    removable = [item for item in entries[_SNAPSHOT_KEEP:] if item["snapshot_id"] not in protected]
    for item in removable:
        folder = _snapshot_base(data_dir, target) / item["snapshot_id"]
        if folder.is_symlink() or not folder.is_dir():
            continue
        shutil.rmtree(folder)


def prepare_snapshot_update(
    data_dir: str | Path,
    name: str,
    scope: str,
    snapshot_id: str,
    *,
    target_path: str | Path | None = None,
) -> dict:
    """Prepare a normal update review whose source is a retained snapshot."""
    data = _data_path(data_dir)
    target = _resolve_target(data, name, scope, target_path)
    snapshot = _snapshot_folder(data, target, _valid_review_id(snapshot_id))
    source_record = source_identity("local", f"snapshot:{snapshot_id}")
    return _prepare_from_source(
        data,
        name,
        scope,
        snapshot,
        target_path,
        source_record=source_record,
        rollback_from_snapshot=snapshot_id,
    )


def read_update_review(data_dir: str | Path, review_id: str) -> dict:
    """Read public evidence for one durable update review."""
    data = _data_path(data_dir)
    directory, record = _load_record(data, _valid_review_id(review_id))
    if record["status"] == "pending" and _expired(record):
        with mutation_lock(directory / ".review.lock"):
            _mark_expired(directory, record)
        raise SourceUpdateError("review-expired", "update review has expired")
    return _copy_public_preview(record)


def cancel_update_review(data_dir: str | Path, review_id: str) -> dict:
    """Cancel a pending review while retaining its audit record."""
    data = _data_path(data_dir)
    directory, _ = _load_record(data, _valid_review_id(review_id))
    with mutation_lock(directory / ".review.lock"):
        _, record = _load_record(data, review_id)
        if record["status"] == "pending" and _expired(record):
            _mark_expired(directory, record)
            raise SourceUpdateError("review-expired", "update review has expired")
        if record["status"] != "pending":
            raise SourceUpdateError("review-not-pending", "update review is no longer pending")
        record["status"] = "cancelled"
        record["cancelled_at"] = _iso(_now())
        _write_record(directory, record)
        candidate = directory / "candidate"
        if candidate.exists() and not candidate.is_symlink():
            shutil.rmtree(candidate)
        return _copy_public_preview(record)


def _review_candidate(data_dir: Path, review_id: str) -> Path:
    directory = _review_dir(data_dir, review_id)
    candidate = directory / "candidate"
    if candidate.is_symlink() or not candidate.is_dir():
        raise SourceUpdateError("review-candidate-changed", "staged review candidate is unavailable")
    return candidate


def _commit_error(exc: SourceLockError, current: Path, candidate: Path, record: dict) -> SourceUpdateError:
    try:
        if local_manifest(candidate)["sha256"] != record["candidate"]["content_hash"]:
            return SourceUpdateError("review-candidate-changed", "staged review candidate changed")
    except SourceLockError:
        return SourceUpdateError("review-candidate-changed", "staged review candidate is unavailable")
    try:
        if local_manifest(current)["sha256"] != record["candidate"]["current_hash"]:
            return SourceUpdateError("target-changed", "installed target changed after review")
    except SourceLockError:
        return SourceUpdateError("target-changed", "installed target changed after review")
    if "stale" in str(exc).lower():
        return SourceUpdateError("target-changed", "installed target or review candidate changed")
    return SourceUpdateError("commit-failed", "reviewed update could not be applied")


def _commit_response(record: dict, target: dict, result: dict, warning: str | None = None) -> dict:
    response = {
        "committed": True,
        "review_id": record["review_id"],
        "snapshot_id": record["review_id"],
        "target": target,
        "content_hash": result.get("content_hash"),
        "source_lock": result.get("source_lock"),
        "rollback_available": True,
    }
    if warning:
        response.update({"result": "committed_with_warning", "code": "committed-with-warning", "warning": warning})
    return response


def commit_update_review(
    data_dir: str | Path,
    review_id: str,
    *,
    name: str,
    scope: str,
    target_path: str | Path | None = None,
    approve: bool = False,
) -> dict:
    """Apply one pending review through the source-lock mutation seam."""
    if approve is not True:
        raise SourceUpdateError("approval-required", "explicit approval is required to apply an update")
    data = _data_path(data_dir)
    review_id = _valid_review_id(review_id)
    directory, _ = _load_record(data, review_id)
    with mutation_lock(directory / ".review.lock"):
        _, record = _load_record(data, review_id)
        if record["status"] == "pending" and _expired(record):
            _mark_expired(directory, record)
            raise SourceUpdateError("review-expired", "update review has expired")
        if record["status"] != "pending":
            raise SourceUpdateError("review-not-pending", "update review is no longer pending")
        if record.get("target", {}).get("name") != name or record.get("target", {}).get("scope") != scope:
            raise SourceUpdateError("target-mismatch", "apply arguments do not match the reviewed target")
        target = _resolve_target(data, name, scope, target_path)
        if not _same_target(record["target"], target) or record["target"].get("disabled") != target.get("disabled"):
            raise SourceUpdateError("target-changed", "installed target identity changed after review")
        candidate = _review_candidate(data, review_id)
        try:
            if local_manifest(candidate)["sha256"] != record["candidate"]["content_hash"]:
                raise SourceUpdateError("review-candidate-changed", "staged review candidate changed")
            if local_manifest(Path(target["physical_path"]))["sha256"] != record["candidate"]["current_hash"]:
                raise SourceUpdateError("target-changed", "installed target changed after review")
        except SourceLockError as exc:
            raise _commit_error(exc, Path(target["physical_path"]), candidate, record) from exc
        snapshot_root = _snapshot_base(data, target) / review_id
        try:
            result = commit_local_update(
                target["physical_path"],
                candidate,
                target=target,
                review=record["source_review"],
                approve=True,
                snapshot_root=snapshot_root,
                name=name,
                source=record["source"],
            )
        except SourceLockError as exc:
            raise _commit_error(exc, Path(target["physical_path"]), candidate, record) from exc
        warning = None
        record["status"] = "committed"
        record["committed_at"] = _iso(_now())
        record["snapshot_id"] = review_id
        try:
            _write_record(directory, record)
        except (OSError, SourceUpdateError):
            warning = "filesystem update committed; review status could not be persisted"
        if scope == "global":
            try:
                with _scope_store(data, scope):
                    Store(data_dir=data).resync()
            except (OSError, StoreError, ValueError):
                warning = "filesystem update committed; global index reconciliation is pending"
        try:
            _prune_snapshots(data, target)
        except (OSError, SourceUpdateError, ValueError):
            warning = "filesystem update committed; snapshot retention could not be completed"
        return _commit_response(record, target, result, warning)


def list_update_snapshots(
    data_dir: str | Path,
    name: str,
    scope: str,
    *,
    target_path: str | Path | None = None,
) -> list[dict]:
    """List retained recovery snapshots for one exact observed target."""
    data = _data_path(data_dir)
    target = _resolve_target(data, name, scope, target_path)
    return _snapshot_entries(data, target)


__all__ = [
    "SourceUpdateError",
    "cancel_update_review",
    "commit_update_review",
    "list_update_snapshots",
    "prepare_local_update",
    "prepare_snapshot_update",
    "read_update_review",
]
