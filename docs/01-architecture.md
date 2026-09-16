# Architecture — Skills Manager

**Version 0.6.0**

**AI manifest**: Current architecture and data-flow facts verified against source on September 16, 2026 (repo-map refresh: split CLI/web policy modules, launcher executable trust checks, validated data-root selection, URL-aware validator references, pinned first-party workflow actions, CODEOWNERS/dependabot governance, sensitive-file ignore rules, and a 728-test suite). The filesystem is the source of truth; SQLite is a rebuildable index; the local web UI is a second front-end over the same Store/scopes layers the CLI uses.

## Repo map

```text
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
    paths.py         # validated data_dir(), db_path(), subdirs (containment adapter)
    path_safety.py   # trusted roots, resolved containment, canonical skill paths
    diagnostics.py   # stderr-only recovery/optional-enrichment diagnostics
    launcher_security.py # trusted PATH executable discovery for dev launchers
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
  desktop_launcher.py # optional, unbundled loopback-only app-window launcher (issue #9; no runtime dep, not packaged)
  tests/             # stdlib unittest regression suite (728 tests, 2026-09-16)
  check_docs.py      # machine-checkable docs/source gate: HADS headers, links/anchors,
                     # table integrity, CLI/REST/Store surface parity, file inventory
  check_complexity.py# AST complexity ratchet (+ complexity-baseline.json)
  check_package_data.py # wheel/sdist package-data verification + vendored-bundle hash
  requirements-build.txt # pinned, hash-verified build toolchain (SEC-8)
  MANIFEST.in        # sdist contents — prunes tests/ (SEC-13)
  .gitattributes     # keeps the vendored Vue bundle byte-stable (SEC-9)
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

**[SPEC]** `data_dir()` = `$SKILLS_MANAGER_DATA` -> `$XDG_DATA_HOME` -> `~/.local/share`, then appends `skills-manager`. The selected base and appended manager root are canonicalized and must be trusted writable directories; unsafe roots fail closed. Newly created manager components use owner-only permissions. Subdirs: `skills/`, `trash/`, `templates/`, `backups/`, `snapshots/`, and `evals/` (created lazily only when eval run results are recorded); `db_path()` = `data_dir()/skills-manager.db`.

**[NOTE]** Eval run workspaces live at `evals/<name>-workspace/iteration-N/…`, deliberately outside `skills/`, so the skill scan, `doctor` orphan detection, archive export, and the SQLite index never treat run data as skill data. See @docs/ADR-003-registry-bridge-and-eval-harness.md.

## Data flow

```text
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

## Symlink policy

**[SPEC]** Symlinks are followed only as far as containment allows, and the
*named* entry is what a name-addressed operation acts on.

- Name-addressed skill paths resolve through `path_safety.contained_entry()`,
  which returns the **named** entry while still requiring its resolved target to
  stay under the managed root (`contained_path()` resolves and therefore throws
  the final component away). An in-root alias `alias -> real` used to make
  `get_skill('alias')` report `real`, `remove('alias')` delete `real` and leave a
  dangling link, and double-list the physical skill (SCOPE-3).
- `scopes.sync_skill` copies a skill tree with `symlinks=True` and refuses a tree
  that holds a link whose target escapes it (`scopes._escaping_links`). Copying
  links as *content* read bytes from outside every managed root into another
  agent scope (SCOPE-1); copying an escaping link *as a link* would install a
  dangling or out-of-scope reference in the destination.
- `Store.export()` and `atomic_io.tree_content_hash()` do not follow symlinks, so
  an archive's manifest covers only bytes inside the managed root and an archive
  that previously could not be re-imported now round-trips (STORE-9).
- An out-of-root link *target* mentioned inside a document stays a warning and
  never fails `validate` (issue #7 verdict); the enforcement signal is
  `insights.risk_scan()`'s medium finding.

## Locking model

**[SPEC]** Locking is in-process and two-level; it is not a cross-process lock.

- `atomic_io.mutation_lock(path)` returns a reentrant lock keyed by the resolved
  path, held in a bounded registry (`MAX_MUTATION_LOCKS = 512`; only provably
  free locks are evicted, so a reentrant holder cannot lose its lock).
- A mutation takes a **per-skill lock** on `<skill>/SKILL.md` and/or the
  **library-wide index lock** at `<data>/skills/.skillsmgr-index-lock`
  (`store._index_lock_path`). `store._skill_and_index_locks()` holds both, always
  index-first, so a whole-tree scan (`resync`/`db rebuild`) and a per-skill write
  cannot interleave (STORE-2, STORE-12).
- Whole-trash operations (`restore`, `purge_trash`) serialize on a single
  `<data>/trash/.trash-lock` key, because per-skill keys cannot make them exclude
  each other (STORE-5).
- The primitive is `threading.RLock`, so it excludes threads inside **one**
  process only. Concurrent CLI and web UI on one data dir have no mutual
  exclusion — that is `STORE-11`/`SEC-12`, recorded as **OPEN** in
  @docs/13-audit-remediation-status-2026-09-11.md.

## Root and consumer model

**[NOTE]** The current `Scope` facade is a compatibility layer over physical
roots. Root identity is `Path.resolve()`: aggregate listings and sync planning
collapse aliases by resolved physical path, keeping the first stable descriptor
for display while direct lookups by an existing scope id stay compatible
(`skillsmgr/root_discovery.py`). `ADR-002-root-consumer-effective-state.md` defines the approval-gated
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
