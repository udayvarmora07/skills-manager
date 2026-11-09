"""Bind manager sidecars to the install this tool wrote them for.

``.skillsmgr-provenance.json`` and ``.skillsmgr-source-lock.json`` live inside a
skill directory, which any other installer (or a package dropped into an agent
scope) can write.  A well-formed forgery therefore used to read as trusted
evidence.  A binding record kept in the manager's private data directory -- which
a skill package cannot write -- makes a sidecar trusted only for the exact
install path and exact bytes this tool recorded.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import atomic_io
from .context import active_store
from . import paths
from .path_safety import mkdir_private


PROVENANCE_FILENAME = ".skillsmgr-provenance.json"
SOURCE_LOCK_FILENAME = ".skillsmgr-source-lock.json"
MANAGER_SIDECARS = frozenset({PROVENANCE_FILENAME, SOURCE_LOCK_FILENAME})

BINDING_DIRNAME = "sidecar-bindings"
MAX_BINDING_BYTES = 4096
BINDING_VERSION = 1


def _real_skill_dir(skill_dir: str | Path) -> Path:
    """Return the resolved identity of one skill directory."""
    return Path(os.path.realpath(Path(skill_dir).expanduser()))


def _binding_root(resolved: Path) -> Path:
    """Choose the requesting store, or a stable root for unbound callers."""
    store = active_store()
    if store is not None:
        return Path(os.path.realpath(Path(store.data_dir).expanduser()))
    # Preserve direct operations on a Store's own tree without allowing an
    # unrelated Store registration to redirect external agent-scope records.
    containing = atomic_io.registered_root_containing(resolved)
    return containing if containing is not None else paths.data_dir()


def _binding_dir(skill_dir: str | Path) -> Path:
    """Return the private directory holding this install's binding records."""
    resolved = _real_skill_dir(skill_dir)
    return _binding_root(resolved) / BINDING_DIRNAME


def _record_name(resolved: Path, sidecar_name: str) -> str:
    """Return the record filename for one resolved path and sidecar name."""
    key = str(resolved).encode("utf-8") + b"\x00" + sidecar_name.encode("utf-8")
    return hashlib.sha256(key).hexdigest() + ".json"


def record_path(skill_dir: str | Path, sidecar_name: str) -> Path:
    """Return the full record path for one install and sidecar name."""
    resolved = _real_skill_dir(skill_dir)
    return _binding_root(resolved) / BINDING_DIRNAME / _record_name(
        resolved, sidecar_name
    )


def _ensure_binding_dir(root: Path) -> Path:
    """Create or verify ``<root>/sidecar-bindings`` as owner-only, non-symlink."""

    directory = root / BINDING_DIRNAME
    mkdir_private(directory)
    info = os.lstat(directory)
    if not os.path.isdir(directory) or os.path.islink(directory):
        raise OSError(f"sidecar binding directory is not a plain directory: {directory}")
    getuid = getattr(os, "getuid", None)
    if getuid is not None:
        if info.st_uid != getuid():
            raise OSError(f"sidecar binding directory is owned by another user: {directory}")
        if info.st_mode & 0o077:
            os.chmod(directory, 0o700)
    return directory


def _iso_now() -> str:
    """Return the current UTC time in the manager's timestamp format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_binding(skill_dir: str | Path, sidecar_name: str, sidecar_bytes: bytes) -> Path:
    """Record that this tool wrote *sidecar_bytes* into *skill_dir*.

    The record is kept under the manager's private data root and is written
    atomically with owner-only permissions.  Failure to record raises so the
    caller can remove the unbound sidecar instead of leaving evidence no read
    can trust.
    """
    if not isinstance(sidecar_name, str) or not sidecar_name:
        raise ValueError("sidecar name must be a non-empty string")
    if not isinstance(sidecar_bytes, (bytes, bytearray)):
        raise TypeError("sidecar bytes must be bytes")
    resolved = _real_skill_dir(skill_dir)
    directory = _ensure_binding_dir(_binding_root(resolved))
    destination = directory / _record_name(resolved, sidecar_name)
    value = {
        "version": BINDING_VERSION,
        "path": str(resolved),
        "sidecar": sidecar_name,
        "sha256": hashlib.sha256(bytes(sidecar_bytes)).hexdigest(),
        "recorded_at": _iso_now(),
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
    if os.path.lexists(destination) and os.path.islink(destination):
        raise OSError("sidecar binding record cannot be a symlink")
    atomic_io.atomic_write_text(destination, encoded)
    os.chmod(destination, 0o600)
    return destination


def _read_record(path: Path) -> dict | None:
    """Return a bounded binding record, or ``None`` when none can be used."""
    try:
        if os.path.islink(path) or not path.is_file():
            return None
        if os.stat(path).st_size > MAX_BINDING_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _record_matches(value: object, resolved: Path, sidecar_name: str,
                    expected: str) -> bool:
    """Return whether a stored record describes exactly these install bytes."""
    if not isinstance(value, dict) or value.get("version") != BINDING_VERSION:
        return False
    if value.get("path") != str(resolved) or value.get("sidecar") != sidecar_name:
        return False
    recorded = value.get("sha256")
    return isinstance(recorded, str) and recorded.lower() == expected


def binding_state(skill_dir: str | Path, sidecar_name: str, sidecar_bytes: bytes) -> str:
    """Classify a sidecar against the private binding record for this install.

    Returns ``"recorded"`` when the record exists for the resolved install path
    and the sidecar's exact bytes, ``"mismatch"`` when a record exists but does
    not describe these bytes, and ``"unrecorded"`` otherwise.  Reads create
    nothing and this never raises.
    """
    try:
        resolved = _real_skill_dir(skill_dir)
        directory = _binding_root(resolved) / BINDING_DIRNAME
    except Exception:
        return "unrecorded"
    if not os.path.lexists(directory):
        return "unrecorded"
    if os.path.islink(directory) or not os.path.isdir(directory):
        return "mismatch"
    try:
        path = directory / _record_name(resolved, sidecar_name)
        if not os.path.lexists(path):
            return "unrecorded"
        expected = hashlib.sha256(bytes(sidecar_bytes)).hexdigest()
        record = _read_record(path)
    except Exception:
        return "mismatch"
    if record is None:
        return "mismatch"
    return "recorded" if _record_matches(record, resolved, sidecar_name, expected) else "mismatch"


__all__ = ["BINDING_DIRNAME", "binding_state", "record_binding"]
