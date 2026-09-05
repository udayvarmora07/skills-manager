"""Persistent store for skills.

The filesystem is the source of truth: each installed skill lives in
``<data>/skills/<name>/SKILL.md`` (or ``SKILL.md.disabled`` while disabled).
SQLite is a rebuildable index over that tree, used for fast listing, search
and history. The database can be regenerated at any time from the on-disk
skills via :meth:`Store.resync` / :meth:`Store.db_rebuild`.
"""

from __future__ import annotations

import json
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
from .frontmatter import dump_frontmatter, parse_frontmatter, FrontmatterError
from .validator import MAX_COMPATIBILITY, MAX_DESCRIPTION, MAX_NAME, NAME_RE

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


class StoreError(Exception):
    """Raised for any store-level failure (validation, I/O, conflicts)."""


class SkillNotFound(StoreError):
    """Raised when an operation targets a skill that does not exist."""


def now_iso() -> str:
    """Return the current UTC time in ``YYYY-MM-DDTHH:MM:SSZ`` form."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trash_timestamp() -> str:
    return now_iso().replace(":", "-").replace("T", "_")


def _coerce_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _strip_trash_suffix(name: str) -> str:
    match = _TRASH_TS_RE.search(name)
    if match:
        return name[: match.start()]
    return name


def _is_zip_archive(path: Path) -> bool:
    """Return True when *path* is a zip (by content, not suffix).

    Uses :func:`zipfile.is_zipfile` rather than a ``PK\\x03\\x04`` magic
    check so empty zips (``PK\\x05\\x06`` end-of-central-directory) are
    also routed to the zip extractor, which reports them cleanly.
    """
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def _safe_join(root: Path, *parts: str) -> Path | None:
    """Join *parts* onto *root*, returning None if the result escapes."""
    candidate = (root.joinpath(*parts)).resolve() if parts else root.resolve()
    try:
        inside = candidate.is_relative_to(root.resolve())
    except AttributeError:  # Python < 3.9 fallback
        inside = str(candidate).startswith(str(root.resolve()) + "/") or candidate == root.resolve()
    return candidate if inside else None


def _extract_tar_guarded(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract *tar* into *dest* without the blanket ``filter="data"`` API.

    Used on Python < 3.12 where ``filter=`` is unavailable: each member is
    validated (no absolute paths, no ``..``, no escaping links) before
    extraction, so the fallback is as safe as the filtered path.
    """
    root = dest.resolve()
    for member in tar.getmembers():
        if member.name.startswith(("/", "\\")) or ".." in Path(member.name).parts:
            raise StoreError(f"unsafe archive member: {member.name!r}")
        target = _safe_join(dest, member.name)
        if target is None:
            raise StoreError(f"unsafe archive member: {member.name!r}")
        if member.issym() or member.islnk():
            link_target = (target.parent / (member.linkname or "")).resolve()
            try:
                inside = link_target.is_relative_to(root)
            except AttributeError:
                inside = str(link_target).startswith(str(root) + "/")
            if not inside:
                raise StoreError(f"unsafe archive link: {member.name!r}")
        tar.extract(member, path=str(dest))


def _extract_zip_guarded(archive: Path, dest: Path) -> None:
    """Extract a zip archive into *dest* with traversal/link guards."""
    try:
        with zipfile.ZipFile(archive) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise StoreError(f"invalid archive: corrupt member {bad!r}")
            for info in zf.infolist():
                name = info.filename
                if not name or name.startswith(("/", "\\")) or ".." in Path(name).parts:
                    raise StoreError(f"unsafe archive member: {name!r}")
                target = _safe_join(dest, *Path(name).parts)
                if target is None:
                    raise StoreError(f"unsafe archive member: {name!r}")
                if name.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    except zipfile.BadZipFile as exc:
        raise StoreError(f"invalid archive: {exc}") from exc
    manifest_path = dest / "manifest.json"
    if manifest_path.is_file():
        return
    # Tolerate GitHub-style zips: hoist a single top-level dir or a bare
    # ``skills/`` tree so the manifest/skills layout below still applies.
    entries = [p for p in dest.iterdir()]
    candidates = [p for p in entries if p.is_dir()]
    for cand in candidates:
        if (cand / "manifest.json").is_file():
            for child in cand.iterdir():
                target = dest / child.name
                if target.exists():
                    continue
                shutil.move(str(child), str(target))
            shutil.rmtree(cand, ignore_errors=True)
            return
    for cand in candidates:
        if (cand / "skills").is_dir():
            src = cand / "skills"
            dst = dest / "skills"
            if not dst.exists():
                shutil.move(str(src), str(dst))
            return


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
        skill_dir = self.skills_dir / name
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
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get(self, name: str) -> dict:
        """Return the full record for a skill, including its body and path."""
        self._init_db()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise SkillNotFound(f"skill '{name}' is not installed")
            result = dict(row)
            skill_dir = self.skills_dir / name
            result["path"] = str(skill_dir) if skill_dir.is_dir() else None
            return result
        finally:
            conn.close()

    def search(self, term: str) -> list[dict]:
        """Case-insensitive search over name, description and body."""
        self._init_db()
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, description, category, license, version, disabled, "
                "updated_at FROM skills WHERE status = 'active' AND "
                "(name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' "
                "OR body LIKE ? ESCAPE '\\') ORDER BY name",
                (pattern, pattern, pattern),
            ).fetchall()
            return [dict(r) for r in rows]
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
        """Create a new skill from validated inputs."""
        name = name.strip()
        if not NAME_RE.fullmatch(name) or len(name) > MAX_NAME:
            raise StoreError(
                f"invalid skill name {name!r}: must match {NAME_RE.pattern} "
                f"(1-{MAX_NAME} chars)"
            )
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
        skill_dir = self.skills_dir / name
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

        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        self._upsert_entry(name)
        conn = self._connect()
        try:
            self._history(conn, name, "create")
            conn.commit()
        finally:
            conn.close()
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
        chosen = (name or source.name).strip()
        if not NAME_RE.fullmatch(chosen) or len(chosen) > MAX_NAME:
            raise StoreError(
                f"invalid skill name {chosen!r}: must match {NAME_RE.pattern} "
                f"(1-{MAX_NAME} chars)"
            )
        try:
            data, _ = parse_frontmatter((source / "SKILL.md").read_text(encoding="utf-8"))
        except FrontmatterError:
            data = {}
        if isinstance(data.get("name"), str) and data["name"] != chosen:
            raise StoreError(
                f"frontmatter name {data['name']!r} does not match target name "
                f"{chosen!r}; rename the skill first"
            )
        skill_dir = self.skills_dir / chosen
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
        """Apply partial updates to a skill, preserving unknown frontmatter keys."""
        skill_dir = self.skills_dir / name
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
            md_file.write_text(content, encoding="utf-8")
            self._upsert_entry(name)
            conn = self._connect()
            try:
                self._history(conn, name, "edit")
                conn.commit()
            finally:
                conn.close()
        return {"name": name, "changed": changed}

    def remove(self, name: str, purge: bool = False) -> dict:
        """Move a skill to the trash, or permanently delete it with ``purge``."""
        skill_dir = self.skills_dir / name
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
                target = self.trash_dir / f"{name}-{_trash_timestamp()}"
                counter = 1
                while target.exists():
                    target = self.trash_dir / f"{name}-{_trash_timestamp()}-{counter}"
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

    def restore(self, name: str) -> dict:
        """Move the newest trashed copy of a skill back into the tree."""
        candidates = sorted(
            (
                p
                for p in self.trash_dir.iterdir()
                if p.is_dir()
                and _strip_trash_suffix(p.name) == name
            ),
            key=lambda p: p.stat().st_mtime,
        ) if self.trash_dir.is_dir() else []
        if not candidates:
            raise StoreError(f"no trashed copy of '{name}' found")
        source = candidates[-1]
        skill_dir = self.skills_dir / name
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
        skill_dir = self.skills_dir / name
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
        skill_dir = self.skills_dir / name
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
            if not path.is_dir():
                continue
            size = sum(
                f.stat().st_size for f in path.rglob("*") if f.is_file()
            )
            result.append(
                {
                    "name": _strip_trash_suffix(path.name),
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
                    if not path.is_dir():
                        continue
                    if _TRASH_TS_RE.search(path.name) is None:
                        continue
                    name = _strip_trash_suffix(path.name)
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

    def export(self, dest: str | Path | None = None) -> Path:
        """Package all installed skills into a gzipped tar archive."""
        self._init_db()
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        if dest is None:
            dest = self.backups_dir / f"export-{_trash_timestamp()}.tar.gz"
        else:
            dest = Path(dest).expanduser()
        entries = self._scan_dir(self.skills_dir)
        manifest = {
            "app": "skills-mgr",
            "version": __version__,
            "created": now_iso(),
            "skills": [
                {
                    "name": e["name"],
                    "description": e["description"],
                    "license": e["license"],
                    "version": e["version"],
                    "category": e["category"],
                }
                for e in entries
            ],
        }
        with tarfile.open(dest, "w:gz") as tar:
            for entry in entries:
                source = self.skills_dir / entry["name"]
                for file in sorted(source.rglob("*")):
                    if file.is_file():
                        tar.add(file, arcname=f"skills/{entry['name']}/{file.relative_to(source)}")
            payload = json.dumps(manifest, indent=2).encode("utf-8")
            import io

            info = tarfile.TarInfo("manifest.json")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        return dest

    def backup(self, dest: str | Path | None = None) -> Path:
        """Alias of :meth:`export` for backup semantics."""
        return self.export(dest=dest)

    def import_(self, archive: str | Path, force: bool = False) -> dict:
        """Install skills from a skills-mgr archive into the tree.

        Accepts ``.tar.gz``/``.tgz``/``.tar`` (as produced by
        :meth:`Store.export`) and ``.zip`` (e.g. a GitHub "Download ZIP"
        of a skills repo whose top level holds ``skills/<name>/`` or
        ``<name>/SKILL.md`` trees).
        """
        archive = Path(archive).expanduser()
        if not archive.is_file():
            raise StoreError(f"archive not found: {archive}")
        self._init_db()
        tmp = Path(tempfile.mkdtemp(prefix="skillsmgr-import-"))
        imported: list[str] = []
        skipped: list[str] = []
        try:
            if _is_zip_archive(archive):
                _extract_zip_guarded(archive, tmp)
            else:
                try:
                    with tarfile.open(archive, "r:*") as tar:
                        names = tar.getnames()
                        if "manifest.json" not in names:
                            raise StoreError(
                                "not a skills-mgr archive (missing manifest.json)"
                            )
                        try:
                            tar.extractall(tmp, filter="data")
                        except TypeError:
                            _extract_tar_guarded(tar, tmp)
                except tarfile.TarError as exc:
                    raise StoreError(f"invalid archive: {exc}") from exc
            manifest_path = tmp / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # Manifest-less archives (e.g. GitHub zips): fall through to
                # the bare ``skills/`` scan below.
                manifest = {}
            skills = manifest.get("skills") or []
            for entry in skills:
                name = entry.get("name") if isinstance(entry, dict) else entry
                if not name or not NAME_RE.fullmatch(str(name)):
                    continue
                source = tmp / "skills" / str(name)
                if not source.is_dir():
                    skipped.append(str(name))
                    continue
                dest = self.skills_dir / str(name)
                if dest.exists():
                    if not force:
                        skipped.append(str(name))
                        continue
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
                self._upsert_entry(str(name))
                imported.append(str(name))
            conn = self._connect()
            try:
                for name in imported:
                    self._history(conn, name, "import")
                conn.commit()
            finally:
                conn.close()
            if not skills and (tmp / "skills").is_dir():
                for source in sorted((tmp / "skills").iterdir()):
                    if not source.is_dir():
                        continue
                    dest = self.skills_dir / source.name
                    if dest.exists() and not force:
                        skipped.append(source.name)
                        continue
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(source, dest)
                    self._upsert_entry(source.name)
                    imported.append(source.name)
                conn = self._connect()
                try:
                    for name in imported:
                        self._history(conn, name, "import")
                    conn.commit()
                finally:
                    conn.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return {
            "imported": imported,
            "skipped": skipped,
            "source": archive.name,
            "created": now_iso(),
        }

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
            active_names = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM skills WHERE status = 'active'"
                ).fetchall()
            }
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
        trash_count = (
            len([p for p in self.trash_dir.iterdir() if p.is_dir()])
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
            and not (trashed_names - set(_strip_trash_suffix(p.name) for p in (self.trash_dir.iterdir() if self.trash_dir.is_dir() else ())))
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
            "trash_count": trash_count,
            "templates_count": templates_count,
            "ok": ok,
        }

    def db_rebuild(self) -> dict:
        """Delete the database and rebuild it entirely from the tree."""
        if self.db_path.exists():
            self.db_path.unlink()
        return self.resync()
