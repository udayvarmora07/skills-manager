# Architecture — Skills Manager

**Version 0.2.0**

**AI manifest**: Current architecture and data-flow facts verified against source on September 8, 2026. The filesystem is the source of truth; SQLite is a rebuildable index; the local web UI is a second front-end over the same Store/scopes layers the CLI uses.

## Repo map

```
skills-manager/
  skillsmgr/
    __init__.py      # __version__ = "1.0.0"
    __main__.py      # entry: python3 -m skillsmgr -> cli.main()
    cli.py           # argparse CLI, prog="skills-mgr"
    store.py         # Store: FS + SQLite index; StoreError, SkillNotFound
    archive.py       # archive preflight, extraction, staged commit policy
    atomic_io.py     # atomic text writes, mutation locks, tree hashes
    observations.py  # non-persisted hashes, provenance, frontmatter partitions
    root_discovery.py# physical-root and observed-scope policy
    paths.py         # data_dir(), db_path(), subdirs, resolved containment helpers
    path_safety.py   # resolved root-containment and canonical skill-path policy
    frontmatter.py   # parse/dump SKILL.md YAML-ish frontmatter
    validator.py     # canonical name/field rules, Issue dataclass
    search.py        # regex search + scoring
    templates.py     # default template + template list/new
    colors.py        # TTY-aware color helpers
  smoke_store.py     # smoke test driving the Store API
  tests/             # stdlib unittest regression suite
  check_docs.py      # machine-checkable docs/source consistency gate
  AGENTS.md          # hot cache (this repo's operating manual)
  docs/              # HADS docs (this tree)
  task.md            # live checklist
```

## Data model

**[SPEC]** The filesystem is the source of truth.

- Skill: `<data>/skills/<name>/SKILL.md`. Disabled: `<data>/skills/<name>/SKILL.md.disabled`.
- SQLite at `<data>/skills-manager/skills-manager.db` is an index only — rebuilt by `db rebuild`/`db resync`; `SCHEMA_VERSION = "1"`. Never hand-edit the DB; never trust SQLite over the filesystem.
- Trash: `<data>/trash/` (removed skills move here). Backups: `<data>/backups/` (timestamped tarballs). Templates: `<data>/templates/*.md`.

## Data-dir resolution

**[SPEC]** `data_dir()` = `$SKILLS_MANAGER_DATA` -> `$XDG_DATA_HOME` -> `~/.local/share`, then appends `skills-manager`. Subdirs: `skills/`, `trash/`, `templates/`, `backups/`, and `snapshots/`; `db_path()` = `data_dir()/skills-manager.db`.

## Data flow

```
CLI (cli.py) ──┐
               ├──> Store/scopes ──> filesystem (source of truth)
Web UI         ─┘          │
                           └──> SQLite index (rebuildable cache)
```

- `Store.list/search/stats` may read the index; mutations (`add/remove/enable/...`) always write the filesystem and update the index in the same operation.
- `resync`/`db_rebuild` re-scan the filesystem and rebuild the index from scratch.

**[SPEC]** Any skill name entering a filesystem operation is validated by the
canonical name rule before path construction. Resolved paths are checked to
remain inside their managed root, including existing symlink targets. This
applies to global Store operations, agent-scope operations, URL-decoded REST
path parameters, and CLI names.

## Root and consumer model

**[NOTE]** The current `Scope` facade is a compatibility layer over physical
roots. `ADR-002-root-consumer-effective-state.md` defines the approval-gated
future vocabulary (`SkillRoot`, `Consumer`, `ConsumerRootBinding`,
`SkillInstance`, and `EffectiveSkill`). Until that model is approved, aggregate
scope listings and sync planning deduplicate resolved physical paths without
adding new public entities or SQLite state. Discovery research is recorded in
@docs/12-agent-root-discovery-2026-09-08.md.

## GUI relationship

**[NOTE]** The GUI is the local web UI (`skillsmgr/webapp.py` + vendored Vue; see @docs/08-web-ui.md). It uses Store/scopes public behavior and surfaces `StoreError`/`SkillNotFound` as clean JSON/UI errors, never raw tracebacks. The GTK proposal remains historical in @docs/05-gui-plan.md.

## Constraints

**[SPEC]** Locked constraints — do not deviate without asking:

1. Filesystem stays the source of truth.
2. SQLite schema/`SCHEMA_VERSION` unchanged.
3. CLI stdlib-only.
4. Web UI: stdlib backend, vendored Vue, no build step, loopback bind by default.
5. No new CLI commands or Store methods without approval (see AGENTS.md judgment boundaries).
