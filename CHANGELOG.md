# Changelog

All notable changes to this project are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.0.1] — 2026-09-10

### Added

- Published the `skill-control-plane` 1.0.1 distribution through the controlled
  TestPyPI → PyPI → GitHub Release workflow, including provenance attestation
  and post-publish install/CRUD verification. The `skills-manager` repository,
  `skillsmgr` import package, and `skills-mgr` CLI executable remain unchanged.
- ZIP archive import for the existing `import` command and `PUT /api/import`
  route (issue #5, approved 2026-09-10): content-sniffed tar/ZIP detection,
  canonical member-name and layout allowlists, duplicate detection,
  compressed/expanded/member/path/nesting/ratio budgets, ZIP symlink-bit
  rejection, explicit contained-path extraction, and the existing staged
  commit/hash pipeline. No new CLI command, no schema change, no dependency.
- Regression corpus for the ZIP slice: round trip, traversal, absolute,
  backslash, drive-letter, symlink, duplicate, malformed central metadata,
  slash-only directory entries, per-member ratio bombs, full-import failures,
  and a live REST import.

### Fixed

- A failed staging copy no longer deletes the destination skill. Previously a
  `copytree` failure that happened before the original was moved aside was
  indistinguishable from "no original existed", so the user's skill directory
  was removed (`skillsmgr/archive.py`).
- ZIP compression-ratio budget is enforced per member as well as per archive; a
  stored incompressible member can no longer mask a later highly compressible
  one.
- `--full` imports of trash/templates are now one all-or-nothing transaction:
  every payload is validated before any mutation, each is staged and swapped
  with rollback, and failures surface as `StoreError` (REST → 400) instead of
  raw `OSError` with mixed old/new state. Restored trash names are reconciled
  into the index so `stats()`/`doctor()` agree with `trash_list()`.
- Manifest validation rejects a non-boolean `full` flag and non-plain
  `trash`/`templates` entry names before any filesystem work.
- The REST no-mutation tests compare persisted state instead of
  `Store.get()` snapshots that embed the read-time `observed_at` stamp, which
  made them fail whenever two reads straddled a UTC second boundary (seen on
  the Python 3.14 CI leg). A genuine mutation is still detected.
- The concurrency contract helper waits for worker threads with a generous
  deadline instead of a fixed 10 s per-thread join, which flaked on loaded CI
  runners while still detecting genuinely stuck threads.
- `check_package_data.py --dist-dir --install` now actually installs the exact
  artifacts it inspected; the install step used to be skipped silently.
- CI portability: the cross-platform job compiles with `python -m compileall`
  (Windows runners do not expand `skillsmgr/*.py`), `contained_path` test
  expectations resolve the root (macOS `/var` → `/private/var`), the ZIP
  backslash case asserts the contained-import invariant on Windows (where
  `zipfile` normalizes `\` to `/` inside `ZipInfo`), and the browser harness
  discovers Chrome's DevTools port from `DevToolsActivePort` with a longer
  cold-start budget and requires Node ≥ 22 for the global WebSocket (the CI
  browser job is pinned accordingly).

- Milestone 9 read-only insight foundation (`skillsmgr/insights.py`, pure stdlib-only helpers, no CLI/Store/schema/network changes): per-consumer observed views with precedence explicitly unresolved, two-way/three-way diffs, five-state ownership classification, provenance summaries, update previews with rollback flags, stage-only quarantine plans, explainable static risk scans, offline registry dry-runs gated on explicit trust, provider-neutral advisory eval plans, and a deferred signed-bundle policy. Locked by 57 red-first hermetic tests in `tests/test_insights_contracts.py` (20 foundation + 11 fail-closed + 9 round-3 strictness + 7 round-4 boundaries + 5 round-5 audit locks + 5 deep-E2E).
- Browser UX/a11y baseline: dev-only Chrome CDP viewport harness with console/runtime/network failure capture; keyboard `/`, `?`, `Esc`, and Tab dialog contracts; labelled/inert modal focus lifecycle; safer destructive defaults; live status announcements; escaped Markdown editor preview; and sync source/target/overwrite/rollback preview.
- Internal seams: CLI parser and handlers split behind `skillsmgr.cli` compatibility adapters; no-build frontend domain policy split into `webui/domain.js` before `app.js`.
- Release engineering baseline: CI now runs a 3.10–3.14 unit matrix plus a
  Linux/macOS/Windows path/archive matrix, separate unit/adversarial/package/
  docs/browser jobs with least-privilege `contents: read` permissions, and a
  build-once package gate (`check_package_data.py --dist-dir` inspects the
  exact wheel/sdist CI publishes). A tag-gated `release.yml` builds once,
  verifies the exact artifacts, attests build provenance, publishes via PyPI
  Trusted Publishing (TestPyPI then the protected `release` environment, no
  long-lived token), creates a GitHub Release, and verifies the PyPI install
  (CLI help, vendored web assets, hermetic CRUD) plus tag/version alignment.
- Cross-platform containment parity: `contained_path()` and archive member
  validation now reject Windows `\` separators and drive-letter prefixes on
  every host, with hermetic regressions proving the behavior on Linux.

- Atomic sibling-temp skill/snapshot/template writes with flush/fsync/replace,
  same-process per-document mutation serialization, rollback on index/history
  failures, doctor diagnostics for transaction artifacts and filesystem/index
  drift, SHA-256 archive content-hash verification, and a CI-backed
  `check_docs.py` documentation/source consistency gate.
- Root discovery baseline: corrected Cursor's `~/.cursor/skills` path,
  deduplicated resolved physical scope roots for aggregate counts and sync,
  and recorded the approval-gated consumer/effective-state model plus official
  discovery research.
- Scope observations now support consumer-specific recursive discovery, explicit
  root availability (`writable`, `read-only`, `missing`, `unsupported`), and
  observed instance states; precedence-based shadowing remains approval-gated.
- Preserved unknown frontmatter extensions and added derived document observations
  (portable fields, extension fields, content/metadata hashes, timestamps, and
  provenance). Extracted archive, atomic-I/O, and root-discovery policy into
  internal modules, plus root-containment into `path_safety.py`, with compatibility
  adapters.

- Archive/trash safety hardening: forced imports cannot turn invalid names into
  destructive paths; tar members are preflighted in a private temporary tree;
  duplicate, traversal, unexpected-layout, symlink, hard-link, FIFO, and other
  special members are rejected; tar extraction uses `data_filter` when
  available and a guarded regular-file/directory fallback otherwise; malformed
  trash entries are ignored consistently.
- Archive intake budgets and migration contract: tar and ZIP
  compressed/expanded/member/path/nesting/ratio limits, strict versioned
  manifests, extracted frontmatter name checks, content-based format detection,
  guarded ZIP extraction (including symlink-bit rejection), and staged per-skill
  import rollback with explicit imported/skipped reporting.
- Spec-lint+ (`validator.py`): `description_score()` (use-context + filler detection), description warnings (missing "Use … when …", vague filler), body token warning (`MAX_BODY_TOKENS=5000`, progressive-disclosure guidance), `scripts/`/`references/`/`assets/` layout check for dangling mentions.
- Cross-scope dedup: `scopes.find_duplicates()` (same-name + descriptions-differ flag), surfaced in `doctor --scope all`, `/api/doctor?scope=all`, and the doctor modal with Sync… converge buttons.
- Token budget view (verified complete): `tokens --scope all` aggregate + `largest`, `/api/stats?window=` + `/api/tokens`, frontend budget bar with window selector.
- Open-source launch kit: `README.md`, `LICENSE` (MIT), `pyproject.toml`, CI workflow, issue/PR templates, `SECURITY.md`, `ROADMAP.md`.

## [1.0.0] — 2026-09-04

### Added

- CLI (`skills-mgr`): 26 commands + `trash`/`templates`/`db` subcommands; `--json` output; exit codes 0/1/2/130.
- Agent scopes: `global`, `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, merged `all` view; `sync` between scopes; scope-aware `list/view/search/doctor/stats/tokens/install`.
- Local web UI (stdlib backend, vendored Vue 3, loopback-only): CRUD, live search, trash with undo, validate/doctor/stats/history, templates, import/export, sync modal, dark theme.
- `tokens`: per-skill/scope token and context-window estimates (tiktoken when available, chars/4 fallback).
- `install`: dry-run-first wrapper over the `skills` npm package with allowlist validation.
- Filesystem-as-source-of-truth model with rebuildable SQLite index (`db rebuild`/`resync`).

### Fixed

- `validate --all` crash, PATCH `name` 500, import traversal/type/empty guards, 25 MB body caps, generic 500s, tar `filter="data"`, restore/purge timestamp handling, frontend race guards, scope-aware undo/restore.

### Security

- No critical findings. See `security_best_practices_report.md` and `skills-manager-threat-model.md`.
