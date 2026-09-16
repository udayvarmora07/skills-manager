"""Persistent store for skills.

The filesystem is the source of truth: each installed skill lives in
``<data>/skills/<name>/SKILL.md`` (or ``SKILL.md.disabled`` while disabled).
SQLite is a rebuildable index over that tree, used for fast listing, search
and history. The database can be regenerated at any time from the on-disk
skills via :meth:`Store.resync` / :meth:`Store.db_rebuild`.
"""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
import time
import zipfile
import zlib
import gzip
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import paths
from . import __version__
from .diagnostics import diagnose as _diagnose
from .atomic_io import atomic_write_text, mutation_lock, tree_content_hash
from . import archive as _archive
from .path_safety import mkdir_private
from .frontmatter import dump_frontmatter, parse_frontmatter, FrontmatterError
from .validator import (
    MAX_COMPATIBILITY,
    MAX_DESCRIPTION,
    MAX_NAME,
    NAME_RE,
    validate_skill_name,
)

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    name        TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'active',
    description TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT 'uncategorized',
    license     TEXT,
    version     TEXT,
    disabled    INTEGER NOT NULL DEFAULT 0,
    added_at    TEXT,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS history (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL,
    action TEXT NOT NULL,
    at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
"""

# Suffix written by remove() as ``name-<ts>`` where <ts> ends in ``Z``; when
# two trashes collide within one second a ``-<n>`` counter is appended AFTER
# the ``Z`` (``name-<ts>-1``).  The regex accepts the counter on either side
# of an optional ``Z`` so every entry this writer produces stays canonical.
_TRASH_TS_RE = re.compile(r"-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d+)?Z?(?:-\d+)?$")

SNAPSHOT_KEEP = 5
_SNAPSHOT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z?(?:-\d+)?$")
_SCOPE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

def _mutation_lock(path: Path):
    return mutation_lock(path)


def _reject_both_documents(skill_dir: Path, name: str) -> None:
    """Refuse a directory that holds both SKILL.md and SKILL.md.disabled.

    Shared by the store and the scope adapters so the one-document invariant
    has a single wording and a single enforcement point.
    """
    from .loader import conflicting_documents

    if conflicting_documents(skill_dir):
        raise StoreError(
            f"skill '{name}' has both SKILL.md and SKILL.md.disabled; "
            "remove one of the two documents first"
        )


def _with_skill_lock(skill_dir: Path, func, *args, **kwargs):
    """Run *func* under the per-skill mutation lock shared with create/edit.

    The nested lock/unlock body rarely changes, so centralizing it keeps the
    individual mutation methods from accumulating complexity-budget drift.
    """
    lock = _mutation_lock(skill_dir / "SKILL.md")
    lock.acquire()
    try:
        return func(*args, **kwargs)
    finally:
        lock.release()


def _index_lock_path(skills_dir: Path) -> Path:
    """The lock key every library-wide mutation and index scan shares (STORE-12).

    ``resync()``/``db_rebuild()`` read the whole skills tree and then delete
    index rows for whatever they did not see, so a skill created between the
    scan and the delete pass was reported as ``removed`` while its directory
    was on disk.  Per-skill locks cannot exclude a whole-tree scan, so every
    mutation takes this one key as well, and the scan takes it for the whole
    pass.
    """
    return skills_dir / ".skillsmgr-index-lock"


def _with_index_lock(skills_dir: Path, func, *args, **kwargs):
    """Run *func* under the shared library/index lock."""
    lock = _mutation_lock(_index_lock_path(skills_dir))
    lock.acquire()
    try:
        return func(*args, **kwargs)
    finally:
        lock.release()


def _with_scan_lock(root: Path, func, *args, **kwargs):
    """Run an indexing pass under the shared library lock (STORE-12)."""
    return _with_index_lock(root, func, *args, **kwargs)


@contextmanager
def _skill_and_index_locks(skills_dir: Path, skill_dir: Path):
    """Hold the shared index lock and one skill's lock together.

    A mutation must exclude both a whole-tree scan (STORE-12) and a concurrent
    mutation of the same skill (STORE-2), and the two locks are always taken in
    this order so they cannot deadlock against each other.
    """
    with _mutation_lock(_index_lock_path(skills_dir)):
        with _mutation_lock(skill_dir / "SKILL.md"):
            yield


def _open_index_db(db_path: Path) -> sqlite3.Connection:
    """Open the index database, translating a driver failure (BUG-1)."""
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        raise StoreError(f"could not open the skill index: {exc}") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _trash_lock_dir(trash_dir: Path) -> Path:
    """The lock key that serializes whole-trash operations.

    ``restore()`` and ``purge_trash()`` both read and then destroy or consume
    the *same* trash entries.  They lock per-skill paths, which cannot exclude
    each other, so restore() could pick a candidate that purge_trash() deleted
    a moment earlier (raw FileNotFoundError), or commit a row for a copy that
    no longer exists.  One lock over the trash directory itself is the seam
    they share.
    """
    return trash_dir / ".trash-lock"


def _stage_sibling(dest: Path) -> Path:
    """Return an unused staging path beside *dest* for an atomic install.

    The name is what ``_is_transaction_artifact`` recognises, so a crash that
    leaves the staging directory behind is reported by ``doctor()`` instead of
    masquerading as a real skill directory.
    """
    base = dest.parent / f"{dest.name}.skillsmgr-stage"
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = Path(f"{base}.{counter}")
        counter += 1
    return candidate


def _has_trash_copy(trash_dir: Path, name: str) -> bool:
    """True when the trash still holds at least one entry for *name*."""
    if not trash_dir.is_dir():
        return False
    return any(_trash_entry_name(path) == name for path in trash_dir.iterdir())


def _trash_prune_candidates(trash_dir: Path) -> list[tuple[Path, str]]:
    """Return ``(path, name)`` for every validated trash entry, in scan order.

    Purging two timestamped copies of one skill must report the name once, so
    the caller dedupes ``name``; the *paths* stay distinct because both copies
    have to be deleted.
    """
    candidates: list[tuple[Path, str]] = []
    for path in sorted(trash_dir.iterdir()):
        name = _trash_entry_name(path)
        if name is not None:
            candidates.append((path, name))
    return candidates


def _sync_parent_directory(path: Path) -> None:
    """Best-effort fsync of a directory entry after a create/replace."""
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def _unique_dest(directory: Path, stem: str, suffix: str) -> Path:
    """Return an unused ``stem + suffix`` path inside *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    target = paths.contained_path(directory, f"{stem}{suffix}")
    counter = 1
    while target.exists():
        target = paths.contained_path(directory, f"{stem}-{counter}{suffix}")
        counter += 1
    return target


def _move_within_tree(source: Path, dest: Path) -> None:
    """Move *source* to *dest*, falling back to copy+delete across devices."""
    try:
        os.replace(source, dest)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    shutil.copytree(source, dest, symlinks=True)
    shutil.rmtree(source)


def _archive_members(root: Path) -> list[Path]:
    """Return the *regular* files of a tree, in a stable order (STORE-9).

    Archived members must be exactly the regular single-link files whose bytes
    :func:`atomic_io.tree_content_hash` hashes: ``tar.add`` stores a symlink as
    a ``SYMTYPE`` member, which ``archive.validate_members`` rejects, so an
    archive containing just one symlink used to fail import entirely -- the
    whole backup, every skill in it, became unimportable.
    """
    members: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            continue
        if path.is_file():
            members.append(path)
    return members


def _resync_row_changed(row, entry: dict) -> bool:
    """Compare one scanned filesystem skill against its index row."""
    return (
        row["status"] != "active"
        or row["description"] != entry["description"]
        or row["body"] != entry["body"]
        or row["category"] != entry["category"]
        or row["license"] != entry["license"]
        or row["version"] != entry["version"]
        or row["disabled"] != entry["disabled"]
    )


def _resync_row_update(conn, entry: dict, name: str) -> None:
    """Reconcile one index row to match the live filesystem skill."""
    conn.execute(
        "UPDATE skills SET status = 'active', description = ?, body = ?, "
        "category = ?, license = ?, version = ?, disabled = ?, "
        "updated_at = ? WHERE name = ?",
        (
            entry["description"],
            entry["body"],
            entry["category"],
            entry["license"],
            entry["version"],
            entry["disabled"],
            now_iso(),
            name,
        ),
    )


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    return atomic_write_text(path, text, encoding=encoding, replace=os.replace)


def _tree_content_hash(root: Path) -> str:
    return tree_content_hash(root)

MAX_ARCHIVE_COMPRESSED_BYTES = _archive.MAX_ARCHIVE_COMPRESSED_BYTES
MAX_ARCHIVE_EXPANDED_BYTES = _archive.MAX_ARCHIVE_EXPANDED_BYTES
MAX_ARCHIVE_MEMBER_BYTES = _archive.MAX_ARCHIVE_MEMBER_BYTES
MAX_ARCHIVE_MEMBERS = _archive.MAX_ARCHIVE_MEMBERS
MAX_ARCHIVE_PATH_LENGTH = _archive.MAX_ARCHIVE_PATH_LENGTH
MAX_ARCHIVE_NESTING = _archive.MAX_ARCHIVE_NESTING
MAX_ARCHIVE_COMPRESSION_RATIO = _archive.MAX_ARCHIVE_COMPRESSION_RATIO


def _live_index_totals(conn, live: list[str]) -> tuple[int, dict]:
    """Return ``(disabled_count, category_counts)`` for skills that exist on disk.

    Counted over *live* names only (STORE-10): an index row whose directory is
    gone is residue, and must not be counted as an installed skill.
    """
    if not live:
        return 0, {}
    placeholders = ", ".join("?" for _ in live)
    disabled = conn.execute(
        f"SELECT COUNT(*) AS c FROM skills WHERE disabled = 1 AND name IN ({placeholders})",
        live,
    ).fetchone()["c"]
    categories = {
        row["category"]: row["c"]
        for row in conn.execute(
            "SELECT category, COUNT(*) AS c FROM skills "
            f"WHERE status = 'active' AND name IN ({placeholders}) "
            "GROUP BY category ORDER BY c DESC, category",
            live,
        ).fetchall()
    }
    return disabled, categories


def _skills_tree_size(skills_dir: Path) -> int:
    """Total size in bytes of every file below the skills tree, or 0."""
    if not skills_dir.is_dir():
        return 0
    return sum(
        path.stat().st_size for path in skills_dir.rglob("*") if path.is_file()
    )


class StoreError(Exception):
    """Raised for any store-level failure (validation, I/O, conflicts)."""


def _without_transaction_artifacts(entries: list[dict]) -> list[dict]:
    """Drop scan rows that name a transaction artifact of this store.

    A staging marker whose name does not pass the canonical-name guard comes
    back from the loader as a link-escape row; it is a transaction artifact,
    reported by ``doctor()`` under its own heading, not a skill (STORE-13).
    """
    artifact_names = {
        entry["name"] for entry in entries if _is_transaction_artifact(entry["name"])
    }
    if not artifact_names:
        return entries
    return [entry for entry in entries if entry["name"] not in artifact_names]


@contextmanager
def _driver_errors(action: str):
    """Translate ``sqlite3.Error`` escaping a database block (BUG-1).

    ``cli.py`` handles ``(StoreError, ValueError, OSError)`` and everything
    else becomes "unexpected error: <raw text>" with a traceback, and the Web
    UI answers 500.  No driver exception should ever get that far, so the
    handful of blocks that run raw SQL wrap themselves in this.
    """
    try:
        yield
    except sqlite3.Error as exc:
        raise StoreError(f"skill index {action} failed: {exc}") from exc


class SkillNotFound(StoreError):
    """Raised when an operation targets a skill that does not exist."""


def now_iso() -> str:
    """Return the current UTC time in ``YYYY-MM-DDTHH:MM:SSZ`` form."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trash_timestamp() -> str:
    return now_iso().replace(":", "-").replace("T", "_")


def _check_snapshot_target(scope: str, name: str) -> None:
    if not _SCOPE_ID_RE.fullmatch(scope) or scope in (".", ".."):
        raise StoreError(f"invalid scope {scope!r}")
    try:
        validate_skill_name(name)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


def write_snapshot(data_dir: Path, scope: str, name: str, text: str) -> str:
    """Save pre-write skill content and retain only the newest five snapshots."""
    _check_snapshot_target(scope, name)
    snap_dir = paths.contained_path(Path(data_dir) / "snapshots", scope, name)
    snap_dir.mkdir(parents=True, exist_ok=True)
    with _mutation_lock(snap_dir):
        base = _trash_timestamp()
        snap_id = base
        counter = 1
        while (snap_dir / f"{snap_id}.md").exists():
            snap_id = f"{base}-{counter}"
            counter += 1
        snapshot_path = snap_dir / f"{snap_id}.md"
        _atomic_write_text(snapshot_path, text)
        files = sorted(snap_dir.glob("*.md"), key=lambda p: p.name)
        while len(files) > SNAPSHOT_KEEP:
            files.pop(0).unlink()
    return snap_id


def list_snapshots(data_dir: Path, scope: str, name: str) -> list[str]:
    """Return valid snapshot ids for a skill, newest first."""
    _check_snapshot_target(scope, name)
    snap_dir = paths.contained_path(Path(data_dir) / "snapshots", scope, name)
    if not snap_dir.is_dir():
        return []
    return sorted(
        (p.stem for p in snap_dir.glob("*.md") if _SNAPSHOT_ID_RE.fullmatch(p.stem)),
        reverse=True,
    )


def read_snapshot(data_dir: Path, scope: str, name: str, snapshot: str) -> str:
    """Read a validated snapshot id for a skill."""
    _check_snapshot_target(scope, name)
    if not _SNAPSHOT_ID_RE.fullmatch(snapshot):
        raise StoreError(f"invalid snapshot id {snapshot!r}")
    path = paths.contained_path(Path(data_dir) / "snapshots", scope, name, f"{snapshot}.md")
    if not path.is_file():
        raise StoreError(f"no snapshot {snapshot!r} for '{name}' in scope '{scope}'")
    from .loader import read_skill_text_strict

    return read_skill_text_strict(path, subject=f"snapshot {snapshot!r} for '{name}'")


def _coerce_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _trash_entry_name(path: Path) -> str | None:
    """Return a canonical skill name for a valid trash directory name."""
    if path.is_symlink() or not path.is_dir():
        return None
    match = _TRASH_TS_RE.search(path.name)
    if match is None or match.end() != len(path.name):
        return None
    name = path.name[: match.start()]
    try:
        return validate_skill_name(name)
    except ValueError:
        return None


def _is_transaction_artifact(name: str) -> bool:
    return (
        name.endswith((".skillsmgr-stage", ".skillsmgr-backup"))
        or ".skillsmgr-stage." in name
        or ".skillsmgr-backup." in name
    )


def _is_temporary_file(name: str) -> bool:
    """True only for *our* temporary files, never a user's own.

    STORE-14: ``name.endswith((".tmp", ".temp"))`` matched any file a user
    happened to keep inside a skill (``notes.tmp``), which turned
    ``doctor().ok`` into ``False`` with no API-accessible fix.  Every artifact
    this tool writes carries one of its own markers.
    """
    return (
        ".skillsmgr-tmp" in name
        or name in {".skillsmgr-stage", ".skillsmgr-backup"}
        or ".skillsmgr-stage" in name
        or ".skillsmgr-backup" in name
    )


def _stale_snapshots(data_dir: Path) -> list[str]:
    snapshots_root = data_dir / "snapshots"
    if not snapshots_root.is_dir():
        return []
    return sorted(
        str(path.relative_to(data_dir))
        for path in snapshots_root.rglob("*")
        if path.is_file()
        and (
            path.suffix != ".md"
            or not _SNAPSHOT_ID_RE.fullmatch(path.stem)
            or len(path.relative_to(snapshots_root).parts) != 3
        )
    )


#: STORE-11: a mutation that dies — or loses a cross-process race — between
#: creating its staging file and renaming it leaves an artifact nothing else
#: cleans.  ``doctor()`` reports it, so ``ok`` stays False, and before this
#: sweep no supported repair path existed (the documented one is ``resync``).
#: A live writer holds its staging file for the duration of a single write, so
#: only artifacts older than this grace window are treated as abandoned.
TRANSACTION_ARTIFACT_GRACE_SECONDS = 300


def _sweep_abandoned_artifacts(
    data_dir: Path, *, now: float | None = None
) -> tuple[list[str], list[str]]:
    """Remove abandoned transaction artifacts under *data_dir*.

    Returns ``(cleared, failed)`` as data-dir-relative names.  A directory is
    removed before its children are visited, so a stage tree is cleared as one
    unit; anything that cannot be removed is reported rather than retried.
    """
    if not data_dir.is_dir():
        return [], []
    cutoff = (time.time() if now is None else now) - TRANSACTION_ARTIFACT_GRACE_SECONDS
    cleared: list[str] = []
    failed: list[str] = []
    removed: set[Path] = set()
    for path in sorted(data_dir.rglob("*"), key=lambda item: len(item.parts)):
        if not (_is_transaction_artifact(path.name) or _is_temporary_file(path.name)):
            continue
        if any(parent in removed for parent in path.parents):
            continue
        try:
            if path.lstat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        try:
            if path.is_symlink() or not path.is_dir():
                path.unlink()
            else:
                shutil.rmtree(path)
        except OSError as exc:
            failed.append(str(path.relative_to(data_dir)))
            _diagnose(
                f"resync could not clear abandoned transaction artifact "
                f"{path.relative_to(data_dir)}",
                exc,
            )
            continue
        removed.add(path)
        cleared.append(str(path.relative_to(data_dir)))
    return cleared, failed


def _doctor_artifacts(data_dir: Path, trash_dir: Path, templates_dir: Path) -> dict:
    """Return leftover transaction/temp/snapshot artifacts and directory counts."""
    paths = list(data_dir.rglob("*"))
    trash_names = (
        {name for path in trash_dir.iterdir() if (name := _trash_entry_name(path))}
        if trash_dir.is_dir()
        else set()
    )
    return {
        "transaction_artifacts": sorted(
            str(path.relative_to(data_dir))
            for path in paths
            if _is_transaction_artifact(path.name)
        ),
        "temporary_files": sorted(
            str(path.relative_to(data_dir))
            for path in paths
            if _is_temporary_file(path.name)
        ),
        "stale_snapshots": _stale_snapshots(data_dir),
        "trash_names": trash_names,
        "trash_count": len(trash_names),
        "templates_count": (
            len(list(templates_dir.glob("*.md"))) if templates_dir.is_dir() else 0
        ),
    }


def _normalize_archive_member_name(name: str) -> str:
    try:
        return _archive.normalize_member_name(name)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _validate_archive_members(
    tar: tarfile.TarFile,
    compressed_size: int,
) -> list[tuple[tarfile.TarInfo, str]]:
    """Compatibility adapter for the extracted archive inspector."""
    try:
        return _archive.validate_members(tar, compressed_size)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _validate_archive_manifest(manifest: object) -> list[dict]:
    """Compatibility adapter for the extracted manifest validator."""
    try:
        return _archive.validate_manifest(manifest)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _extract_archive_members(
    tar: tarfile.TarFile,
    dest: Path,
    members: list[tuple[tarfile.TarInfo, str]],
) -> None:
    """Compatibility adapter for the extracted safe extractor."""
    try:
        return _archive.extract_members(tar, dest, members)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _validate_zip_members(
    archive: zipfile.ZipFile,
    compressed_size: int,
) -> list[tuple[zipfile.ZipInfo, str]]:
    """Compatibility adapter for the ZIP member preflight."""
    try:
        return _archive.validate_zip_members(archive, compressed_size)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _extract_zip_members(
    archive: zipfile.ZipFile,
    dest: Path,
    members: list[tuple[zipfile.ZipInfo, str]],
) -> None:
    """Compatibility adapter for the guarded ZIP extractor."""
    try:
        return _archive.extract_zip_members(archive, dest, members)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _validate_full_payload(kind: str, source: Path) -> bool:
    """Return whether one preflighted full-import payload is usable."""
    if kind == "trash":
        return source.is_dir() and _trash_entry_name(source) is not None
    return source.is_file()


def _plan_full_restore(store: "Store", tmp: Path, manifest: dict) -> list[tuple[str, str, Path, Path]]:
    """Validate full-archive trash/templates payloads before any mutation.

    Every manifest entry must resolve to a safe contained destination and to an
    existing archive payload; otherwise the whole import fails before a single
    live skill or metadata file is touched.
    """
    entries: list[tuple[str, str, Path, Path]] = []
    for kind in ("trash", "templates"):
        dest_root = store.trash_dir if kind == "trash" else store.templates_dir
        for label in manifest.get(kind) or []:
            source = tmp / kind / label
            if not _validate_full_payload(kind, source):
                raise StoreError(f"archive {kind} entry is missing or invalid: {label!r}")
            try:
                dest = paths.contained_path(dest_root, label)
            except ValueError as exc:
                raise StoreError(f"archive {kind} entry escapes the data directory: {label!r}") from exc
            entries.append((kind, label, source, dest))
    return entries


def _record_restored_trash(store: "Store", labels: list[str]) -> None:
    """Reconcile the index with trash entries installed by a full import."""
    if not labels:
        return
    conn = store._connect()
    try:
        for label in labels:
            name = _trash_entry_name(store.trash_dir / label)
            if name is None or _safe_skill_path(store.skills_dir, name).is_dir():
                continue
            conn.execute(
                "INSERT OR IGNORE INTO skills (name, status, added_at, updated_at) "
                "VALUES (?, 'trashed', ?, ?)",
                (name, now_iso(), now_iso()),
            )
            conn.execute(
                "UPDATE skills SET status = 'trashed', updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
        conn.commit()
    finally:
        conn.close()


def _extract_import_archive(archive: Path, dest: Path) -> None:
    """Sniff and safely extract either supported archive format."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive, "r") as zipped:
            members = _validate_zip_members(zipped, archive.stat().st_size)
            _extract_zip_members(zipped, dest, members)
        return
    with tarfile.open(archive, "r:*") as tar:
        members = _validate_archive_members(tar, archive.stat().st_size)
        _extract_archive_members(tar, dest, members)


def _has_skill_document(source: Path) -> bool:
    try:
        return _archive.has_skill_document(source)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _validate_imported_skill(source: Path, name: str) -> None:
    try:
        return _archive.validate_imported_skill(source, name)
    except _archive.ArchiveError as exc:
        raise StoreError(str(exc)) from exc


def _safe_skill_path(root: Path, name: str) -> Path:
    """Return a validated, root-contained skill path as ``StoreError``."""
    try:
        return paths.safe_skill_path(root, name)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


class Store:
    """Manages the skills directory tree and the SQLite index."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir).expanduser() if data_dir else paths.data_dir()
        self.skills_dir = self.data_dir / "skills"
        self.trash_dir = self.data_dir / "trash"
        self.templates_dir = self.data_dir / "templates"
        self.backups_dir = self.data_dir / "backups"
        self.db_path = self.data_dir / "skills-manager.db"

    # ------------------------------------------------------------------ db

    def _connect(self) -> sqlite3.Connection:
        """Open the index database, translating driver failures (BUG-1).

        Every database access goes through here, so this is the one seam that
        guarantees no ``sqlite3.Error`` escapes the Store: ``cli.py`` catches
        ``(StoreError, ValueError, OSError)`` and would otherwise print a raw
        "unexpected error: no such table: skills" instead of a clean dialog.
        """
        return _open_index_db(self.db_path)

    def _init_db(self) -> None:
        for path in (
            self.data_dir,
            self.skills_dir,
            self.trash_dir,
            self.templates_dir,
            self.backups_dir,
        ):
            mkdir_private(path)
        conn = self._connect()
        try:
            self._bootstrap_schema(conn)
        finally:
            conn.close()

    @staticmethod
    def _bootstrap_schema(conn: sqlite3.Connection) -> None:
        """Create the tables and metadata a fresh data directory needs."""
        with _driver_errors("initialisation"):
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()

    def _history(self, conn: sqlite3.Connection, name: str, action: str) -> None:
        conn.execute(
            "INSERT INTO history (name, action, at) VALUES (?, ?, ?)",
            (name, action, now_iso()),
        )

    def _load_skill(self, skill_dir: Path) -> dict:
        from .loader import load_skill as _shared_load

        return _shared_load(skill_dir)

    @staticmethod
    def _commit_history(conn: sqlite3.Connection, name: str, action: str) -> int | None:
        """Record one history row and commit, returning its row id.

        The write happens here rather than at each call site so a driver
        failure (BUG-1) is always translated before it can reach a caller that
        only handles StoreError.  The id is returned so a rollback can remove
        *this* row (STORE-14): the previous cleanup deleted every ``create``
        row for the name, so a failed re-create of a once-removed skill erased
        its original creation record.
        """
        try:
            cursor = conn.execute(
                "INSERT INTO history (name, action, at) VALUES (?, ?, ?)",
                (name, action, now_iso()),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise StoreError(f"could not record history for '{name}': {exc}") from exc

    def _upsert_entry(self, name: str) -> dict:
        skill_dir = _safe_skill_path(self.skills_dir, name)
        if not skill_dir.is_dir():
            raise SkillNotFound(f"skill '{name}' is not installed")
        entry = self._load_skill(skill_dir)
        conn = self._connect()
        try:
            self._upsert_row(conn, name, entry)
            conn.commit()
        except sqlite3.Error as exc:
            # The other half of the BUG-1 seam: a driver failure while writing
            # the index must surface as the Store error contract, not as a raw
            # sqlite3 exception on its way to a traceback.
            raise StoreError(f"could not update the skill index: {exc}") from exc
        finally:
            conn.close()
        return entry

    @staticmethod
    def _upsert_row(conn: sqlite3.Connection, name: str, entry: dict) -> None:
        """Write one skill's index row (insert or reconcile)."""
        row = conn.execute(
            "SELECT status, disabled, added_at FROM skills WHERE name = ?", (name,)
        ).fetchone()
        if row is not None:
            current = conn.execute(
                "SELECT description, body, category, license, version "
                "FROM skills WHERE name = ?",
                (name,),
            ).fetchone()
            content_same = tuple(current) == (
                entry["description"],
                entry["body"],
                entry["category"],
                entry["license"],
                entry["version"],
            )
            # A live skill directory on the filesystem is by definition an
            # active skill: any existing row (e.g. left 'trashed' by an
            # earlier remove of the same name) must become 'active' again
            # so list()/stats/doctor stay consistent with the filesystem.
            if (
                row["status"] == "active"
                and row["disabled"] == entry["disabled"]
                and content_same
            ):
                return
            conn.execute(
                "UPDATE skills SET description = ?, body = ?, category = ?, "
                "license = ?, version = ?, disabled = ?, status = 'active', "
                "updated_at = ? WHERE name = ?",
                (
                    entry["description"],
                    entry["body"],
                    entry["category"],
                    entry["license"],
                    entry["version"],
                    entry["disabled"],
                    now_iso(),
                    name,
                ),
            )
            return
        now = now_iso()
        conn.execute(
            "INSERT INTO skills (name, status, description, body, category, "
            "license, version, disabled, added_at, updated_at) "
            "VALUES (?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                entry["description"],
                entry["body"],
                entry["category"],
                entry["license"],
                entry["version"],
                entry["disabled"],
                now,
                now,
            ),
        )

    def _scan_dir(self, root: Path) -> list[dict]:
        from .loader import scan_dir as _shared_scan

        # STORE-13: document-less directories are drift the store must see, but
        # the store's own staging markers are transaction artifacts, not skill
        # husks -- they are reported by doctor() under their own heading.  The
        # husks are collected here rather than inside loader.scan_dir because
        # the store's own index-lock marker name is not a valid skill name, so
        # the generic name guard would classify it as something else.
        entries = _without_transaction_artifacts(_shared_scan(root))
        entries.extend(self._husk_entries(root))
        return sorted(
            entries, key=lambda item: (item["name"].lower(), item.get("path", ""))
        )

    def _husk_entries(self, root: Path) -> list[dict]:
        """Return drift rows for subdirectories of *root* that hold no document.

        A directory named like a skill but without a ``SKILL.md``/
        ``SKILL.md.disabled`` never reaches the loader (its name may not even
        pass the canonical-name guard), so it is reported here instead: doctor()
        then sees the husk an interrupted remove/purge left behind.
        """
        from .loader import _husk_record

        husks: list[dict] = []
        try:
            children = sorted(path for path in root.iterdir() if path.is_dir())
        except OSError:
            return husks
        for child in children:
            if _is_transaction_artifact(child.name):
                continue
            try:
                if (child / "SKILL.md").is_file() or (child / "SKILL.md.disabled").is_file():
                    continue
            except OSError:
                continue
            husk = _husk_record(child)
            husk["path"] = str(child)
            husks.append(husk)
        return husks

    def _skill_names_on_disk(self) -> set[str]:
        """Names of skill directories that exist on disk right now (STORE-10).

        The index is rebuildable, so every read path filters its rows through
        the filesystem instead of trusting a row over the tree.
        """
        try:
            return {path.name for path in self.skills_dir.iterdir() if path.is_dir()}
        except OSError:
            return set()

    # ------------------------------------------------------------- public

    def init_db(self) -> None:
        """Create the data directories, tables and metadata if missing."""
        self._init_db()

    def resync(self) -> dict:
        """Rebuild the index from the skills directory tree.

        Holds the skills-directory lock (STORE-12) so a skill created between
        the scan and the delete pass cannot be reported as ``removed`` while its
        directory is on disk.  Existing rows keep their ``added_at``; rows whose
        content changed get a new ``updated_at``; active rows with no directory
        on disk are removed.  No history entries are written (this is an
        indexing operation).
        """
        return _with_scan_lock(self.skills_dir, self._resync_locked)

    def _resync_locked(self) -> dict:
        self._init_db()
        # STORE-11: repair what a dead or cross-process-interleaved mutation left
        # behind, so doctor().ok can return to True without hand-deleting files.
        cleared, _failed = _sweep_abandoned_artifacts(self.data_dir)
        if cleared:
            _diagnose(
                f"resync cleared {len(cleared)} abandoned transaction artifact(s): "
                + ", ".join(cleared[:5])
                + ("…" if len(cleared) > 5 else "")
            )
        scanned = {e["name"]: e for e in self._scan_dir(self.skills_dir)}
        conn = self._connect()
        try:
            added, updated, removed = 0, 0, 0
            for name, entry in scanned.items():
                # STORE-13: a directory with no document is drift, never an
                # indexable skill.
                if entry.get("document_missing"):
                    continue
                row = conn.execute(
                    "SELECT status, description, body, category, license, version, "
                    "disabled FROM skills WHERE name = ?",
                    (name,),
                ).fetchone()
                if row is None:
                    now = now_iso()
                    conn.execute(
                        "INSERT INTO skills (name, status, description, body, category, "
                        "license, version, disabled, added_at, updated_at) "
                        "VALUES (?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            name,
                            entry["description"],
                            entry["body"],
                            entry["category"],
                            entry["license"],
                            entry["version"],
                            entry["disabled"],
                            now,
                            now,
                        ),
                    )
                    added += 1
                    continue
                changed = _resync_row_changed(row, entry)
                if changed:
                    # A live directory is by definition an active skill; rows
                    # left 'trashed' by an earlier remove whose directory has
                    # returned (e.g. raw sync writes) must be reactivated.
                    _resync_row_update(conn, entry, name)
                    updated += 1
            for row in conn.execute("SELECT name FROM skills WHERE status = 'active'"):
                if row["name"] not in scanned:
                    conn.execute("DELETE FROM skills WHERE name = ?", (row["name"],))
                    removed += 1
            # A 'trashed' row left behind by a lost restore/purge race has no
            # trash directory and no live directory: nothing on the filesystem
            # can ever reactivate it, so no other pass would repair it and
            # doctor() would report drift forever.  Reconcile those rows here.
            for row in conn.execute("SELECT name FROM skills WHERE status = 'trashed'"):
                if row["name"] in scanned or _has_trash_copy(self.trash_dir, row["name"]):
                    continue
                conn.execute("DELETE FROM skills WHERE name = ?", (row["name"],))
                removed += 1
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_resync', ?)",
                (now_iso(),),
            )
            conn.commit()
        finally:
            conn.close()
        return {"added": added, "updated": updated, "removed": removed}

    def list(self) -> list[dict]:
        """Return installed skills (active and disabled) sorted by name."""
        self._init_db()
        on_disk = self._skill_names_on_disk()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, status, description, category, license, version, "
                "disabled, added_at, updated_at FROM skills "
                "WHERE status = 'active' ORDER BY name"
            ).fetchall()
            # STORE-10: a row whose directory is gone (a crash between the
            # filesystem move and the index commit) must not be advertised:
            # the filesystem is the source of truth, so the index is filtered
            # by it rather than trusted over it.
            result = [dict(r) for r in rows if r["name"] in on_disk]
            from .loader import load_skill, name_is_addressable

            for record in result:
                self._observe_index_row(record)
            return result
        finally:
            conn.close()

    def _observe_index_row(self, record: dict) -> None:
        """Merge live filesystem observations into one ``list()`` row.

        SCOPE-15: a rogue index row whose name fails the canonical rule made
        ``_safe_skill_path`` raise StoreError, and that single row took down
        ``scan_scope("global")``, ``list_all()`` and ``search_all()`` together
        while ``list_scopes()`` (filesystem-only) still rendered -- so the UI
        showed healthy scope counts beside an erroring All list.  Such a row is
        index residue, not an addressable skill: it is marked and left alone
        instead of aborting every aggregate.
        """
        from .loader import load_skill, name_is_addressable

        record.setdefault("addressable", name_is_addressable(record["name"]))
        if not record["addressable"]:
            record["malformed"] = True
            record["decode_error"] = (
                f"invalid skill name {record['name']!r}: it fails the "
                "canonical name rule and cannot be addressed by name"
            )
            return
        skill_dir = _safe_skill_path(self.skills_dir, record["name"])
        try:
            observed = load_skill(skill_dir)
        except (OSError, SkillNotFound, UnicodeError, StoreError):
            return
        for key in (
            "content_hash",
            "metadata_hash",
            "observed_at",
            "provenance",
            "portable_frontmatter",
            "frontmatter_extensions",
            "malformed",
            "decode_error",
        ):
            if key in observed:
                record[key] = observed[key]
        if isinstance(record.get("provenance"), dict):
            record["provenance"]["scope"] = "global"
            record["provenance"]["consumer"] = "skills-manager"

    def get(self, name: str) -> dict:
        """Return the full record for a skill, including its body and path.

        ``installed`` reports whether the skill directory exists on disk
        (STORE-10): an ``active`` row left behind by a crash between the
        filesystem move and the index commit used to be served as an installed
        skill, with its stale stored body, while ``doctor()`` called the tree
        unhealthy.  ``path`` is ``None`` in that case, and callers that need an
        on-disk document must check ``installed``.
        """
        skill_dir = _safe_skill_path(self.skills_dir, name)
        self._init_db()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise SkillNotFound(f"skill '{name}' is not installed")
            result = dict(row)
            installed = skill_dir.is_dir()
            result["installed"] = installed
            result["path"] = str(skill_dir) if installed else None
            if skill_dir.is_dir():
                observed = self._load_skill(skill_dir)
                for key in (
                    "content_hash",
                    "metadata_hash",
                    "observed_at",
                    "provenance",
                    "portable_frontmatter",
                    "frontmatter_extensions",
                    "malformed",
                    "decode_error",
                ):
                    if key in observed:
                        result[key] = observed[key]
                if isinstance(result.get("provenance"), dict):
                    result["provenance"]["scope"] = "global"
                    result["provenance"]["consumer"] = "skills-manager"
            return result
        finally:
            conn.close()

    def search(self, term: str) -> list[dict]:
        """Case-insensitive search over name, description and body."""
        from .search import rank_results

        self._init_db()
        on_disk = self._skill_names_on_disk()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, description, category, license, version, disabled, "
                "updated_at, body FROM skills WHERE status = 'active' ORDER BY name",
            ).fetchall()
            # STORE-10: only search what the filesystem still holds.
            records = [dict(r) for r in rows if r["name"] in on_disk]
            if not term:
                return [{k: v for k, v in record.items() if k != "body"} for record in records]
            ranked = rank_results(records, term)
            return [
                {k: v for k, v in record.items() if k != "body"}
                for record, _ in ranked
            ]
        finally:
            conn.close()

    def create(
        self,
        name: str,
        description: str,
        *,
        license: str | None = None,
        category: str | None = None,
        compatibility: str | None = None,
        version: str | None = None,
        allowed_tools: str | None = None,
        metadata_extra: dict | None = None,
        body: str | None = None,
    ) -> dict:
        try:
            canonical_name = validate_skill_name(name.strip())
        except ValueError as exc:
            raise StoreError(str(exc)) from exc
        # The shared index lock serializes this mutation with resync()/
        # db_rebuild(), which otherwise scanned before the change and deleted
        # the new row after it (STORE-12).
        return _with_index_lock(
            self.skills_dir,
            self._create_unlocked,
            canonical_name,
            description,
            license=license,
            category=category,
            compatibility=compatibility,
            version=version,
            allowed_tools=allowed_tools,
            metadata_extra=metadata_extra,
            body=body,
        )

    def _create_unlocked(
        self,
        name: str,
        description: str,
        *,
        license: str | None = None,
        category: str | None = None,
        compatibility: str | None = None,
        version: str | None = None,
        allowed_tools: str | None = None,
        metadata_extra: dict | None = None,
        body: str | None = None,
    ) -> dict:
        """Create a new skill from validated inputs."""
        try:
            name = validate_skill_name(name.strip())
        except ValueError as exc:
            raise StoreError(str(exc)) from exc
        if not description or not description.strip():
            raise StoreError("description is required")
        description = description.strip()
        if len(description) > MAX_DESCRIPTION:
            raise StoreError(
                f"description exceeds {MAX_DESCRIPTION} characters"
            )
        if compatibility and len(compatibility) > MAX_COMPATIBILITY:
            raise StoreError(
                f"compatibility exceeds {MAX_COMPATIBILITY} characters"
            )
        skill_dir = _safe_skill_path(self.skills_dir, name)
        if skill_dir.exists():
            raise StoreError(f"skill '{name}' already exists")
        # BUG-1: every other public entry point bootstraps the schema; without
        # this the first-ever mutation on a fresh data dir raised a raw
        # sqlite3.OperationalError('no such table: skills'), and the rollback
        # in the handler below failed the same way.
        self._init_db()

        data: dict = {"name": name, "description": description}
        if license:
            data["license"] = license
        if compatibility:
            data["compatibility"] = compatibility
        if version:
            data["version"] = version
        if allowed_tools:
            if isinstance(allowed_tools, str):
                allowed_tools = allowed_tools.strip()
            elif isinstance(allowed_tools, (list, tuple)):
                allowed_tools = [
                    t.strip() for t in allowed_tools if str(t).strip()
                ]
            data["allowed-tools"] = allowed_tools
        metadata = dict(metadata_extra or {})
        if category:
            metadata["category"] = category
        if metadata:
            data["metadata"] = metadata

        if body is None:
            body = f"# {name}\n"
        if not body.endswith("\n"):
            body += "\n"
        content = dump_frontmatter(data, key_order=list(data.keys())) + body

        history_id: int | None = None
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(skill_dir / "SKILL.md", content)
            self._upsert_entry(name)
            conn = self._connect()
            try:
                history_id = self._commit_history(conn, name, "create")
            finally:
                conn.close()
        except Exception:
            self._rollback_failed_create(name, skill_dir, history_id)
            raise
        return {"name": name, "path": str(skill_dir)}

    def _rollback_failed_create(
        self, name: str, skill_dir: Path, history_id: int | None
    ) -> None:
        """Undo a failed ``create``: its own history row, its index row, its tree.

        STORE-14: the history delete used to match every ``create`` row for the
        name, so a failed re-create of a once-removed skill erased the original
        creation record.  Only the row this attempt inserted (``history_id``) is
        removed.
        """
        try:
            conn = self._connect()
            try:
                if history_id is not None:
                    conn.execute("DELETE FROM history WHERE id = ?", (history_id,))
                conn.execute("DELETE FROM skills WHERE name = ?", (name,))
                conn.commit()
            finally:
                conn.close()
        except Exception as cleanup_exc:
            _diagnose(f"create cleanup failed for {name!r}", cleanup_exc)
        try:
            shutil.rmtree(skill_dir)
        except OSError as cleanup_exc:
            _diagnose(f"create filesystem cleanup failed for {name!r}", cleanup_exc)

    def add(self, src: str | Path, name: str | None = None) -> dict:
        """Install an existing skill directory (or SKILL.md file) by copy."""
        source = Path(src).expanduser()
        if source.is_file() and source.name == "SKILL.md":
            source = source.parent
        if not source.is_dir():
            raise StoreError(f"source is not a directory: {src}")
        if not (source / "SKILL.md").is_file():
            raise StoreError(
                f"source must contain SKILL.md (got {source / 'SKILL.md'!s})"
            )
        try:
            chosen = validate_skill_name((name or source.name).strip())
        except ValueError as exc:
            raise StoreError(str(exc)) from exc
        try:
            data, _ = parse_frontmatter((source / "SKILL.md").read_text(encoding="utf-8"))
        except FrontmatterError:
            data = {}
        if isinstance(data.get("name"), str) and data["name"] != chosen:
            raise StoreError(
                f"frontmatter name {data['name']!r} does not match target name "
                f"{chosen!r}; rename the skill first"
            )
        skill_dir = _safe_skill_path(self.skills_dir, chosen)
        # Never install a directory that already violates the one-document
        # invariant: the store would inherit a skill whose next toggle
        # destroys one of the two documents (STORE-3).  Checked before the
        # lock so the cheap validation stays outside the critical section.
        _reject_both_documents(source, chosen)
        # The destination's per-skill lock covers the existence check *and* the
        # copy: without it a concurrent remove() can move the partly-copied
        # directory to the trash mid-copy, leaving a husk that doctor() still
        # calls healthy (STORE-2).  The copy itself goes to a staging sibling
        # and is renamed into place, so the destination never appears
        # half-populated.  The lock key is derived from the same path create/
        # edit/remove use; it is resolved before the directory exists, so it
        # must be computed here rather than inside the helper.
        lock = _mutation_lock(_index_lock_path(self.skills_dir))
        lock.acquire()
        try:
            return self._add_unlocked(source, chosen)
        finally:
            lock.release()

    def _add_unlocked(self, source: Path, chosen: str) -> dict:
        """Copy a validated *source* skill directory into place."""
        skill_dir = _safe_skill_path(self.skills_dir, chosen)
        if skill_dir.exists():
            raise StoreError(f"skill '{chosen}' already exists")
        self._init_db()
        stage = _stage_sibling(skill_dir)
        try:
            shutil.copytree(source, stage)
            os.replace(stage, skill_dir)
        except OSError as exc:
            shutil.rmtree(stage, ignore_errors=True)
            raise StoreError(f"could not install skill '{chosen}': {exc}") from exc
        self._upsert_entry(chosen)
        conn = self._connect()
        try:
            self._commit_history(conn, chosen, "add")
        finally:
            conn.close()
        return {"name": chosen, "path": str(skill_dir)}

    def edit(
        self,
        name: str,
        description: str | None = None,
        license: str | None = None,
        category: str | None = None,
        compatibility: str | None = None,
        version: str | None = None,
        allowed_tools: str | None = None,
        metadata_extra: dict | None = None,
        body: str | None = None,
    ) -> dict:
        skill_dir = _safe_skill_path(self.skills_dir, name)
        with _skill_and_index_locks(self.skills_dir, skill_dir):
            return self._edit_unlocked(
                name,
                description=description,
                license=license,
                category=category,
                compatibility=compatibility,
                version=version,
                allowed_tools=allowed_tools,
                metadata_extra=metadata_extra,
                body=body,
            )

    def _edit_unlocked(
        self,
        name: str,
        description: str | None = None,
        license: str | None = None,
        category: str | None = None,
        compatibility: str | None = None,
        version: str | None = None,
        allowed_tools: str | None = None,
        metadata_extra: dict | None = None,
        body: str | None = None,
    ) -> dict:
        """Apply partial updates to a skill, preserving unknown frontmatter keys."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        if not skill_dir.is_dir():
            raise SkillNotFound(f"skill '{name}' is not installed")
        md_file = skill_dir / "SKILL.md"
        if not md_file.is_file():
            if (skill_dir / "SKILL.md.disabled").is_file():
                raise StoreError(f"skill '{name}' is disabled; enable it first")
            raise SkillNotFound(f"skill '{name}' has no SKILL.md")
        from .loader import read_skill_text_strict

        text = read_skill_text_strict(md_file, subject=f"skill '{name}'")
        try:
            data, original_body = parse_frontmatter(text)
        except FrontmatterError as exc:
            # CLI-2 / SCOPE-12: treating an unparseable document as "no
            # frontmatter" made the rewrite re-emit the corrupt document as the
            # *body* and dump a fresh frontmatter block above it -- four '---'
            # fences and no 'name', with exit 0.  Fail closed, mirroring the
            # undecodable-document policy.
            raise StoreError(
                f"cannot safely edit skill '{name}': its frontmatter is "
                f"malformed ({exc}); repair it by hand first"
            ) from exc
        original_keys = list(data.keys())

        changed = False
        if description is not None:
            description = description.strip()
            if not description:
                raise StoreError("description cannot be empty")
            if len(description) > MAX_DESCRIPTION:
                raise StoreError(f"description exceeds {MAX_DESCRIPTION} characters")
            if data.get("description") != description:
                data["description"] = description
                changed = True
        if license is not None and data.get("license") != license:
            data["license"] = license
            changed = True
        if compatibility is not None:
            if len(compatibility) > MAX_COMPATIBILITY:
                raise StoreError(
                    f"compatibility exceeds {MAX_COMPATIBILITY} characters"
                )
            if data.get("compatibility") != compatibility:
                data["compatibility"] = compatibility
                changed = True
        if version is not None and data.get("version") != version:
            data["version"] = version
            changed = True
        if allowed_tools is not None and data.get("allowed-tools") != allowed_tools.strip():
            data["allowed-tools"] = allowed_tools.strip()
            changed = True
        if category is not None:
            if not isinstance(data.get("metadata"), dict):
                data["metadata"] = {}
            if data["metadata"].get("category") != category:
                data["metadata"]["category"] = category
                changed = True
        if metadata_extra:
            if not isinstance(data.get("metadata"), dict):
                data["metadata"] = {}
            for key, value in metadata_extra.items():
                if data["metadata"].get(key) != value:
                    data["metadata"][key] = value
                    changed = True
        if body is not None:
            if not body.endswith("\n"):
                body += "\n"
            if body != original_body:
                original_body = body
                changed = True

        if changed:
            key_order = original_keys + [k for k in data if k not in original_keys]
            content = dump_frontmatter(data, key_order=key_order) + original_body
            replaced = False
            try:
                write_snapshot(self.data_dir, "global", name, text)
                _atomic_write_text(md_file, content)
                replaced = True
                self._upsert_entry(name)
                conn = self._connect()
                try:
                    self._commit_history(conn, name, "edit")
                finally:
                    conn.close()
            except OSError as exc:
                if replaced:
                    try:
                        _atomic_write_text(md_file, text)
                        self._upsert_entry(name)
                    except Exception as rollback_exc:
                        _diagnose(f"edit rollback failed for {name!r}", rollback_exc)
                raise StoreError(f"could not replace skill '{name}' safely: {exc}") from exc
            except Exception:
                if replaced:
                    try:
                        _atomic_write_text(md_file, text)
                        self._upsert_entry(name)
                    except Exception as rollback_exc:
                        _diagnose(f"edit rollback failed for {name!r}", rollback_exc)
                raise
        return {"name": name, "changed": changed}

    def remove(self, name: str, purge: bool = False) -> dict:
        """Move a skill to the trash, or permanently delete it with ``purge``."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        # Whole-directory moves must serialize with create/edit/restore which
        # lock the same per-skill path; otherwise a concurrent writer can
        # strand its temp file inside a trash copy (see atomic_io). A bare
        # try/finally (no handlers) keeps the complexity ratchet flat.
        return _with_index_lock(
            self.skills_dir, self._remove_unlocked, name, purge=purge
        )

    def _remove_unlocked(self, name: str, purge: bool = False) -> dict:
        """Move a skill to the trash, or permanently delete it with ``purge``."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        if not skill_dir.is_dir():
            # A row may still record a trashed copy; removing it again would
            # be a silent no-op claiming success, so fail honestly.  Trash
            # copies are managed through restore()/purge_trash().
            raise SkillNotFound(f"skill '{name}' is not installed")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT status FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if purge:
                self._purge_skill(skill_dir, name)
                conn.execute("DELETE FROM skills WHERE name = ?", (name,))
                self._history(conn, name, "purge")
                result = {"name": name, "action": "purged"}
            else:
                self.trash_dir.mkdir(parents=True, exist_ok=True)
                target = paths.contained_path(
                    self.trash_dir, f"{name}-{_trash_timestamp()}"
                )
                counter = 1
                while target.exists():
                    target = paths.contained_path(
                        self.trash_dir, f"{name}-{_trash_timestamp()}-{counter}"
                    )
                    counter += 1
                shutil.move(str(skill_dir), str(target))
                conn.execute(
                    "UPDATE skills SET status = 'trashed', updated_at = ? "
                    "WHERE name = ?",
                    (now_iso(), name),
                )
                self._history(conn, name, "trash")
                result = {"name": name, "action": "trashed", "trash_path": str(target)}
            conn.commit()
            return result
        finally:
            conn.close()

    def _purge_skill(self, skill_dir: Path, name: str) -> None:
        """Permanently delete one skill tree and report a clean failure.

        ``shutil.rmtree`` used to run in place (STORE-7): a part-way failure
        (unwritable subdirectory, NFS, ENOTEMPTY) escaped as a raw
        ``PermissionError`` *after* ``SKILL.md`` had already been unlinked, so
        the skill stayed listed ``active``, was served by ``get()`` with its
        stored body, and ``stats()`` counted it -- all while its document was
        gone.  The tree is displaced first, so the two outcomes are honest:
          * the whole tree is gone, or
          * the skill is *not* advertised: either it is untouched (nothing was
            deleted) or its destroyed husk is parked out of the skills tree and
            its index row is dropped.
        """
        if not skill_dir.is_dir():
            return
        stage = _stage_sibling(skill_dir)
        try:
            os.replace(skill_dir, stage)
        except OSError as exc:
            raise StoreError(f"could not purge skill '{name}': {exc}") from exc
        try:
            shutil.rmtree(stage)
            return
        except OSError as exc:
            message = f"could not purge skill '{name}': {exc}"
        if _has_skill_document(stage):
            try:
                os.replace(stage, skill_dir)
            except OSError as rollback_exc:
                _diagnose(
                    f"purge rollback failed for {name!r}; the tree is parked at {stage}",
                    rollback_exc,
                )
                raise StoreError(
                    f"{message}; its tree is parked at {stage} and is reported "
                    "by doctor()"
                ) from rollback_exc
            raise StoreError(message)
        # The document is already gone, so the skill cannot be installed
        # any more: drop its index row instead of advertising a husk.  The
        # remnant stays parked under the staging name doctor() reports.
        self._drop_index_row(name)
        raise StoreError(f"{message}; its remaining tree is parked at {stage}")

    def _drop_index_row(self, name: str) -> None:
        """Delete one skill's index row and history entry after a damaged purge."""
        conn = self._connect()
        try:
            with _driver_errors("purge"):
                conn.execute("DELETE FROM skills WHERE name = ?", (name,))
                conn.commit()
        finally:
            conn.close()

    def restore(self, name: str, snapshot: str | None = None) -> dict:
        """Restore from trash, or roll back to a validated snapshot."""
        _safe_skill_path(self.skills_dir, name)
        if snapshot is not None:
            content = read_snapshot(self.data_dir, "global", name, snapshot)
            skill_dir = _safe_skill_path(self.skills_dir, name)
            md_file = skill_dir / "SKILL.md"
            if not md_file.is_file():
                if (skill_dir / "SKILL.md.disabled").is_file():
                    raise StoreError(f"skill '{name}' is disabled; enable it first")
                raise SkillNotFound(f"skill '{name}' has no SKILL.md")
            with _mutation_lock(_index_lock_path(self.skills_dir)):
                from .loader import read_skill_text_strict

                current = read_skill_text_strict(md_file, subject=f"skill '{name}'")
                write_snapshot(self.data_dir, "global", name, current)
                try:
                    _atomic_write_text(md_file, content)
                    self._upsert_entry(name)
                    conn = self._connect()
                    try:
                        self._commit_history(conn, name, f"restore --snapshot {snapshot}")
                    finally:
                        conn.close()
                except Exception:
                    try:
                        _atomic_write_text(md_file, current)
                        self._upsert_entry(name)
                    except Exception as rollback_exc:
                        _diagnose(f"snapshot rollback failed for {name!r}", rollback_exc)
                    raise
            return {"name": name, "snapshot": snapshot}
        skill_dir = _safe_skill_path(self.skills_dir, name)
        # The whole read-then-move sequence runs under the trash lock so a
        # concurrent purge_trash() cannot delete the candidate we picked
        # between listing it and moving it (STORE-5).
        index_lock = _mutation_lock(_index_lock_path(self.skills_dir))
        index_lock.acquire()
        trash_lock = _mutation_lock(_trash_lock_dir(self.trash_dir))
        trash_lock.acquire()
        try:
            candidates = sorted(
                (
                    p
                    for p in self.trash_dir.iterdir()
                    if _trash_entry_name(p) == name
                ),
                key=lambda p: p.stat().st_mtime,
            ) if self.trash_dir.is_dir() else []
            if not candidates:
                raise StoreError(f"no trashed copy of '{name}' found")
            source = candidates[-1]
            # check-then-move body is unchanged in the helper below.
            return _with_skill_lock(skill_dir, self._restore_unlocked, name, skill_dir, source)
        finally:
            trash_lock.release()
            index_lock.release()

    def _restore_unlocked(self, name: str, skill_dir, source) -> dict:
        """Move a validated trash copy back into the skills directory."""
        if skill_dir.exists():
            raise StoreError(
                f"cannot restore '{name}': a skill with that name already exists"
            )
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(source), str(skill_dir))
        except OSError as exc:
            # The copy vanished or is not movable: a clean StoreError, never a
            # raw OSError escaping to callers (REST would answer 500).
            raise StoreError(
                f"cannot restore '{name}' from {source}: {exc}"
            ) from exc
        self._upsert_entry(name)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET status = 'active', updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
            self._commit_history(conn, name, "restore")
        finally:
            conn.close()
        return {"name": name, "restored_from": str(source)}

    def disable(self, name: str) -> dict:
        """Rename SKILL.md to SKILL.md.disabled so validators skip the skill."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        out = _with_index_lock(self.skills_dir, self._disable_unlocked, name)
        return {"name": name, "disabled": out}

    def _disable_unlocked(self, name: str) -> bool:
        """Rename the enabled document to the disabled filename."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        md_file = skill_dir / "SKILL.md"
        if not md_file.is_file():
            if (skill_dir / "SKILL.md.disabled").is_file():
                raise StoreError(f"skill '{name}' is already disabled")
            raise SkillNotFound(f"skill '{name}' is not installed")
        _reject_both_documents(skill_dir, name)
        try:
            md_file.rename(skill_dir / "SKILL.md.disabled")
        except FileNotFoundError:
            # STORE-11: the mutation lock is process-local, so a second process on
            # this data dir (CLI + web UI) can move the document between the
            # checks above and this rename.  Fail cleanly instead of leaking a
            # raw FileNotFoundError that doctor() then cannot explain.
            raise StoreError(
                f"skill '{name}' changed concurrently (another process moved "
                "SKILL.md); retry the disable"
            ) from None
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET disabled = 1, updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
            self._commit_history(conn, name, "disable")
        finally:
            conn.close()
        return True

    def enable(self, name: str) -> dict:
        """Rename SKILL.md.disabled back to SKILL.md."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        out = _with_index_lock(self.skills_dir, self._enable_unlocked, name)
        return {"name": name, "disabled": out}

    def _enable_unlocked(self, name: str) -> bool:
        """Rename the disabled document back to SKILL.md."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        disabled_file = skill_dir / "SKILL.md.disabled"
        if not disabled_file.is_file():
            if (skill_dir / "SKILL.md").is_file():
                raise StoreError(f"skill '{name}' is already enabled")
            raise SkillNotFound(f"skill '{name}' is not installed")
        _reject_both_documents(skill_dir, name)
        try:
            disabled_file.rename(skill_dir / "SKILL.md")
        except FileNotFoundError:
            # See the disable path: a cross-process move must not surface as a
            # raw FileNotFoundError (STORE-11).
            raise StoreError(
                f"skill '{name}' changed concurrently (another process moved "
                "SKILL.md.disabled); retry the enable"
            ) from None
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET disabled = 0, updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
            self._commit_history(conn, name, "enable")
        finally:
            conn.close()
        return False

    def trash_list(self) -> list[dict]:
        """List soft-deleted skills in the trash directory."""
        if not self.trash_dir.is_dir():
            return []
        result = []
        for path in sorted(self.trash_dir.iterdir()):
            name = _trash_entry_name(path)
            if name is None:
                continue
            size = sum(
                f.stat().st_size for f in path.rglob("*") if f.is_file()
            )
            result.append(
                {
                    "name": name,
                    "trash_path": str(path),
                    "size_bytes": size,
                    "modified": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
        return sorted(result, key=lambda r: r["name"])

    def purge_trash(self) -> dict:
        """Permanently delete everything in the trash.

        Every ``rmtree`` runs *before* the index transaction opens (STORE-6):
        holding one write transaction across the file deletions made every
        concurrent writer wait out sqlite3's busy timeout and then fail with a
        raw ``sqlite3.OperationalError``, because the transaction stayed open
        for as long as the slowest directory removal took.
        """
        if not self.trash_dir.is_dir():
            return {"purged": []}
        with _mutation_lock(_trash_lock_dir(self.trash_dir)):
            purged = self._purge_trash_files()
            self._drop_trash_rows(purged)
        return {"purged": purged}

    def _purge_trash_files(self) -> list[str]:
        """Delete every validated trash entry, deduping repeated skill names."""
        purged: list[str] = []
        for path, name in _trash_prune_candidates(self.trash_dir):
            self._purge_entry(path, name)
            if name not in purged:
                purged.append(name)
        return purged

    def _drop_trash_rows(self, purged: list[str]) -> None:
        """Delete the index rows of the trash entries that were just removed."""
        if not purged:
            return
        conn = self._connect()
        try:
            with _driver_errors("purge"):
                self._trash_delete_rows(conn, purged)
                conn.commit()
        finally:
            conn.close()

    def _purge_entry(self, path: Path, name: str) -> None:
        """Remove one validated trash entry from the filesystem.

        Raises a clean :class:`StoreError` instead of a raw ``OSError``, and
        leaves the entry's index row untouched: rows are only deleted once the
        whole trash has been removed, so a failed purge never leaves a skill
        listed that has no copy anywhere.
        """
        try:
            shutil.rmtree(path)
        except OSError as exc:
            raise StoreError(f"could not purge trash: {exc}") from exc

    def _trash_delete_rows(self, conn, names: list[str]) -> None:
        """Delete the index rows and write the history for purged entries."""
        for name in names:
            conn.execute(
                "DELETE FROM skills WHERE name = ? AND status = 'trashed'",
                (name,),
            )
            self._history(conn, name, "purge")

    def stats(self) -> dict:
        """Return counts, sizes and a category breakdown.

        Counts come from the filesystem (STORE-10): a row with no directory is
        index residue, not an installed skill, and used to be counted ``active``
        while ``list()`` advertised it and ``get()`` served its stored body.
        """
        self._init_db()
        on_disk = self._skill_names_on_disk()
        conn = self._connect()
        try:
            listed = [
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM skills WHERE status = 'active'"
                ).fetchall()
            ]
            total = conn.execute("SELECT COUNT(*) AS c FROM skills").fetchone()["c"]
            trashed = conn.execute(
                "SELECT COUNT(*) AS c FROM skills WHERE status = 'trashed'"
            ).fetchone()["c"]
            live = [name for name in listed if name in on_disk]
            disabled, categories = _live_index_totals(conn, live)
        finally:
            conn.close()
        db_bytes = self.db_path.stat().st_size if self.db_path.is_file() else 0
        return {
            "total": total,
            "active": len(live),
            "disabled": disabled,
            "trashed": trashed,
            "db_rows": total,
            "size_bytes": _skills_tree_size(self.skills_dir),
            "db_bytes": db_bytes,
            "categories": categories,
        }

    # ------------------------------------------------------ export/import

    def export(self, dest: str | Path | None = None, full: bool = False) -> Path:
        """Package skills, optionally including trash and templates.

        Atomicity and naming (STORE-8): the archive is streamed into a sibling
        temp file and moved into place only once it is complete, so a failure
        can never leave a truncated, manifest-less archive occupying the path
        of a good one; and a default name is made unique with a ``-<n>``
        counter, because ``export()`` and ``backup()`` share a one-second
        timestamp and used to silently overwrite each other.
        """
        self._init_db()
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        stem = "full-export" if full else "export"
        if dest is None:
            dest = _unique_dest(self.backups_dir, f"{stem}-{_trash_timestamp()}", ".tar.gz")
        else:
            dest = Path(dest).expanduser()
            dest.parent.mkdir(parents=True, exist_ok=True)
        entries = self._scan_dir(self.skills_dir)
        manifest = {
            "app": "skills-mgr",
            "version": __version__,
            "created": now_iso(),
            "full": bool(full),
            "skills": [
                {
                    "name": e["name"],
                    "description": e["description"],
                    "license": e["license"],
                    "version": e["version"],
                    "category": e["category"],
                    "content_hash": _tree_content_hash(
                        _safe_skill_path(self.skills_dir, e["name"])
                    ),
                }
                for e in entries
            ],
        }
        trash_names: list[str] = []
        template_names: list[str] = []
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{dest.name}.", suffix=".skillsmgr-export", dir=dest.parent
        )
        os.close(handle)
        temp_dest = Path(temp_name)
        try:
            with tarfile.open(temp_dest, "w:gz") as tar:
                for entry in entries:
                    source = _safe_skill_path(self.skills_dir, entry["name"])
                    for file in _archive_members(source):
                        tar.add(
                            file,
                            arcname=f"skills/{entry['name']}/{file.relative_to(source)}",
                        )
                if full:
                    if self.trash_dir.is_dir():
                        for trashed in sorted(self.trash_dir.iterdir()):
                            if not trashed.is_dir() or _trash_entry_name(trashed) is None:
                                continue
                            trash_names.append(trashed.name)
                            for file in _archive_members(trashed):
                                tar.add(
                                    file,
                                    arcname=f"trash/{trashed.name}/{file.relative_to(trashed)}",
                                )
                    if self.templates_dir.is_dir():
                        for template in sorted(self.templates_dir.glob("*.md")):
                            if template.is_file():
                                template_names.append(template.name)
                                tar.add(template, arcname=f"templates/{template.name}")
                    manifest["trash"] = trash_names
                    manifest["templates"] = template_names
                payload = json.dumps(manifest, indent=2).encode("utf-8")
                import io

                info = tarfile.TarInfo("manifest.json")
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            os.replace(temp_dest, dest)
            _sync_parent_directory(dest.parent)
        except BaseException:
            temp_dest.unlink(missing_ok=True)
            raise
        return dest

    def backup(self, dest: str | Path | None = None, full: bool = False) -> Path:
        """Alias of :meth:`export` for backup semantics."""
        return self.export(dest=dest, full=full)

    def import_(self, archive: str | Path, force: bool = False, full: bool = False) -> dict:
        """Install skills and optionally restore full-library data."""
        archive = Path(archive).expanduser()
        if not archive.is_file():
            raise StoreError(f"archive not found: {archive}")
        self._init_db()
        tmp = Path(tempfile.mkdtemp(prefix="skillsmgr-import-"))
        imported: list[str] = []
        skipped: list[str] = []
        try:
            try:
                _extract_import_archive(archive, tmp)
            except (tarfile.TarError, zipfile.BadZipFile, EOFError, zlib.error, gzip.BadGzipFile, NotImplementedError, UnicodeError) as exc:
                # Truncated gzip/tar streams surface as EOFError, zlib.error,
                # or gzip.BadGzipFile rather than tarfile.TarError; every
                # malformed archive must fail as a clean StoreError, never as
                # a raw decompressor exception.
                raise StoreError(f"invalid archive: {exc}") from exc
            manifest_path = tmp / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise StoreError(f"invalid archive manifest: {exc}") from exc
            skills = _validate_archive_manifest(manifest)
            if full and not manifest.get("full"):
                raise StoreError("archive is not a full export; re-export with --full")
            full_entries = _plan_full_restore(self, tmp, manifest) if full else []
            planned: list[tuple[str, Path, dict]] = []
            planned_names: set[str] = set()
            for entry in skills:
                name = entry["name"]
                if name in planned_names:
                    raise StoreError(f"duplicate skill in archive manifest: {name!r}")
                planned_names.add(name)
                source = tmp / "skills" / name
                if not source.is_dir():
                    raise StoreError(f"archive manifest skill path is missing: {name!r}")
                if not _has_skill_document(source):
                    raise StoreError(f"archive manifest skill has no SKILL.md: {name!r}")
                _validate_imported_skill(source, name)
                _safe_skill_path(self.skills_dir, name)
                planned.append((name, source, entry))

            if not skills and (tmp / "skills").is_dir():
                for source in sorted((tmp / "skills").iterdir()):
                    if not source.is_dir():
                        continue
                    try:
                        name = validate_skill_name(source.name)
                    except ValueError:
                        skipped.append(source.name)
                        continue
                    if name in planned_names:
                        raise StoreError(f"duplicate skill in archive: {name!r}")
                    planned_names.add(name)
                    if not _has_skill_document(source):
                        skipped.append(source.name)
                        continue
                    _validate_imported_skill(source, name)
                    _safe_skill_path(self.skills_dir, name)
                    planned.append((name, source, {"name": name})
                    )

            if skills and (tmp / "skills").is_dir():
                unexpected = sorted(
                    p.name for p in (tmp / "skills").iterdir()
                    if p.is_dir() and p.name not in planned_names
                )
                if unexpected:
                    raise StoreError(
                        f"archive contains skills missing from manifest: {unexpected[0]!r}"
                    )

            # All archive and content validation is complete before this first
            # destination deletion/copy, so force cannot partially apply an
            # archive that fails later preflight checks.
            for name, source, entry in planned:
                dest = _safe_skill_path(self.skills_dir, name)
                if dest.exists():
                    if not force:
                        skipped.append(name)
                        continue
                stage_root = tmp / "commit-staging"
                stage_root.mkdir(parents=True, exist_ok=True)
                try:
                    # The destination's per-skill lock is the same lock create/
                    # edit/remove take.  Without it a force-import could
                    # displace-and-replace a document while a concurrent edit()
                    # was mid-write, silently discarding a committed edit that
                    # still held the lock (STORE-4).
                    committed, reason = _with_skill_lock(
                        dest,
                        _archive.commit_staged_skill,
                        source,
                        dest,
                        stage_root,
                        entry.get("content_hash"),
                        upsert=self._upsert_entry,
                    )
                except Exception as exc:
                    committed, reason = False, str(exc)
                if committed:
                    imported.append(name)
                else:
                    skipped.append(f"{name}: {reason}")
            conn = self._connect()
            try:
                for name in imported:
                    self._commit_history(conn, name, "import")
            finally:
                conn.close()
            restored_trash: list[str] = []
            restored_templates: list[str] = []
            skipped_full: list[str] = []
            if full:
                try:
                    restored_trash, restored_templates, skipped_full = _archive.restore_full_payload(
                        full_entries, replace=force
                    )
                except _archive.ArchiveError as exc:
                    raise StoreError(str(exc)) from exc
                _record_restored_trash(self, restored_trash)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        result = {
            "imported": imported,
            "skipped": skipped,
            "source": archive.name,
            "created": now_iso(),
        }
        if full:
            result["restored_trash"] = restored_trash
            result["restored_templates"] = restored_templates
            result["skipped_full"] = skipped_full
        return result

    # -------------------------------------------------------------- misc

    def history(self, name: str | None = None, limit: int = 50) -> list[dict]:
        """Return recent history rows, newest first."""
        self._init_db()
        conn = self._connect()
        try:
            if name:
                rows = conn.execute(
                    "SELECT id, name, action, at FROM history WHERE name = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name, action, at FROM history ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def doctor(self) -> dict:
        """Audit consistency between the filesystem tree and the database."""
        self._init_db()
        scanned = {e["name"]: e for e in self._scan_dir(self.skills_dir)}
        conn = self._connect()
        try:
            db_rows = conn.execute("SELECT COUNT(*) AS c FROM skills").fetchone()["c"]
            active_rows = {
                r["name"]: dict(r)
                for r in conn.execute(
                    "SELECT name, description, body, category, license, version, disabled "
                    "FROM skills WHERE status = 'active'"
                ).fetchall()
            }
            active_names = set(active_rows)
            trashed_names = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM skills WHERE status = 'trashed'"
                ).fetchall()
            }
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        orphan_dirs = sorted(set(scanned) - active_names)
        stale_rows = sorted(active_names - set(scanned))
        # Documents that are not valid UTF-8 are reported as their own drift
        # class (issue #13): the loader keeps the row readable with replacement
        # characters, so it can match the index byte-for-replacement and would
        # otherwise be invisible to the body comparison below.
        undecodable_documents = sorted(
            name for name, entry in scanned.items() if entry.get("decode_error")
        )
        # Directories holding both SKILL.md and SKILL.md.disabled are a real
        # defect, not cosmetic drift: the next toggle destroys one document,
        # and no automatic repair can choose which one the user meant.  Report
        # them so ``ok`` is False and thereby observable.
        conflicting_documents = sorted(
            name for name, entry in scanned.items() if entry.get("document_conflict")
        )
        filesystem_index_drift = sorted(
            name
            for name in set(scanned) & active_names
            if any(
                scanned[name].get(key) != active_rows[name].get(key)
                for key in ("description", "body", "category", "license", "version", "disabled")
            )
        )
        artifacts = _doctor_artifacts(self.data_dir, self.trash_dir, self.templates_dir)
        transaction_artifacts = artifacts["transaction_artifacts"]
        temporary_files = artifacts["temporary_files"]
        stale_snapshots = artifacts["stale_snapshots"]
        trash_count = artifacts["trash_count"]
        templates_count = artifacts["templates_count"]
        ok = (
            integrity == "ok"
            and not orphan_dirs
            and not stale_rows
            and not filesystem_index_drift
            and not undecodable_documents
            and not conflicting_documents
            and not transaction_artifacts
            and not temporary_files
            and not stale_snapshots
            and not (trashed_names - artifacts["trash_names"])
        )
        return {
            "data_dir": str(self.data_dir),
            "dirs": {
                "skills": str(self.skills_dir),
                "trash": str(self.trash_dir),
                "templates": str(self.templates_dir),
                "backups": str(self.backups_dir),
                "db": str(self.db_path),
            },
            "db_integrity": integrity,
            "skills_on_disk": len(scanned),
            "db_rows": db_rows,
            "orphan_dirs": orphan_dirs,
            "stale_rows": stale_rows,
            "filesystem_index_drift": filesystem_index_drift,
            "undecodable_documents": undecodable_documents,
            "conflicting_documents": conflicting_documents,
            "transaction_artifacts": transaction_artifacts,
            "temporary_files": temporary_files,
            "incomplete_transactions": transaction_artifacts,
            "stale_snapshots": stale_snapshots,
            "trash_count": trash_count,
            "templates_count": templates_count,
            "ok": ok,
        }

    def db_rebuild(self) -> dict:
        """Delete the database and rebuild it entirely from the tree.

        Runs under the skills-directory lock (STORE-12) so the index is never
        unlinked while a mutation is mid-flight, and so the rebuild cannot
        observe a half-applied skill.
        """
        return _with_scan_lock(self.skills_dir, self._rebuild_index_locked)

    def _rebuild_index_locked(self) -> dict:
        for path in (
            self.db_path,
            Path(f"{self.db_path}-journal"),
            Path(f"{self.db_path}-wal"),
            Path(f"{self.db_path}-shm"),
        ):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
        return self._resync_locked()
