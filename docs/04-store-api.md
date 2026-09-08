# Store API — Skills Manager

**Version 0.1.0**

**AI manifest**: The `Store` class is the single gateway between the CLI/GUI and skill data (filesystem + SQLite index). Facts verified against `store.py` on 2026-08-13. The GUI MUST use only this API — never touch files or the DB directly. Run `python3 smoke_store.py` after any change to `store.py`.

## Invariants

**[SPEC]**

- The filesystem is the source of truth. SQLite is a rebuildable index only (`SCHEMA_VERSION = "1"`, store.py:26). Never trust the DB over the FS.
- Never hand-edit the DB; use `db rebuild`/`db resync` to repair drift.
- All errors are raised as exceptions — callers surface them as clean dialogs/messages, never tracebacks.
- Every filesystem operation derived from a skill name first uses the canonical
  `validate_skill_name()` rule and the resolved `contained_path()` guard. A name
  that is invalid, absolute, parent-traversing, or reaches outside a managed
  root raises `StoreError` before the filesystem is mutated.

## Exceptions

- `StoreError` (store.py:57) — generic store failure (duplicate, invalid state, I/O).
- `SkillNotFound` (store.py:61, subclasses `StoreError`) — skill absent or unavailable (e.g. disabled).
- `FrontmatterError` — malformed SKILL.md frontmatter (from `frontmatter.py`).

## Constructor

`Store(data_dir: Path | None = None)` (store.py:92) — resolves `<data>/skills-manager` (see @docs/01-architecture.md), creates layout, inits DB.

## Public methods

**[SPEC]** Signatures and semantics verified from source.

- `create(self, name, description, *, license=None, category=None, compatibility=None, version=None, allowed_tools=None, metadata_extra=None, body=None) -> dict` — name must match `NAME_RE`, ≤ `MAX_NAME` (64); description required, non-empty, ≤ `MAX_DESCRIPTION` (1024); compatibility ≤ `MAX_COMPATIBILITY` (500). Duplicate name or existing dir → `StoreError`. Returns skill dict.
- `edit(self, name, description=None, license=None, category=None, compatibility=None, version=None, allowed_tools=None, metadata_extra=None, body=None) -> dict` — partial update; unknown frontmatter keys are preserved. `SkillNotFound` if not installed or no SKILL.md; `StoreError` if disabled. Returns updated skill dict.
- `list(self, include_disabled=False) -> list[dict]`
- `get(self, name) -> dict` — raises `SkillNotFound` if absent.
- `search(self, pattern, limit=None) -> list[(name, description, score)]` — scoring per @docs/02-modules.md.
- `add(self, path, name=None) -> dict` — import an existing SKILL.md file.
- `remove(self, name, purge=False) -> dict` — trash by default; `purge=True` deletes permanently.
- `restore(self, name) -> dict` — from trash.
- `disable(self, name) -> dict` / `enable(self, name) -> dict` — rename `SKILL.md` <-> `SKILL.md.disabled`; trashed skills may be disallowed until restored.
- `trash_list(self) -> list[dict]` / `purge_trash(self) -> dict`
- `stats(self) -> dict` — counts and summary.
- `export(self, dest=None) -> dict` / `backup(self, dest=None) -> dict` — archive to `backups/` by default.
- `import_(self, archive, force=False) -> dict` — `StoreError` if archive missing; `tempfile.mkdtemp(prefix="skillsmgr-import-")`; returns `{imported: [...], skipped: [...]}`.
- `history(self, name=None, limit=50) -> list[dict]`
- `doctor(self) -> dict` — health check; lists FS/DB inconsistencies.
- `db_rebuild(self)` / `db_resync(self)` — rebuild: drop + re-create index from FS; resync: sync without dropping. FS untouched.

## SQLite schema (index only)

**[SPEC]** `_SCHEMA` (store.py ~28-53):

```sql
CREATE TABLE IF NOT EXISTS skills (
  name TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'active',
  description TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'uncategorized',
  license TEXT,
  version TEXT,
  disabled INTEGER NOT NULL DEFAULT 0,
  added_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  action TEXT NOT NULL,
  at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
```

**[NOTE]** Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ` (`now_iso()`). Trash-named files match `_TRASH_TS_RE` = `-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d+)?Z?$` (suffix on trashed skill names). `_connect()` uses `sqlite3.Row` + `PRAGMA foreign_keys = ON`.

## Internal helpers (private)

**[NOTE]** `_init_db()`, `_history(action)`, `_load_skill(path)`, `_upsert_entry(name, ...)`, `_scan_dir()`, and the private path-guard adapter are used by public methods; they are not part of the API contract. Approximate line references should be regenerated when source moves.

## Open questions

- `[?]` None currently.
