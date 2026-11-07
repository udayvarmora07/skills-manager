"""Shared mechanics for private, expiring, single-use review artifacts.

Three modules keep their own review store and their own domain contract:

* ``skillsmgr.registry``      ``<data>/registry-reviews/<id>.json``
* ``skillsmgr.backup_sync``   ``<data>/sync-reviews/<id>.json``
* ``skillsmgr.source_update`` ``<data>/source-update-reviews/<id>/review.json``

They had drifted into three separate copies of the same *mechanics*.  This
module owns only the mechanics; it deliberately does not unify semantics.

Shared and extracted here
-------------------------
* review-id shape and validation (``^[0-9a-f]{32}$``);
* random review-id generation (``secrets.token_hex(16)``);
* rejecting a symlink in a destination's ancestry before building a path;
* rejecting credential-shaped keys before data reaches disk;
* reading the declared ``expires_epoch`` and deciding expiry;
* bounded JSON encoding with each caller's own size limit;
* the private atomic write: an owner-only directory and a 0600 sibling temp
  file, fsync, and atomic replace;
* review reads with size checks (missing, oversized, unreadable) and caller messages;
* the single-use gate that requires a record still be ``pending``;
* the version-1 review header check.

Deliberately kept per module (do not unify these)
-------------------------------------------------
* **Storage shape.** registry and backup_sync store one flat ``<id>.json``;
  source_update stores ``<id>/review.json`` next to a staged ``candidate/``
  tree. Each caller still constructs its own artifact paths.
* **Id generation.** registry and source_update use ``secrets.token_hex(16)``;
  backup_sync derives its id from the target, candidate hash and remote
  manifest, then truncates a SHA-256 digest to 32 hex characters.
* **Status vocabulary.** registry and backup_sync accept ``pending`` and
  ``committed``; source_update also persists ``cancelled`` and ``expired`` and
  rewrites the record when a review lapses.
* **Expiry semantics.** registry separates an unusable ``expires_epoch``
  ("invalid") from a lapsed one ("expired"); backup_sync reports both as
  expired; source_update additionally accepts a numeric string (it reads the
  value with ``float()``) and marks the record ``expired`` on disk.
* **TTLs and size limits.** 24 h everywhere, but the review payload limits are
  16 MiB (registry), 16 MiB (backup_sync) and 2 MiB (source_update), and
  source_update counts the trailing newline in its limit while the other two
  do not.
* **JSON framing.** registry writes default ``json.dumps`` separators;
  backup_sync and source_update write compact separators.
* **Error classes and messages.** ``RegistryError``, ``BackupSyncError`` and
  ``SourceUpdateError`` (with its stable ``code``) are preserved exactly, as
  are their messages and the REST status mapping callers branch on.
* **Mutation locks.** registry locks ``<id>.json`` from the CLI/commit seam,
  backup_sync locks the review file, and source_update locks
  ``<id>/.review.lock`` while also taking the library index lock at commit.
* **Public projections and extra fields.** Each module keeps its own record
  shape, ``_review_public``/``registry_review_public``/
  ``_copy_public_preview`` projection, and commit/tombstone bookkeeping.
* **Audit artifacts.** source_update prunes the staged candidate on cancel and
  expiry; the other two have no staged tree to prune.

Validation helpers take a ``fail`` callable that builds the caller's own
exception. Each module retains its own error type and message.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import Callable


#: A review id is exactly 32 lowercase hexadecimal characters.  All three
#: stores built paths from this shape before writing anything.
REVIEW_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

#: Keys that look like credentials.  A review must never persist one, because
#: it is written to disk and read back by a separate transaction.
CREDENTIAL_KEYS = frozenset({"authorization", "bearer", "credential", "password", "secret", "token"})

#: Builds a caller-owned exception; ``raise fail(message)``.
Fail = Callable[[str], BaseException]


def new_review_id() -> str:
    """Return a fresh, unguessable 32-character review id."""
    return secrets.token_hex(16)


def is_valid_review_id(review_id: object) -> bool:
    """Return whether *review_id* has the exact review-id shape."""
    return isinstance(review_id, str) and REVIEW_ID_PATTERN.fullmatch(review_id) is not None


def has_review_header(value: object) -> bool:
    """Return whether *value* looks like a version-1 review record."""
    return isinstance(value, dict) and value.get("version") == 1


def ensure_private_directory(directory: str | Path) -> None:
    """Create *directory* (and parents) owner-only, tightening an existing one."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)


def reject_symlink_ancestors(
    path: str | Path,
    fail: Fail,
    *,
    symlink_message: str,
    inspect_message: str | None,
    normalize: bool = True,
) -> None:
    """Reject a symlink anywhere in *path*'s existing ancestry.

    ``inspect_message`` is a ``str.format`` template for an unreadable
    component; pass ``None`` to let the ``OSError`` propagate unchanged.
    """
    current = Path(os.path.abspath(path)) if normalize else Path(path)
    while True:
        try:
            is_link = current.is_symlink()
        except OSError as exc:
            if inspect_message is None:
                raise
            raise fail(inspect_message.format(exc=exc)) from exc
        if is_link:
            raise fail(symlink_message)
        if current.parent == current:
            return
        current = current.parent


def reject_credential_keys(
    value: object,
    fail: Fail,
    *,
    message: str,
    allowed: frozenset[str] = frozenset(),
    keys: frozenset[str] = CREDENTIAL_KEYS,
) -> None:
    """Reject credential-shaped dictionary keys at any depth."""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower().replace("-", "_") if isinstance(key, str) else ""
            if normalized not in allowed and (
                normalized in keys or any(part in keys for part in normalized.split("_"))
            ):
                raise fail(message)
            reject_credential_keys(nested, fail, message=message, allowed=allowed, keys=keys)
    elif isinstance(value, list):
        for nested in value:
            reject_credential_keys(nested, fail, message=message, allowed=allowed, keys=keys)


def review_expiry(record: object, *, numeric_strings: bool = False):
    """Return the declared ``expires_epoch`` number, or ``None`` if unusable.

    ``numeric_strings`` mirrors ``source_update``'s historical ``float()``
    read; the other two stores require a real number.
    """
    if not isinstance(record, dict):
        return None
    value = record.get("expires_epoch")
    if isinstance(value, (int, float)):
        return value
    if numeric_strings:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def encode_review(
    record: object,
    *,
    separators: tuple[str, str] | None = None,
    fail: Fail | None = None,
    json_error: str | None = None,
) -> bytes:
    """Encode *record* as UTF-8 review JSON with the caller's framing.

    With ``fail``/``json_error`` an encoding failure becomes the caller's own
    error; without them the ``TypeError``/``ValueError`` propagates exactly as
    it did before.
    """
    try:
        return json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=separators
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        if fail is None or json_error is None:
            raise
        raise fail(json_error.format(exc=exc)) from exc


def enforce_review_size(encoded: bytes, limit: int, fail: Fail, message: str) -> None:
    """Reject a review payload above the caller's own byte limit."""
    if len(encoded) > limit:
        raise fail(message)


def write_private_bytes(path: str | Path, payload: bytes) -> None:
    """Atomically replace a registry review through a 0600 sibling temp file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".review-tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        try:
            os.fchmod(fd, 0o600)
        except BaseException:
            os.close(fd)
            raise
        try:
            stream = os.fdopen(fd, "wb")
        except BaseException:
            os.close(fd)
            raise
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_bounded_json(
    path: str | Path,
    limit: int,
    fail: Fail,
    *,
    missing_message: str,
    size_message: str,
    unreadable_message: str,
) -> object:
    """Read JSON after checking file size, refusing links and oversized files."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise fail(missing_message)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise fail(unreadable_message.format(exc=exc)) from exc
    if size > limit:
        raise fail(size_message)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise fail(unreadable_message.format(exc=exc)) from exc


def require_status(record: object, expected: str, fail: Fail, message: str) -> None:
    """Enforce the single-use gate: *record* must still hold *expected*."""
    if not isinstance(record, dict) or record.get("status") != expected:
        raise fail(message)


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory fsync so a completed review survives a crash."""
    try:
        directory_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)
