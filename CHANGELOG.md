# Changelog

All notable changes to this project are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed

- **A palette step was a second name for another one, and the landing page's
  secondary button was wearing it.** `--line-2` carried `--mute-line`'s exact
  value in both themes and was read nowhere in the product; its four readers
  were all in `site/site.css`. It is deleted from both themes of both
  stylesheets, from `DESIGN.md`, and from the four lists that named it —
  `REQUIRED`, the doc-comparison alias, the site palette allow-list and the
  unread-token exemption table.

  Removing it found two things no gate had looked for. The page's
  `.btn-secondary` was painting that value — **1.50:1** against `--surface` in
  light, **1.45:1** in dark — while the product's identically-named button
  painted `--line-3` at **3.24:1 / 3.53:1**; both now paint the same step and
  both clear the 3:1 that WCAG 2.2 SC 1.4.11 asks of a control boundary. And
  the page was declaring four tokens the product does not have, including
  `--ok-line`, retired the day before; nothing could see it because the
  palette test iterates a hand-written list of tokens the page is *allowed* to
  restate, so it only ever compared names it already knew. Both are gates now:
  one derives "does the page own a name the product has retired?" from the two
  stylesheets, and `check_design_tokens` fails an unread-token exemption that
  is byte-identical to a value the product already reads.

- **The design contract described a product that no longer exists.**
  `DESIGN.md` drew a 240px rail (the shipped rail is `--rail-w: 56px`), a fixed
  392px list pane (the track is `minmax(320px, 380px)`), a 28px compact button
  (`.btn-sm` is 26px), a status bar carrying a last-scan time the API has no
  field for, and a budget-meter axis "running to 125%" when it is
  `max(125, ceil(peak / 25) * 25)` — a fixed axis would clamp the bar the
  component exists to reveal. It now describes the shell as built: the icon rail
  and how its labels are carried rather than deleted, the rail-anchored panel
  holding the scope switcher and context meter, the drawer built at ≤760px with
  761–768 deliberately keeping the rail, the status bar's real facts and their
  declared degradation order, and the three centred measures the three views
  actually use.

  The fix is gated, because the finding is that nothing compared them:
  `check_design_tokens.py`'s `check_doc_numbers()` derives the rail width, every
  layout band's grid template, every `--dur*` token and value, both button
  heights and each static status-bar fact out of the stylesheet and the markup,
  and fails when the contract stops stating them — 12 figures, 4 mutations
  caught by `tests/test_redesign_doc_numbers.py`. No rendered pixel changes.

### Added

- **`site/` — a static landing page that cannot state an unsupported fact.**
  One HTML file, one stylesheet, six vendored woff2 and one screenshot captured
  from the running app: hero, install band, a six-row capability ledger, the
  scope table, the CLI reference and a closer. It is a repository artefact and
  is **not** in the wheel; a contract asserts that in that direction, so a
  packaging line that shipped it would fail the suite.

  The reason it is gated the way it is: a landing page is prose, and prose is
  where a claim survives code review, because nothing in this repository had
  ever checked a sentence. `tests/test_redesign_site.py` therefore derives
  every fact the page states out of the file that owns it — both palettes and
  the type families from `skillsmgr/webui/styles.css`, the command list and its
  headline count from `docs/03-cli-surface.md`, the scope ids, labels and
  directory spellings from `skillsmgr/scopes.py`, the global scope's path from
  `skillsmgr/paths.py`, and the distribution name, Python floor and licence
  from `pyproject.toml` — and fails when they disagree. It caught a real error
  in the page it was written for: the global scope row named
  `$SKILLS_MANAGER_DATA/skills`, one path component short of the directory the
  tool actually creates.

- **A contract that read the next view's comment.**
  `settings_sidepanel_block()` in `tests/test_redesign_settings_layout.py`
  sliced a fixed 3,000 characters from a block about 1,100 characters long, so
  it swallowed the whole next branch of the view chain. The assertion that the
  Settings rail's current marker follows the reader's choice rather than a
  scroll-spy therefore failed on the word "scrolls" inside a comment
  documenting a different view. It now slices to the next `v-else-if` and
  strips comments — the end condition the chain itself defines. The claim is
  unchanged and strictly narrower: a comment is not copy a reader can see.

### Changed

- **The editor waits for Save to tell you a field is empty, and never told you
  a name was invalid at all.** Required-field messages appeared only after
  `saveSkill`, and the name field's own hint stated the catalog's rule —
  lowercase letters, digits and single hyphens, 1–64 characters — in prose while
  nothing checked it, so the reader met that rule as a 400 and a toast. There
  is now one validator, read by both the blur handler and `saveSkill`, so the
  two paths cannot drift apart. "Required" is said only about a field the reader
  typed into and emptied: tabbing through a form you have not started says
  nothing. A format message is a verdict rather than a second statement of the
  rule, because the hint above it is always visible. Two labels that carried
  their own format hint in parentheses — `Allowed tools (comma-separated)` and
  `Body (SKILL.md content)` — no longer do, so every field the detail pane also
  names is spelled identically in both places.

- **The editor's preview was a second rendering of the same document.** The
  create/edit dialog and the Library's Source tab already called the same
  `renderMarkdown`, and the preview still looked nothing like the Source tab:
  `.markdown-preview` carried three declarations (a border, some padding and a
  14px size) and none of the document rules that give `.body` its heading
  ladder, list rhythm, blockquote, code and tables. A reader comparing the two
  places a skill body appears was comparing two renderings. Every document rule
  now carries both hosts, the preview inherits its base size the way `.body`
  does instead of declaring a smaller one, and the two are pinned by comparing
  *computed styles between the two live renders* rather than by a list of
  selectors. From 900px the body field splits into Markdown and rendered
  preview side by side on one declared shared scroll height, so a long document
  scrolls in place instead of pushing Save out of the dialog; below that the
  panes stack and neither scrolls internally. The preview is a named, focusable
  region, because a scrollable pane with no name is unreachable by keyboard.

- **The detail pane is a tab shell (5 panels, not one 1,900px scroll).** The
  Library's selected-skill pane used to be a single scroll in which the entire
  metadata table sat behind a closed `Skill details` disclosure, the list of
  observed copies rendered only when a skill had more than one copy, and the
  rendered document ran off the bottom — so the three things a reader opens a
  skill for were the three things furthest from its name. It is now a
  `role="tablist"` over five `role="tabpanel"`s (Overview · Source · Instances
  · History · Quality) with roving `tabindex` and Arrow/Home/End navigation
  that move selection *and* focus. A skill with one observed copy now says so
  instead of rendering an empty panel. History is fetched when the tab is
  opened rather than when the skill is selected, and the rows carry the
  scope and name they belong to, so switching skill mid-request cannot land
  the previous skill's history under the new skill's heading. The pane's
  Quality tab states only observed evidence — parser and addressability flags,
  measured size and token counts, provenance when the server returns it — and
  says on screen what it does not infer.

- **The font test asserted the wrong thing, twice.** It probed English prose and
  called that coverage of the typeface. The interface ships **21 non-ASCII
  codepoints** — an em dash at 144 uses, a middot, an ellipsis, arrows, a
  checkmark — and not one was asserted to render anywhere, while
  `document.fonts.check()` returns `True` for a glyph the face does not carry.
  The inventory is now derived from the shipped sources, so a character added
  yesterday is covered today rather than whenever someone remembers. Every one
  is rasterised and compared against a Private Use codepoint: a `.notdef` box
  is a real failure, and nothing else is.

  The method is pixels, not advance width, and the reason is measured rather
  than assumed: in a monospaced face the advance is constant for *every*
  codepoint including `.notdef`, so a width probe cannot tell a tofu box from a
  letter — and across faces the widths collide by coincidence, with `–`, `§` and
  `↑` all measuring 31.8px in one pass. The first version of this test then
  compared against bare `sans-serif`, which is not what the token falls back to
  (`system-ui` wins first), so it reported "vendored" for a glyph that had left
  the vendored face — caught by injecting `unicode-range` onto Geist Sans 400
  and watching the suite stay green over the exact defect it exists to find. The
  baseline is now the shipped stack with *only* the vendored families removed,
  and that mutation is caught by name.

  Measured on this tree, all 21 paint, and **five** (`↻ ⌘ ▸ ▾ ✓`) come from a
  system face rather than Geist. Those are UI furniture rather than prose and
  per-glyph fallback is intended for skill bodies, so the prose set is asserted
  and the fallback set is pinned by name — a tripwire, not a design ruling, so
  it cannot grow in silence.

- **The bulk bar no longer promises exactness it cannot deliver.** The bar
  counts *exact physical instances*, and directly beneath that sentence the
  Tags control was writing **logical names**: `/api/catalog/tags` is keyed by
  name, so selecting one copy of a three-copy skill tagged all three, silently.
  The REST contract is frozen and the catalog has no per-instance key to
  address, so the fix is the sentence rather than the request — the tag panel
  now names every entry it will write and its copy count, counted from the same
  loaded set the request's `names` are derived from. The same honesty pass
  covers the other unsaid thing: a target restored from the selection snapshot
  carries a path and a disabled flag observed at *selection* time, and the
  review dialog now counts and admits those. `Clear` moved onto the count row —
  it ends the selection rather than acting on it, and it was 57 of the 373px
  the verb row needed inside a 362px bar at 390px — taking the bar from 135px to
  113px at 390 and 105px to 83px at 768, for 10px at 1280 where the count row
  grows to the button's height. The tag panel was also re-anchored: it centred
  itself on a summary at the far left of the verb row, which put half of it at
  negative x at 1280px and rendered its own label as "o apply".

- **The web UI was redesigned.** The visual system is now specified in
  `DESIGN.md` at the repository root — tokens, their measured contrast ratios,
  and the reasoning — and enforced by `check_design_tokens.py`, which
  re-derives every ratio from the shipped stylesheet on each run. The palette
  moved off a warm canvas-and-copper scheme onto a cool bone ground with one
  reserved ink, because the previous one sat in a named AI-tell cluster;
  the composition, density and type were kept. A new **context-budget meter**
  leads the Overview: on a machine where three scope roots each hold more
  skill text than an entire 1M-token context window, that is the most
  consequential thing this tool observes, and burying it under a skill count
  is the wrong priority. Library rows now **group their observed identities by
  state with problems first**, so the scopes that disagree are the first thing
  the eye lands on, and a value shared by every visible row is stated once in
  the pane header instead of badged hundreds of times. The typeface is
  **vendored** rather than fetched — Geist Sans and Geist Mono, SIL OFL 1.1,
  400/500/600 — so the app works offline and no third party is in the page.
  The faces deliberately carry no `unicode-range`: an earlier pass restricted
  every face to `latin-ext`, which shipped 176 KB of woff2 that matched no
  English character in the interface while every "is the font vendored" check
  passed. That failure is now caught three ways — declared faces must resolve
  to shipped files, must not be restricted away from ASCII, and must be real
  `wOF2` containers — and `tests/e2e/test_font_render.py` measures a rendered
  probe against a phantom family in a real browser, because reading a
  stylesheet cannot tell you whether a face actually loaded.

### Fixed

- **The UI said "Malformed" for skills that are not malformed.** The backend
  reports a precise reason and the interface collapsed every reason into one
  word. On a machine where skills are symlinked into a shared store, that
  mislabelled 301 of 1,962 instances and pointed readers at repairing
  frontmatter when the actual remedy is to stop linking or copy the tree in.
  A refused symlink is now reported as **"Linked outside root"**, its own
  state, with its own count in Quality and on the Overview. The behaviour is
  unchanged — the tool still declines to follow a symlink out of its managed
  root, which is what keeps a write from landing outside it — only the name
  is now accurate.
- **The vendored typeface covered no ASCII.** Faces shipped, the files were in
  the package, and every check for them passed, while every page silently
  rendered in the fallback: all six rules carried only a `latin-ext`
  character range. A vendored face that covers none of the glyphs a page uses
  is the same failure as one that was never shipped. Coverage and `src`
  resolution are now asserted.
- **The typeface did not ship at all.** The package manifest listed the
  vendored runtime assets but not the font directory, so an installed copy
  would have declared the family and rendered the fallback. Both the wheel and
  the sdist now carry it, verified by a clean install.


- **CI is green again.** `main` had been failing on every push since
  2026-09-16. `unit (py3.10)` and `unit (py3.11)` failed on a test that asserted
  one of two both-correct outcomes of a failed purge, chosen by the order the
  filesystem enumerates directory entries. The test now asserts the invariant it
  exists to protect — a skill is never advertised once its document is gone — and
  is verified order-independent across ten directory names. The browser,
  package/release-artifact, docs, and adversarial-security gates had been skipped
  on every run as a result and now execute.
- **The registry client works again.** skills.sh moved its read API behind
  project OIDC, so `--browse`, `--search`, `--curated` and the whole `--fetch`
  install path returned HTTP 401 in production. Search now reads the public
  `/api/search` route and fetch/detail the public `/api/download` route. The
  download route's `hash` is produced by an undocumented upstream algorithm, so
  it is recorded as `upstream_hash` with `upstream_hash_verified: false` instead
  of being asserted; integrity rests on the manager's own framed digest.
  `--browse`/`--curated` need a token and now say so, naming the working
  alternative, rather than surfacing a bare 401.
- **A legacy over-permissive data directory is no longer a dead end.** A root
  created before the ownership control landed was permanently unusable, with an
  error that named the condition but not the fix. A directory that is
  owner-held, has an acceptable parent chain, and is recognisably this tool's
  data is now tightened to `0o700` with its contents intact; anything else is
  refused with the exact `chmod` command.
- **The agent-scope toggle is now excluded.** `toggle_skill` did
  check-then-rename with no lock while its sibling scope writers all took one.
- **A concurrent edit can no longer be lost to an update commit.** The update
  commit revalidated the target and then replaced the tree under a review lock
  that `Store.edit` never took, so an edit landing in that window was silently
  overwritten. The library index lock is now held across the whole window.
- **Corrected the documented locking model.** The architecture doc still
  described in-process `threading.RLock` with cross-process exclusion "OPEN";
  the code has used an advisory `flock`/`msvcrt` lock since the fix. Three code
  comments repeating the same belief were corrected.
- **An undefined spacing token.** `--s3` was used 13 times and defined nowhere,
  the only undefined custom property in the stylesheet, so eight components
  rendered with no intended spacing.
- **Reduced motion now stops the strobe.** Two animations are `infinite` and the
  reduced-motion block only forced duration, so they still ran.
- **Border contrast.** The token forming the only visible boundary on form
  inputs measured 1.62:1 in light and 2.06:1 in dark, failing WCAG 1.4.11 in
  both themes. Both now clear 3:1.
- Accessibility: the "Update from folder" control failed WCAG 2.5.3
  `label-content-name-mismatch`; adapter links rendered in default browser blue;
  the trash purge control now names what it destroys and sits below the list it
  removes.
- **The agent-facing management skill now ships.** It was absent from the sdist
  *and* the wheel, so `pip install` gave no access to the only artifact that
  lets an AI agent drive this tool safely. It ships as package data, and the
  packaging gate now proves it is present and readable.
- **A read no longer writes.** `GET /api/skills` (and the other read routes)
  created four directories and a 32 KB SQLite index on first request, and a
  damaged layout answered a mixture of `400`s and `200`s. Reads now create
  nothing, and a broken layout answers one repairable `404` naming the path.
- **An unsafe multipart upload part no longer vanishes.** It was skipped while
  the response still said `200 {"skipped": []}` — user data silently dropped
  under a payload claiming nothing was skipped.
- **`GET /api/export` no longer writes an archive** into `<data>/backups` on
  every request; it streams the download and leaves nothing behind.
- **Bad query parameters are `400`s, not silent defaults.** This includes
  `/api/sync` iterating a string `to_scopes` one character at a time.
- **One error shape everywhere:** `{"error", "code"}`, so a client can branch on
  one key.
- **A skill whose directory is gone is a `404` in REST** and no longer serves
  its stored body, while `doctor()` still reports it as a stale row.
- **The web server binds the host it validated.** A trailing space or a bare
  IPv6 literal passed the loopback policy and then raised a raw `gaierror`.
- **One Ctrl-C no longer permanently wedges a coalesced read endpoint.**
- **The frontend's observed state has one source.** Five hand-copied predicates
  (the audit counted three) disagreed with each other, `invalid` was missing from
  the domain label map so it never appeared in Quality, and the Escape ladder
  hand-copied a key order it did not match. Requests across 10 navigations fell
  from 17 to 9.

### Changed

- **The primary read path is 34-40% faster** (interleaved A/B at 1,200 skills:
  `list()` -34%, `list_all()` -40%, `doctor()` -16%, `search()` -39%).
- **The two god routers were split.** `_route_get` 89 -> 13 and `_route_post`
  80 -> 11, guarded by 16 characterisation tests that pass on the pre-refactor
  tree as well.
- **`GET /api/skills` accepts opt-in `limit`/`offset`** with `X-Total-Count`;
  paging parameters that are not implemented are refused rather than ignored.
- **The complexity ratchet fails when a baseline entry sits above its measured
  metric.** It previously carried silent headroom -- `_route_get` was recorded
  at 96 while the code measured 13 -- and the ratchet only fails on *increase*.

- **The complexity ratchet now measures real modules.** It tracked `cli.py`, which
  became a 160-line adapter in a CLI split, leaving 2,076 lines of CLI logic
  unguarded and 43 of 169 baseline entries resolving to nothing. Targets now
  cover 16 modules (261 → 631 functions, ~4,750 → ~13,000 LOC), and a baseline
  entry that no longer matches a measured function is a hard failure rather than
  a silently dropped guard.
- The browser harness reports which ownership check rejected an executable, and
  reports Chrome's own startup error instead of discarding its stderr. CI
  re-enables Chrome's user-namespace sandbox on the runner and tightens the Node
  tool cache, rather than passing `--no-sandbox` and weakening the pinned SEC-15
  decision.

- **The Library was reworked so the Overview leads with what needs attention.**
  The Overview hero is gone and the attention queue is the first block on the
  page; the duplicated "Observed state" panel it displaced now appears once, as
  the `Observed copies` / `Malformed` / `Unaddressable` metrics of the summary
  list. The Library uses a single 40px filter bar instead of stacked controls,
  suppresses a uniform scope or state to screen-reader-only text rather than
  repeating it on every row, holds an 11px type floor and 56px rows, and makes
  each row's primary line the scope and observed state — paths move into
  disclosures carrying a Copy button, and the `Largest:` chip row is deleted
  from every viewport. Rendered evidence for six viewports is committed at
  `.specs/evidence/ui-g8-release-1.0.2-2026-10-06/`.
  **Not yet done:** no human perceptual review, no non-Chromium engine, no
  forced-colors mode, no 200%/400% zoom, and no screen-reader pass — the
  harness renders, it does not sign off. That gate is the participant pilot in
  `docs/25-design-partner-pilot-kit.md`, which has not been run.

### Tests

- 902 tests, up from 888. New coverage: the purge invariant across ten
  enumeration orders, the registry's public routes and hash demotion, the
  orphaned-baseline-key gate, the agent-scope toggle's critical section, the
  update commit's exclusion window, the data-root upgrade path, and the Markdown
  renderer executed over 17 hostile payloads in a Node `vm` (it had been stubbed
  at 8 sites and run by no test at all).

### Package release candidate

- Prepared version 1.0.2 metadata and PyPI installation copy for the next
  release. The candidate build is verified locally and remains unpublished.

### Guided first scan and performance evidence

- Added a skippable first-scan guide for populated and empty libraries. It shows
  observed roots, one exact instance, divergent-copy evidence, and existing
  Library/Quality/read-only explanation paths without inferring a loaded winner
  or changing skills.
- Added an opt-in `skills-manager-management` skill example with dry-run-first
  inventory, exact-target preview, explicit approval, recovery checks, and
  manual installation/removal instructions. It is not auto-installed or
  included in the Python distribution.
- Extended the bounded baseline harness for cold and warm inventories of 100,
  1,000, and 10,000 actual `SKILL.md` files, with explicit incomplete-sample
  and p95 rules. The 10,000-skill run is recorded as incomplete where its
  runtime budget was reached.

### Public onboarding

- Corrected the README's comparison with the multi-agent skills CLI and
  clarified the local-candidate update boundary. Added a dated current-build
  screenshot captured with synthetic fixtures and a draft-PR route for
  contributors who cannot open an issue.

### P0 trust gate and release metadata hardening

- Fixed full-import rollback diagnostics so an `OSError` restoring a previous
  payload reports the surviving dotted backup path without masking the
  original `StoreError`.
- Added a single pinned Ruff 0.16.8 CI gate for `F821`/`F822`/`F823`, completed
  the dated Bandit 1.9.4 review, and replaced silent CLI/scope enrichment
  failures with diagnostics and bounded degradation evidence.
- Made documentation discovery deterministic across tracked Markdown,
  first-party `docs/` plans, and an explicit top-level allowlist; hardened the
  optional web opener against unsafe PATH entries.
- Migrated packaging to SPDX/PEP 639 metadata and made artifact checks verify
  `License-Expression`, `License-File`, deprecated-classifier removal, and
  byte-identical `LICENSE` content.

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
