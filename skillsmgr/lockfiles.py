"""Read-only evidence for lockfiles written by the ``skills`` CLI.

The filesystem remains the source of truth.  This module never writes, caches,
or contacts the network: it only parses ``skills-lock.json`` (project lock,
version 1) and ``.skill-lock.json`` (global lock, version 3), compares each
declared skill with its installed copy, and reports what the recorded hashes
say.  A hash mismatch is evidence that bytes or ordering differ -- never proof
of tampering or of an available update.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlparse, urlunparse


MAX_LOCK_BYTES = 4 * 1024 * 1024
MAX_LOCK_ENTRIES = 500
MAX_UNDECLARED = 500
MAX_HASH_FILES = 2_000
MAX_HASH_BYTES = 64 * 1024 * 1024
MAX_STRING = 512

PROJECT_LOCK_VERSION = 1
GLOBAL_LOCK_VERSION = 3
PROJECT_LOCK_FILENAME = "skills-lock.json"
GLOBAL_LOCK_FILENAME = ".skill-lock.json"
APM_LOCK_FILENAME = "apm.lock.yaml"

_SKIP_DIRS = frozenset({".git", "node_modules"})
_SANITIZE_RE = re.compile(r"[^a-z0-9._]+")
_LOCK_VERSIONS = {"project": PROJECT_LOCK_VERSION, "global": GLOBAL_LOCK_VERSION}
_VERSION_KINDS = {value: key for key, value in _LOCK_VERSIONS.items()}
_ENTRY_FIELDS = (
    "source",
    "sourceType",
    "sourceUrl",
    "ref",
    "skillPath",
    "version",
    "via",
    "subagents",
    "wellKnownDigest",
    "installMode",
    "installedAt",
    "updatedAt",
    "pluginName",
    "sourceBaseUrl",
)


class LockfileError(ValueError):
    """Raised when a bounded lockfile operation cannot be completed."""


class LockfileTooLarge(LockfileError):
    """Raised when a skill folder exceeds the local hashing budget."""


# One report request hashes at most this much in total, across every entry of
# every lock. Without it the per-skill budget alone allowed ~500 x 64 MiB per
# unauthenticated /api/doctor?hygiene=1 request (independent review, 2026-11-07).
MAX_REQUEST_HASH_FILES = 20_000
MAX_REQUEST_HASH_BYTES = 256 * 1024 * 1024


class _RequestBudget:
    __slots__ = ("files", "bytes")

    def __init__(self) -> None:
        self.files = 0
        self.bytes = 0

    def add(self, size: int) -> None:
        self.files += 1
        self.bytes += max(0, size)
        if self.files > MAX_REQUEST_HASH_FILES or self.bytes > MAX_REQUEST_HASH_BYTES:
            raise LockfileTooLarge("the report's total hashing budget is spent; "
                                   "remaining entries were not hashed")


_REQUEST_BUDGET: contextvars.ContextVar[_RequestBudget | None] = contextvars.ContextVar(
    "skillsmgr_lockfile_request_budget", default=None)


class _HashBudget:
    """Shared per-skill file/byte budget for both hash algorithms.

    It also charges the request-wide budget when one is active.
    """

    __slots__ = ("files", "bytes", "request")

    def __init__(self) -> None:
        self.files = 0
        self.bytes = 0
        self.request = _REQUEST_BUDGET.get()

    def add(self, size: int) -> None:
        self.files += 1
        self.bytes += max(0, size)
        _enforce_skill_budget(self.files, self.bytes)
        if self.request is not None:
            self.request.add(size)


def _enforce_skill_budget(files: int, size: int) -> None:
    if files > MAX_HASH_FILES:
        raise LockfileTooLarge(f"skill folder exceeds {MAX_HASH_FILES} files")
    if size > MAX_HASH_BYTES:
        raise LockfileTooLarge(f"skill folder exceeds {MAX_HASH_BYTES} bytes")


def _bounded(value: object, limit: int = MAX_STRING) -> str:
    text = value if isinstance(value, str) else str(value)
    text = text.replace("\x00", "\ufffd")
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "\u2026"


def sanitize_name(name: object) -> str:
    """Reproduce the ``skills`` CLI directory-name sanitisation."""
    text = (name if isinstance(name, str) else str(name)).lower()
    text = _SANITIZE_RE.sub("-", text)
    text = text.strip(".-")
    text = text[:255]
    return text or "unnamed-skill"


_WITHHELD_SOURCE = "source withheld (unparseable)"


def _parse_source(text: str):
    """Return ``(parsed_url, None)`` or ``(None, safe_label)``.

    Anything that cannot be parsed and rebuilt is withheld rather than echoed,
    because an unparsed string may still carry userinfo or a token.
    """
    if len(text) > 2048 or "\x00" in text:
        return None, _WITHHELD_SOURCE
    try:
        parsed = urlparse(text)
    except ValueError:
        return None, _WITHHELD_SOURCE
    if not parsed.scheme or not parsed.netloc:
        return None, (_WITHHELD_SOURCE if "@" in text else _bounded(text))
    return parsed, None


def safe_source_url(value: object) -> str:
    """Return a credential-free source label with userinfo/query removed."""
    if not isinstance(value, str) or not value.strip():
        return ""
    text = value.strip()
    parsed, fallback = _parse_source(text)
    if parsed is None:
        return fallback
    host = parsed.hostname or ""
    netloc = f"[{host}]" if ":" in host else host
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return _bounded(urlunparse((parsed.scheme, netloc, parsed.path, "", "", "")))


def _directory_files(root: Path):
    """Yield regular-file entries without following symlinks or skipped dirs."""
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        is_symlink = entry.is_symlink()
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError:
                        continue
                    if is_symlink:
                        continue
                    if is_dir:
                        if entry.name not in _SKIP_DIRS:
                            stack.append(Path(entry.path))
                        continue
                    if is_file:
                        yield Path(entry.path)
        except OSError:
            continue


def computed_folder_hash(directory: str | Path, order: str = "codepoint") -> str:
    """Return the upstream ``computedHash`` for *directory* under *order*.

    ``order`` is ``"codepoint"`` (plain Python string order) or ``"casefold"``
    (a case-insensitive approximation of JavaScript's ICU ``localeCompare``).
    Neither is guaranteed to reproduce ICU ordering for arbitrary text; callers
    must treat a mismatch as one of the two possible explanations.
    """
    if order not in {"codepoint", "casefold"}:
        raise LockfileError(f"unsupported ordering {order!r}")
    root = Path(directory).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise LockfileError("skill folder is not a readable directory")
    budget = _HashBudget()
    collected = []
    for path in _directory_files(root):
        try:
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
        except OSError as exc:
            raise LockfileError(str(exc)) from exc
        budget.add(size)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise LockfileError(str(exc)) from exc
        key = (relative.casefold(), relative) if order == "casefold" else relative
        collected.append((key, relative, data))
    collected.sort(key=lambda item: item[0])
    digest = hashlib.sha256()
    for _key, relative, data in collected:
        digest.update(relative.encode("utf-8"))
        digest.update(data)
    return digest.hexdigest()


def _git_blob_digest(data: bytes) -> bytes:
    # SHA-1 is the Git object identifier format, not a security/trust digest.
    return hashlib.sha1(b"blob %d\x00" % len(data) + data, usedforsecurity=False).digest()


def _tree_entry_name(entry, as_enabled: bool) -> bytes:
    # This tool disables a skill by renaming SKILL.md to SKILL.md.disabled.
    # Compared under its enabled name, a disabled-but-unchanged skill matches
    # the upstream tree instead of reading as drift.
    name = "SKILL.md" if as_enabled and entry.name == "SKILL.md.disabled" else entry.name
    return name.encode("utf-8", "surrogateescape")


def _git_tree_digest(directory: Path, budget: _HashBudget, as_enabled: bool = False) -> bytes:
    rows = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        target = os.fsencode(os.readlink(entry.path))
                        budget.add(len(target))
                        rows.append((entry.name.encode("utf-8", "surrogateescape"),
                                     b"120000", _git_blob_digest(target)))
                    elif entry.is_dir(follow_symlinks=False):
                        if entry.name == ".git":
                            continue
                        child = _git_tree_digest(Path(entry.path), budget)
                        rows.append((entry.name.encode("utf-8", "surrogateescape"),
                                     b"40000", child))
                    elif entry.is_file(follow_symlinks=False):
                        path = Path(entry.path)
                        size = path.stat().st_size
                        budget.add(size)
                        data = path.read_bytes()
                        mode = b"100755" if path.stat().st_mode & stat.S_IXUSR else b"100644"
                        rows.append((_tree_entry_name(entry, as_enabled),
                                     mode, _git_blob_digest(data)))
                except OSError as exc:
                    # An unreadable entry makes the tree unknowable; skipping
                    # it would report a false "differs".
                    raise LockfileError(f"cannot read {entry.name!r}") from exc
    except OSError as exc:
        raise LockfileError(str(exc)) from exc
    rows.sort(key=lambda row: row[0] + (b"/" if row[1] == b"40000" else b""))
    body = b"".join(
        mode + b" " + name + b"\x00" + digest for name, mode, digest in rows
    )
    return hashlib.sha1(b"tree %d\x00" % len(body) + body, usedforsecurity=False).digest()


def skill_folder_tree_sha(directory: str | Path, *, as_enabled: bool = False) -> str:
    """Return the local git tree object SHA-1 for *directory*.

    This is the same object hash GitHub reports as ``skillFolderHash`` for a
    skill folder, computed with the standard library only.
    """
    root = Path(directory).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise LockfileError("skill folder is not a readable directory")
    return _git_tree_digest(root, _HashBudget(), as_enabled).hex()


def _invalid(path: Path, kind: str, reason: str) -> dict:
    return {
        "path": _bounded(str(path)),
        "kind": kind,
        "state": "invalid",
        "reason": _bounded(reason),
        "version": None,
        "entries": [],
        "omitted": 0,
        "total_entries": 0,
    }


def _lock_kind(version: object, kind: str | None) -> str | None:
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    if kind is not None:
        return kind if _LOCK_VERSIONS.get(kind) == version else None
    return _VERSION_KINDS.get(version)


def _normalized_entry(name: str, value: dict) -> dict:
    entry = {"name": _bounded(name, 128)}
    for key in _ENTRY_FIELDS:
        if key in value:
            entry[key] = _bounded(value[key])
    for key in ("computedHash", "skillFolderHash"):
        if key in value:
            entry[key] = _bounded(value[key], 128)
    return entry


def _missing_lock(target: Path, kind: str) -> dict:
    return {
        "path": _bounded(str(target)),
        "kind": kind,
        "state": "missing",
        "reason": "lockfile is not present",
        "version": None,
        "entries": [],
        "omitted": 0,
        "total_entries": 0,
    }


def _load_lock_document(target: Path, kind: str) -> tuple[dict | None, dict | None]:
    """Return ``(payload, invalid_record)``; exactly one of the two is set."""
    try:
        if target.is_symlink():
            return None, _invalid(target, kind, "lockfile is a symlink")
        if not target.exists():
            return None, _missing_lock(target, kind)
        if not target.is_file():
            return None, _invalid(target, kind, "lock path is not a regular file")
        if target.stat().st_size > MAX_LOCK_BYTES:
            return None, _invalid(target, kind, f"lockfile exceeds {MAX_LOCK_BYTES} bytes")
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return None, _invalid(target, kind, f"lockfile cannot be read: {exc}")
    if not isinstance(data, dict):
        return None, _invalid(target, kind, "lockfile root is not an object")
    return data, None


def read_lock(path: str | Path, *, kind: str | None = None) -> dict:
    """Parse one lockfile into a bounded, JSON-safe evidence record."""
    target = Path(path).expanduser()
    if kind is not None and kind not in _LOCK_VERSIONS:
        raise LockfileError(f"unsupported lock kind {kind!r}")
    data, problem = _load_lock_document(target, kind or "unknown")
    if problem is not None:
        return problem
    resolved_kind = _lock_kind(data.get("version"), kind)
    if resolved_kind is None:
        return _invalid(
            target,
            kind or "unknown",
            f"unsupported lockfile version {data.get('version')!r}",
        )
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return _invalid(target, resolved_kind, "lockfile skills is not an object")
    entries = []
    for name in sorted(skills, key=lambda item: (str(item).casefold(), str(item))):
        value = skills[name]
        if not isinstance(value, dict):
            return _invalid(target, resolved_kind, f"skill entry {name!r} is not an object")
        entries.append(_normalized_entry(str(name), value))
    omitted = max(0, len(entries) - MAX_LOCK_ENTRIES)
    return {
        "path": _bounded(str(target)),
        "kind": resolved_kind,
        "state": "ok",
        "reason": "",
        "version": int(data["version"]),
        "entries": entries[:MAX_LOCK_ENTRIES],
        "omitted": omitted,
        "total_entries": len(entries),
    }


def _source_label(entry: dict) -> dict:
    label = safe_source_url(entry.get("sourceUrl"))
    if not label:
        # The fallback goes through the same credential stripping.
        label = safe_source_url(entry.get("source", ""))
    return {
        "label": label,
        "source_type": _bounded(entry.get("sourceType", ""), 64),
    }


_TREE_DIFFERS = (
    "the local folder differs from the recorded upstream tree; this is not a "
    "tampering verdict (the upstream installer also omits metadata.json, "
    "__pycache__ and __pypackages__, so a folder that held them never matches)"
)
_ICU_ORDERING = (
    "ICU localeCompare ordering is not reproducible with the standard "
    "library; a mismatch may be ordering, not content"
)


def _computed_outcome(directory: Path, recorded: str) -> tuple[str, str]:
    for order in ("codepoint", "casefold"):
        if computed_folder_hash(directory, order) == recorded:
            return "match", ""
    return "mismatch_or_unverifiable", _ICU_ORDERING


def _tree_outcome(directory: Path, recorded: str) -> tuple[str, str]:
    if skill_folder_tree_sha(directory) == recorded:
        return "match", ""
    # Only a lone SKILL.md.disabled is renamed; with both documents present a
    # rename would create a duplicate tree entry.
    lone_disabled = (directory / "SKILL.md.disabled").is_file() and not (directory / "SKILL.md").exists()
    if lone_disabled and skill_folder_tree_sha(directory, as_enabled=True) == recorded:
        return "match", "matches the recorded tree once SKILL.md.disabled is read as SKILL.md"
    return "differs_from_recorded_tree", _TREE_DIFFERS


def _hash_outcome(directory: Path, entry: dict, mode: str) -> tuple[str, str]:
    """Return ``(hash_status, hash_reason)`` for one installed copy."""
    recorded_key = "computedHash" if mode == "computed" else "skillFolderHash"
    recorded = entry.get(recorded_key, "")
    if not isinstance(recorded, str) or not recorded.strip():
        return "not_recorded", "the lockfile does not record a hash for this skill"
    recorded = recorded.strip().lower()
    outcome = _computed_outcome if mode == "computed" else _tree_outcome
    try:
        return outcome(directory, recorded)
    except LockfileTooLarge as exc:
        return "too_large", str(exc)
    except (LockfileError, OSError, RecursionError) as exc:
        return "unverifiable", _unverifiable_reason(exc)


def _unverifiable_reason(exc: BaseException) -> str:
    if isinstance(exc, RecursionError):
        return "the skill folder nests too deeply to hash"
    return _bounded(str(exc))


def _entry_evidence(entry: dict, installed_root: Path, mode: str) -> dict:
    directory = installed_root / sanitize_name(entry.get("name", ""))
    row = {
        "name": _bounded(entry.get("name", ""), 128),
        "installed_path": _bounded(str(directory)),
        "present": directory.is_dir(),
        "disabled": (directory / "SKILL.md.disabled").is_file(),
        "hash_status": "missing",
        "hash_reason": "",
        "source": _source_label(entry),
    }
    if not row["present"]:
        row["hash_reason"] = "the declared skill folder is not installed"
        return row
    if directory.is_symlink():
        row["hash_status"] = "unverifiable"
        row["hash_reason"] = "symlinked directory"
        return row
    row["hash_status"], row["hash_reason"] = _hash_outcome(directory, entry, mode)
    return row


def _counts(rows: list[dict]) -> dict:
    result = {
        "declared": len(rows),
        "present": 0,
        "missing": 0,
        "match": 0,
        "differs": 0,
        "unverifiable": 0,
        "not_recorded": 0,
        "too_large": 0,
    }
    differing = {"mismatch_or_unverifiable", "differs_from_recorded_tree"}
    for row in rows:
        status = row["hash_status"]
        result["present"] += int(row["present"])
        result["missing"] += int(not row["present"])
        result["match"] += int(status == "match")
        result["differs"] += int(status in differing)
        result["unverifiable"] += int(status == "unverifiable")
        result["not_recorded"] += int(status == "not_recorded")
        result["too_large"] += int(status == "too_large")
    return result


def _evaluated_lock(lock: dict, installed_root: Path, mode: str) -> dict:
    result = dict(lock)
    result["installed_root"] = _bounded(str(installed_root))
    if lock.get("state") != "ok":
        result["entries"] = []
        result["counts"] = _counts([])
        return result
    rows = [
        _entry_evidence(entry, installed_root, mode)
        for entry in lock.get("entries", [])
    ]
    result["entries"] = rows
    result["counts"] = _counts(rows)
    return result


def _unavailable_lock(kind: str, reason: str) -> dict:
    return {
        "path": "",
        "kind": kind,
        "state": "unavailable",
        "reason": _bounded(reason),
        "version": None,
        "entries": [],
        "omitted": 0,
        "total_entries": 0,
        "installed_root": "",
        "counts": _counts([]),
    }


def _undeclared(installed_root: Path, lock: dict) -> dict:
    result = {"names": [], "total": 0, "truncated": False}
    if lock.get("state") != "ok" or not installed_root.is_dir():
        return result
    declared = {sanitize_name(entry.get("name", "")) for entry in lock.get("entries", [])}
    try:
        names = sorted(
            item.name
            for item in installed_root.iterdir()
            if item.is_dir() and not item.is_symlink() and not item.name.startswith(".")
        )
    except OSError:
        return result
    names = [name for name in names if name not in declared]
    result["total"] = len(names)
    result["names"] = names[:MAX_UNDECLARED]
    result["truncated"] = len(names) > MAX_UNDECLARED
    return result


def _total_counts(locks: list[dict]) -> dict:
    total = _counts([])
    for lock in locks:
        for key, value in lock.get("counts", {}).items():
            total[key] = total.get(key, 0) + int(value)
    return total


def unavailable_evidence(reason: str) -> dict:
    """Return the lockfile section shape when evidence cannot be gathered."""
    return {
        "policy": "read-only evidence; a hash mismatch is not a tampering verdict",
        "global": _unavailable_lock("global", reason),
        "project": _unavailable_lock("project", "no project root context is available"),
        "undeclared": {"names": [], "total": 0, "truncated": False},
        "summary": _counts([]),
        "unavailable_signals": [
            {"signal": "lockfiles", "explanation": _bounded(reason)}
        ],
        "limits": {
            "max_lock_bytes": MAX_LOCK_BYTES,
            "max_lock_entries": MAX_LOCK_ENTRIES,
            "max_undeclared": MAX_UNDECLARED,
            "max_hash_files": MAX_HASH_FILES,
            "max_hash_bytes": MAX_HASH_BYTES,
        },
    }


def lockfile_evidence(
    home: str | Path | None,
    project_root: str | Path | None = None,
    xdg_state_home: str | Path | None = None,
) -> dict:
    """Build the read-only lockfile evidence section for a hygiene report."""
    token = _REQUEST_BUDGET.set(_RequestBudget())
    try:
        return _lockfile_evidence(home, project_root, xdg_state_home)
    finally:
        _REQUEST_BUDGET.reset(token)


def _lockfile_evidence(home, project_root, xdg_state_home) -> dict:
    if home is None:
        return unavailable_evidence("home directory is not resolvable")
    home_path = Path(home).expanduser()
    global_path = (
        Path(xdg_state_home).expanduser() / "skills" / GLOBAL_LOCK_FILENAME
        if xdg_state_home
        else home_path / ".agents" / GLOBAL_LOCK_FILENAME
    )
    global_lock = _evaluated_lock(
        read_lock(global_path, kind="global"),
        home_path / ".agents" / "skills",
        "tree",
    )
    if project_root is None:
        project_lock = _unavailable_lock(
            "project", "no project root context is available to this report"
        )
        project_installed = None
    else:
        project_path = Path(project_root).expanduser()
        project_installed = project_path / ".agents" / "skills"
        project_lock = _evaluated_lock(
            read_lock(project_path / PROJECT_LOCK_FILENAME, kind="project"),
            project_installed,
            "computed",
        )
    signals = []
    if project_root is not None:
        apm = Path(project_root).expanduser() / APM_LOCK_FILENAME
        if apm.is_file():
            signals.append({
                "signal": "apm-lock",
                "explanation": "YAML parsing is not available in the standard library",
                "path": _bounded(str(apm)),
            })
    return {
        "policy": "read-only evidence; a hash mismatch is not a tampering verdict",
        "global": global_lock,
        "project": project_lock,
        "undeclared": _undeclared(home_path / ".agents" / "skills", global_lock),
        "summary": _total_counts([global_lock, project_lock]),
        "unavailable_signals": signals,
        "limits": {
            "max_lock_bytes": MAX_LOCK_BYTES,
            "max_lock_entries": MAX_LOCK_ENTRIES,
            "max_undeclared": MAX_UNDECLARED,
            "max_hash_files": MAX_HASH_FILES,
            "max_hash_bytes": MAX_HASH_BYTES,
        },
    }


__all__ = [
    "LockfileError",
    "LockfileTooLarge",
    "sanitize_name",
    "safe_source_url",
    "computed_folder_hash",
    "skill_folder_tree_sha",
    "read_lock",
    "lockfile_evidence",
    "unavailable_evidence",
]
