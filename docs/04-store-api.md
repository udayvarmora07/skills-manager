# Store API — Skills Manager

**Version 0.2.1**

**AI manifest**: The `Store` class is the single gateway between the CLI/web UI and global skill data (filesystem + SQLite index). Facts verified against `store.py` on September 11, 2026 (source citations are symbol names, not line numbers — the line numbers here had drifted onto unrelated code). The UI MUST use public Store/scopes behavior — never hand-edit files or the DB. Run `python3 smoke_store.py` after any change to `store.py`.

## Invariants

**[SPEC]**

- The filesystem is the source of truth. SQLite is a rebuildable index only (`SCHEMA_VERSION = "1"`, the module constant in `store.py`). Never trust the DB over the FS.
- Never hand-edit the DB; use `db rebuild`/`db resync` to repair drift.
- All errors are raised as exceptions — callers surface them as clean dialogs/messages, never tracebacks.
- Every filesystem operation derived from a skill name first uses the canonical
  `validate_skill_name()` rule and the resolved `contained_path()` guard. A name
  that is invalid, absolute, parent-traversing, or reaches outside a managed
  root raises `StoreError` before the filesystem is mutated.

## Exceptions

- `StoreError` (the module-level class in `store.py`) — generic store failure (duplicate, invalid state, I/O).
- `SkillNotFound` (subclasses `StoreError`) — skill absent or unavailable (e.g. disabled).
- `FrontmatterError` — malformed SKILL.md frontmatter (from `frontmatter.py`).

## Constructor

`Store(data_dir: Path | None = None)` — resolves `<data>/skills-manager` (see @docs/01-architecture.md) and assigns the layout paths.  **It does not create the layout or initialise the DB** (STORE-14): every public entry point calls `_init_db()` itself, so the first use of any method bootstraps the schema.  Call `init_db()` explicitly when an empty data directory must exist before the first call.

## Public methods

**[SPEC]** Signatures and semantics verified from source.

- `create(self, name, description, *, license=None, category=None, compatibility=None, version=None, allowed_tools=None, metadata_extra=None, body=None) -> dict` — name must match `NAME_RE`, ≤ `MAX_NAME` (64); description required, non-empty, ≤ `MAX_DESCRIPTION` (1024); compatibility ≤ `MAX_COMPATIBILITY` (500). Duplicate name or existing dir → `StoreError`. Returns `{"name", "path"}` — **not** the full skill record (STORE-14).
- `edit(self, name, description=None, license=None, category=None, compatibility=None, version=None, allowed_tools=None, metadata_extra=None, body=None) -> dict` — partial update; unknown frontmatter keys are preserved. `SkillNotFound` if not installed or no SKILL.md; `StoreError` if disabled, or if the document's frontmatter is unparseable (CLI-2/SCOPE-12). Returns `{"name", "changed"}` — **not** the full skill record (STORE-14).
- `list(self) -> list[dict]` — returns active rows, including disabled ones, annotated with `disabled`; there is **no** `include_disabled` parameter (STORE-14).
- `get(self, name) -> dict` — raises `SkillNotFound` if absent. Returned records
  include derived, non-persisted observations: portable/extension frontmatter
  partitions, content and metadata hashes, observed timestamp, and provenance.
- `search(self, term) -> list[dict]` — searches name, description, body, and category through the bounded wildcard scorer described in @docs/02-modules.md; invalid query complexity raises `ValueError`. Scope adapters use the public `list()`/`get()` seams when they need body-aware ranking. CLI global and merged searches pass their requested Store through that adapter, so `--data-dir` remains authoritative.
- `add(self, src, name=None) -> dict` — install an existing skill directory (or SKILL.md file) from `src`; `name` overrides the destination name.
- `remove(self, name, purge=False) -> dict` — trash by default; `purge=True` deletes permanently.
- `restore(self, name, snapshot=None) -> dict` — from trash, or from a validated
  snapshot under `<data>/snapshots/global/<name>/`; the current content is saved
  first when rolling back.
- `disable(self, name) -> dict` / `enable(self, name) -> dict` — rename `SKILL.md` <-> `SKILL.md.disabled`; trashed skills may be disallowed until restored.
- `trash_list(self) -> list[dict]` / `purge_trash(self) -> dict` — only exact
  canonical skill names with valid timestamp suffixes are recognized in trash;
  malformed, symlinked, and prefix-collision directories are ignored. `purged`
  lists each purged skill once even when several timestamped copies existed.
- `stats(self) -> dict` — counts and summary.
- `export(self, dest=None, full=False) -> Path` / `backup(self, dest=None, full=False) -> Path` — slim skills-only archive by default; `full=True` adds validated trash and templates.
- Export manifests include a SHA-256 content hash for each skill tree; imports verify hashes in staging and after commit when present. Hashes are verification metadata, not SQLite state.
- `import_(self, archive, force=False, full=False) -> dict` — imports `.tar.gz`/`.tgz`/`.tar`
  and ZIP content (sniffed by content, not only filename). Resource-budget
  violations, unsafe traversal/Windows/special members, unsupported manifest
  versions/names/paths, and invalid extracted documents raise `StoreError`.
  ZIP members are manually extracted to contained paths and symlink-bit entries
  are rejected. Each skill is staged independently before replacement;
  successful names appear in `imported`, failures/already-present names in
  `skipped`, and failed replacements restore the previous destination. A failed
  staging copy leaves the existing skill directory untouched.
- `full=True` requires a boolean `full` flag and plain-name `trash`/`templates`
  entries; every payload is validated before any mutation, then installed as one
  all-or-nothing transaction that rolls back on failure and raises
  `StoreError`. Restored trash names are reconciled into the index so `stats()`
  and `doctor()` agree with `trash_list()`. Existing entries are skipped unless
  `force=True`.
- `history(self, name=None, limit=50) -> list[dict]`; snapshot IDs are exposed
  through the module-level `list_snapshots(data_dir, scope, name)` helper and
  the CLI/REST history surfaces.
- Snapshot helpers `write_snapshot`, `list_snapshots`, and `read_snapshot` are
  module-level guarded helpers; snapshots are not SQLite data and are retained
  newest-five per scope/name.
- `doctor(self) -> dict` — health check; lists FS/DB inconsistencies, content drift, incomplete transaction artifacts, temporary files, stale snapshots, and repair guidance via `db resync`.
- `resync(self) -> dict` — re-index from the skills tree **without** dropping the database: it adds new directories, refreshes changed rows, and removes active rows whose directory is gone, returning `{"added", "updated", "removed"}`. No history entries are written (this is an indexing operation), and it takes the library-wide index lock (STORE-12). Note the method is `resync()`, **not** `db_resync()` — the latter does not exist; `db resync` is the *CLI* spelling of this method (STORE-14 follow-up).
- `db_rebuild(self) -> dict` — delete the index file (plus `-journal`/`-wal`/`-shm`) and rebuild it entirely from the tree, returning `{"added", "updated", "removed"}`. Also runs under the library-wide index lock.
- `init_db(self) -> None` — create the data directories, tables and metadata if missing. Every public entry point calls it itself, so it is only needed when an empty data directory must exist before the first call.

**[SPEC]** Eval harness results are **not** Store data: `skillsmgr/evals.py`
reads `evals/evals.json` from a skill directory and writes run results under
`<data>/evals/<name>-workspace/iteration-N/…` as files. No `Store` method,
SQLite table, or `SCHEMA_VERSION` change was added for it, and a score never
gates an install or an edit. See @docs/ADR-003-registry-bridge-and-eval-harness.md.

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

**[NOTE]** Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ` (`now_iso()`). Trash-named files match `_TRASH_TS_RE` = `-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d+)?Z?(?:-\d+)?$` (suffix on trashed skill names), so a collision counter may follow the `Z` (STORE-14). `_connect()` uses `sqlite3.Row` + `PRAGMA foreign_keys = ON`.

## Internal helpers (private)

**[NOTE]** `_init_db()`, `_history(action)`, `_load_skill(path)`, `_upsert_entry(name, ...)`, `_scan_dir()`, and the private path-guard adapter are used by public methods; they are not part of the API contract. Approximate line references should be regenerated when source moves.

## Open questions

- `[?]` None currently.
