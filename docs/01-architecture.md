# Architecture — Skills Manager

**Version 0.1.0**

**AI manifest**: Where things live and how data flows. The filesystem is the source of truth; SQLite is a rebuildable index; the GUI is a second front-end over the same `Store` layer the CLI uses.

## Repo map

```
skills-manager/
  skillsmgr/
    __init__.py      # __version__ = "1.0.0"
    __main__.py      # entry: python3 -m skillsmgr -> cli.main()
    cli.py           # argparse CLI, prog="skills-mgr"
    store.py         # Store: FS + SQLite index; StoreError, SkillNotFound
    paths.py         # data_dir(), db_path(), subdirs
    frontmatter.py   # parse/dump SKILL.md YAML-ish frontmatter
    validator.py     # name/field rules, Issue dataclass
    search.py        # regex search + scoring
    templates.py     # default template + template list/new
    colors.py        # TTY-aware color helpers
  smoke_store.py     # smoke test driving the Store API
  tests/             # empty — no test files yet
  AGENTS.md          # hot cache (this repo's operating manual)
  docs/              # HADS docs (this tree)
  task.md            # live checklist
```

## Data model

**[SPEC]** The filesystem is the source of truth.

- Skill: `<data>/skills/<name>/SKILL.md`. Disabled: `<data>/skills/<name>/SKILL.md.disabled`.
- SQLite at `<data>/skills-manager/skills.db` is an index only — rebuilt by `db rebuild`/`db resync`; `SCHEMA_VERSION = "1"`. Never hand-edit the DB; never trust SQLite over the filesystem.
- Trash: `<data>/trash/` (removed skills move here). Backups: `<data>/backups/` (timestamped tarballs). Templates: `<data>/templates/*.md`.

## Data-dir resolution

**[SPEC]** `data_dir()` = `$SKILLS_MANAGER_DATA` -> `$XDG_DATA_HOME` -> `~/.local/share`, then appends `skills-manager`. Subdirs: `skills/`, `trash/`, `templates/`, `backups/`; `db_path()` = `data_dir()/skills.db`.

## Data flow

```
CLI (cli.py) ──┐
               ├──> Store (store.py) ──> filesystem (source of truth)
GUI (gui.py) ──┘            │
                            └──> SQLite index (rebuildable cache)
```

- `Store.list/search/stats` may read the index; mutations (`add/remove/enable/...`) always write the filesystem and update the index in the same operation.
- `resync`/`db_rebuild` re-scan the filesystem and rebuild the index from scratch.

## GUI relationship

**[NOTE]** The GUI (GTK4, in progress — see @docs/05-gui-plan.md) is a second front-end on the same `Store` API. It must not bypass `store.py`; error handling mirrors the CLI (clean dialogs for `StoreError`/`SkillNotFound`, never raw tracebacks).

## Constraints

**[SPEC]** Locked constraints — do not deviate without asking:

1. Filesystem stays the source of truth.
2. SQLite schema/`SCHEMA_VERSION` unchanged.
3. CLI stdlib-only.
4. GUI toolkit: GTK4 via PyGObject (GTK3 3.24 only as fallback).
5. No new CLI commands or Store methods without approval (see AGENTS.md judgment boundaries).
