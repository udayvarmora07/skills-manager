# Changelog

All notable changes to this project are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Web UI robustness

Ported the remaining valid findings from the historical frontend test report:
CRLF-safe Markdown rendering, array-safe compatibility formatting, accessible
Path metadata markup, stronger chip-count contrast, visible raw-metadata
enrichment failures, and clean drained `413` responses for oversized bodies.
The current suite is **728 tests** with **222 complexity-tracked functions**.

### Final audit tail

The final five low/info audit findings are closed: frontmatter dumping now
rejects over-depth/cyclic programmatic containers (`FM-20`), template names use
canonical bounded/reserved-name validation (`FM-21`), script-risk matches are
explicitly advisory heuristics (`INS-1`), offline registry previews never
self-assert trust/hash/eligibility (`INS-2`), and the `cmd_open` report is a
verified false positive (`INFO-1`). The current suite is **721 tests** with
**219 complexity-tracked functions**. No command, Store method, schema,
dependency, or bind changed.

The remaining partial frontmatter finding (`FM-9`) is now fixed: control-bearing
keys round-trip through escaped double-quoted output, and serialized-key
collisions fail before duplicate-key documents are emitted. The current suite
is **722 tests** with **221 complexity-tracked functions**.

### Security hardening

The next six low/info audit findings are addressed. First-party GitHub Actions
are pinned to reviewed commit SHAs; the browser harness keeps Chrome's sandbox
enabled and binds its ephemeral CDP listener to loopback; and both developer
launchers skip unsafe PATH matches through a shared ownership/permission check
(`SEC-14`…`SEC-16`). Environment-selected data roots are canonicalized and
validated before use (`SEC-19`). `CODEOWNERS`, GitHub Actions Dependabot updates, and the
protected `release` environment strengthen release governance (`SEC-17`), while
`.gitignore` covers local configuration, databases, credentials, and private
keys (`SEC-18`). No product command, Store method, schema, runtime dependency,
or public bind changed.

### Frontmatter and validation

The frontmatter validator follow-up closes five low-severity audit findings:
folded `>` scalars preserve line breaks around more-indented content (`FM-13`),
Windows device names are rejected before they become paths (`FM-15`), NUL-byte
link/layout references become validation warnings instead of raw path errors
(`FM-16`), frontmatter names are checked even when no caller name is supplied
(`FM-17`), and passive "should be used when" descriptions satisfy the
use-context check (`FM-18`). The audit tracker now reads **88 fixed, 1 partial,
1 accepted, 12 open** of 102.

The follow-up also normalizes URL-decoded link and layout references so existing
targets with fragments, queries, encoded spaces, or sentence punctuation do not
produce false warnings (`FM-19`).

### Security

Batch 5 of the 2026-09-11 deep-audit remediation: the last Medium findings
(`SEC-5`…`SEC-9`) plus `SEC-13`, whose open question a real build settled. The
tracker now reads **67 fixed, 1 partial, 1 accepted, 33 open** of 102; the
remaining 33 are 3 Medium (`STORE-11`, `SCOPE-5`, `SCOPE-8`) and 30 Low/Info.
No locked constraint moved — no new CLI command,
no `Store` method, no schema change, no runtime dependency, no build step in the
web UI.

- **CSP.** `form-action 'none'` is now sent, because `form-action` does not fall
  back to `default-src`, so an injected `<form action="https://…">` can no longer
  submit (`SEC-5`). `script-src 'unsafe-eval'` stays: the vendored bundle is the
  runtime+compiler build and removing it needs precompiled render functions, i.e.
  a build step, which the locked constraints forbid. That trade-off, its cost and
  the condition that would revisit it are now documented in `docs/08-web-ui.md`
  and pinned by a test instead of being left implicit (`SEC-4`, recorded as
  *accepted*).
- **Malicious or merely unlucky uploads returned HTTP 500 with the exception
  text in the server log.** A multipart folder upload containing both `a` (a
  file) and `a/b/SKILL.md` (a directory) failed with a raw `IsADirectoryError`,
  and a NUL byte in a filename returned the interpreter's own `embedded null
  byte` message. Both are now a plain `400` naming the conflict
  (`a file and a directory share the name 'a'`), and no raw exception text
  reaches the client (`SEC-6`).
- **Release supply chain.** The `contents: write` release job no longer installs
  or executes a distribution fetched from public PyPI: every install there is
  `--no-index` against the artifacts that workflow built and attested, and the
  post-publish PyPI verification moved to a new job with `contents: read` only
  (`SEC-7`). The build backend is exactly pinned (`setuptools==84.0.0`) and the
  outer toolchain is locked and hash-verified in `requirements-build.txt`,
  installed with `--require-hashes` and used with `--no-isolation`, in both CI
  and the release workflow — so the attested bytes no longer depend on whatever
  PyPI serves on release day (`SEC-8`).
- **Vendored frontend dependency.** `check_package_data.py` records and verifies
  the vendored `vue.global.prod.js` upstream version, URL, sha256 and size, in the
  source tree and inside both built artifacts, before the optional build step —
  previously a PR could replace a 158 KB minified file that runs same-origin with
  access to every mutation endpoint with nothing to notice it (`SEC-9`).
  `.gitattributes` marks the file `-text` so line-ending translation cannot break
  the recorded hash.
- **Published sdist contents.** The sdist shipped `tests/test*.py`, and the gate
  could not see it: sdist members outside `skillsmgr/` were dropped before the
  "must never ship" policy ran, so its own regression test only ever covered a
  wheel fixture. Members are now inspected and `MANIFEST.in` prunes `tests`
  (73 → 45 members) (`SEC-13`, now fully closed).

### Fixed

Remediation of the 2026-09-11 deep audit (`DEEP-AUDIT-2026-09-11.md`), run as
four batches in the audit's own severity order: **61 finding IDs closed and 3
partially closed, out of 102** (`FM-9`; plus `SEC-5` and `SEC-13`, whose closed
halves came from `BUG-9` and `BUG-13`). Per-finding disposition is recorded in
`docs/13-audit-remediation-status-2026-09-11.md`. (The batches set out to close
46 agenda items; they closed more IDs than that, because several items covered
more than one finding.)

- **Data loss.** An indented `---` inside a multi-line frontmatter value silently
  truncated the value and promoted the remainder into the body on every write.
  An interrupt during `import`'s commit move could destroy the user's only copy of
  a skill. A skill directory holding both `SKILL.md` and `SKILL.md.disabled` was
  installed by `add` and then silently destroyed one document on the next toggle.
  A force-import could discard an already-committed `edit`. `restore`/`purge_trash`
  raced and could leave an index row `resync` could never repair.
- **Crashes on one bad document.** A sequence frontmatter root, an out-of-range
  `\U` escape, a lone surrogate, an unreadable `SKILL.md`, and a raw
  `sqlite3.OperationalError` from `create()` on a fresh data dir all failed
  loudly-but-raw or aborted whole views; each is now a clean error or a reported
  drift row.
- **Security.** `GET` routes now pass the same Host/Origin/Fetch-Metadata policy as
  mutations (closing the tracked DNS-rebinding read gap), the
  `doctor?explain=` diagnostic no longer discloses the real agent-skill inventory
  or `data_dir` and is confined to the manager's data directory, and its
  directory walk is bounded by work rather than result count.
- **Untrusted input.** A hostile `evals.json` regex could hang the CLI and freeze
  the web-UI process GIL-wide; regex assertions now run under a wall-clock budget.
  Control characters in `--metadata` keys are rejected, and both edit paths fail
  closed on a malformed document instead of emitting a second frontmatter block.
  ANSI/control characters are stripped from untrusted display fields.
- **Round-trip fidelity.** Multi-line frontmatter values now survive
  dump → parse exactly (indentation, whitespace-only lines, CR content, tabs
  before `#`, newline-only values, YAML chomping indicators).
- **Store integrity.** `purge_trash` no longer holds one write transaction across
  every directory removal; `remove(purge=True)` displaces the tree before deleting
  it, so a partial purge can never advertise a skill whose document is already
  gone; `export()` is atomic, collision-free within a second, and leaves no
  truncated archive; `export`/`tree_content_hash` no longer follow symlinks (an
  archive containing one used to be rejected by the importer); reads and `stats`
  reflect filesystem truth instead of index residue; `resync`/`db_rebuild` take
  the shared library lock; and `doctor` reports document-less directories as drift.
- **Web-app hardening.** All nine silent `except Exception: pass` blocks now
  report through the diagnostics channel and mark the affected payload as
  degraded; `HEAD` answers like `GET`; `OPTIONS`/`TRACE` return a JSON 405 with
  the standard security headers instead of a header-less HTML 501.
- **Loader and scope consistency.** Names that fail the canonical rule are listed
  but flagged unaddressable rather than erroring on click; an undecodable
  document no longer publishes replacement characters as its description; one
  rogue index row can no longer abort every global aggregate; `HOME=""` no longer
  relocates agent scopes to `/`; and a grouping directory sharing a skill's name
  no longer hides the skill beneath it.
- **Gate and hygiene.** The package-data check now refuses artifacts shipping
  tests, docs, environment files, databases or bytecode; the CI SHA-pin contract
  now covers reusable-workflow references; the mutation-lock table is bounded;
  and dead frontend/frontmatter helpers were removed.
- **Documentation truth.** `docs/04-store-api.md` now matches the implementation
  for the constructor, `list`, `create`, `edit` and the trash-timestamp regex.
- **Diagnostics and UI.** The effective-resolution diagnostic no longer over-claims
  its top-level verdict, no longer reports one file as two candidates or as its own
  shadowed copy, and shares one identity for the global scope. Two in-process web
  servers on different data dirs can no longer read or write each other's data.
  The All-skills view no longer hides same-name instances inside one recursive
  scope. The frontend remove dialog is bound to the skill it was opened for.

### Docs

- Documentation truth pass after the deep-audit remediation (no product change):
  `docs/SESSION-CONTEXT.md` no longer claims reads are not `Host`-validated
  (`SEC-1` closed that; the request policy guards `GET`/`HEAD` too) and its gate
  counts now match a real run (607 tests, 216 functions);
  `docs/03-cli-surface.md` documents the `--metadata` control-character
  rejection, the fail-closed `edit`, and the terminal-output sanitization seam;
  `docs/08-web-ui.md` documents the all-method request policy,
  `HEAD`/`OPTIONS`/`TRACE`, the `degraded` arrays, the `doctor?explain` disclosure
  boundary and `addressable: false`; `docs/01-architecture.md` records the symlink
  policy and the locking model; the security docs mark the read-path and terminal
  threats as mitigated and the remainder as open; and every `file.py:line`
  citation in the threat model, the security report and `docs/04-store-api.md` was
  replaced with a symbol name because all of them had drifted.
- The documentation gate (`check_docs.py`) now also checks HADS headers for every
  `docs/*.md`, local link **anchors**, markdown table integrity, single trailing
  newlines, `Store`/REST/CLI surface parity and the session-context file
  inventory; each new check is pinned by a regression test. Three real defects it
  found are fixed: an unescaped `|` that gave a table an extra column, a line
  starting with `#2` that rendered as a spurious H1, and eleven files that did not
  end with a newline.

### Changed

- `Store.edit` / `scopes.edit_skill` now **refuse** a document whose frontmatter is
  unparseable, instead of rewriting it (which produced a second frontmatter block).
- `sync_skill` now **refuses** to copy a skill holding a symlink that points outside
  it, and copies in-scope symlinks as links rather than following them.
- A skill cluster addressed by name now resolves to the *named* entry, so an in-root
  symlink alias no longer makes a write mutate its target.

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
