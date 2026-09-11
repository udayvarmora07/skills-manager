# Architecture — Skills Manager

**Version 0.2.1**

**AI manifest**: Current architecture and data-flow facts verified against source on September 10, 2026 (repo-map refresh: split CLI/web policy modules, `insights.py`, harness, smoke fixtures, package-data gate; ZIP archive import plus transactional full-import restore; 315-test suite). The filesystem is the source of truth; SQLite is a rebuildable index; the local web UI is a second front-end over the same Store/scopes layers the CLI uses.

## Repo map

```
skills-manager/
  skillsmgr/
    __init__.py      # __version__ = "1.0.1"
    __main__.py      # entry: python3 -m skillsmgr -> cli.main()
    cli.py           # stable adapter: main/build_parser + handler/private-helper aliases
    cli_parser.py    # argparse construction (27 top-level + 3 aliases; 7 nested)
    cli_handlers.py  # command behavior + name/data validation
    cli_output.py    # JSON/errors/table rendering
    store.py         # Store: FS + SQLite index; StoreError, SkillNotFound
    scopes.py        # agent-scope model + per-agent filesystem ops
    loader.py        # shared SKILL.md loader + dir scanner (Store + scopes)
    tokens.py        # token/context estimation
    archive.py       # archive preflight, extraction, staged commit policy
    atomic_io.py     # atomic text writes, mutation locks, tree hashes
    observations.py  # non-persisted hashes, provenance, frontmatter partitions
    root_discovery.py# physical-root and observed-scope policy
    effective.py     # read-only effective-resolution diagnostic (doctor --explain)
    paths.py         # data_dir(), db_path(), subdirs (containment adapter)
    path_safety.py   # resolved root-containment and canonical skill-path policy
    diagnostics.py   # stderr-only recovery/optional-enrichment diagnostics
    frontmatter.py   # parse/dump SKILL.md YAML-ish frontmatter
    validator.py     # canonical name/field rules, Issue dataclass
    search.py        # regex search + scoring
    templates.py     # default template + template list/new
    colors.py        # TTY-aware color helpers
    webapp.py        # stdlib backend: routing + server (policy in web_*.py)
    web_security.py  # loopback mutation validation policy
    web_serialization.py # JSON body/response helpers
    web_upload.py    # multipart folder-upload staging policy
    insights.py      # read-only Milestone 9 helpers (pure, no CLI/Store/schema)
    webui/           # index.html, styles.css, domain.js, app.js, static/vendor/vue
  smoke_store.py     # smoke test driving the Store API (hermetic fixture)
  smoke_web.py       # smoke test driving the REST API (hermetic fixture)
  smoke_fixtures.py  # shared tmp-store + loopback-server lifecycle helpers
  browser_harness.py # dev-only system-Chrome CDP viewport probe (no runtime dep)
  tests/             # stdlib unittest regression suite (315 tests, 2026-09-10)
  check_docs.py      # machine-checkable docs/source consistency gate
  check_complexity.py# AST complexity ratchet (+ complexity-baseline.json)
  check_package_data.py # wheel/sdist package-data verification
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

**[SPEC]** `data_dir()` = `$SKILLS_MANAGER_DATA` -> `$XDG_DATA_HOME` -> `~/.local/share`, then appends `skills-manager`. Subdirs: `skills/`, `trash/`, `templates/`, `backups/`, `snapshots/`, and `evals/` (created lazily only when eval run results are recorded); `db_path()` = `data_dir()/skills-manager.db`.

**[NOTE]** Eval run workspaces live at `evals/<name>-workspace/iteration-N/…`, deliberately outside `skills/`, so the skill scan, `doctor` orphan detection, archive export, and the SQLite index never treat run data as skill data. See @docs/ADR-003-registry-bridge-and-eval-harness.md.

## Data flow

```
CLI (cli.py/cli_parser.py/cli_handlers.py/cli_output.py) ──┐
               ├──> Store/scopes ──> filesystem (source of truth)
Web UI         ─┘          │
(webapp.py + web_security/serialization/upload) │
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
