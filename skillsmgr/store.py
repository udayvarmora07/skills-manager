"""Persistent store for skills.

The filesystem is the source of truth: each installed skill lives in
``<data>/skills/<name>/SKILL.md`` (or ``SKILL.md.disabled`` while disabled).
SQLite is a rebuildable index over that tree, used for fast listing, search
and history. The database can be regenerated at any time from the on-disk
skills via :meth:`Store.resync` / :meth:`Store.db_rebuild`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import paths
from . import __version__
from .atomic_io import atomic_write_text, mutation_lock, tree_content_hash
from . import archive as _archive
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

_TRASH_TS_RE = re.compile(r"-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d+)?Z?$")

SNAPSHOT_KEEP = 5
_SNAPSHOT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z?(?:-\d+)?$")
_SCOPE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

def _mutation_lock(path: Path):
    return mutation_lock(path)


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


class StoreError(Exception):
    """Raised for any store-level failure (validation, I/O, conflicts)."""


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
    return path.read_text(encoding="utf-8")


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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        for path in (
            self.data_dir,
            self.skills_dir,
            self.trash_dir,
            self.templates_dir,
            self.backups_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()
        finally:
            conn.close()

    def _history(self, conn: sqlite3.Connection, name: str, action: str) -> None:
        conn.execute(
            "INSERT INTO history (name, action, at) VALUES (?, ?, ?)",
            (name, action, now_iso()),
        )

    def _load_skill(self, skill_dir: Path) -> dict:
        from .loader import load_skill as _shared_load

        return _shared_load(skill_dir)

    def _upsert_entry(self, name: str) -> dict:
        skill_dir = _safe_skill_path(self.skills_dir, name)
        if not skill_dir.is_dir():
            raise SkillNotFound(f"skill '{name}' is not installed")
        entry = self._load_skill(skill_dir)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT status, disabled, added_at FROM skills WHERE name = ?", (name,)
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
            else:
                same = (
                    row["disabled"] == entry["disabled"]
                    and (
                        conn.execute(
                            "SELECT description, body, category, license, version "
                            "FROM skills WHERE name = ?",
                            (name,),
                        ).fetchone()
                    )
                    is not None
                )
                if same:
                    current = conn.execute(
                        "SELECT description, body, category, license, version "
                        "FROM skills WHERE name = ?",
                        (name,),
                    ).fetchone()
                    same = (
                        current["description"] == entry["description"]
                        and current["body"] == entry["body"]
                        and current["category"] == entry["category"]
                        and current["license"] == entry["license"]
                        and current["version"] == entry["version"]
                    )
                if not same:
                    conn.execute(
                        "UPDATE skills SET description = ?, body = ?, category = ?, "
                        "license = ?, version = ?, disabled = ?, updated_at = ? "
                        "WHERE name = ?",
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
            conn.commit()
        finally:
            conn.close()
        return entry

    def _scan_dir(self, root: Path) -> list[dict]:
        from .loader import scan_dir as _shared_scan

        return _shared_scan(root)

    # ------------------------------------------------------------- public

    def init_db(self) -> None:
        """Create the data directories, tables and metadata if missing."""
        self._init_db()

    def resync(self) -> dict:
        """Rebuild the index from the skills directory tree.

        Existing rows keep their ``added_at``; rows whose content changed get a
        new ``updated_at``; active rows with no directory on disk are removed.
        No history entries are written (this is an indexing operation).
        """
        self._init_db()
        scanned = {e["name"]: e for e in self._scan_dir(self.skills_dir)}
        conn = self._connect()
        try:
            added, updated, removed = 0, 0, 0
            for name, entry in scanned.items():
                row = conn.execute(
                    "SELECT description, body, category, license, version, disabled "
                    "FROM skills WHERE name = ?",
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
                changed = (
                    row["description"] != entry["description"]
                    or row["body"] != entry["body"]
                    or row["category"] != entry["category"]
                    or row["license"] != entry["license"]
                    or row["version"] != entry["version"]
                    or row["disabled"] != entry["disabled"]
                )
                if changed:
                    conn.execute(
                        "UPDATE skills SET description = ?, body = ?, category = ?, "
                        "license = ?, version = ?, disabled = ?, updated_at = ? "
                        "WHERE name = ?",
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
                    updated += 1
            for row in conn.execute("SELECT name FROM skills WHERE status = 'active'"):
                if row["name"] not in scanned:
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
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, status, description, category, license, version, "
                "disabled, added_at, updated_at FROM skills "
                "WHERE status = 'active' ORDER BY name"
            ).fetchall()
            result = [dict(r) for r in rows]
            from .loader import load_skill

            for record in result:
                skill_dir = _safe_skill_path(self.skills_dir, record["name"])
                try:
                    observed = load_skill(skill_dir)
                except (OSError, SkillNotFound):
                    continue
                for key in (
                    "content_hash",
                    "metadata_hash",
                    "observed_at",
                    "provenance",
                    "portable_frontmatter",
                    "frontmatter_extensions",
                ):
                    if key in observed:
                        record[key] = observed[key]
                if isinstance(record.get("provenance"), dict):
                    record["provenance"]["scope"] = "global"
                    record["provenance"]["consumer"] = "skills-manager"
            return result
        finally:
            conn.close()

    def get(self, name: str) -> dict:
        """Return the full record for a skill, including its body and path."""
        _safe_skill_path(self.skills_dir, name)
        self._init_db()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise SkillNotFound(f"skill '{name}' is not installed")
            result = dict(row)
            skill_dir = _safe_skill_path(self.skills_dir, name)
            result["path"] = str(skill_dir) if skill_dir.is_dir() else None
            if skill_dir.is_dir():
                observed = self._load_skill(skill_dir)
                for key in (
                    "content_hash",
                    "metadata_hash",
                    "observed_at",
                    "provenance",
                    "portable_frontmatter",
                    "frontmatter_extensions",
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
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, description, category, license, version, disabled, "
                "updated_at, body FROM skills WHERE status = 'active' ORDER BY name",
            ).fetchall()
            records = [dict(r) for r in rows]
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
        skill_dir = _safe_skill_path(self.skills_dir, canonical_name)
        with _mutation_lock(skill_dir / "SKILL.md"):
            return self._create_unlocked(
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

        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(skill_dir / "SKILL.md", content)
            self._upsert_entry(name)
            conn = self._connect()
            try:
                self._history(conn, name, "create")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            try:
                conn = self._connect()
                try:
                    conn.execute("DELETE FROM history WHERE name = ? AND action = 'create'", (name,))
                    conn.execute("DELETE FROM skills WHERE name = ?", (name,))
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                pass
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise
        return {"name": name, "path": str(skill_dir)}

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
        if skill_dir.exists():
            raise StoreError(f"skill '{chosen}' already exists")
        self._init_db()
        shutil.copytree(source, skill_dir)
        self._upsert_entry(chosen)
        conn = self._connect()
        try:
            self._history(conn, chosen, "add")
            conn.commit()
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
        with _mutation_lock(skill_dir / "SKILL.md"):
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
        text = md_file.read_text(encoding="utf-8")
        try:
            data, original_body = parse_frontmatter(text)
        except FrontmatterError:
            data, original_body = {}, text
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
                    self._history(conn, name, "edit")
                    conn.commit()
                finally:
                    conn.close()
            except OSError as exc:
                if replaced:
                    try:
                        _atomic_write_text(md_file, text)
                        self._upsert_entry(name)
                    except Exception:
                        pass
                raise StoreError(f"could not replace skill '{name}' safely: {exc}") from exc
            except Exception:
                if replaced:
                    try:
                        _atomic_write_text(md_file, text)
                        self._upsert_entry(name)
                    except Exception:
                        pass
                raise
        return {"name": name, "changed": changed}

    def remove(self, name: str, purge: bool = False) -> dict:
        """Move a skill to the trash, or permanently delete it with ``purge``."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT status FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None and not skill_dir.is_dir():
                raise SkillNotFound(f"skill '{name}' is not installed")
            if purge:
                if skill_dir.is_dir():
                    shutil.rmtree(skill_dir)
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
                if skill_dir.is_dir():
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
            with _mutation_lock(md_file):
                current = md_file.read_text(encoding="utf-8")
                write_snapshot(self.data_dir, "global", name, current)
                try:
                    _atomic_write_text(md_file, content)
                    self._upsert_entry(name)
                    conn = self._connect()
                    try:
                        self._history(conn, name, f"restore --snapshot {snapshot}")
                        conn.commit()
                    finally:
                        conn.close()
                except Exception:
                    try:
                        _atomic_write_text(md_file, current)
                        self._upsert_entry(name)
                    except Exception:
                        pass
                    raise
            return {"name": name, "snapshot": snapshot}
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
        skill_dir = _safe_skill_path(self.skills_dir, name)
        if skill_dir.exists():
            raise StoreError(
                f"cannot restore '{name}': a skill with that name already exists"
            )
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(skill_dir))
        self._upsert_entry(name)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET status = 'active', updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
            self._history(conn, name, "restore")
            conn.commit()
        finally:
            conn.close()
        return {"name": name, "restored_from": str(source)}

    def disable(self, name: str) -> dict:
        """Rename SKILL.md to SKILL.md.disabled so validators skip the skill."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        md_file = skill_dir / "SKILL.md"
        if not md_file.is_file():
            if (skill_dir / "SKILL.md.disabled").is_file():
                raise StoreError(f"skill '{name}' is already disabled")
            raise SkillNotFound(f"skill '{name}' is not installed")
        md_file.rename(skill_dir / "SKILL.md.disabled")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET disabled = 1, updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
            self._history(conn, name, "disable")
            conn.commit()
        finally:
            conn.close()
        return {"name": name, "disabled": True}

    def enable(self, name: str) -> dict:
        """Rename SKILL.md.disabled back to SKILL.md."""
        skill_dir = _safe_skill_path(self.skills_dir, name)
        disabled_file = skill_dir / "SKILL.md.disabled"
        if not disabled_file.is_file():
            if (skill_dir / "SKILL.md").is_file():
                raise StoreError(f"skill '{name}' is already enabled")
            raise SkillNotFound(f"skill '{name}' is not installed")
        disabled_file.rename(skill_dir / "SKILL.md")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET disabled = 0, updated_at = ? WHERE name = ?",
                (now_iso(), name),
            )
            self._history(conn, name, "enable")
            conn.commit()
        finally:
            conn.close()
        return {"name": name, "disabled": False}

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
        """Permanently delete everything in the trash."""
        purged = []
        if self.trash_dir.is_dir():
            conn = self._connect()
            try:
                for path in sorted(self.trash_dir.iterdir()):
                    name = _trash_entry_name(path)
                    if name is None:
                        continue
                    shutil.rmtree(path)
                    conn.execute(
                        "DELETE FROM skills WHERE name = ? AND status = 'trashed'",
                        (name,),
                    )
                    self._history(conn, name, "purge")
                    purged.append(name)
                conn.commit()
            finally:
                conn.close()
        return {"purged": purged}

    def stats(self) -> dict:
        """Return counts, sizes and a category breakdown."""
        self._init_db()
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) AS c FROM skills").fetchone()["c"]
            disabled = conn.execute(
                "SELECT COUNT(*) AS c FROM skills WHERE disabled = 1"
            ).fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) AS c FROM skills WHERE status = 'active'"
            ).fetchone()["c"]
            trashed = conn.execute(
                "SELECT COUNT(*) AS c FROM skills WHERE status = 'trashed'"
            ).fetchone()["c"]
            categories = {
                r["category"]: r["c"]
                for r in conn.execute(
                    "SELECT category, COUNT(*) AS c FROM skills "
                    "WHERE status = 'active' GROUP BY category ORDER BY c DESC, category"
                ).fetchall()
            }
        finally:
            conn.close()
        size_bytes = 0
        if self.skills_dir.is_dir():
            size_bytes = sum(
                f.stat().st_size for f in self.skills_dir.rglob("*") if f.is_file()
            )
        db_bytes = self.db_path.stat().st_size if self.db_path.is_file() else 0
        return {
            "total": total,
            "disabled": disabled,
            "active": active,
            "trashed": trashed,
            "size_bytes": size_bytes,
            "db_bytes": db_bytes,
            "categories": categories,
        }

    # ------------------------------------------------------ export/import

    def export(self, dest: str | Path | None = None, full: bool = False) -> Path:
        """Package skills, optionally including trash and templates."""
        self._init_db()
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        if dest is None:
            stem = "full-export" if full else "export"
            dest = self.backups_dir / f"{stem}-{_trash_timestamp()}.tar.gz"
        else:
            dest = Path(dest).expanduser()
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
        with tarfile.open(dest, "w:gz") as tar:
            for entry in entries:
                source = _safe_skill_path(self.skills_dir, entry["name"])
                for file in sorted(source.rglob("*")):
                    if file.is_file():
                        tar.add(file, arcname=f"skills/{entry['name']}/{file.relative_to(source)}")
            if full:
                if self.trash_dir.is_dir():
                    for trashed in sorted(self.trash_dir.iterdir()):
                        if not trashed.is_dir() or _trash_entry_name(trashed) is None:
                            continue
                        trash_names.append(trashed.name)
                        for file in sorted(trashed.rglob("*")):
                            if file.is_file():
                                tar.add(file, arcname=f"trash/{trashed.name}/{file.relative_to(trashed)}")
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
            if zipfile.is_zipfile(archive):
                raise StoreError("ZIP archives are not supported; use a tar archive")
            try:
                with tarfile.open(archive, "r:*") as tar:
                    members = _validate_archive_members(tar, archive.stat().st_size)
                    _extract_archive_members(tar, tmp, members)
            except tarfile.TarError as exc:
                raise StoreError(f"invalid archive: {exc}") from exc
            manifest_path = tmp / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise StoreError(f"invalid archive manifest: {exc}") from exc
            skills = _validate_archive_manifest(manifest)
            if full and not manifest.get("full"):
                raise StoreError("archive is not a full export; re-export with --full")
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
                    committed, reason = _archive.commit_staged_skill(
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
                    self._history(conn, name, "import")
                conn.commit()
            finally:
                conn.close()
            restored_trash: list[str] = []
            restored_templates: list[str] = []
            skipped_full: list[str] = []
            if full:
                for trash_name in manifest.get("trash") or []:
                    if not isinstance(trash_name, str) or Path(trash_name).name != trash_name:
                        skipped_full.append(f"trash/{trash_name}")
                        continue
                    source = tmp / "trash" / trash_name
                    if not source.is_dir() or _trash_entry_name(source) is None:
                        skipped_full.append(f"trash/{trash_name}")
                        continue
                    dest = paths.contained_path(self.trash_dir, trash_name)
                    if dest.exists() and not force:
                        skipped_full.append(f"trash/{trash_name}")
                        continue
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(source, dest)
                    restored_trash.append(trash_name)
                for template_name in manifest.get("templates") or []:
                    if not isinstance(template_name, str) or Path(template_name).name != template_name or not template_name.endswith(".md"):
                        skipped_full.append(f"templates/{template_name}")
                        continue
                    source = paths.contained_path(tmp / "templates", template_name)
                    if not source.is_file():
                        skipped_full.append(f"templates/{template_name}")
                        continue
                    dest = paths.contained_path(self.templates_dir, template_name)
                    if dest.exists() and not force:
                        skipped_full.append(f"templates/{template_name}")
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, dest)
                    restored_templates.append(template_name)
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
        filesystem_index_drift = sorted(
            name
            for name in set(scanned) & active_names
            if any(
                scanned[name].get(key) != active_rows[name].get(key)
                for key in ("description", "body", "category", "license", "version", "disabled")
            )
        )
        transaction_artifacts = sorted(
            str(path.relative_to(self.data_dir))
            for path in self.data_dir.rglob("*")
            if path.name.endswith((".skillsmgr-stage", ".skillsmgr-backup"))
            or ".skillsmgr-stage." in path.name
            or ".skillsmgr-backup." in path.name
        )
        temporary_files = sorted(
            str(path.relative_to(self.data_dir))
            for path in self.data_dir.rglob("*")
            if ".skillsmgr-tmp" in path.name
            or path.name.endswith((".tmp", ".temp"))
            or path.name in {".skillsmgr-stage", ".skillsmgr-backup"}
            or ".skillsmgr-stage" in path.name
            or ".skillsmgr-backup" in path.name
        )
        snapshots_root = self.data_dir / "snapshots"
        stale_snapshots = sorted(
            str(path.relative_to(self.data_dir))
            for path in snapshots_root.rglob("*")
            if path.is_file()
            and (
                path.suffix != ".md"
                or not _SNAPSHOT_ID_RE.fullmatch(path.stem)
                or len(path.relative_to(snapshots_root).parts) != 3
            )
        ) if snapshots_root.is_dir() else []
        trash_count = (
            len([p for p in self.trash_dir.iterdir() if _trash_entry_name(p)])
            if self.trash_dir.is_dir()
            else 0
        )
        templates_count = (
            len(list(self.templates_dir.glob("*.md")))
            if self.templates_dir.is_dir()
            else 0
        )
        ok = (
            integrity == "ok"
            and not orphan_dirs
            and not stale_rows
            and not filesystem_index_drift
            and not transaction_artifacts
            and not temporary_files
            and not stale_snapshots
            and not (
                trashed_names
                - {
                    name
                    for p in (self.trash_dir.iterdir() if self.trash_dir.is_dir() else ())
                    if (name := _trash_entry_name(p)) is not None
                }
            )
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
            "transaction_artifacts": transaction_artifacts,
            "temporary_files": temporary_files,
            "incomplete_transactions": transaction_artifacts,
            "stale_snapshots": stale_snapshots,
            "trash_count": trash_count,
            "templates_count": templates_count,
            "ok": ok,
        }

    def db_rebuild(self) -> dict:
        """Delete the database and rebuild it entirely from the tree."""
        if self.db_path.exists():
            self.db_path.unlink()
        return self.resync()
