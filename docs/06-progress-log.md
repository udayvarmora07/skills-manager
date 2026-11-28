# Progress Log — Skills Manager

**Version 0.8.5**

**AI manifest**: Current delivery receipts and a bounded resident window.
Earlier entries moved verbatim to @docs/archive/06-progress-log-through-2026-11-17.md;
older archives remain indexed by @docs/archive/README.md. The live queue is
@task.md. Retained historical sections are explicitly labeled below.

## 2026-11-28 — Advanced re-review polish

**[NOTE]** Skill copies now uses clearer copy and place wording and catches duplicate new-profile names before saving. Phone touch targets are scoped to Advanced, including the review dialog. Five focused comparison retries passed under CPU load. The first full-suite attempt was interrupted after malformed inherited Git configuration affected its concurrent unittest run. The centred confirmation remains for Phase 8 review.

## 2026-11-28 — Paper follow-up recovery and layout

**[NOTE]** Returning to Needs attention or New skill refreshes folder
observations after a failed write. The project name and mark are consistent,
and the Read copy picker identifies project folders by path. The remaining
phone targets, disclosure chevrons, panel insets and welcome rows have
browser checks. Quality explains partial scans and text-length estimates in
plain language. See @docs/62-redesign-review-2026-11-28.md.

## 2026-11-28 — Paper write confirmations

**[NOTE]** Create and permanent removal confirmations stay visible and in
the live region on the route opened by the action. Leaving a screen clears
its old feedback. A late success stays with its original visit, while a late
write failure is still announced. Chromium covers creation, permanent
removal, manual navigation and navigation during the post-write file check.

## 2026-11-28 — Advanced Skill copies

**[NOTE]** The maintainer chose Advanced → Add skills → Skill copies for bulk
tags, profile assignment and operations on individual folders. A profile save
preserves the existing profile's description and native settings and refuses
a stale edit. Linked copies remain read-only. Chromium covers selection,
tagging, creating and extending profiles, inventory retry, and removal with
Undo.

## 2026-11-28 — Paper browser smoke

**[NOTE]** The browser smoke harness opens the Paper Skills route and waits
for two stable checks. It dismisses the welcome card for the populated
scenario so the table rows and Needs attention count are both exercised.
The empty and failure scenarios check their Paper messages. The harness
keeps its existing JSON fields.

## 2026-11-28 — Paper review fixes, Batch 2

**[NOTE]** New skill confirms before replacing edited instructions and
explains failed previews and creates. The Editor and phone touch targets
follow the approved rows. The Skills table uses chevron controls and falls
back to all desktop places for unknown filters. Needs attention names the
replacement source and blocks the fix shortcut after an error. Needs
attention and Trash reveal long lists in batches. The Skill page, Advanced,
Why and Trash use the approved terms and explain their evidence in plain
language. See @docs/62-redesign-review-2026-11-28.md for dispositions.

**[NOTE]** A Node benchmark of square statuses and row verdicts for 10,000
synthetic skills measured 340 ms before and 98 ms after, using medians of
five timed runs per revision. The browser now renders the Working indicator
on visible cells while retaining its existing status and verdict data until
the filesystem refresh. This benchmark measures model work only.

**[NOTE]** The final tree passed 2,561 tests on each of Python 3.11–3.14
(13 skipped on 3.11–3.13 and 12 on 3.14), all 124 Chromium checks,
the focused Firefox popup check, both smokes, documentation, tokens,
complexity, and Ruff. Synthetic screenshots cover both themes at 390,
1,280, 1,440 and 1,920 px.

## 2026-11-28 — Paper review fixes, Batch 1

**[NOTE]** First launch shows the detected folders and the A16 welcome card.
The Paper disclosure icon keeps its size across the reader, Editor, Trash
and tool and Settings rails. Old Skills routes replace their history entry
with the Paper table. The Skill page’s Read copy picker retains access to
same-name copies, including reloads from an exact tool result.

**[NOTE]** Doctor separates index health from its broader findings and
links to Needs attention when there are items. Why checks existing copies
first and links to the Skill page. Trash receipts, backup reviews, Needs
attention errors, and success notices clear on navigation. In-flight write
failures still appear when they finish. See @docs/62-redesign-review-2026-11-28.md.

**[NOTE]** Commit `6e0fa71` passed 2,560 tests on each of Python 3.11–3.14
(13 skipped on 3.11–3.13 and 12 on 3.14), 113 Chromium browser checks,
both smokes, documentation, tokens, complexity, and Ruff.

## 2026-11-28 — Redesign review at Phase 5

**[NOTE]** Five parallel read-only reviews covered design fidelity, UX,
frontend code, backend data safety, and process and docs. They checked the
build at `3c67c42`. Findings are in @docs/62-redesign-review-2026-11-28.md.
The fix-now items are:

- the 6 px disclosure chevron caused by the classic `styles.css` override;
- the first-launch screen not matching A16;
- links into classic views (Exact instances, Agents overview, Sync map);
- Doctor's index pill contradicting its own findings;
- Why isn't it running? opening on a non-problem;
- state carrying over between routes.

The backend found no data-loss path and no locked-constraint change. On
Python 3.12 the suite ran 2,557 tests, OK, 13 skipped. Python 3.11, 3.13 and
3.14 and the Chromium e2e were not re-run.

## 2026-11-28 — Paper Advanced directory

**[NOTE]** The maintainer approved Q2. Advanced groups existing tools by
task, keeps Settings and What to track available when tool groups are off,
and preserves the directory search when returning from a tool. The Add
skills switch now controls Update from folder. Doctor has its own report
in Check my setup and uses the existing hygiene API.

**[NOTE]** The maintainer requested all current work be pushed to main,
including the older handoff package. The S9 screen remains ready for review.

**[NOTE]** Local verification passed on Python 3.11–3.14 and in all 104
Chromium checks. Advanced is ready for the maintainer's S9 screen review.

## 2026-11-28 — Phase 4 passed hosted CI

**[NOTE]** Needs attention and Trash & backups landed at `382364b` on `main`.
All 17 GitHub CI jobs passed. The Advanced tool mapping decision (Q2)
precedes Phase 5 implementation.
[GitHub CI run](https://github.com/udayvarmora07/jackfield/actions/runs/46113385797).

## 2026-11-28 — Paper Trash & backups

**[NOTE]** The maintainer approved Needs attention and delegated the scope
and restore-conflict choices. Trash & backups shows a unified library and
agent list. Restore addresses the exact saved copy and preserves it when
the destination is occupied. Permanent emptying applies to the library.
Checked library imports preserve the reviewed action for each entry and
keep existing folders when an addition's destination becomes occupied.
The download date and size are shown after browser handoff and stored per
browser.

**[NOTE]** Local verification passed on Linux with Python 3.11–3.14,
including 103 Chromium checks and headed zoom at 200% and 400%. The
maintainer approved Trash & backups for Phase 4 integration.

## 2026-11-28 — Paper Needs attention

**[NOTE]** The redesigned screen uses the same per-place issues for To fix
and the navigation count. Review shows the exact folders and document
comparison before checked replacement. Skipped issues remain selectable.
Verified repairs appear under Fixed, and Undo checks the installed tree
before restoring the prior folder. Binary and ambiguous copies keep manual
guidance.

## 2026-11-28 — Phase 3 passed hosted CI

**[NOTE]** Commit `614bc4b` landed as a fast-forward on `main`. All 17 GitHub
CI jobs passed, including the cross-platform suites and the browser run.
[GitHub CI run](https://github.com/udayvarmora07/jackfield/actions/runs/46056334181).

## 2026-11-28 — Editor approved for Phase 3 integration

**[NOTE]** The maintainer approved the Editor checkpoint. A failed staging
cleanup after publication now leaves confirmed saves and their Undo receipts
in the response. Jackfield records the leftover staging path for diagnosis.

## 2026-11-28 — Editor saves to missing places

**[NOTE]** The Editor now lists missing writable places unchecked. Save
publishes the edited document with the source’s supporting files. The
server verifies the exact source document and each observed destination
root. It refuses occupied destinations and returns a tree receipt for
every confirmed addition. Undo restores existing snapshots and moves an
added folder to Trash while its tree still matches the receipt. A failed
index update after a successful move returns the actual Trash path.

## 2026-11-28 — Paper review and Phase 3 integration

**[NOTE]** The integration includes the four-artifact review corrections and
the Skill page, Editor, New skill page and per-skill diagnosis completed so
far. Saving an edited skill to a new location remains open in @build-progress.md.

## 2026-11-27 — Exact Skill page documents and Details

**[NOTE]** Read and File text use the same on-disk document from the selected
folder. Details shows supporting-file line counts where available and the
personal Claude Code skill listing estimate. The reader checks the selected
folder and hash before showing the document. An out-of-date library index
can no longer supply the Skill page’s rendered body.

## 2026-11-27 — Paper everyday skill workflows

**[NOTE]** The working tree has the Paper Skill page, Editor, New skill page
and per-skill diagnosis. The reader reuses the Skills table’s checked changes.
Editor writes and Undo verify an exact folder and document hash. The create
preview uses the same serializer as the write, and the diagnosis distinguishes
observed settings from unknown runtime behavior. The open acceptance items are
recorded in @build-progress.md.

## 2026-11-27 — Phase 3 status check

**[NOTE]** Updated the project status board to show Phase 2 on `main`, the
four-artifact corrections in the working tree, and the Skill page as the first
Phase 3 task. The build plan lists the four browser flows required to close
Phase 3. See @project-status.md.

## 2026-11-27 — Paper and tracking corrections from the four-artifact review

**[NOTE]** Skills now reports Claude Code's observed Off declaration and
OpenCode's Deny rule. Replacement previews state how each affected skill file
will be switched. The two-version panel reads both versions and marks their
squares on hover and focus. Below 900 px the panel is a sheet and returns focus
to its opener. The Skills table now hosts the stop-tracking confirmation and
project-picker shortcuts. The navigation count uses the same evidence across
routes, and Undo stays available while the user is on the page.

**[NOTE]** Tracking Undo uses the revision of the save it reverses. The write
response carries that operation's revision even if another writer advances it.
Readable broken settings get a private backup. Links, non-regular entries
and oversized files are moved aside intact. An incomplete folder scan
withholds exact disappearance counts. The favicon uses the kit's small mark,
the data-root example resolves correctly, and the tests check inline tokens,
the replacement file state and the browser latency budgets.

## 2026-11-27 — Paper redesign Phase 2 Skills table

**[NOTE]** The Skills route now opens the table and its selected-square
panel. The phone-width list shows one agent and opens a modal sheet. The
artifact review checked the approved local v13 tokens and v58 boards against
the implementation and consulted the corresponding Claude session records.
It fixed wrapped agent-folder headers and keyboard focus after choosing a
“Did you mean” search suggestion. See @build-progress.md.

**[NOTE]** The table uses existing checked batch operations and exact Trash
entries for copy changes. Regression cases exercise a populated folder
appearing during Sync, a dangling destination link, and permissions changes
invalidating a reviewed batch. The guarded Undo checks the replacement
before moving it to Trash and putting back the saved folder.

**[NOTE]** All 87 Chromium scenarios and the Python 3.11–3.14 discovery
suites passed locally. Retrying the live design references in the regular
Chrome profile verified the Shadows values, the canvas artboard list, and the
naming and brand-kit guidance. The exported boards still support comparison
of prototype screen content.

## 2026-11-27 — Paper redesign Phase 1 shell

**[NOTE]** Added the four-place desktop and phone navigation, hash router and
redirects, shared dialog and Undo components, search and command palette, and
Not found screen. Existing Agents overview and Sync map workflows are
available from Skills views during the transition. Browser regression checks
cover search and navigation, including clearing URL filters on return to
plain Skills. See @build-progress.md for local and integration status.

**[NOTE]** The Python 3.11–3.14 suites and 78 Chromium scenarios passed
locally, along with smoke, static, HTTP and packaging checks. Search and Not
found were inspected in both themes at desktop and phone widths.

**[NOTE]** The integration review found draft loss on Back and Cancel, a
late template response that could overwrite typed instructions, and a direct
editor route that could not retry a failed read. Added browser regressions and
fixed these cases. A tracking form also retains input when only the hash query
changes.

**[NOTE]** Phase 1 reached `main` as `72401c7` after local verification of
the staged tree. All 17 GitHub jobs passed, including the Linux, macOS,
Windows and headless Chromium suites.
[GitHub CI run](https://github.com/udayvarmora07/jackfield/actions/runs/45997716936)

## 2026-11-27 — Paper redesign Phase 0 foundations

**[NOTE]** Imported the approved v13 design-system export into the current web
UI. The generated token sheet changes both themes through temporary aliases.
The app uses the approved Jackfield lockup and monochrome agent marks, and
ships the IBM Plex subsets with their licence. The contrast and package checks
cover the new assets. The Turned off filter now includes mixed-state copies,
and Contradiction check recognises unqualified tabs versus spaces directives.
See @build-progress.md for the remaining screen work.

**[NOTE]** The browser fixture now runs from an empty project inside its
temporary home. The existing checkout's installed project skills were changing
search matches and Add to agent targets. All 71 browser checks passed after
isolation. The Python 3.11–3.14 suites, smoke checks, token and documentation
checks, and pinned wheel and sdist clean installs also passed locally.

**[NOTE]** Phase 0 reached `main` as `c3087ec` after the staged snapshot passed
the local verification ladder. All 17 jobs passed on GitHub, including the
Linux, macOS, and Windows suites.
[GitHub CI run](https://github.com/udayvarmora07/jackfield/actions/runs/45982680566)

## 2026-11-27 — Redesign status board refreshed

**[NOTE]** Updated `project-status.md` and `project-status.html` from the approved
v13 design system, v58 screen inventory and current build checklist. The board
records Q3 as settled, flags the older handoff package, and points to Phase 0
when the maintainer resumes implementation.

## 2026-11-27 — Brand working files and project status committed

**[NOTE]** Committed the remaining brand exploration files in `branding/jackfield/`
(work boards, Field J variants, concept sheet, kit check, shelf and test sheets,
and `renders/`) plus the root `project-status.md` / `project-status.html` board.
Before commit: gitleaks found no leaks, and a scan found no emails other than the
`alex@example.com` placeholder, no home paths and no PNG text metadata. Per Q8,
`handoff/` (and its zip, a byte-identical copy of the folder) stays out of git.
No product code changed.

## 2026-11-27 — Redesign decisions Q1, Q3, Q4, Q8

**[SPEC]** The maintainer chose the recommended answers: Cursor and custom-agent squares say On
with "settings aren't checked" in the panel (Q1); the token gate reads `design/tokens.json` and
`DESIGN.md` becomes a guide without colour values (Q3); Off in settings does not count in Needs
attention (Q4); `requirements.md`, `ui-progress.md` and `designs/final/` are committed after the
sample home path in four boards was changed to `/home/you/` (Q8). Recorded in
@docs/redesign-build/09-open-questions-and-risks.md.

## 2026-11-27 — Redesign build spec

**[NOTE]** Added @docs/61-redesign-build-spec-2026-11-27.md and ten files in
`docs/redesign-build/`: the plan to build the approved redesign (design system
v13, canvas v58) into `skillsmgr/webui/` without a build step or new backend
routes, in phases 0–8. Sources were read on 2026-11-27: the design system
artifact (tokens, README, 18 component guides, `bundle.css`), all 25 light
boards in `designs/final/` (byte-identical to the canvas; sampled sha256), the
briefs, and the current code (routes, model, API calls, packaging and the 12
test files that read the frontend). No product code changed.

**[NOTE]** Findings recorded in the spec: the handoff package is stale (DS v11,
14 screens); the Advanced board lists 11 tool rows while the app has 21 tool
ids (Q2); Cursor and custom agents have no settings reader, so whether their
squares may say On is open (Q1); `requirements.md`, `ui-progress.md` and
`designs/final/` are untracked although the spec cites them (Q8); two board
pairs hard-code a sample home path with the maintainer's first name in their
scripts.

## 2026-11-27 — Seven-day session audit, repository cleanup, suite isolation

**[NOTE] Audit.** All 16 Claude sessions of 2026-11-20…27 (and the Codex
sessions that resumed two of them) were read against `main`. Every change they
made is on `main` and `origin/main`; CI is green on `10e4aec`. The two sessions
that ended mid-work (2026-11-22 AI QA batch 3, 2026-11-23 UI pass) were finished
in `bd67b89` and `f814d4f`/`0766a0f`.

**[NOTE] Cleanup.** Removed the worktrees and branches whose work was already
on `main`: `claude/ci-portability-4e60d5` (every patch on `main`),
`claude/list-perf-965a4d` (landed as `82a4bfd`/`5db30c6`) and the agent
worktree `agent-a08c0fe58a3d5c3ea`, whose uncommitted diff is on `main` in
`868e67a`, except a stat-counting fixture that `487de61` replaced on purpose.
Deleted the two stale Dependabot branches (PRs #16 and #18 closed; `main` pins
`checkout` 7.0.1 and `setup-node` 7.1.0). Each tip and the worktree diff are
kept under `refs/wip/branches/*` and `refs/wip/stale-worktrees/agent-a08c-20261127`.
The installed third-party skills in `.agents/skills` and `.claude/skills` are
excluded locally (`.git/info/exclude`), not committed.

**[SPEC]** The unit suite no longer treats the checkout as a project.
`tests/test_00_portable_environment.py` wraps `scopes._cwd()` so that, while the
working directory is the repository root, project scopes read an empty folder.
Before this, those installed skills made 15 "all scopes" tests fail locally
while CI (a clean checkout) stayed green. Tests that `chdir` or patch `_cwd`
are unaffected; `test_the_checkout_is_not_a_project_but_other_folders_are`
covers both sides.

## 2026-11-27 — Skills Manager renamed to Jackfield

**[SPEC]** The owner approved renaming everything user-facing (2026-11-26):
the CLI is `jackfield` with `skills-mgr` kept as an alias (both are console
scripts for `skillsmgr.cli:main`); the web UI title, header, library mark,
messages, README, current reference docs, installers' text and the shipped
skill (`skillsmgr/examples/jackfield-management/`) use the new name.

**[SPEC]** Data is never moved. `paths.data_dir()` appends `jackfield` for a new
install and uses an existing `<base>/skills-manager` in place when no
`<base>/jackfield` exists. `JACKFIELD_DATA`, `JACKFIELD_REGISTRY_TOKEN` and
`JACKFIELD_AI_ENV_KEY_ENDPOINT` win; the `SKILLS_MANAGER_*` names are still read
when the new one is unset (an explicitly blank AI endpoint variable stays off).

**[SPEC]** Kept on purpose: the internal module `skillsmgr`, the backup format id
`"app": "skills-mgr"` (old backups restore), the index file `skills-manager.db`,
the API `consumer` value `skills-manager`, install markers and temp prefixes,
and every dated or archived document. The PyPI distribution stays
`skill-control-plane` until the release that publishes `jackfield`; installers,
`tools/verify_published.py` and trusted publishing switch with that release.

**[NOTE] Repository and checkout.** GitHub `udayvarmora07/skills-manager` is now
`udayvarmora07/jackfield`; the old web, clone and raw URLs redirect. The local
checkout moved from `~/skills-manager` to `~/jackfield`; `~/skills-manager` is a
symlink so existing sessions, worktrees and tool configs keep resolving, and
`git worktree repair` updated the three `.claude/worktrees` and
`~/overnight-ui/worktree`.

**[NOTE] Remaining names.** The design and UX briefs, `.ui-craft/`, `TODO.md`/`PLAN.md`
paths, the e2e npm package (`jackfield-e2e-tools`) and the brand kit now say Jackfield.
`check_docs.py` checks README links against the `udayvarmora07/jackfield` prefixes; with the
old prefixes it had silently stopped checking all 37 README links after the repository rename.
Local folders `~/jackfield-artifacts`, `~/jackfield.worktrees`, the Codex handoff and bundle,
and `~/.local/share/jackfield-devtools` were renamed (dated docs still name the old paths).

**[NOTE] Defects found while renaming.** (1) In-process `--data-dir` set the data
variable for the rest of the process; with a new higher-precedence name the leak
pointed 478 tests at deleted temp roots. `cli.main` now scopes the override to
one command (`_scoped_data_env`). (2) The suite clears an inherited
`JACKFIELD_DATA` (`tests/test_00_portable_environment.py`) and the harnesses set
both names, so a developer's own setting cannot aim tests at their library.
(3) The unsafe-root hint first suggested a base that resolved back to the same
unsafe legacy folder; it again names a fresh private subtree.
`tests/test_jackfield_rename.py` pins the fallback, precedence, symlink handling,
the no-leak rule and both legacy variables.

## 2026-11-26 — Jackfield name study and brand mark

**[NOTE] Name.** "Skills Manager" stops fitting once MCP servers arrive. A naming
pass (Igor's name types, Lexicon's process, Neumeier-style criteria, dev-tool and
rename case studies) checked 40 candidates against PyPI, npm and GitHub's agent
space. The owner shortlisted Shadowboard, Tackleboard, Jackfield and Patchbay;
**Jackfield** scored highest (32/35). Shadowboard was dropped because "shadow MCP
servers" is OWASP MCP09:2025. The product is **not renamed in code yet**, and no
trademark or domain search has been run. Research and scoring:
https://claude.ai/artifact/Aag9hffBrvbZhQpmgSGPnB (private).

**[NOTE] Mark.** The vetted MIT `logo-design` skill (kaankiziltug/logo-design-skill
at e9eaddc0789) is installed in `.claude/skills/logo-design/`. Five directions,
then seven variants of the owner's pick (Field J), were tested at 16–64 px, in
one colour, reversed and against real marks. The owner chose **B7 Quiet soft J**:
a 3×3 field whose lit cells spell J, three quiet cells, and one blue jack.
Kit: `branding/jackfield/kit/` (SVG masters, PNGs, web icons, board,
`GUIDELINES.md`); guide: https://claude.ai/artifact/C2DFx7Tp3SNYUEmawBgm3G.

**[NOTE] Wired in.** `skillsmgr/webui/logo.svg` (favicon and README image) is the new
mark on the same 32-unit grid (viewBox unchanged, so `BrandMarkTests` holds),
adaptive to the OS colour scheme. The header mark in `index.html` uses the same
paths coloured by tokens: `--ink`, `--brand` for the jack, `--line` for the quiet
cells. The jack therefore shows the current teal `--brand` in the app until
design system v11 (blue `#2D58D0`) lands; the standalone `logo.svg` uses the kit blue.

## 2026-11-26 — Agent tracking web UI

Mapped the approved Agent tracking screens onto the shipped UI (option A): What to track at
`#/settings/tracking` with Add other agent / Edit and Add project folder
(`index.html` markup, `trackingMixin` in `app.js`), Sync map column ▾ menus
whose Stop tracking confirm opens in the map's side panel, the Skills project
picker and notices (Found agent, broken file, missing project, no agents),
Tools hiding switched-off groups with a Turn it on page, a Tools → Settings
"What to track" row, and palette entries. `model.js` gains `agentMark` (marks
for agents the table doesn't list). Every change is one revision-checked PUT
with Undo; only the newest change keeps its Undo, because Undo restores the
whole earlier document. Failures, including 409, show beside their row.

Verified by hand in the built-in browser on the seeded e2e fixture: stop and
Undo, the panel confirm (focus to its heading, Esc back to ▾), add Kilo with
live checks, tool groups off/on, the project picker, the Found Gemini notice,
a 409 from a file changed on disk, a broken file and Reset, and no horizontal
scroll at 375 px. `tools/e2e_v2/browser.cjs` gains two tests (stop tracking
with Undo; add then remove a custom agent) and the tracking pages join the
overflow sweep; `run.py` seeds `~/.kilo/skills`.
`tests/test_v2_interface_contracts.py` now allows the documented
`/api/tracking` family.

Fixed after the first e2e run: `refresh()` had awaited the tracking report, so
every refresh took as long as its slowest read; "Backup download/import"
failed because its second file was picked while the first import's refresh
still held `busy`. The report now loads alongside, never blocking the skills,
and a sequence number keeps an older read from replacing a newer read or a
save's answer. The column menu and project picker follow the WAI-ARIA menu
button pattern: focus moves to the first item on open, arrows move, Esc returns
to the button, Tab out closes. "Add-to-agent single target is selected and
creates a copy" fails on untouched `HEAD` too (checked on a `git archive HEAD`
copy with the repo-root skill folders present), so it was not caused here.

The maintainer confirmed A ("A: fit shipped UI") afterwards. Per its second
condition, both stop-tracking confirms gained the mini table preview: today's
columns and their skill counts, the leaving one struck through and hatched.

An independent review (Sonnet subagent) found state bugs, all fixed:
- Undo is not offered when removing a project folder or custom agent whose
  folder is gone (the server would refuse to re-add it).
- An "Only <agent>" Skills filter resets when that agent leaves.
- Switches and radios re-render after a failed save.
- Failures off the What to track page show as a toast.
- Undo waits while another save runs.
- Focus returns to the picker button after a choice.
- The info lines sit outside `role="menu"`, and Home/End work.
- The column menu is placed on the viewport, so the scrolling table no longer
  clips it.
- Names compare with spaces collapsed, as the server does.
- A folder check for earlier text can't land.

A full e2e run then caught a regression the manual checks had missed: the
shared dialog read `dialog.columns.length` for every dialog, so every other
dialog failed to render (14 tests). It is guarded now. "No uncaught page
errors" stayed green throughout: a Vue render error is not a page error, so
that check can't see this class of failure.

"Backup download/import" raced the first import's refresh, which holds the
disabled picker for about 50 ms. It passed or failed by timing. The test now
waits for the picker to be enabled before the second pick.

Final run: 69 pass. Two fail, and both fail on an untouched `HEAD` copy too:
"Header search reopens…" and "Add-to-agent single target…".

## 2026-11-26 — Agent tracking backend

- New `skillsmgr/tracking.py` (named by the signed-off contract) for
  `<data>/tracking.json`: hand-readable, home-relative paths, atomic write with
  mode 0600 under the cross-process mutation lock, `revision` checked (stale →
  409 "These settings changed in another window."), a broken file shown as
  "track everything found" and copied to `<data>/tracking.broken-<stamp>.json`
  before the first new save.
- Routes: `GET /api/tracking` (settings plus live report: per agent found /
  folder status / skill count / skills only here / folders read / also reads;
  Shared folder; project folders; newly found agents), `PUT /api/tracking`
  (whole document, every rule re-checked; Undo = PUT the previous one) and
  `POST /api/tracking/check-folder` (read-only; counts skill folders by
  existence of `SKILL.md`, never opens a file).
- `scopes.known_scopes()` gains an optional overlay that only the web server
  binds per request thread, so `/api/scopes`, stats, skills, search, tokens,
  batch, sync and per-skill writes filter or refuse untracked agents on the
  server ("Cursor isn't tracked…"); custom agents get a writable flat scope;
  project scopes follow `projects.showing`. The CLI binds nothing, so
  `--scope` is unchanged. A missing file reproduces today's view exactly.
- Hostile review fixes before declaring done: a hand-edited file can't point a
  custom agent or the shown project outside the home folder (left out of the
  view, never writable); the home folder is never auto-listed as a project;
  links inside a tracked agent into an untracked agent's folder still read as
  the tracked agent's skill; agents on the page at the first choice count as
  seen, so the "Found Gemini" notice fires only for later arrivals.
- Complexity ratchet: `known_scopes`, `_route_library_get`, `_route_new_post`
  and `_route_put` were split into helpers; their baselines go down, none up.
- Found while verifying: the repo-root `.claude/skills/` and `.agents/skills/`
  installed on 2026-11-24 are picked up as start-up project scopes, so 15
  existing tests fail when the suite runs from the repository root — on an
  untouched `HEAD` checkout too — and pass from a clean working directory.
  Not caused by this change; left as is.
- UI not started: the approved screens assume the unshipped "one table"
  redesign; waiting on the maintainer's choice (see `task.md`).

## 2026-11-24 — Install AI Tooltip project skills

- Installed `uxui-workflow` and all 12 skill folders from `ai-tooltip-skill-set`
  under both `.agents/skills/` and `.claude/skills/`. The upstream skill files,
  phase references and per-skill `LICENSE.txt` notices are copied unchanged.
- Sources: [AiTooltip/uxui-workflow](https://github.com/AiTooltip/uxui-workflow)
  at `2f507d7c50efaaaefc7a05e16aecbc8b4aa6df18` and
  [AiTooltip/ai-tooltip-skill-set](https://github.com/AiTooltip/ai-tooltip-skill-set)
  at `e200967b38c4d4193af21c71c96e431cfc15eee8`.
- Codex's current project skill root is `.agents/skills/`; Claude Code's is
  `.claude/skills/`. Other agents that implement the shared project skill root
  can discover the `.agents/skills/` copies. The skill sources remain Claude
  authored; UI steps that depend on Claude Design may need the documented HTML
  fallback in other agents.
- Verified all 13 skills in each root and compared the copies with the cloned
  source trees. No automated tests were run; this change only adds skill files
  and project delivery records.

## 2026-11-24 — Repeat UI and workflow audit

- Sync map actions wrap within the side panel. An inventory with tied copies
  exposed a clipped Inbox link at a 1366-pixel viewport.
- Browser Back closes an idle dialog from the previous page and moves focus
  to the destination heading. Unsaved editor changes still trigger a discard
  confirmation.
- The AI draft scope selector uses singular wording for a one-skill library.
- Browser regressions cover a tied-copy panel at 1366, 1024 and 320 pixels
  and the Back sequence from an open New skill dialog.
- Repeat verification passed 70 Chromium and 69 Firefox scenarios, plus
  2,473 Python test cases with 13 skips. Chromium included real 200% and 400%
  zoom. The audit recorded five visual checks per image for 85 captures.
  Axe reported zero violations across 124 page and 14 dialog scans.

## 2026-11-23 — Desktop UI and workflow audit

- Empty Home, Skills, Inbox and Sync map states now describe the observed
  state and offer relevant actions. The populated Home cards show a navigation
  affordance, and Skills sorts controls and status counts into readable rows.
- Exact-copy reviews keep their heading and actions in view while long
  selections scroll inside a keyboard-focusable list. Checkbox accents follow
  the app palette.
- The reader exposes copy selection and highlighting alongside the document
  at laptop and narrow widths. The editor has labeled formatting controls, a
  shared Write/Preview switch and an in-flow save area on shorter screens.
- The header command palette has a pointer entry. Global search clears stale
  Skills filters, arrow selection stays in view, and single-key shortcuts
  respect focused controls. Search and the reader tree omit non-skill
  observations. Reader history is refreshed on skill navigation.
- Trigger, eval, budget, overlap, description and contradiction previews must
  still match the displayed inputs before the UI permits a model send. Late
  estimates are discarded when their inputs change. The Trigger test picker
  hides records ineligible for simulation.
- Reference decisions came from Linear's empty and detail states, Raycast's
  grouped keyboard search and Primer's data-table guidance. Skills Manager
  retains its own desktop layout and the tokens in DESIGN.md.
- Verification covered 2,473 Python test cases with 13 skips, 68 Chromium
  scenarios, 67 Firefox scenarios, both smoke suites, and 16 HTTP contract
  requests. Chromium ran 200% and 400% zoom checks. Automated accessibility
  scans covered 31 views in both themes at 1366 and 320 pixels. The separate
  visual log records five checks on each of 81 captures. Model-enabled browser
  scenarios used synthetic responses.

## 2026-11-23 — One interface at `/`, desktop-first redesign pass

- The classic interface is removed. The interface moved from `webui/v2/` to
  `webui/` and is served at `/`; `/index.html`, `/v2`, `/v2/`, `/classic` and
  `/classic/` answer a 307 to `/` with fixed local locations. `/v2/<asset>` still
  serves old asset links. Classic-only tests (131), `tools/e2e_classic` and
  `static/fonts/plex.css` are deleted; shared domain, preference and renderer
  tests are kept, and the exact state-label map test now loads `domain.js`
  directly.
- The look follows `DESIGN.md` again, rewritten for the one interface: cool
  bone ground instead of cream, IBM Plex Sans (vendored) instead of Jakarta and
  Newsreader, Plex Mono for every identifier, ink primary buttons, a teal signal
  ink for focus, the current tab and counts, and a cool graphite dark theme.
  `check_design_tokens.py` reads the current tokens (light and dark) and passes.
- Desktop first (the server is loopback-only, so users are on laptops and
  monitors): Home agent cards use an auto-fill grid with meters on the card
  floor; the Skills header fits a 768px screen; the reader shows the skill's real
  name in mono and folds long descriptions; code blocks scroll sideways; the Sync
  map fits six agents at 1280px and is capped on wide screens; Recovery stacks
  its short cards; Tools pages share one frame with a pinned "All tools" link.
- Quality renders findings 50 at a time (a 2,000-finding library was a
  110,000px page). Validate a copy and Update from folder filter their copy
  pickers instead of listing 2,077 options.
- The command palette is a grouped, arrow-key list that finds pages by
  synonyms; the header search lists matches instead of switching pages while
  typing. Disabled buttons look unavailable; focus rings are one teal ring.
- AI pages with AI off say what the tool does and show the three-step flow; the
  AI settings page leads with the no-login warning. Copy fixes: "Can't be read"
  everywhere, "Review" instead of "Fix it", sizes in KB/MB, no middle-dot
  metadata, no stale "both interfaces" or CLI-only wording.
- Evidence: two audits and seven five-pass reports covering 182 captures.
  The dark-core and laptop drafts were recovered from the interrupted session.
  The earlier Help capture showed search. Help, diagnosis and add-to-agent
  dialogs were checked separately with local fixtures.
- The resumed review made selected controls easier to see in both themes,
  restored the height of new-skill textareas, showed full reader paths by
  agent, and fixed the Quality evidence disclosure and narrow-window Tools
  navigation. Header search clears between reader entries, and Show all opens
  the filtered shelf even when a suggestion is highlighted. The diagnosis
  dialog groups its controls and makes the full skill path available on demand.
- Package commands again show offline registry evidence beside the exact
  command. Workspace inspection ignores duplicate submissions while loading.
- Porting notes and Explain risk findings work with AI off. When a model is
  configured, the app shows the optional request and destination before sending,
  and a change to the prompt or destination invalidates the preview.
- The browser harness checks the root interface on six viewports and five
  scenarios. The remaining migration tests and complexity baseline were
  brought into line with the root interface and simplified routing.

## 2026-11-23 — Render skill Markdown in both readers

- Both readers and the editor previews share the locally bundled markdown-it
  15.0.3 parser. Pipe tables have column headers and scoped scrolling. Nested
  lists, task checkboxes, quotes, headings and code render from Markdown tokens.
- V2 comparison marks rendered blocks and table rows. HTML remains text,
  images render as alt text, and v2 retains visible link destinations.
- Added the upstream bundle integrity check and packaged license notices.
  Regression cases cover formatting, content safety and narrow screens.

## 2026-11-22 — Resume AI feature QA

- Resumed the interrupted Claude QA on the staged batch 3 tree and recovered
  the CLI, browser, accessibility, static-analysis and mutation evidence.
- Fixed ablation intervals that changed when identical outcomes arrived in a
  different order. Section ablations match historical runs only for the same
  section and skill revision. Form feeds no longer create section boundaries.
- Kept fenced examples out of contradiction candidates when a would-be
  closing fence has an info string. Malformed judge and routing answers no
  longer abort the run when their IDs or choices are arrays or objects.
- Fixed home-relative source labels for Windows in contradiction reports,
  following failures in the hosted Windows suites.
- The CDP smoke harness opens a blank tab and attaches scenario hooks before
  navigating, so it starts one navigation per check.
- Description rewrites need usable held-out scores to recommend a candidate.
  The gap needs four answered prompts per split. Repeats of one prompt count
  once toward that minimum.

## 2026-11-22 — Rewrite gap, three-vote judge, reasons per rule

- Description rewrites report `gap` (seen-prompt score minus held-out score),
  flag `overfit` at 0.2 or more, and add a `selection_note` when several
  candidates compete on the same prompts.
- The contradiction judge accepts `votes` 3 (both orders plus a repeat,
  unanimous or `unclear`); `--votes` on the CLI and a v2 control.
- `density` rows count `with_reason`, `conditional` and `prohibitive`
  directive lines (wording effect from arXiv 2611.04367, model-dependent).
- New test: instruction text planted in a skill reaches the judge only inside
  an untrusted block and never in the system prompt.
- `ai ablate` adds `previous`: the last ablation of the same skill and section,
  labelled with its model and whether model and revision still match.
- Claude Code listing sections add `largest_cuts`, ranked across all entries,
  because `entries` stops at 100 and could hide the biggest cuts.
- Built in a separate worktree while the previous batch's ladder ran.

## 2026-11-22 — Thin descriptions, placebo arm, density and stale references

- Listing entries carry `thin` (description under the validator's 20
  characters, name-only entries excluded); `doctor --hygiene` and the v2
  listing card list them.
- `ai ablate --placebo` / `placebo: true` runs a third variant with the removed
  text swapped for same-length neutral filler and reports `placebo_statistics`.
- `ai conflicts` reports `density` per instruction file (dense above 150) and,
  with a project, deterministic `stale_references` for paths, package scripts,
  make targets and Python files that do not exist. On this repository it found
  none after bare file names were resolved project-wide.

## 2026-11-22 — Round 4 research and literature-driven statistics fixes

- Read Reddit, X, Instagram and Quora through the user's own Chrome (reports
  15–17) and about 58 papers (report 18); summarized in docs/60 "Round 4".
- `trial_stats` bootstrap resamples cases only and adds `min_detectable`;
  `ai ablate` adds the `untested` decision for all-pass or all-fail runs and
  states the detectable loss; the contradiction judge requires agreement in
  both orders. v2 shows the detectable difference on every statistics card.
- Two X handles of accounts that are not public figures were redacted from
  report 16.

## 2026-11-22 — Ablate and retire, contradiction check, description cuts (slice 2)

- `skillsmgr/ai_ablate.py` and `skills-mgr ai ablate` (docs/60 G1): replays a
  library skill's eval cases with the whole skill and without one section or
  the whole skill. Removal is proposed when the interval's upper end is at most
  10 points; a section removal is staged as an ordinary reviewed edit (Recovery
  labels it "removal test"), a whole skill gets the slash-only, disable,
  archive ladder. A `coverage_warning` says when no check ever differed, since
  such cases may not test the removed text.
- `skillsmgr/conflicts.py`, `skillsmgr/ai_conflicts.py` and `skills-mgr ai
  conflicts` (G2): heuristic candidate pairs between user and project
  CLAUDE.md/AGENTS.md/GEMINI.md and one scope's skills, with verbatim quotes and
  file line numbers; an optional AI judge sees only the two quoted lines.
  Skill-against-skill pairs were dropped after a run on a real 220-skill
  library produced 200 noisy pairs; with that rule it produced 5 plausible ones.
- Listing report (G3): `cut_chars` per Claude Code entry and per-skill
  `entries` for Codex; `doctor --hygiene` prints the five largest cuts and the
  v2 listing card lists them.
- v2 tool pages "Does it earn its place?" and "Contradiction check", checked in
  the browser against a fake local model. Fixed during that check: library
  skills had no body in the conflict scan (the index holds none).
- Command inventory is now 33 + 28 + 3 = 64.

## 2026-11-22 — AI features research loop

- Ran three rounds with twelve research agents across Reddit, X, YouTube,
  GitHub, Hacker News, forums, Bilibili, V2EX, Quora, Instagram, vendor docs,
  products and literature, using `opencli`, `agent-reach`, `agent-browser` and
  `gh` read-only. Instagram search returned nothing usable and Zhihu and
  Xiaohongshu were blocked.
- Fact-checked 30 weight-bearing claims: 23 confirmed, 7 partly right with
  corrections applied, none wrong.
- Consolidated proposals G1–G15 and a proposed slice 2 (ablate and retire,
  delivered-listing report, contradiction check) in
  @docs/60-ai-features-research-loop-2026-11-22.md, with sanitized raw reports
  in @docs/research/2026-11-22-ai-loop/README.md. Documentation only.

## 2026-11-22 — Honest AI test statistics and per-hunk accept (slice 1)

- Added `trial_stats.py`: paired lift over cases with a 95% bootstrap interval
  that resamples cases and trials, and a verdict of helps, hurts, inconclusive
  or ungraded. Fewer than three graded requests or four graded paired
  observations are always inconclusive, because repeats of one request say
  nothing about others. Simulation on known effects gave 95–98.5% interval coverage and
  a 0.7% false "helps/hurts" rate with no effect, which is conservative.
- AI evals and current-vs-proposed comparisons accept `trials` (1–5; v2 defaults
  to 3), shuffle call order, and report statistics, output-token regressions and
  assertions that never discriminate. Each eval repeat is its own iteration.
- AI edits list line hunks. Keeping a subset restages a fresh review with no
  model call and cancels the full proposal. Reviews and the snapshots they
  create carry AI provenance, shown in the snapshot list as "Before AI edit by
  MODEL: request · kept N of M changes".
- A hostile review found three defects, now fixed with regression tests: an
  uncapped diff (86 s on a repetitive 2,000-line body, now bounded), a hunk
  selection that could orphan or wrongly cancel a review, and a "helps" verdict
  from one request repeated five times.
- Verified in the browser against a local fake model: hunk selection, a
  12-call comparison with statistics, reviewed save, the Recovery label and
  repeated evals. Marked slice 1 shipped in
  @docs/59-ai-everywhere-research-2026-11-22.md.

## 2026-11-22 — Research AI across every feature

- Ran four sourced research passes (user demand, competitors, literature, AI UX
  patterns) and checked their reported gaps against the repository. Mapped all
  CLI and v2 surfaces to current and proposed AI support, and ranked 15 new
  proposals led by a library health and retire assistant, a model-upgrade
  recheck and repeated-trial statistics. Recorded the approval decisions they
  need. See @docs/59-ai-everywhere-research-2026-11-22.md. Documentation only.

## 2026-11-22 — Integrate AI authoring into the v2 skill lifecycle

- Added editable drafts with optional examples and confirmed trigger cases to
  New skill. Added selected-text and whole-body proposals to the exact-copy
  editor, with a current-tree check, explicit apply and Recovery snapshot.
- Integrated paired output comparisons, downloadable evidence, agent discovery
  and routing diagnosis, browser-local OpenCode trace reading, and a handoff
  from a failed request to the editor. Added shortlist preview and copy links
  to library search, plus cited explanations in Sync map and Inbox comparisons.
  See @docs/08-web-ui.md.
- Hostile review fixes: the edit preview plan now binds the selected offsets,
  so a repeated phrase cannot be swapped after preview. A failing second
  comparison model keeps the first model's paid results as a `partial` run with
  `alternate_error`, and results list every model used. A JSON `null` example
  counts as absent. Added plan-binding, second-model and CRLF round-trip tests.
  Verified: 2,494-test suite, docs, complexity, both smoke tests and the v2
  browser e2e suite (56 checks), rerun after the fixes with 2,500 tests.

## 2026-11-22 — Research AI authoring and the skill lifecycle

- Compared current AI workflows with user reports, vendor implementations and
  paired skills evaluations. Recommended in-context AI creation and exact-copy
  editing, followed by comparative tests and runtime diagnosis.
- Documented shipped capabilities, a ranked backlog, proposed acceptance tasks,
  and the limits of present simulation and native evidence. See
  @docs/58-ai-authoring-and-skill-lifecycle-research-2026-11-22.md.
- Passed the documentation consistency check and the focused AI verification
  runner, including 85 tests and the saved-evidence dry run.

## 2026-11-22 — Compare exact copies and review agent restores

- Applied the comparison research to Sync map and Inbox. Both show the
  actual copy paths and bounded Markdown changes, with aligned panes where
  they fit and a wrapped unified view on narrow screens. Inbox allows review
  of any affected target. Skills carries the typed name into Sync map and
  keeps the exact reader selection visible.
- Agent trash restores show the saved folder and restore coverage before the
  action. The dialog keeps the selected entry visible on failure. Agent trash
  read errors identify their scope and expose a retry. See @docs/08-web-ui.md.
- Exercised keyboard retry and cancellation, same-name restore selection,
  occupied destinations, and wrapped changes at 320 px and 390 px in Chrome.
  Checked comparison roles and change labels in the Linux accessibility tree.

## 2026-11-21 — Compare public Mobbin collections and narrow-screen diff views

- Opened public Mobbin collections and screen previews anonymously. Selected
  Intercom for keeping item identity and details together and Philips Hue for
  wording and actions after a failed read.
- Exercised Pierre Diffs, diff2html and Diffchecker in Chrome. Selected
  Pierre's single-column layout for narrow text comparison and documented
  its demo's inner scrolling and page overflow. Reviewed Kaleidoscope and
  Meld for file-level comparison and evidence coverage.
  See @docs/57-v2-mobbin-and-comparison-references-2026-11-21.md.
- Verified all three pages and five embedded captures in the editable
  Draw.io comparison board on 2026-11-22 without an account.

## 2026-11-21 — Repeat reference selection with live screens and source

- Replaced the initial reference shortlist with Zed Extensions, Obsidian
  Community, Playwright Trace Viewer and GitButler Operations History. The
  selection went through discovery, live walkthroughs or published product
  captures, and a comparison against alternatives.
- Reviewed pinned frontend source from GitHub and opened a synthetic
  comparison trace in the actual viewer. The trace showed different
  evidence in Before and After while retaining the selected action.
  See @docs/56-v2-reference-selection-loop-2026-11-21.md.

## 2026-11-21 — Study reference workflows for the next v2 design pass

- Compared live Raycast Store search, Astro's mobile page outline and a
  public GitHub Issues empty-result flow. Studied native and signed-in
  recovery, scope and triage flows through the vendors' guides.
- Measured current v2 positions at 390 × 844 CSS pixels in a synthetic
  workspace. Documented which patterns fit local skill workflows, which
  claims the references support, and what to test with participants.
  See @docs/55-v2-ui-reference-study-2026-11-21.md.
- Assembled 13 source-linked reference cards and eight screenshots into a
  five-page editable Draw.io board. Checked every page in the Draw.io editor
  without signing in.

## 2026-11-21 — Make Tools, Quality and Recovery easier to navigate

- Tools now filters its grouped directory by name or task. Narrow tool pages
  show an All tools link above the page title. The desktop sidebar scrolls
  independently when needed.
- Quality and Recovery provide section shortcuts that scroll and move keyboard
  focus without rewriting the route. Recovery uses a two-column layout when
  space permits and labels the library backup and full archive separately.
- Consulted Awwwards' Viture Dashboard for hierarchy, Godly/Recent Design's
  Sidebar Sub-Menu by Pranav Patel for grouped navigation, and Inspo's Raycast
  and Astro Docs results for search and section navigation. The changes use
  existing v2 layout, type and color tokens.
- The native desktop accessibility tree showed focus on the Findings heading
  after activating its shortcut. Axe 4.10.2 reported zero violations across the
  three changed pages at 320px and 1440px in both themes.
- Verified with 2,489 unit tests (13 skipped), 53 v2 browser scenarios,
  40 classic browser scenarios, both smoke tests and the documentation,
  design-token and complexity checks.

## 2026-11-21 — Close the delegated review and add library archiving

- Added explicit, previewed `archive apply` and guarded `archive restore`
  for a selected manager-library folder. The receipt binds the original
  name and reviewed bytes. The operation preserves companions and disabled
  state and refuses changed copies, links, pins, and occupied destinations.
  Staleness-based selection still requires independent continuity evidence.
- Direct keyboard and Orca review and a visual pass across 26 route and
  viewport combinations supported the release decision. The current tool
  tab stays visible on narrow layouts. Toasts no longer cover modal actions.
- Each of five synthetic pilot rehearsals restored the original Codex
  document and supporting file. Same-name Recovery entries now identify
  their order and target. The release decision uses synthetic and screen
  reader diagnostics. Participant research retains its consent protocol.
- The local suite ran 2,489 tests with 13 skips and no failures. All 51 v2
  browser scenarios and both smoke tests passed. Both exact artifacts
  passed clean installation and the 1.0.2 upgrade and restore rehearsal.
  The installed wheel also passed the archive and restore round trip.

## 2026-11-21 — Rehearse the v2 screen-reader walkthrough

- The desktop and phone Inbox links now use the same accessible name and
  pluralize the current count. The page skip link is inert while a v2 dialog
  is open and works again on dismissal.
- Chromium's accessibility tree and keyboard input verified the walkthrough
  on the synthetic pilot. The evidence and fixture instructions are in
  @docs/32-continuation-verification-2026-11-06.md. Spoken sign-off remains open.
- All 51 v2 browser scenarios passed, including the tool routes at widths of
  320, 768 and 1280 pixels in both themes. Both smoke tests and clean installs
  of the rebuilt wheel and source distribution passed.
- The navigation regression also passed in Firefox 151. The local suite
  ran 2,481 tests with 13 skips and no failures. Hosted macOS and Windows
  repeated the exact-artifact install, upgrade, restore and downgrade checks
  on `9a43357`.
  [Follow-up hosted rehearsal](https://github.com/udayvarmora07/skills-manager/actions/runs/44904992122)

## 2026-11-21 — Preserve shared-root pin evidence in the archive preview

- When equivalent scope scans resolve to one physical root, the consolidated
  archive row includes pins from the represented scopes and shows which
  scopes supplied them. A regression verifies that a Codex pin appears on a
  coalesced Claude Code row and no longer appears there after the roots diverge.

## 2026-11-21 — Record hosted rehearsal and fidelity preflight

- GitHub-hosted macOS and Windows passed exact wheel and source distribution
  checks and clean installs at `06943c5`. Both upgraded an existing 1.0.2
  library to 1.1.0, restored the 1.0.2 full backup in a fresh library, and
  reopened the original library after reinstalling 1.0.2. The run was
  manually dispatched for verification.
  [Hosted rehearsal](https://github.com/udayvarmora07/skills-manager/actions/runs/44903486924)
- The OpenCode-scoped simulator preflight matched all four synthetic listing
  entries and estimated three passes over 12 prompts with zero provider
  calls. The separate native replay reproduced eight scripted skill calls
  and four scripted no-call cases. The attended same-model comparison
  remains open. See @docs/48-ai-http-study-2026-11-17.md.

## 2026-11-21 — Preserve package-data bytes on Windows checkouts

- The hosted macOS release rehearsal passed at `1e8bcd1`. Windows failed
  the exact-artifact check before running the upgrade because Git converted
  the Bash completion file to CRLF. An isolated checkout with
  `core.autocrlf=true` reproduced the failure against the hosted artifacts.
- Git now keeps LF for both shell completions, the packaged example
  documents and the license. The verifier still compares exact bytes.
  [First hosted rehearsal](https://github.com/udayvarmora07/skills-manager/actions/runs/44903097110)

## 2026-11-21 — Fix Windows backup and uninstall failures

- Backup capture compares the creation timestamp reported by both path and
  handle stats on Windows Python 3.12 and later. This prevents false source
  conflicts on Python 3.14 while retaining the file identity, size and
  modification-time checks.
- Legacy PowerShell uninstall closes the distribution metadata reader before
  removing the verified environment. A handle probe reproduced the leak and
  checked the fix.
- The local suite ran 2,480 tests with seven skips and no failures. Both
  smoke tests, clean package installs and the upgrade rehearsal passed.

## 2026-11-21 — Restore the hosted Hurl check

- GitHub moved `ubuntu-latest` to Ubuntu 26.04. The Hurl 8.1.0 binary
  requires `libxml2.so.2`, so the HTTP job now uses Ubuntu 24.04 and
  installs its `libxml2` package. A version check tests binary startup
  before the fixture server starts.
- Hurl 8.1.0 started locally on Ubuntu 24.04 and all 16 requests passed.
  The CI and QA contract suite passed all 37 tests.

## 2026-11-21 — Fail backups with unreadable supporting folders

- Slim and full backups now report a supporting folder read failure during
  capture or verification. Previously both scans could omit the same
  unreadable directory and publish an incomplete archive. A failed scan
  preserves the existing archive and removes the staged file.
- With a real unreadable folder, the installed CLI exited with an error
  and kept the previous archive. The Web API returned HTTP 400 without a
  download. Python 3.12 ran 2,479 tests with seven skips and no failures.
  Archive contracts passed on Python 3.11–3.14. Both smoke tests, all 16
  Hurl requests, both artifact installs, and the 1.0.2 upgrade and downgrade
  rehearsal passed.

## 2026-11-21 — Verify backup checksums before restoring

- A full restore now checks recorded skill checksums before changing any
  skill, trash entry, template, or catalog file. A missing checksum remains
  valid for older backups. Ordinary imports still report per-skill skips.
- The installed CLI and REST API refused an archive with a mismatched
  checksum and preserved the existing data. The verified public 1.0.2
  backup still restored into the candidate. Both release artifacts and both
  smoke tests passed. Python 3.12 ran 2,478 tests with seven skips and no
  failures, and the archive contracts passed on Python 3.11–3.14.

## 2026-11-21 — Explain and retry backup conflicts in Recovery

- An export that sees a concurrent source change returns a `409` response
  with `backup_source_changed`. Recovery shows progress while preparing a
  download and a persistent retry message if the library changes. Both views
  block duplicate export actions while a download request is in progress.
- The REST regression verified that a real source change returns no
  attachment. Chrome passed all 50 v2 scenarios and 40 classic scenarios
  with 352 classic assertions, including the conflict and retry in both
  views. Python 3.12 ran 2,477 tests with seven skips and no failures. Both
  smoke tests and all 16 HTTP requests passed. The rebuilt wheel and sdist
  installed cleanly and the published-version upgrade rehearsal passed.

## 2026-11-21 — Check backup sources before publishing

- Export checks the membership of the selected roots and the paths and file
  revisions it captured. A detected change returns a retry message and leaves
  any previous archive untouched. Root membership checks also catch moves
  when directory timestamps are unchanged.
- Regression tests cover trashing and restoring a skill during export,
  changing and adding a supporting file, and downloading an empty library
  without creating its data directory.
- The installed candidate wheel preserved 10,000 supporting files through
  a full export and import. For that Linux fixture the median export time
  was 1.71 seconds, up from 1.51 seconds in the previous build over three
  runs each. Both release artifacts installed cleanly and the upgrade
  rehearsal passed. The full Python 3.12 suite ran 2,475 tests with seven
  skips and no failures. Both smoke tests and all 16 HTTP requests passed.

## 2026-11-21 — Protect managed state from backup destinations

- Backup and export preserve managed data such as pins, usage consent and
  undo receipts. Explicit archive paths under `backups/` and root-level
  `.tar.gz` names still work. A backup folder linked to another managed
  state directory is refused.
- Export writes to the checked physical parent. If the requested parent
  link is redirected during the scan, it returns the actual archive path.
- The installed candidate CLI preserved active pin and consent files when
  they were selected as output paths. Its default full export still worked.
  Both release artifacts passed clean installs and the published-version
  upgrade and restore rehearsal passed. The full Python 3.12 suite ran
  2,471 tests with seven skips and no failures. Both smoke tests and all 16
  HTTP requests passed.

## 2026-11-21 — Make the published-package quickstart safer

- The README starts with a read-only inventory. Bash and PowerShell examples
  create, trash, and recover a sample skill in a temporary manager library,
  leaving existing agent roots out of the write path.
- Repository documents and images use absolute URLs so the packaged README
  resolves them from PyPI. The documentation gate checks these URLs against
  the repository as well as checking internal headings.
- The Bash and PowerShell samples passed on Linux with the published 1.0.2
  wheel and the 1.1.0 candidate. Both candidate artifacts passed clean
  installs and contain the exact updated README. PyPA's renderer found no
  unresolved same-page links. Python 3.12 ran 2,467 tests with seven skips
  and no failures.

## 2026-11-21 — Preserve unrelated environments during PowerShell installation

- Added an ownership marker and a per-prefix lock to the PowerShell
  installer. It leaves unrelated environments and linked prefixes intact,
  and uses literal paths when removing an owned environment.
- Older installations in the default Windows path are recognized by the
  existing launcher and package metadata. An unmarked custom prefix lacks
  that ownership evidence and is preserved. The hosted workflow now runs
  the ownership tests with Windows PowerShell 5.1.
- PowerShell 7.4.20 on Linux passed the offline 1.0.2 to 1.1.0 upgrade and
  uninstall in a directory with spaces and brackets. A separate process was
  refused while the prefix lock was held. All 31 installer tests passed,
  and the Python 3.12 suite ran 2,466 tests with seven skips and no failures.
  Native Windows verification remains pending.

## 2026-11-21 — Preserve unrelated environments during POSIX installation

- The shell installer checks for a launcher collision before installing. It
  keeps existing foreign links and publishes a new launcher without replacing
  an occupied path. An ownership marker and per-prefix lock protect creation,
  retry and removal of the installer's virtual environment.
- Older installs still upgrade or uninstall when their launcher identifies
  the environment. The shell installer refuses unrelated virtual environments
  and leaves their files intact.
- The local 1.1.0 wheel passed offline install, legacy adoption, and uninstall
  with spaces in both paths. The rehearsal preserved an unrelated environment
  and a dangling foreign launcher. The Linux Python 3.12 suite ran 2,460 tests
  with eight skips and no failures. Installer tests passed on Python 3.11–3.14.

## 2026-11-21 — Preserve archive inventory across scope aliases

- The archive dry run uses the scope's discovery rules when a flat, grouped,
  or recursive scope shares a physical root. Project aliases participate.
  Equivalent stable scans share their inventory. Reader hints cover selected
  scopes observed at the same root.
- Candidate rows identify the relative skill folder, so grouped copies with
  the same name are distinguishable. An omitted unaddressable skill marks the
  inventory partial. Archive eligibility remains gated on continuous evidence.
- Both release verifiers now start virtual-environment creation through the
  resolved Python interpreter. The package check previously failed with a
  symlinked launcher even though the artifact itself was valid.
- The installed 1.1.0 wheel reported 10,000 distinct grouped folders through
  a project alias and flagged truncation at 10,001. Both packaged artifacts
  passed a clean install through a symlinked interpreter, and the upgrade,
  full restore and previous-version reinstall passed on Linux Python
  3.11–3.14. Python 3.12 ran 2,453 tests with eight skips and no failures.
  Both smoke tests and the 16 HTTP regression requests passed.

## 2026-11-21 — Wire HTTP regression contracts into CI

- Added a GitHub CI job that verifies Hurl 8.1.0 by SHA-256 before running
  the synthetic HTTP contracts. Failed runs with a JUnit report retain it as
  `http-contract-failures`.
- Added the Recovery contract for a skill named `purge`, checking that
  restoring it preserves unrelated trash. All four contracts and 16 requests
  passed locally. A deliberate wrong expectation confirmed the JUnit summary
  identifies the Recovery assertion and prints its actual and expected values.
- Verified the hash-pinned Keploy v3.7.13 Linux binary against a synthetic
  saved run in an isolated network namespace. The summary accepts its known
  cgroup startup warning in `--keploy` mode and names the failing
  `restore-skill` case with HTTP 200 expected and 404 observed.
- Verified the local workflow step against the upstream Hurl archive, a failing
  contract, and a corrupted archive. The Python 3.12 suite ran 2,448 tests with
  eight skips and no failures. The QA and workflow contract tests passed on
  Python 3.11–3.14. The new job still needs its first hosted run.

## 2026-11-21 — Rehearse upgrades before publication

- Added a reproducible upgrade check against the hash-pinned public 1.0.2
  wheel. It checks CLI state and exact document and supporting-file bytes for
  active, disabled and trashed skills, along with a saved template. It verifies
  a full restore in a fresh candidate library and reopening the original
  library after reinstalling 1.0.2.
- The release verification job now installs the same built wheel and source
  distribution and runs the upgrade check on Linux, macOS and Windows.
  A manual run stops after verification. Matching version tags still control
  attestation and the publication jobs.
  [Published 1.0.2 wheel](https://pypi.org/project/skill-control-plane/1.0.2/#files)
- The exact candidate wheel passed the upgrade, restore and previous-version
  reinstall on Linux with Python 3.11–3.14. The Linux installer also passed
  with Python 3.11 on a symlinked path, including removal of the launcher.
  The final Python 3.12 suite ran 2,445 tests with eight skips and no
  failures. Hosted macOS and Windows CI passed at baseline `80f1dd8`.
  The follow-up hosted rehearsal is recorded above.
  [Baseline CI run](https://github.com/udayvarmora07/skills-manager/actions/runs/44743791588)

## 2026-11-21 — Add developer HTTP regression reports

- Added an optional Hurl runner with synthetic Library, project discovery,
  and toggle contracts. Hurl 8.1.0 passed all three contracts and ten
  requests. The JUnit summary lists failed cases and their assertions,
  with a nonzero exit status for failures or invalid reports.
- Reviewed Snyk Agent Scan and Keploy's published source and data handling.
  The QA runner uses local synthetic requests and accepts JUnit reports
  exported from Keploy. The Linux release asset and official OCI layer timed
  out in this first check. The follow-up above records the native Linux export.
  [Developer QA guide](../tools/qa/README.md)

## 2026-11-21 — Observe standalone Gemini skill documents

- Doctor can report a Gemini or shared root's direct `SKILL.md` using its
  frontmatter name and exact file path. The observation is read-only.
  Managed-root reports omit standalone documents outside their allowlist.
- Archive preview marks manager inventory partial when it sees a standalone
  Gemini document. A recursive scope scan excludes the scope directory
  itself from its per-skill folder rows.
  [Gemini skill loader](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/skills/skillLoader.ts)
- Linux Python 3.11–3.14 each ran 2,439 tests without failures, with seven
  or eight skips. Both smoke tests and both package clean installs passed.

## 2026-11-21 — Verify the published-version upgrade path

- Installed the hash-verified public 1.0.2 wheel into an isolated environment,
  created active, disabled and trashed sample skills, then upgraded to the
  1.1.0 candidate. All three documents retained their exact bytes. A full
  backup created by 1.0.2 restored the same files into a fresh candidate
  library.
  [Published wheel](https://pypi.org/project/skill-control-plane/1.0.2/#files)
- Updated the README's supported-scope, diagnostic and recovery claims to
  reflect the shipped product boundaries.

## 2026-11-21 — Discover Gemini and Command Code project skills

- Workspaces previously recognized project-local Gemini and Command Code
  roots that were missing from the scoped CLI, REST inventory and archive
  preview. They now share the same project-root conventions. Shell
  completions include `project-gemini` and `project-commandcode`.
- Command Code finds skills in grouping folders in both its project and user
  scopes. Inventory and Doctor stop walking when they reach a skill folder,
  including a disabled one, so supporting files stay part of that skill.
  Gemini inventory uses immediate child folders.
  [Command Code docs](https://commandcode.ai/docs/skills)
  [Gemini loader](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/skills/skillLoader.ts)
- The installed CLI listed and opened both project skills. The REST test
  matched Workspaces roots and scope counts to the corresponding skill
  lists. Linux Python 3.11–3.14 ran 2,434 tests per interpreter with zero
  failures and seven or eight skips. Both smoke tests and both clean installs
  passed. Headless Chrome passed 49 v2 checks and 39 classic scenarios
  with 349 classic assertions.

## 2026-11-20 — Validate cached usage evidence

- Reproduced malformed scan summaries breaking consumers and cached summary
  fields claiming complete coverage. Cached reports now return documented
  observations only. A damaged summary is marked `cache-invalid` for its
  agent, and valid counts and other agents' summaries remain available.
- Saved count buckets require canonical UTC days and supported nonnegative
  counts. Legacy integer counts still load. A successful refresh can rebuild
  a damaged aggregate cache from the consented transcripts.
- On 2026-11-21, Linux Python 3.11–3.14 each ran 2,431 tests with zero
  failures and seven or eight skips. Both smoke tests, clean installs,
  offline AI verification, and an installed CLI check for usage reporting
  and archive preview passed.

## 2026-11-20 — Honor project lockfile write protection

- Vercel checks an existing lockfile's write permissions before replacing it.
  Skills Manager now checks write access before staging an apply and before
  publishing an apply or undo. Preview remains available for readable files.
  [Vercel lock source](https://github.com/vercel-labs/skills/blob/main/src/local-lock.ts)
- Two regressions reproduced apply replacing a read-only file and undo
  overwriting a file after write access changed. Both now refuse the mutation
  and preserve the file. Undo also preserves the receipt for a later retry.
- Linux Python 3.11–3.14 each ran 2,428 tests with no failures and seven
  or eight skips. Both smoke tests, package clean installs, and an installed
  CLI check for refused apply and successful apply and undo passed.

## 2026-11-20 — Recover interrupted native settings and project lock writes

- Both writers used to replace their target before a final receipt write
  could fail. New receipts retain the original bytes and identify the staged
  file before replacement. Undo checks that file's identity, content hash
  and permissions. Neither vendor file format changed.
- Interruption tests complete each rename, raise before apply returns and
  restore the previous file through undo. A separate byte-identical native
  replacement and a matching lock written after a failed publish are refused.
- The project-lock writer reads the staged revision after closing all write
  handles so Windows can report the final write timestamp.
  [Microsoft file times documentation](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times)
- Linux Python 3.11–3.14 each ran 2,426 tests successfully, including seven
  or eight skips per version. Both smoke tests and the clean-install wheel
  and sdist interruption checks passed. Receipts from the previous checkpoint
  restored the exact original files. A forced exit left the project lock's
  companion lock in place. Undo recovered once the test cleared that lock.

## 2026-11-20 — Keep pin undo available after an interrupted write

- Reproduced a pin being saved when finalizing its receipt failed. Undo used
  to refuse the pending receipt. The file now carries the exact plan ID and
  the pre-write receipt can be used once the new file is in place.
- Undo checks the current file, the matched plan and the retained preimage.
  An older interrupted unpin cannot undo a later unpin of the same skill.
  Earlier confirmed receipts still match by their saved hash. If updating a
  consumed receipt fails after restoring the pin, undo reports the successful
  restore and emits a diagnostic for the receipt.
- Both clean-installed packages restored the exact original pin file from a
  separate CLI process after interrupted unpin. Linux Python 3.11–3.14 each
  ran 2,423 tests with no failures, and both smokes passed.

## 2026-11-20 — Restore full archive metadata before replacing skills

- A full import used to replace active skills before a metadata write could
  fail and return an error without a skill result. The rollback group for
  trash, templates and catalog now completes first. A later per-skill
  replacement still produces an individual success or skip result.
- Fixtures deny a template copy and trash index update. The original skill,
  binary companion and history survive, and new skills are left uninstalled.
  A retry restores the archive. An active and trashed copy of the same name
  remain distinct and the active copy owns the index row.
- Duplicate trash or template labels now fail preflight before installation.
- Both failures reproduced on the previous checkpoint. Linux Python
  3.11–3.14 each ran 2,419 tests without a failure. Store and web smokes
  passed. Both unpublished 1.1.0 packages passed all four targeted
  full-restore checks after clean installation.

## 2026-11-20 — Keep failed imports from replacing skills

- Forced full imports check existing trash, template and catalog destinations
  before any active-skill installation. The metadata restore rechecks those
  destinations under its mutation locks before replacing them.
- Import writes the skill row and its history in the same SQLite transaction
  while the original files are still available for rollback. A regression
  test denies history inserts through SQLite and verifies that the original
  disabled document, binary companion, index row and history survive. The
  same archive imports successfully once writes are allowed.
- Both Recovery interfaces display the import result beside the controls.
  In Chrome, one real synthetic full import installed a skill, restored a
  trash entry, template and catalog, and reported why another skill was
  skipped. An invalid archive left an alert visible in v2.
- Linux Python 3.11–3.14 each ran 2,417 tests without a failure. Store and
  web smokes passed, as did 49 v2 and 39 classic Chrome checks. Both
  unpublished 1.1.0 packages passed five archive regressions after a clean
  install. The package, complexity, documentation, workflow and lint checks
  also passed.

## 2026-11-20 — Verify primary documents and protect backup destinations

- Reproduced an export that listed a skill whose document vanished after
  inventory. Export now validates the primary document bytes written for each
  active skill with the importer's rules. Missing or conflicting documents and
  empty listed trash entries fail before publication.
- Reproduced an explicit export into a live skill document. Destination
  validation now protects the library, recovery folders, catalog and SQLite
  files. A check of the resolved parent also covers writes through a directory
  alias while allowing ordinary backup destinations.
- Manifest and catalog JSON recursion errors use the existing import
  preflight diagnostics. Tests inject the decoder error and verify that no
  skill is installed.
- Linux Python 3.11–3.14 each ran 2,414 tests without a failure. Both smokes
  and the clean-installed wheel and source archive passed. The CLI refused
  a backup destination on a live skill, and the web route returned HTTP 400
  for an invalid document without sending an archive.

## 2026-11-20 — Preserve concurrent backups and validate archive paths

- Reproduced two same-second default backups returning the same path. The
  backup directory lock now covers name selection and publication after TAR
  verification. Existing names include dangling links, which reserve their
  own path without being followed.
- Six simultaneous processes with the same default timestamp published six
  different TAR files. All six passed archive validation.
- TAR and ZIP preflight reject a file that conflicts with an explicit or
  implicit directory before extracting members. On Windows the same checks
  reject reserved components, duplicate file names with different casing,
  and directory case aliases.
  [Windows filename rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)
- Linux Python 3.11–3.14 each ran 2,408 tests without a failure. The Windows
  path rules were exercised in the Linux suite. Both smokes, the shared
  temporary-root test, documentation, complexity, workflow and lint checks
  passed. The current tree also restored the 10,000-file and 120-template
  fixture under the 64-descriptor limit.
- The clean-installed wheel and source distribution passed full backup recovery
  and restored the 1.0.2 archive. The unpublished artifacts and logs are in
  `backup-address-verification` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.

## 2026-11-20 — Make exported backups restorable at larger file counts

- Reproduced a successful TAR export that its own importer rejected at 200
  members. TAR now permits 12,000 members and 12,000 directories under fixed
  byte, nesting and compression limits. ZIP retains its 200-member limit.
  Export applies the importer's resource checks before publishing the archive.
- Export hashes the paths and bytes it saves, records hardlinked file contents
  as regular files, and omits install-local evidence. Clean installs of both
  candidate packages restored an archive from the published 1.0.2 CLI whose
  legacy manifest included a source-lock file. The restored skill and binary
  reference matched the original and the source-lock file was removed.
- A Linux tmpfs fixture exported 10,000 references and 120 templates in
  2.672 seconds. Import took 5.396 seconds under a soft limit of 64 open
  descriptors. Reference hashes and template bytes matched and Store doctor
  passed. A shared template-directory lock replaces the per-file import locks.
- The unpublished packages and round-trip logs are in
  `archive-portability-verification` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- Linux Python 3.11–3.14 each ran 2,403 tests with no failures. The shared
  temporary-root test, both smokes, Ruff, Bandit on the touched runtime modules,
  documentation, complexity and workflow checks also passed.

## 2026-11-20 — Preserve original files across failed archive imports

- Reproduced two failures with disposable libraries. Full import left a
  template absent after a replacement rename failed. Ordinary import erased
  the displaced skill and its supporting file when both replacement and
  rollback were denied.
- Both paths stage beside the destination and record the swap before the
  first rename. A blocked rollback keeps the private backup and reports its
  location. Index resync and later import attempts preserve that directory.
- Full-backup trash, templates and catalog metadata roll back together on
  publication failure or an index reconciliation error. Catalog restore
  requires the declared metadata file and preserves companion files beside
  it. The per-skill import locks the destination and shares the index lock.
- Restored across separate staging and destination mounts. In five pairs of
  simultaneous CLI imports, exactly one installed the skill and exactly one
  restored the catalog. Both fresh package installs recovered the active
  skill, binary supporting file, template, catalog and trash from a full
  backup. The unpublished packages and logs are in
  `archive-import-verification` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- Linux Python 3.11–3.14 each ran 2,396 tests without a failure. The shared
  temporary-root trust test passed separately on all four versions. Store
  and web smokes, documentation, complexity and workflow checks passed.

## 2026-11-20 — Verify release recovery and public artifact identity

- Reproduced a failed source-package install on a fresh Python 3.12 venv.
  The installer now provisions the hash-locked build toolchain and installs
  the local source archive with dependency and index lookup disabled. A local
  wheelhouse also allows the toolchain bootstrap to run without an index.
  [Python 3.12 venv dependency changes](https://docs.python.org/3.12/library/venv.html)
- The CI and release jobs run the packaged recovery probe against both exact
  artifacts. Both verified CLI creation, trash and byte-for-byte restore of
  the document and supporting file. The release gate also runs the existing
  offline AI probe on the exact wheel.
- After PyPI publication, a read-only job compares the listed hashes and
  downloads of both distributions. GitHub Release creation depends on that
  check. The write-capable job uploads the two tested artifacts. The new
  verifier passed against the independently downloaded GitHub assets for
  the existing 1.0.2 release. [PyPI release API](https://docs.pypi.org/api/json/#get-a-release)
- The unpublished 1.1.0 wheel and source distribution, with checksums, are
  in `release-recovery-verification` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- The full suite ran 2,388 tests per interpreter on Linux Python 3.11–3.14
  with no failures. The shared temporary-directory trust test also passed
  separately on all four versions. The workflow syntax check passed locally.

## 2026-11-20 — Make archive preview evidence explicit

- Archive previews now retain scope-scan diagnostics and distinguish
  scanned, missing, partial, shared and unscanned roots. Real CLI fixtures
  covered an empty directory, a file in place of a scope root, aliases
  to one physical directory and a later scope omitted by the row limit.
- Project-scope reader hints now use the documented project-relative roots
  in the consumer catalog. A row with a cached name match identifies that
  evidence separately from a recent primary document modification. Exact
  copy attribution and continuous usage and edit/install coverage remain
  unverified.
- Both unpublished 1.1.0 packages reproduced the JSON and text results in
  clean installs. Previewing the synthetic library preserved skill files,
  the transcript and the usage cache, and created no index. Store and web
  smokes, the offline AI probe and static checks passed. The packages and
  hashes are in `archive-preview-evidence` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- The Linux suite ran 2,381 tests per interpreter on Python 3.11 through
  3.14 with zero failures and seven or eight skips. The shared sticky
  temporary-directory check passed separately on `/tmp` for all four.

## 2026-11-20 — Resume transcript discovery across projects

- Directory discovery now yields transcripts as it finds them and keeps
  earlier events when later discovery reaches the deadline. A separate
  metadata limit bounds directory walks. When the file budget is reached,
  the next refresh can resume by numeric position without saving project
  or transcript names. Resumed coverage remains partial.
- A synthetic collection of 10,001 transcripts across 101 project folders
  counted 10,000 events on the first refresh and one on the second. A third
  refresh preserved the count. Regressions cover cursor wrap after a library
  shrinks and bounded per-agent file marks.
- Multi-agent refreshes rotate their starting agent after reaching the
  shared byte or time limit. Regressions cover an active Claude Code source
  and a waiting Command Code event, and confirm that deferral keeps the
  waiting source's saved position. Report order follows the caller's selection.
- A fresh wheel and source distribution passed installed CLI pagination and
  cross-agent rotation checks, plus the earlier long-file, OpenCode and
  repeated-agent checks. Store and web smokes, the offline AI probe and the
  documentation, complexity, Ruff and Bandit checks passed. The unpublished
  candidate and checksums are in `fair-transcript-refresh` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- The first verification attempt encountered a full filesystem. After
  cleaning generated fixtures and install environments, the Linux suite ran
  2,377 tests per interpreter on Python 3.11 through 3.14 in a private
  temporary directory, with zero failures and seven or eight skips. The
  shared-sticky-directory check skipped there and passed separately on
  `/tmp` on all four interpreters.

## 2026-11-20 — Forward progress within usage scan budgets

- JSONL refreshes count complete records within the available byte and time
  budgets. Each refresh resumes at the saved position. Reaching a deadline
  preserves events already counted. A single 35,651,966-byte synthetic
  session was read in two default-budget refreshes. A separate 10,000-record
  fixture reached all counts in five refreshes at a 450,000-byte scan budget.
  Repeated refreshes left counts stable.
- Long JSONL sessions can exceed one refresh's per-file budget. An oversized
  record stays in discard mode until its newline, even across refreshes.
  Synthetic regressions cover a valid-looking JSON suffix that must be
  skipped and a valid event on the next line that must be counted. Repeating
  an agent selection now spends the same budget as selecting it once.
- OpenCode reports prioritize the current table and newest inserted rows
  within each table. Timed-out reads retain events extracted before the
  deadline after verifying the database snapshot was stable. Tests also
  interrupted a live SQLite query and checked its retained evidence.
- Both unpublished 1.1.0 packages passed package-data and clean-install
  checks, including the long JSONL session and a read-only, byte-limited
  OpenCode scan and repeated `--agent` flags. The wheel passed offline AI
  verification. The packages and checksums are in `usage-scan-budgets` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- The Linux suite ran 2,370 tests on each of Python 3.11, 3.12, 3.13 and
  3.14 with zero failures. Python 3.11 through 3.13 had seven skips each
  and Python 3.14 had six. Store and web smokes, documentation, complexity,
  Ruff, Bandit and design token checks passed.

## 2026-11-20 — HTTP response cleanup and documentation links

- The AI provider and registry clients close HTTP error responses as soon
  as the status, headers and required body details have been read. Three
  cases reproduced the leaked response, then passed with the fix. The AI
  transport and registry suite ran 50 tests on Python 3.14 without resource
  warnings. Both exact release artifacts passed clean-install checks for
  error response closure, along with the earlier usage and archive cases.
  [Python HTTPError response contract](https://docs.python.org/3.14/library/urllib.error.html#urllib.error.HTTPError)
- The documentation gate now resolves Markdown anchors in directly linked
  repository files when Git discovery fails. A real link from the study docs
  to the OpenCode probe instructions exposed the error. Regression tests
  verify valid and missing anchors and keep linked reads inside the repository.
- The final Python 3.12 run completed 2,362 tests with seven skips and zero
  failures. The 23 focused checks also passed on Python 3.11, 3.13 and 3.14.
  The documentation gate passed with Git and with an empty executable search
  path. Ruff, complexity, offline AI evidence and release contract checks passed.
- Chromium and Firefox each passed 49 v2 scenarios and 39 classic scenarios,
  covering 349 assertions per classic run. The unpublished packages, their
  hashes and the browser reports are in `http-response-cleanup` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.
- Two builds with the pinned toolchain produced identical member contents
  in both distributions. The wheel metadata timestamps and the sdist gzip
  timestamps differed, changing both archive hashes. The lock now documents
  the release workflow's build-once artifact identity guarantee.

## 2026-11-20 — Resume bounded transcript refreshes

- A JSONL refresh now resumes from the saved offset when the prior scan
  stopped at an unfinished append. Comparing the previously read prefix
  also lets a short transcript grow without restarting from byte zero.
  Successfully resuming after a skipped oversized or malformed record
  keeps the source marked partial.
- Two regressions reproduced the missing events when only the appended
  record fit the remaining budget. Both now pass. The focused usage and
  lifecycle suite passed 45 tests on each supported Python version, 3.11
  through 3.14. The full suite ran 2,358 tests on each version with zero
  failures. Python 3.11 through 3.13 had seven skips each and Python 3.14
  had six. The Store and web smokes and the documentation, complexity, Ruff
  and design gates passed.
- Rebuilt the unpublished 1.1.0 wheel and sdist and verified both in clean
  environments. Each found OpenCode's selected database and its activation,
  showed the archive evidence gaps, and resumed a capped JSONL refresh.
  The wheel passed the offline AI verification. Packages and checksums are
  in `archive-and-usage-refresh` under
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.

## 2026-11-20 — OpenCode consent and archive evidence

- Usage consent follows an absolute `XDG_DATA_HOME` and a configured
  `OPENCODE_DB`. Changed roots require new consent. A cached report suppresses
  evidence if the cache belongs to a different root. An authorized refresh
  rebuilds that agent's aggregates from the consented root.
- The read-only OpenCode reader now counts durable explicit skill activations
  alongside completed skill-tool calls. In an isolated OpenCode 2.3.2 run,
  an explicit activation with `resume: false` appeared exactly once in each
  of two refreshes. The SQLite database hash stayed identical across refreshes.
  [OpenCode database selection](https://github.com/anomalyco/opencode/blob/v2.3.2/packages/cli/src/database-path.ts)
- Archive previews show documented scope consumers and each reader's coverage
  status. Modification evidence is compared in UTC even if a timestamp
  carries a local offset. Consumer mapping is partial and continuous usage
  and edit/install evidence remain unverified, so archive moves stay gated.
- The full Python 3.12 suite ran 2,356 tests with seven skips and zero failures.
  The 43 focused usage and lifecycle tests also passed on Python 3.11, 3.13
  and 3.14. Store and web smokes, documentation, static, complexity and offline
  AI evidence gates passed. The rebuilt unpublished 1.1.0 wheel and sdist
  passed package-data checks and clean-install consent, usage and archive
  preview checks. Packages and checksums are in `archive-evidence-refresh`
  under `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.

## 2026-11-20 — Native replay and moderated pilot fixture

- Replayed all 12 saved prompts through OpenCode 2.3.2 in a loopback-only
  namespace, with a fresh home and project for each case. The four skill names
  and descriptions matched the saved simulation listing. Across 32 scripted
  provider requests, eight cases completed a skill call and carried its body
  into the follow-up request. Four cases stopped without a skill call. Two
  replay reports were byte-identical. The saved report is
  `~/skills-manager-artifacts/2026-11-20-fidelity-replay/opencode-offline-replay.json`.
  The stub scripted the outcomes. An attended provider run is still needed
  for any same-model agreement rate.
- The v2 test launcher can keep a seeded fixture open for a moderated pilot.
  Fixture processes use private agent roots and a server environment without
  inherited provider credentials or proxy settings. The browser rehearsal
  synced the synthetic Codex copy, confirmed that Recovery refuses to
  overwrite an occupied folder, and restored the original text and companion
  file after the synced copy was moved aside. Ctrl-C stopped the server.
- Fixed an obscured Inbox Sync button found during the rehearsal. Document
  scroll padding now keeps controls clear of the sticky header and phone
  navigation. The regression reproduced the desktop failure at `80f1dd8`
  and passed on the working tree in Chromium and Firefox, at 1280 × 577 and
  390 × 577. [W3C focus visibility guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)
- Closed [issue #14](https://github.com/udayvarmora07/skills-manager/issues/14)
  after confirming both Host-header cases were covered on `main`.
- Rebuilt the unpublished 1.1.0 candidate with the scroll fix. Both exact
  artifacts passed the package-data gate, clean installs and installed CSS
  checks. The wheel passed the offline provider smoke. The refreshed
  checksums and packages are in the `pilot-and-focus-refresh` subfolder of
  `~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.

The final local suite ran 2,352 tests on Python 3.12 with seven skips and
zero failures. Chromium and Firefox passed 49 v2 scenarios each. Headed
Chrome passed actual 200% and 400% zoom. The web smoke, AI evidence,
documentation, design token, complexity and static checks passed.

## 2026-11-20 — Usage, Sync and release-candidate review

- Verified the original Windows and browser fixes on
  [CI for `80f1dd8`](https://github.com/udayvarmora07/skills-manager/actions/runs/44743791588).
  All 16 jobs passed. The F-1 and F-2 Host behavior reported in issue #14
  is covered by the current web-client contracts.
- Checked OpenCode 2.3.2 through the isolated fake provider and the database
  it wrote. Both usage refreshes counted the one completed synthetic skill
  call and left the database hash unchanged. The reader supports legacy
  rows and checkpointed assistant messages, retains partial coverage for
  capped scans, and ignores timestamps outside the report's UTC window.
  The archive move remains gated on continuous evidence for all consumers.
- The v2 reader guards repeated Sync clicks. Recovery identifies previous
  copies saved by Sync, and the affected surfaces explain when to use the
  full folder in Recovery instead of text Undo.
- Set the local candidate version to 1.1.0 and retained the current PyPI
  distribution. Both publication jobs pin the reviewed v1.14.3 commit of
  the PyPI publish action. A matching version tag triggers the workflow,
  with TestPyPI preceding PyPI. [Upstream release](https://github.com/pypa/gh-action-pypi-publish/releases/tag/v1.14.3)
- Retained the tracked `.specs/` evidence and Git history. Recorded the
  product and market decisions in docs/27 and docs/45. No buyer demand or
  participant evidence was added.
- Approved the nine-image `d2257c8` pilot package for dated product
  illustrations. Verified each PNG's hash, size and metadata, and inspected
  the captures, including the disposable path in the Inbox. The ZIP's
  SHA-256 is `551858fffabbd8246f4137182ed32e6e8c60b6614a57bf61f1ffa149f875c8a2`.
  The captions name the older checkpoint. Participant and human accessibility
  checks remain open.

Local verification ran 2,348 cases on Python 3.12 (7 skips, zero failures)
and 123 focused cases each on Linux Python 3.11, 3.13 and 3.14. Both smokes,
Ruff, Bandit, syntax, complexity, docs, design tokens and offline AI
evidence checks passed. The Chrome and Firefox v2 suites passed 48
scenarios each. Classic passed 349 assertions in each engine. Headed
Chrome passed actual 200% and 400% zoom on the six main routes. A synthetic
10,000-activation fixture kept one count per activation across concurrent
refreshes. The new usage and repeated Sync regressions failed against
`80f1dd8` and passed with these changes.

The hash-locked 1.1.0 wheel and source distribution passed the exact
package-data gate, clean installs, and installed CLI creation, reading, and
lifecycle report checks. The wheel passed the offline provider test. The
checksummed artifacts are in
`~/skills-manager-artifacts/2026-11-20-release-candidate-1.1.0/`.

## 2026-11-20 — Windows CI follow-up and offline fidelity probe

- GitHub CI reproduced the same four failing tests on Windows 3.11 and
  3.14. A new lockfile receipt now records the platform's writable mode, and
  Undo accepts older receipts for newly created Windows locks while still
  checking the written bytes and the Windows read-only flag. Bounded
  descriptor reads use binary mode, which preserves the exact bytes in
  portable hashes and incremental transcript offsets. Codex command parsing
  preserves Windows path separators and quoted paths. The next manual
  refresh on Windows rereads old text watermarks and retains known event
  IDs for deduplication.
- The Chrome smoke harness retries only temporary profile cleanup failures
  with `ENOTEMPTY` or `EEXIST`. A persistent error still fails the harness.
  GitHub logged successful page probes before an `ENOTEMPTY` cleanup failure.
  [CI with the cleanup failure](https://github.com/udayvarmora07/skills-manager/actions/runs/44738831473)
  [Latest CI at the start of this work](https://github.com/udayvarmora07/skills-manager/actions/runs/44741155867)
- Added a repeatable, development-only OpenCode 2.3.2 probe. The Linux
  loopback-only run saw three fake-provider requests, two containing the
  synthetic listing, one completed skill event, and one follow-up request
  carrying the skill's synthetic body. The stub selected the tool.
  @docs/48-ai-http-study-2026-11-17.md records the run.

Linux ran 2,342 unit cases on each of Python 3.11–3.14 with 7/7/7/6 skips
and zero failures. Both smokes passed, and Chrome passed six viewports and
four scenarios. Compile, Ruff, Bandit, complexity, docs, design tokens and
offline AI checks passed. Pinned wheel and sdist checks passed, and eight
lifecycle cases passed from a clean install of each artifact. The new Windows
behavior still needs confirmation on GitHub's Windows runners.

## 2026-11-20 — Pilot capture refresh and Recovery rehearsal

- Captured nine screens from `d2257c8` in headless Chrome, including the
  Inbox overwrite preview and the previous Codex folder in Recovery after
  Sync. The synthetic fixture includes a disabled skill, an unreadable
  document and a divergent copy with a supporting file. All image dimensions
  and SHA-256 checksums matched the manifest. Visual review confirmed that
  the Inbox path points inside the disposable fixture. The private ZIP is
  `~/skills-manager-artifacts/2026-11-20-pilot/2026-11-20-d2257c8-pilot-screenshots.zip`.
- Selecting Claude Code as the source showed one destination, Codex.
  Selecting Codex showed two destinations, Claude Code and the shared folder.
  Sync from Claude Code copied both fixture files to Codex and saved both
  original files in Recovery. Restore refused the occupied path. After the
  rehearsal set the current copy aside, the exact Recovery entry restored
  both original files. External use and consented participant sessions
  still require human approval and participation.
- To inform the `.specs/` retention decision, the current subtree at `d2257c8`
  produced a 37,883,054-byte gzip-compressed Git archive. Twelve tracked
  Markdown files outside the subtree contain literal `.specs/` references.
  These measurements describe the current archive and reference surface.
  They do not estimate the size of a history rewrite. The owner decision
  remains open.

## 2026-11-20 — Lifecycle evidence and remaining-task review

- `archive candidates` now shows the primary document modification time
  for active and disabled copies. The CLI skips linked or malformed documents
  and keeps the scan independent of the SQLite index. Recent mtime and cached
  usage use the same UTC date window. Archive apply and restore still require
  continuous usage coverage, verified consumer mapping and edit/install
  evidence. See @docs/54-usage-lifecycle-lock-native-profiles-2026-11-20.md.
- Reviewed the dated `2359e7a` pilot ZIP locally. All seven PNGs matched the
  manifest hashes and viewport dimensions, and the files contained only PNG
  header, image data and end chunks. Visual review found synthetic names and
  no visible personal paths or account identifiers. The captures document the
  named checkpoint and predate the later Inbox overwrite preview. External
  approval and consented sessions remain with the maintainer.
- Rechecked the ten retained HTTP study artifact hashes. The native harness
  joined all twelve saved prompts to the DeepSeek simulation in dry-run mode,
  including verification of the captured listing fingerprint. This is
  offline input validation. The same-model native run remains an attended
  study. See @docs/48-ai-http-study-2026-11-17.md.

Linux verification ran 2,335 unit cases on each of Python 3.11–3.14, with
7/7/7/6 skips and no failures. Both smokes, compile, CLI help, Ruff, Bandit,
complexity, documentation, design tokens and offline AI evidence checks
passed. The pinned wheel and sdist passed package-data checks and eight
lifecycle tests each after clean installs. Synthetic CLI checks covered an
empty library, two concurrent reports of a single skill, and a 10,001-skill
library truncated at 10,000 rows.

## 2026-11-20 — Claude Code recovery hardening handoff

Continued from Claude Code's `Skills Manager recovery hardening` after
verifying that the recovery commits through `487de61` had reached `main`.
That revision's GitHub CI run completed all 16 jobs successfully.

- Forced Sync identifies the actual v2 Inbox targets, records the previous
  folder in Recovery when its supporting files would change, and reports
  a retained backup path when the move fails. Resync preserves Recovery
  payloads and retained backups. New scoped Recovery entries record and
  validate the original location of nested skills.
- CLI-only usage consents record the selected roots, while usage reports
  distinguish observed counts from parser coverage. Lifecycle reports
  and reversible pins are available. Archive moves await continuous,
  all-consumer observation evidence.
- The CLI verifies Vercel project lockfiles offline and previews guarded
  v2 updates with undo. Native project changes support reviewed settings
  writes, a saved profile's off list, and read-only handoffs. See
  @docs/54-usage-lifecycle-lock-native-profiles-2026-11-20.md.

Verification on Linux: the full Python 3.12 suite ran 2,332 tests with
7 skipped. The 44-test recovery, CLI and profile subset passed on
Python 3.11–3.14. The final lock and usage checks passed 66 tests. Both
smokes, Ruff, complexity, design tokens and documentation gates passed.
Chromium 158 and Firefox 151 each passed 47 v2 checks and 349 classic
assertions. Agent-browser and agent-desktop independently confirmed the Inbox
Sync action's source and destination on an isolated desktop fixture.
The v2 lock hash matched Vercel's `skill-hash.ts` at `57217cf` on a
fixture with nested links, Unicode names, binary bytes and CRLF. Both
distribution artifacts passed package-data checks and all six installed
CLI integration tests. Human perceptual and spoken screen-reader
sign-off remain separate.

## 2026-11-20 — Recovery follow-ups from parallel review

Four parallel subagents (Sonnet/Haiku) worked from this session's gaps: an
agent-scope implementation in an isolated worktree, a hostile review of
`9ca8ff6..4d83e86`, an investigation of a stray CI log line, and a flake hunt
under CPU contention. Their diffs and claims were re-checked before landing.

- Agent-scope `restore_trashed` now shares the global copy, verify, publish,
  retire helper (moved to `atomic_io.move_trash_tree`). The global default
  restore orders by trash stamp and serial with mtime as the last tiebreak,
  so an mtime bump on an older entry no longer changes which copy returns.
  An entry that vanishes during selection is skipped; other inspection
  errors become `StoreError`.
- Review found that `POST /api/trash/purge` with a `{"trash_path": ...}` body
  and no `?scope=` emptied the whole trash (`purge` is a valid skill name).
  Only a bare request purges now; a regression covers both body shapes.
  The shipped UIs always send `?scope=`, so neither was exposed.
- Not changed, recorded for later: Windows directory renames that fail with
  a held handle no longer fall back to copy and delete (only `EXDEV` does);
  new trash names add 26 characters, which matters near MAX_PATH; a crash
  between publishing and retiring leaves both copies until resync.
- The stray `FAIL: File is not a zip file` was a negative-path test writing to
  stderr. It is now captured, and the test asserts the reason for both the
  wheel and the sdist reader, which it previously never reached.
- Flake hunt (18 timing modules, 15 runs each under load): the fidelity
  descendant test failed 4/15 (`State: R` with SIGKILL pending) and the
  skill CI recipe test 1/15 (SIGTERM between `mktemp -d` and `trap`). The
  first now polls up to 5 s, the simulator test uses its short timeout only
  for the timeout case, and the recipe test signals after the stub starts.
  Both modules then passed 10/10 under six busy loops, and on Python 3.11.
- Ladder on the integrated tree: Ruff 0.16.8, compile, complexity (one stale
  baseline entry removed, `_route_trash_post` ratcheted 5 → 4), docs, design
  tokens, unit suite on 3.12 and 3.11, both smokes, v2 and classic e2e.

## 2026-11-20 — Recovery across linked and cross-volume trash

- Global Recovery accepts either the listed trash path or the physical path
  `remove()` returned when the trash folder is a link to another location.
  The incoming string is only compared against listed children of the trash.
- Restore and its rollback now survive `EXDEV`. The fallback stages a copy
  beside the destination, verifies relative names and bytes with
  `tree_content_hash`, publishes it, then parks and deletes the original.
  If the original cannot be parked, the published copy is withdrawn, so only
  the untouched original remains and the restore can be retried.
- New regressions cover a successful cross-volume restore, a copy that does
  not match, an original that cannot be retired (mutation-checked: red with
  the withdrawal disabled), and listed versus returned paths through a linked
  trash. A manual run with data on ext4 and trash linked to `/dev/shm` tmpfs
  restored a skill and its binary companion through a real `EXDEV`.
- `test_restore_reports_a_lost_trash_copy_as_a_store_error` mocked
  `shutil.move`, which restore no longer calls; it now injects the failure at
  `os.rename` and again proves the clean `StoreError`.
- Ladder on the final tree: 2,252 unit cases with 7 skips on Python 3.12 and
  3.11; Store and Web smokes; v2 and classic e2e (39 scenarios, 349
  assertions) in a chmod-700 temp dir; docs, complexity and design tokens.
  macOS and Windows coverage comes from CI.
- CI run 44705858668 then failed only `unit (py3.13)`:
  `test_timeout_terminates_fake_descendant` read `/proc/<pid>/status` while
  the killed child was in the transient `X (dead)` state. The test now accepts
  `Z` or `X`; both prove the child stopped. All nine cross-platform jobs
  (ubuntu, macOS, Windows on 3.11 and 3.14) had already passed.
- The rerun (44707293366) passed 3.13 but hit two other races. On macOS,
  `os.killpg` returned EPERM for a process group holding only zombies; the
  fidelity harness's `_stop` now treats EPERM like ESRCH after killing the
  direct child if it is still alive. The v2 "Peer scope link" scenario read
  `.use` rows once without waiting; it now waits for the shared-folder row.
  The fidelity tests and the full v2 e2e suite pass locally.

## 2026-11-20 — Recovery paths for repeat removals

- A restore followed by another removal in the same UTC second could reuse
  the earlier path in either trash. A browser with the old path could then
  restore the new version. New paths add a numeric suffix ordered by the
  host's monotonic clock, with extra entropy for equal readings. Both trash
  readers still accept dated paths and collision counters from earlier builds.
- Regressions freeze the clock, restore the first version, change the body
  and remove it again. The old path is refused and the new path restores the
  expected bytes. An agent name-only restore still picks the later copy in
  the same second. A full backup containing old and new path formats imported
  both and restored each by its exact path.
- On Linux, Python 3.11–3.14 each ran 2,245 cases with no failures and
  7, 7, 7 and 6 skips. Store and Web smokes, checked package contents and
  clean wheel and sdist installs passed. Chromium and Firefox each passed
  46 v2 scenarios and 39 classic scenarios with 349 classic assertions.

## 2026-11-20 — Firefox replay and pilot screenshot package

- The matching Firefox 151.0 build in a private Playwright cache passed all
  46 v2 scenarios. The classic runner now also accepts `--browser firefox`,
  isolates Codex and Gemini config paths, and records browser and version in
  `results.json`. Both engines passed 39 classic scenarios and 349 assertions.
  Chromium remains the default for CI. The Linux Python 3.12 suite passed
  2,242 cases with seven skips after the runner change.
- Captured seven screenshots from local checkpoint `2359e7a` with synthetic
  skills. The package covers Skills, Sync map and exact copy evidence,
  Workspaces discovery, Quality and Recovery. It includes a phone capture
  of the Sync map and a manifest with dates, viewport sizes and SHA-256
  digests. The ZIP is at
  `~/skills-manager-artifacts/2026-11-20-pilot/2026-11-20-2359e7a-pilot-screenshots.zip`.
  The package is ready for external-use review. Participant sessions and
  human visual and spoken sign-off remain open.
- The Unreleased changelog records the Sync map and exact Recovery changes
  for the maintainer's release-candidate review.
- The `.specs/` checkout contains 288 tracked files totaling 40,234,010
  bytes. Of those, 30,222,125 bytes are under `evidence/` and 9,951,650 under
  `prototypes/`. Git reported 277 unique `.specs/` blobs across named refs
  with 40,787,437 uncompressed bytes. That count includes blobs still in the
  checkout. The checked wheel and sdist contain no `.specs/` entries. The
  [combined verification report](31-combined-e2e-verification-2026-11-06.md)
  and other records still reference this evidence. Retention and any history
  rewrite remain a maintainer decision.

## 2026-11-20 — Sync map review filter and exact Recovery restore

- Sync map can show only skills with a copy that needs review in a displayed
  scope. The filter combines with name search and returns to the first page.
  Opening a different skill copy clears the previous repair selection.
- Both interfaces restore the selected global trash entry. Scoped restore
  also works for a skill named `purge`, while the explicit empty-trash action
  still uses its existing endpoint. A missing selected entry fails without
  restoring a different version. The Store matches paths against listed
  children while holding the index and trash locks.
- Older v2 responses can no longer overwrite newer global trash, agent trash,
  catalog or Recent changes results and errors.
- Linux verification ran 2,242 unit cases on each of Python 3.11–3.14 with
  7, 7, 7 and 6 skips, respectively. Both smokes, the viewport harness,
  Ruff, the medium/high Bandit check, docs, design tokens and complexity
  passed. The pinned wheel and sdist built, passed package inspection and
  installed in fresh environments. Offline AI verification passed.
- Chromium passed 46 v2 scenarios and a separate 200%/400% zoom check.
  Classic passed 39 scenarios and 349 assertions.
  The Sync map filtered 10,000 fixture records, and 20 concurrent restore
  rounds each preserved the unselected trash entry. agent-browser reported
  zero axe violations on the sampled light desktop and dark phone map.
  agent-desktop exposed the filter, table and row through Linux AT-SPI.
- The Playwright Firefox download timed out. A WebDriver smoke on installed
  Firefox 157.0.1 verified the Sync map and review filter. macOS, Windows
  and human spoken or visual sign-off remain outside this run.
- The remaining release, native-tool, and human-study decisions are listed
  in @task.md.

## 2026-11-20 — Shelf density and Sync map matrix

- The Skills shelf remembers its card density. Compact uses a tighter grid and
  one-line description previews. Exact instances uses its existing layout.
- Sync map shows one skill per row and one observed agent scope per column,
  with name search, sticky table headers and 48 rows per page. Cells use glyphs
  and accessible labels for file and content states. Copy details open the
  existing repair panel and can return keyboard focus to the selected cell.
  Same-name copies within one scope are flagged for review.
- Map sync acts on selected eligible rows visible in the repair panel. A
  double-click sent one sync request in the disposable browser fixture.
  Undo restored the original file content. If a later copy fails, the panel
  reports the failure and retains Undo for completed copies with snapshots.
- Browser regression cases cover density after reload, observed states, focus
  return, mobile table scrolling, empty and single-row inventories, and
  filtering and paging a 10,000-skill fixture.
- The 13 px control-label trial saved no toolbar height at seven widths.
  The proposed translucent ink ramp fell below the text threshold on several
  surfaces. Kept the measured scale and palette, improved reader group and
  heading contrast, and added both reader surfaces to the contrast test.
- Quality links to Microsoft APM's audit reference when project metadata
  includes an APM manifest or lock. APM retains ownership of manifest
  validation and package import/export. The research and decisions are in
  @docs/53-apm-and-interface-decisions-2026-11-20.md.
- Verification on the updated tree ran 2,238 unit tests with seven skips,
  43 v2 cases in Chrome, 42 in Firefox and 342 classic browser assertions.
  Chrome covered actual 200% and 400% zoom. Both smokes, package checks
  and offline AI verification passed. Axe reported zero violations in the
  sampled light desktop and dark phone Sync map. Linux AT-SPI exposed the
  search field, table and named copy buttons. Spoken sign-off remains
  a human review item.

## 2026-11-20 — Two residuals closed: legacy Windows archives, repo credential helpers

- **Legacy Windows archives import again.** Tree hashes join names with `/` on
  every OS since 2026-11-20, so a manifest a Windows build wrote earlier (with
  `\`) failed verification for any skill with nested files.
  `atomic_io.tree_hash_matches` accepts the legacy digest only on an exact
  match (top-level files hash the same either way; the bytes are still fully
  hashed). `tests/test_archive_legacy_windows_hash.py` builds such an archive
  and imports it; a wrong digest is still skipped with "content hash mismatch".
- **Repository credential helpers.** `backup_sync.git_fetch` now refuses a
  `credential.helper` (incl. URL-scoped `credential.<url>.helper`) whose scope
  is the repository's own config, before fetching: a helper is a program, so a
  crafted repository could run code. Global/system helpers stay in use (a
  `-c credential.helper=` reset would have broken private HTTPS remotes).
  `_run_git` takes explicit `ok_codes` for the one `git config` lookup that
  exits 1 when nothing matches. Regression test in
  `tests/test_backup_sync_contracts.py` (fails without the fix).

## 2026-11-20 — v2 component ports and guideline pass

**[NOTE]** From the component-library survey (Aceternity, Magic UI, Untitled
UI, and the Vue libraries Inspira UI, shadcn-vue and Reka UI; 68 components
assessed, 13 rewritten for this stack outside the repo under
`~/design-refs/ports/`; Uiverse was blocked by Cloudflare). React/Tailwind/
framer-motion code cannot ship here (no build step, no new runtime
dependency), so only patterns were ported, rewritten from scratch.

- **Recovery backup dropzone** (visual spec: Untitled UI FileUploadDropzone,
  MIT): the bare native "Choose File" input became a labelled drop target. The
  native `#imp-file` input stays inside the `<label>`, so click, keyboard and
  screen readers need no script; a dropped file must end in
  .tar.gz/.tgz/.tar/.zip (the server still decides whether the bytes are an
  archive); status text is `role=status`. New `upload` glyph in the icon set.
- **Switch (WCAG 1.4.11):** the off track (~1.5:1 against the page) gets a 1px
  `--line-strong` ring (3.6:1).
- **Web Interface Guidelines (vercel-labs) pass:** `theme-color` meta for both
  schemes; `touch-action: manipulation` on controls; `scroll-margin-top` on
  anchored headings to clear the sticky bar; `overscroll-behavior: contain` on
  dialogs and the skill tree; `translate="no"` on skill names (identifiers were
  open to browser auto-translation); explicit text colour on `.field` for
  Windows dark-mode selects.
- **Browser surfaces (impeccable craft floor):** text selection uses the
  highlighter token, the caret is brand, scrollbars are quiet.
- CI hygiene: `65f3a62` went red on Windows / Python 3.11 only, three
  unrelated tests erroring in `TemporaryDirectory.cleanup` with WinError 32 on
  a `locks/*.lock` file (the lock code closes its handle on every release; the
  prior seven runs on the same code were green). `tests/test_00_portable_
  environment.py` now retries Windows temp cleanup for up to 2 s; a genuinely
  leaked handle still fails. Windows-only regression test.
- Not ported on purpose: the app already has a switch, tabs, toasts, dialogs
  and a command palette that pass axe and the browser suites; replacing them
  would churn tested markup for little gain. The ports remain a spec to diff.

## 2026-11-20 — v2 reference-driven polish: radii, icon stroke, history runs

**[NOTE]** From the measured reference study (`~/design-refs/`, 14 product UIs
incl. Linear, Vercel, Raycast, Resend, Supabase, Attio, via the godly/awwwards/
inspo MCPs and live pages): the near-universal radius family is 6/8/12/pill,
and icons render at a constant ~1.5px stroke.

- `--r-lg`/`--r-xl` 10 → 12px (cards, panels); controls keep 6, groups 8.
- Icons: `stroke-width: 1.5px` with `vector-effect: non-scaling-stroke` on the
  shapes, so every size renders the same stroke; the 2.4 / 2.2 / 1.2 per-size
  overrides are gone (measured: 1.5px at 14 and 18px).
- Recovery history collapses consecutive rows with one action in one minute
  ("6 skills · Create", names in a native `<details>`); single events are
  unchanged. `tests/test_v2_tool_behaviors.py`.
- Skills shelf letter headers are sticky under the 66px top bar (z-index
  below it), so a long shelf keeps its place; contract-tested.
- Skills toolbar: the Tag filter joins the filter row with a visually-hidden
  label like Agent and Sort (it was the only visible-label filter and sat
  alone on a second row); on phones the header actions span the page gutter
  instead of shrinking to a ragged right edge (measured: right edges 372/372/372
  at 390px).
- Sync copy rewritten in plain words ("whether the skill is on or off, and its
  supporting files"), replacing "file enabled state and companion files".
- Kept on purpose: the three font families and the serif page titles (the
  study endorses a serif display + sans UI + mono system); Plus Jakarta vs Inter
  density was not measured on our screens, so no family swap.

## 2026-11-20 — v2 interface pass: type scale, spacing rhythm, a11y, Home layout

**[NOTE]** Driven by the `better-interface` review (accessibility, layout,
writing, typography, colour, UI skills), two read-only audit subagents (a
designer walk-through at 1440/768/390 in both themes, and an axe-core 4.7
sweep of 11 routes × 2 themes), and design references gathered with the inspo
MCP plus Godly/Awwwards/vendor product UIs (report kept outside the repo at
`~/design-refs/skills-manager-references.md`).

- **Type scale.** 28 ad-hoc font sizes became 11 named tokens (`--fs-caption`
  12 … `--fs-display` 52) in `v2/styles.css`; every size is `calc(N px ×
  --fs-k)`. The "Large text" preference used to enlarge only `body` (almost
  every element sets its own size), so it barely changed anything; it now sets
  `--fs-k: 1.133` and every step follows (verified: card text 13 → 14.7px, h1
  44 → 49.9px, no horizontal overflow). Agent-logo initials stay fixed to their
  tiles. Fonts unchanged: Plus Jakarta Sans / Newsreader / IBM Plex Mono is the
  serif-display + sans-UI + mono pairing the references endorse.
- **Spacing.** 20 distinct `gap` values snapped to one rhythm
  (2/4/6/8/12/16/20/24/32/56).
- **Typography.** `text-wrap: balance` on headings, `pretty` on ledes and card
  descriptions; the empty-state icon stroke (rendered ~2.75px) now matches the
  ~1.5px set.
- **Accessibility.** axe `aria-allowed-attr` (serious): skill-tree status dots
  carried `aria-label` without a role (`role="img"` added); the Inbox badge's
  label moved to visually-hidden text; the formatting bar is a `toolbar` and the
  mini-diff a labelled `region`; the Sync map's mobile list had a second `h1`
  (now `h2`). axe: 0 violations on every route in both themes after the change.
- **Home.** "Shared by most agents" and "Recent changes" moved from the long
  right rail into the main column under the agent cards, removing a ~1,300px
  empty area; agent paths show their informative end (`…/.claude/skills`, full
  path in the tooltip) instead of a leading-ellipsis cut; the "If read in full"
  meter says "under 0.1%" instead of a misleading "0%" over a forced 1.5% bar,
  and its limit tick has a title.
- **Copy.** "skills in all" → "skills in total"; detected apps are "agents"
  throughout the shelf (was "tools"); "Delete forever" → "Delete permanently"
  (matching the rest of the UI).

## 2026-11-20 — Open-queue pass: peer-user check, list payload, card names, Windows reads

**[NOTE]** Work on the agent-actionable entries of the "Open for the maintainer"
list, done unattended at the maintainer's request.

- **ADR-001 revisit (Linux).** `web_security.require_same_user` refuses a
  loopback connection whose client socket another OS user owns, read from
  `/proc/net/tcp[6]` once per connection (~0.2 ms). Unknown ownership keeps the
  old behaviour, so macOS/Windows and restricted `/proc` are unaffected; no
  token, no client contract change. ADR-001 v1.2.0. `tests/test_peer_user.py`.
- **List payload.** `GET /api/skills?body=0` (both UIs' list request) also drops
  `portable_frontmatter` and `frontmatter_extensions`: 896 KB of the 4.8 MB
  body-less `scope=all` response on the maintainer's 2,082 rows, read by no
  list. The detail route and `body=1`/absent are unchanged.
  `test_performance_http`'s projection contract now names the omitted set.
- **Shelf cards (WCAG 2.5.3).** The card link's `aria-label` omitted visible
  text, failing axe's label-content-name-mismatch. The label is gone; the name
  block precedes the status row in the DOM and `.sk-top { order: -1 }` keeps the
  layout. axe 4.7: no violations on the Skills page. A library-only card said
  "In 0 tools"; it now says "Only in your library".
- **Windows reads racing a replace.** `documents.document_text` (the raw route)
  and `loader._probe_document` retry for ≤100 ms on Windows when a document is
  momentarily delete-pending (PermissionError / `is_file()` False). An absent
  document is never retried in scans. `tests/test_windows_read_retry.py`
  patches the platform flag so the branch runs everywhere.
- **Housekeeping.** Leaked 2026-10-09 fixtures `agent-only`/`demo` trashed from
  the maintainer's agent roots (restorable); two dangling Claude links removed.

## 2026-11-20 — Scope scan no longer blanks non-canonical names

**[NOTE]** Found by exploratory testing of the v2 Skills page against the
maintainer's real roots: a Codex row named `.system` showed as an "active"
skill with no description. `loader.scan_dir` passed each enumerated entry to
`path_safety.contained_entry_under`, which applies the skill-name rule to a
single-part path; the resulting `ValueError` was handled as a *link escape*.
So every directory whose name fails `NAME_RE` (`Upper-Case`, `.hidden-skill`)
was listed as a blank link-escape stub ("path escapes managed root"
reason, empty description), and a container with no `SKILL.md` of its own
(Codex's bundled `~/.codex/skills/.system/`) appeared as a skill.

**[SPEC]** `contained_entry_under(..., check_name=False)` is for scans only: the
entry was enumerated, not named by a caller, so containment and the Windows
separator check still run but the name rule does not. Non-canonical rows now
keep their real content and stay marked `unaddressable` (SCOPE-14). A
non-canonical directory with **no** document (Codex's `.system/`) stays visible,
because the v2 Inbox's "Not a skill" note depends on it (docs/08), but as a
document-less husk (`document_missing: true`, `addressable: false`) instead of
a link escape; `husk_record` now carries `addressable`. An empty folder with a
valid name keeps the old contract (not listed outside doctor). Name-addressed
callers keep the default. Doctor output on the maintainer's roots is
byte-identical before and after.

**[NOTE]** The first cut dropped document-less dot-folders entirely; unit tests
stayed green but the v2 browser suite failed ("Home Inbox count equals queue"
expects the `.system` note). Fixed before commit — the browser suites are the
only evidence for that contract.

Also in this pass (v2 copy): the on/off toast read "turned off in Codex. —
frees about…"; the token effect is now its own sentence. The AI "Shorten a
skill" page was titled "AI assist" while no model was configured (its id was
missing from the fallback heading map). Regression tests:
`tests/test_audit_batch4_contracts.py`, `tests/test_v2_interface_contracts.py`
(each fails without its fix).

## 2026-11-20 — Full suite on every OS, browser e2e in CI

**[NOTE]** CI ran only a four-module path/archive subset on macOS and Windows,
and `tools/e2e_v2` / `tools/e2e_classic` (not unittest modules, so `discover`
never reaches them) ran nowhere. The `xplat` job now runs `python -m unittest
discover -s tests` on ubuntu, macOS and Windows (Python 3.11 and 3.14), and a
new `e2e` job (Ubuntu, headless Chrome, sandbox on) runs both browser suites
against throwaway fixtures. Playwright comes from `tools/e2e_deps`, a
hash-verified lockfile installed with `npm ci --ignore-scripts`; it is CI/dev
tooling only, never a package or runtime dependency.

**[NOTE] Product portability bugs the full suite exposed** (each fixed with a
regression test):

- **macOS:** `/var` is a symlink to `/private/var`, so a folder upload
  (`web_upload`: resolved target vs unresolved `mkdtemp` root) and every
  registry fetch/commit (`install`: staging below a symlinked ancestor) failed
  on every default macOS install. Staging directories are now canonical
  (`path_safety.canonical_mkdtemp`). `check_docs` anchors were keyed by an
  unresolved path for the same reason.
- **Windows:** `os.fchmod` does not exist (registry cache, sidecar and review
  writes crashed; `fchmod_private`); `DirEntry.stat()` reports inode 0, so the
  risk scan marked every nested directory "changed" and returned
  `listing-incomplete` with no findings; the regex-assertion deadline needs
  `SIGALRM` and now refuses the pattern (fail closed) instead of raising
  `AttributeError`; the registry provenance manifest sorted `Path` objects
  (case-insensitive on Windows) against a string-sorted snapshot, so any tree
  with `SKILL.md` and `references/` looked like drift; `tree_content_hash` used
  `\` separators, giving an archive a different manifest hash per OS; the
  source-lock digest sorted `Path` objects (now `parts`, which keeps the
  existing POSIX order); `os.replace` onto a document a reader had open raised
  `PermissionError` (now retried briefly on Windows).

**[NOTE] Skips, each precise.** POSIX mode bits (assertions guarded, not whole
tests), shebang-script fake scanner (SkillSpector hook, skipped on Windows),
`fork`, FIFOs, `SIGALRM`, ESC in file names, `~user`, replace-while-open
descriptor races, WSL `bash`, and three concurrency stress tests whose racing
reader/renamer sees a transient sharing violation on Windows (see Open items).
The suite now normalises two platform differences before any test runs
(`tests/test_00_portable_environment.py`): a symlink-free temp root and LF from
`Path.write_text`.

**[?] Open items.** On Windows a reader that races an in-flight document
replace can get a transient `PermissionError`; the writer now retries, readers
do not. The external-scanner hook is not exercised against a fake tool on
Windows. A `macos-latest` leg can sit queued and be cancelled; that is runner
capacity, not a test result.

## 2026-11-19 — Faster all-scope list request (v2 Home first paint)

**[NOTE]** `GET /api/skills?scope=all&body=0` is 29–49% faster on a synthetic
fixture with an unchanged response: paired medians 212 → 128 ms (1,000 records,
root 6 components deep), 270 → 138 ms (10 deep) and 3.95 → 2.79 s (10,000).
Profile: about 30% of the request was `os.path.realpath` re-walking every path
component per row. Changes: one-`lstat` containment below a resolved root
(deferring to `realpath` for links and anything odd), a per-scan memo of resolved
parents for `physical_path`, the global scan's resolved root reused per row, the
reserved-name set hoisted, `os.path.isfile` and a string sidecar probe, and
compact JSON for list pages only. Parsed output identical at 1,000 and 10,000
records. gzip was measured and rejected (loopback-only). No field, schema, CLI or
Store change. Evidence: @docs/52-list-request-performance-2026-11-19.md,
@benchmarks/list-request-2026-11-19.json; tool `benchmarks/list_perf.py`.

## 2026-11-19 — Accept the `localhost` Host alias (issue #14 F-2)

**[NOTE] AI Center busy state.** One `busy` boolean was cleared by whichever
guarded request finished first, re-enabling buttons that start paid model
calls while another request ran. An in-flight counter now keeps it set until
the last one ends; a new Node test fails on the old code ([true, false, false])
and passes now.

**[NOTE] v2 follow-ups and PR #23.** The remaining frontend-review findings
were fixed: the "Compare with" select rendered blank while a copy was already
compared (now bound to the compared copy, verified live), a failed re-read was
shown only on Home, a new import kept the previous result line, and the
command palette navigated while a dialog refused to close. PR #23 (list
request) was reviewed and merged: its lexical containment shortcut answers only
when every component below an already-resolved root is a present, non-link
plain entry (exactly when `realpath` returns the joined path) and defers to
`realpath` otherwise. One post-merge suite run showed a single intermittent
failure that two further full runs did not reproduce.

**[NOTE] Security review.** A subagent reviewed archive, install, upload,
source-lock, backup-sync, frontmatter, CLI and AI paths; five findings were
reproduced and fixed. (1) Any caller of the settings API could point
`base_url` at itself and receive `OPENAI_API_KEY` from the server's
environment on the next call; environment keys now go only to the provider's
default endpoint unless the operator names one endpoint in
`SKILLS_MANAGER_AI_ENV_KEY_ENDPOINT` (the 2026-11-17 study workflow needs that
variable now). The end-to-end repro's fake server received no Authorization
header afterwards. (2) `untrusted_block` put labels into an attribute
unescaped and only defanged lowercase `</untrusted`. (3) `local_manifest` read
a file before its 4 MiB check and `tree_content_hash` read whole files and
blocked on FIFOs; both are bounded/streamed, with an identical digest.
(4) `git_fetch` let `remote.<name>.uploadpack` run a program; it now pins
`--upload-pack` and the pager (a repo-local credential helper is a recorded
residual). (5) `validate --path` printed raw directory names.

**[NOTE] v2 bug review.** A subagent traced the v2 code; each finding was
checked. Ctrl/Cmd+S skipped the Save button's guard, so with no target ticked
it discarded the edit (reproduced, then fixed and re-verified). Clicking inside
a dialog left focus on `body`, so Escape and the Tab trap stopped working
(fixed: the dialog takes focus). `refresh()` and skill history had no
stale-response guard; history never reloaded after a change; Test connection
reloaded the AI form and wiped unsaved edits including a typed key; several
counts printed "1 skills".

**[NOTE] Docs audit.** A subagent compared README and the CLI surface doc with
real runs in an isolated HOME; each finding was re-run before editing. The
README told users to `chmod 700 ~/.local/share/skills-manager`, but the check
is on the base folder, so that never cleared the error; it still said to avoid
`localhost`; and its drift recipe missed body-only differences (plain `doctor
--scope all` flags differing descriptions, `--hygiene` flags differing bodies).
The CLI surface doc lacked `create --metadata` and `trash restore --snapshot/
--scope` and described `templates new` wrongly. `--scope` help omitted
`commandcode`.

**[NOTE] CLI typo hints.** A first-time-user pass found clear errors and exit
codes but no help for typos: `skills-mgr lst` listed 32 commands with no hint on
3.11–3.13 (argparse's `suggest_on_error` exists only on 3.14), and `view
pdf-tool` did not mention `pdf-tools`. Both now suggest the closest match;
skill suggestions come only from library folder names that pass the name rule,
so a hostile directory name cannot reach the terminal. Exit codes are unchanged.

**[NOTE] Tablet help.** The header hid the "?" keyboard-shortcut button from
601 to 900 px although it fits there (checked at 900/820/700/640/601 px with no
overflow and unclipped tabs); it now hides only below 600 px.

**[NOTE]** Maintainer-approved. Opening `http://localhost:<port>` against the
default `127.0.0.1` bind returned 403 on every request. `WebAppServer` now
allows exactly `localhost:<port>` beside the bound literal; Origin follows the
same set. `localhost` resolves on this machine, so a DNS-rebinding page, which
arrives under an attacker-controlled name, is still refused, as are other
ports, bare `localhost`, `sub.localhost` and `localhost.evil.example`. The
pinned rejection test became an acceptance test plus a boundary regression;
ADR-001, the threat model and the web UI client contract were updated.

## 2026-11-19 — Review loop 1: UI fixes, pyflakes gate, repository cleanup

**[NOTE]** An in-depth review (backend, web security boundary, live v2 UI,
lint) produced three v2 fixes: the narrow-width tab mask now applies only
while tabs are clipped (it dimmed "Tools" when every tab fit); a skill held
only in the library reads "only in your library" instead of "in 0 places";
and a Markdown link address containing parentheses is no longer cut short
(new regression test). Ruff now selects all of pyflakes, and 40 dead
imports/variables were removed. Seven `prototype-*` folders, `design-concepts/`
and `.design/` (about 18 MB, referenced by no code, test, CI or packaging)
were removed; three historical links now point at commit `515f5be`.
`.specs/` evidence is kept pending a maintainer decision.

**[NOTE] Loop 2 (accessibility).** Lighthouse scored v2 accessibility 96: 1,508
text nodes on turned-off skill cards fell to 2.4–2.8:1 because the card was
dimmed with `opacity: .6`. Those cards are links, so AA applies; they now use a
dashed edge and passing muted tokens. axe-core (agent-browser `a11y`, WCAG 2.2
AA tags) then flagged white initials on the Claude (3.1:1) and Gemini (4.1:1)
badges; both fills were darkened along their hue to 4.6/4.8:1, and a test pins
every badge fill at 4.5:1 or better. All seven v2 routes now pass axe in light
and dark; Lighthouse reports accessibility, best practices and SEO at 100.

**[NOTE] Brand mark.** v2 had no favicon (`data:,`) and a text "SM" tile. The
new mark is drawn by hand on a 32-unit grid: a folded skill page carrying a
switch, the product's core action. `skillsmgr/webui/v2/logo.svg` is the
favicon and README logo and inverts on dark colour schemes; the header carries
the same drawing coloured by theme tokens so it follows the in-app toggle.
Checked at 16–160 px on light and dark grounds; a test keeps the file
well-formed XML, since a malformed SVG decodes to a silent 0x0 image.

**[NOTE] Loop 3.** At 375 px no v2 route overflows horizontally. A read-only
fuzz sent 3,528 GET requests with malformed parameters (negative, huge, NUL,
traversal, invalid UTF-8) to every read route and received no 5xx. axe found
one classic violation, a scrollable first-scan list keyboard users could not
reach; it is now a focusable, named region. A keyboard walk of v2 showed text
fields signalled focus only by a 1 px border change; they now carry the same
2 px outline as every other control.

**[NOTE] Logo restart.** The owner rejected the page-and-switch mark. A
research pass (studio process: brief, volume, reduction, choosing by function;
2024–26 clichés: sparkles, gradients, circle-with-hole, hexagons, node
networks, documents with badges, toggles) informed five concepts drawn in
parallel with the vetted MIT `logo-designer` skill. Each was rendered at 128,
32 and 16 px, in 1-bit and on dark (board: `docs/images/logo-concepts-2026-11-19.png`).
The S monogram was legible but generic; the bars read as a sort icon; the
stepped and pixel S read as "5". The winner is **the switchboard**: rows are
skills, columns are agents, one row has slipped out of step and its last copy
is the one the tool flags in terracotta. The offset carries the meaning in
1-bit, and every edge sits on a whole pixel at 16 px.

**[NOTE] Real agent marks.** v2 now shows the official marks for Claude Code,
Codex, Cursor, Gemini and OpenCode instead of initials badges. Path data is
vendored verbatim from Simple Icons (CC0-1.0) and theSVG (MIT, Codex), with
the source and licence beside each entry; marks remain their owners'
trademarks and only identify the agent. Monochrome marks take the theme ink,
so they invert in dark mode. Command Code and the shared skills folder keep
initials badges because no open mark exists. All seven routes still pass axe
WCAG 2.2 AA in light and dark.

**[NOTE] Missing marks filled.** The Agent Skills standard's own repository
(agentskills/agentskills, Apache-2.0) carries official adopter logos, so
Command Code now shows its ⌘ symbol (extracted from its lockup) and the shared
`~/.agents/skills` folder shows the Agent Skills hexagon. "Your library" shows
the Skills Manager mark. The icon table supports several paths per mark, a
custom viewBox and theme-token fills. `docs/images/agents/*.svg` are generated
from the same table with a dark-scheme rule and form the README agent row.

**[NOTE] Logo research and refinement (superseded mark).** A survey of logo tooling found no
MCP server worth adopting: the SVG-generation servers wrap an image model
(the "AI slop" risk), and the icon servers only search existing sets. The
adopted pipeline is free CLI tooling: resvg (via `@resvg/resvg-js`) rasterised
the mark at 16/24/32 px for an 8x nearest-neighbour legibility check, which
showed half-pixel edges blurring at 16 px. The mark was redrawn with every edge
on an even coordinate (one whole pixel at 16 px), a solid text line and a
full-width switch track. No PNG/ICO set ships: every supported browser takes
the SVG favicon, and nothing else in the product displays an icon.

## 2026-11-18 — Evidence-based context sweep

**[NOTE]** Applied the supplied video's context-management practices to
the development workflow. `AGENTS.md` now distinguishes verified behavior
from intended change, uses the active task status and routes historical
lookups explicitly. `CLAUDE.md` imports the shared entry point with literal
router pointers. The developer-only context sweep asks for present evidence
and history, gives independent reviewers the claims without the proposed
verdict, and reports before any authorized correction.

The first sweep corrected current guidance for the v1.0.2 release, default
v2 paths, the insights compatibility module, and the data root. It also
updated the historical task label and retired manual release approval claim.
The research and file evidence are in @docs/51-agent-context-sweep-2026-11-18.md.

Initial verification exposed a collision between the skill trial and
the product's project-root discovery. Its test-generated files were
relocated to a private evidence directory. The final procedure lives
under `tools/` with a manual Claude command and an explicit Codex route.

**[NOTE] Verification.** Claude Code 2.1.325 listed `/context-sweep` in an
offline startup probe. Skills Manager's validator accepted the procedure,
and scope discovery found no project skill roots from this change. The
2,175-case test suite passed on Python 3.11–3.14 with 5/5/5/4 optional skips.
Both smokes, docs, complexity, design-token and static gates passed.
The pinned wheel and sdist passed package-data checks and excluded the
developer tooling. The installed-wheel AI probe also passed.

## 2026-11-18 — Published and verified v1.0.2

**[NOTE]** GitHub rejected a retry of the original run because it was
more than 30 days old. Recovery verified the original tag and retained
artifact against both TestPyPI hashes and the original GitHub build
attestations. The run used the existing `release.yml` Trusted Publisher
to publish both files to PyPI with publish attestations. It then created
the GitHub release on the existing tag and passed the published install
and CRUD smoke job.
[Recovery run](https://github.com/udayvarmora07/skills-manager/actions/runs/44252837346)
[PyPI release](https://pypi.org/project/skill-control-plane/1.0.2/)
[GitHub release](https://github.com/udayvarmora07/skills-manager/releases/tag/v1.0.2)

**[NOTE]** Both PyPI file digests and both downloaded GitHub release assets
matched the original artifact. A separate fresh install with the pinned
wheel hash confirmed the version, vendored Vue and CLI create/list. The
original tag still resolves to `ef9bfd6`. The one-time dispatch was removed
from `main` after verification. Future tagged releases use the automatic
TestPyPI-to-PyPI workflow.

## 2026-11-18 — Automatic PyPI release after TestPyPI

**[NOTE]** The maintainer removed the GitHub deployment approval requirement
for package publication. GitHub's API confirmed the existing `release`
environment now has zero required reviewers. The workflow still publishes
through `testpypi` before the `release` environment, which remains the
environment named in the publish job. The completed `v1.0.2` run remains
failed. A retry or a new release tag would start a separate publishing action.
[Release environment](https://github.com/udayvarmora07/skills-manager/settings/environments/21667496623/edit)
[Failed job](https://github.com/udayvarmora07/skills-manager/actions/runs/37442412642/job/112279779295)

## 2026-11-18 — Browser coverage, APM evidence, and offline fidelity probe

**[NOTE]** The v2 browser runner can replay the regression suite in
Playwright-managed Firefox. It records the engine and version and redirects
Codex and Gemini settings reads to fixture paths. Firefox 151 passed all
38 scenarios and headed Chrome 157 passed all 39, including real zoom at
200% and 400%. Both passed the forced-colors focus check. Browser results
are under `/tmp/skillsmgr-remaining-20261118/final-firefox` and
`/tmp/skillsmgr-remaining-20261118/final-chrome`. The classic harness passed
six viewports and four first-scan scenarios. Its six dated screenshots are under
`/tmp/skillsmgr-remaining-20261118/pilot-screenshots-final`. External
screenshot review, human visual and spoken sign-off, and consented
participant sessions remain pending. The protocol is in
@docs/25-design-partner-pilot-kit.md.
[Playwright Firefox setup](https://playwright.dev/docs/browsers#firefox)

**[NOTE]** Selected projects in v2 Quality now report `apm.yml` and
`apm.lock.yaml` as separate unavailable signals. Microsoft defines the first
as the project declaration and the second as a resolved lock. The check uses
two metadata probes, ignores leaf symlinks and non-regular files, and keeps an
inspection error local to the affected signal. APM YAML parsing, installation,
export and project-lock ownership remain deferred. Native profile writes
still need a per-agent write policy. Transcript usage needs a privacy
decision before collection, and stale-archive policy depends on that evidence.
[APM manifest schema](https://github.com/microsoft/apm/blob/main/docs/src/content/docs/reference/manifest-schema.md)
[APM install and lockfile documentation](https://github.com/microsoft/apm/blob/main/docs/src/content/docs/consumer/install-packages.md)

**[NOTE]** An OpenCode 2.3.2 offline probe confirmed that the JSON CLI emits a
completed `skill` tool call and the next model request receives the synthetic
skill instructions. The fake provider directed the call. An attended run
using an approved model and the real transport remains required for native
routing agreement. Source paths, protocol and observed limits are recorded
in @docs/48-ai-http-study-2026-11-17.md.

**[NOTE]** The first parallel matrix run exposed an existing cleanup-test
race on Python 3.12. The process-group kill was pending for the child when
the test inspected `/proc`. The test now polls for an exited or reaped child
with a three-second deadline. The v2 double-click test likewise waits for
the sync response and the completed Undo message before checking filesystem
state. Fresh hash-locked wheel and source artifacts
passed inspection and offline install probes with the pinned backend. The
installed-wheel AI probe passed. The artifacts identify as 1.0.2 and were
built for local verification. The complete Linux matrix passed 2,175 tests
on each of Python 3.11–3.14 with 5/5/5/4 optional skips. Both smokes, the AI
suite, compilation, the docs gate, the complexity ratchet, design tokens,
Ruff and Bandit passed. Current macOS and Windows execution was unavailable.

## 2026-11-18 — Release state recheck

**[NOTE]** The `v1.0.2` release run completed with failure on November 5.
Attempt 3 shows the TestPyPI publish succeeded, the PyPI publish job failed,
and the GitHub Release and published-distribution verification jobs were
skipped. The run reports zero pending deployments. The job has no listed
steps and its log is unavailable, so the cause of the PyPI failure remains
unknown. TestPyPI lists the non-yanked 1.0.2 wheel and sdist; PyPI lists
1.0.1. The repository still declares 1.0.2, so a future 1.1.0 candidate
requires an owner-selected version and a matching reviewed tag. The
workflow builds and verifies once, attests the bytes, then requires the
TestPyPI stage and protected release environment.
[Release run](https://github.com/udayvarmora07/skills-manager/actions/runs/37442412642)
[TestPyPI](https://test.pypi.org/pypi/skill-control-plane/json)
[PyPI](https://pypi.org/pypi/skill-control-plane/json)

**[NOTE]** Public CI for `9aafb94` shows successful jobs except the cancelled
macOS Python 3.14 leg. GitHub's annotations say the hosted runner never
acquired that job and cite macOS ARM64 capacity constraints.
[CI run](https://github.com/udayvarmora07/skills-manager/actions/runs/44135509064)

## 2026-11-17 — Measured size/performance improvement and Rust assessment

**[NOTE]** Completed the maintainer's research-first Rust/stack assessment and
kept the optimized Python/Vue reference. Conditional permission for migration
is recorded; no runtime language, framework, dependency or data/schema change
was justified by the present evidence. The assessment compares optional Rust,
native backends, Tauri, GPUI/Iced/Slint, Go and full rewrites, including size,
startup/RSS, frontend, safety, portability, maintenance and rollback. Sources,
limits and the decision are in
@docs/50-rust-size-and-performance-assessment-2026-11-17.md.

Used all four requested research tools: agent-reach retrieved the uv README and
the original Discord CTO post through its OpenCLI-backed Twitter channel;
OpenCLI Browser read the Vue performance guide in an owned session; Vercel's
agent-browser read Cargo documentation and verified the isolated app. The CTO
post confirms a Rust/GPUI client effort and upcoming testing, not independently
measured resource gains or general availability. No external message/post or
live model request was sent.

Four byte-identical Plex Sans resources now share canonical files. All twelve
font-face weight/style/range descriptors and font bytes remain identical;
prototype references were corrected too. The wheel shrank **14.32%**, from
1,069,942 to **916,682 bytes** including the scan optimization. An incremental
build retained deleted fonts in ignored output; the unchanged exact-members
gate rejected it. Fresh-source, hash-locked wheel/sdist builds and exact installs
pass; all **99** packaged files match source. The isolated wheel target has
4,258,350 file bytes including generated bytecode/metadata, excluding shared
Python/browser runtimes and filesystem allocation overhead.

Combined single-agent Doctor/hygiene requests reuse one diagnostic observation,
with distinct husk/duplicate handling and fresh reads on the next request.
Malformed recursive document directories/links retain separate-scan behavior;
collector errors remain visible. Standalone/global/all paths are unchanged.
Three alternating warm-cache synthetic CLI samples including JSON show
1,000-skill median **829.5 → 674.6 ms** (−18.7%) and 10,000-skill median
**8,127.2 → 6,045.1 ms** (−25.6%). Each after range is below its before range;
small sample counts and shared-host activity preclude p95/portable/UI/global-
scope or Rust-speed claims. Raw samples, CPU/RSS and source hashes:
@benchmarks/rust-assessment-2026-11-17.json.

**[NOTE] Verification:** **2,172 tests** pass on each Python 3.11–3.14
(5/5/5/4 optional skips), including eight new reuse regressions. Both smokes,
docs, unchanged complexity budget, design tokens, Ruff/Bandit, compilation and
exact wheel/sdist install/AI probes pass. Browser checks load all three Sans
weights from two canonical resources with no page errors/overflow, including
320px layouts; v2 fonts also load. Independent review found and verified the
prototype-reference and recursive-directory corrections. No full native-agent,
other-OS, human accessibility or fresh-machine runtime comparison is claimed.
Private traces, source snapshots, artifacts and recovery evidence are retained
at `/tmp/skillsmgr-rust-study-20261117`. The earlier five-task batch is already
pushed as `d97072e`; normal verified main integration remains authorized.
The original 15 owner/release/human/native/deferred entries remain open.

## 2026-11-17 — Second five-task continuation verified for main

**[NOTE]** Completed five bounded tasks: grouped personal Claude folder
observations; supplied-project Codex declarations; plugin manual-only intent
caveats; lockfile normalized-name collisions/source-path uncertainty; and
lossless tracker/progress archival. Native discovery, trusted/session settings
and unique upstream source resolution remain unknown. The two originally cited
lockfile bugs are closed upstream; no stale bug verdict is added. Sources and
bounds: @docs/49-read-only-compatibility-followups-2026-11-17.md.

Review corrected false collisions from display-path truncation, explicit null
source paths mistaken for absence, and display-name truncation changing the
folder being checked. Incomplete advisory reads remain separate from primary
skill-document coverage, so unrelated config/group evidence does not block a
complete document baseline. CLI and both UIs expose group/collision evidence;
scrollable v2 finding JSON now has a named keyboard-focusable region.

**[NOTE] Verification:** All 2,164 tests pass on each Python 3.11–3.14
(5/5/5/4 optional skips), including 34 added tests. Both smokes, docs,
complexity (1,364 functions across 49 files), design tokens, Ruff 0.16.8,
Bandit 1.9.4 (zero findings), compilation and changed JS syntax pass. The two
new observer modules are included in the unchanged complexity budget. Fresh
hash-locked wheel/sdist builds, isolated installs and installed compatibility/
AI probes pass; all 103 packaged source files match both delivery installs.

Agent-browser verified all new finding types, contained project selection,
classic group/collision names, keyboard focus, no page errors and no horizontal
overflow at checked 320/1,440px views. Expanded-view axe 4.12.0 reports zero
automatic violations after the scroll-panel correction. Some contrast checks
and two classic ARIA rules remain inconclusive; no full accessibility or human
spoken-screen-reader sign-off is claimed. Real Windows/macOS and native-agent
comparison remain untested; unsupported safe-reading capabilities report
unavailable. No live model provider was called for this continuation.

All 136 original task sections and 99 original progress sections remain
byte-identical in the live files or new indexed archives. The original 15
gated/deferred live entries remain open, including historical overlaps. Prior
archives and skill data were not modified. The maintainer's additional request
is recorded in `AGENTS.md` v0.3.1: research first, use/install suitable tools,
skills, custom agents, MCP servers and open-source projects as needed, with
Terra/Luna preferences and the specific existing product/release gates retained.

Private matrix logs, browser observations, artifact hashes, source/archive
receipts and recovery checkpoints are retained at
`/tmp/skillsmgr-next5-20261117-wia_vn2t`. Main integration and a normal push are
authorized after this current-tree verification and hostile diff review.

## Resident-history rule (2026-11-17)

**[SPEC]** Keep current delivery receipts and live pending work resident. Move
historical entries verbatim into indexed archives when the resident log grows
past approximately 100,000 characters. Sections with relative Markdown links
stay at their original location; this avoids rewriting historical evidence.
The archival receipt verifies each original entry is still present byte-for-byte
in either its original file or the new archive. The original 15 open tracker
entries remain in the live queue. No skill data, releases or prior archive was
modified by this documentation move.

## 2026-11-17 — Five-task batch verified for main

**[NOTE]** Completed the five selected unlocked tasks: F8 packaged static
Bash/Zsh completion and optional Python 3.14 suggestions; per-skill discovery
evidence in Workspaces; filesystem acquisition degradation for hygiene;
accurate model-simulation wording; and conservative unknown Codex invocation
metadata. History archival was replaced by the last concrete estimate fix.
No new command, flag, Store method, schema or runtime dependency was added.

GPT 6.1 Terra handled completion/packaging and scanner changes in separate
file-owned tasks; GPT 6 Luna handled Codex metadata and independent review.
Root integration added the UI/evidence work and owning docs. Actual Python
3.14 root and nested command typos exit 2 with a suggestion; unsupported Python
versions keep their existing error behavior. Completion scripts are static and
never scan skills, contact a service or change shell startup files. Final
shell review also replaced the Zsh-special `path` variable with a private
grammar variable; its path-preservation regression fails with the original
script and passes with the correction.

The scanner regressions were red before their fixes. Review also corrected
ordinary-folder and file-link false degradation, classified wrong-type roots,
and preserved managed peer links. Discovery matching now enforces flat versus
recursive roots and lexical boundaries, deduplicates represented physical
copies, and labels missing/suppressed scope mappings unverified. A bounded empty
result keeps its partial-evidence notice. These views do not assert runtime
activation or elect precedence winners. Unknown Codex metadata produces a
known-only token subtotal and unknown inclusion, independently of the budget.

**[NOTE] Verification:** 2,130 tests pass on Python 3.12 (five optional skips),
including 36 added tests. Sixty-six focused cases pass on each Python 3.11,
3.13 and 3.14 (two optional skips on 3.11/3.13, one on 3.14). The ordinary host
PATH has no Zsh and skips its case; a separate run using a temporary extracted
Ubuntu Zsh 5.9 passes, including shell-path preservation. Bash execution/syntax,
static grammar parity and exact packaged script bytes are checked. Both smokes,
docs/design/complexity (1,336 functions), pinned Ruff 0.16.8/Bandit 1.9.4 (zero
findings), compilation and changed JS syntax pass. Initial full runs exposed
synthetic archive fixtures missing the new package data; the fixtures were
updated without changing their security assertions. The final full run is green.

Fresh hash-locked wheel/sdist builds pass package-data checks, installed-wheel
AI verification, and isolated five-task probes from each exact artifact. All
101 packaged files match current source. Private logs, artifact hashes,
source manifests and recovery data are retained at
`/tmp/skillsmgr-five-20261117-42g781b1`.

Agent-browser observed the shared-skill discovery rows and Home's unknown
Codex listing/known budget, plus simulation notices on configured synthetic
Trigger/Budget pages. The fixture used a no-key localhost provider setting
without a provider request. New discovery-panel axe audits passed in settled
light/dark themes with zero violations or incomplete rules. Checks at 320,
768 and 1,440 px found no overflow; no page runtime errors were observed.
No real native-agent comparison, Windows/macOS execution or human visual/
spoken-screen-reader sign-off is claimed. Existing scans remain non-atomic;
files removed before observation can still look absent. Vendor root rules
were reused, not newly re-verified. The maintainer authorized a normal main
push after current-tree verification and hostile diff review. The original
15 release/owner/human/native-fidelity/deferred entries remain open.


## Historical sections retained for relative links

**[NOTE]** The following dated receipts remain verbatim to preserve their
relative Markdown link targets. They are historical, not current test counts.

## 2026-11-06 — Plan: optional SkillSpector hook, then stdlib risk patterns

**[NOTE]** Plan only; no source changed. NVIDIA SkillSpector cannot be merged
(about 20 runtime dependencies, Python >= 3.12, LLM/OSV egress, and a
DO_NOT_INSTALL verdict that conflicts with the advisory-only rule), so the plan
runs an installed copy as an optional external program in the two existing
review chokepoints and later rewrites a few static checks with the stdlib.
Verified locally on v2.12.0: `--format json --no-llm` reported AR1/PE3/SC2 on a
hostile fixture. SC4 still contacts `api.osv.dev` under `--no-llm`, with no
offline switch. See the
[plan](superpowers/plans/2026-11-06-external-skill-scanner.md).

## 2026-11-06 — Complete v2 feature parity and promote the default

**[NOTE]** The maintainer first approved clickable mockups, then explicitly
requested production integration using the existing v2 design and default
promotion after verification. Work is local on `feat/v2-feature-parity`.
The [design inventory](superpowers/specs/2026-11-06-v2-feature-parity-design.md)
records the source baseline; the
[implementation plan](superpowers/plans/2026-11-06-v2-feature-parity.md)
records acceptance evidence. The
[earlier mockup](https://github.com/udayvarmora07/skills-manager/blob/515f5be/prototype-v2-parity/README.md) remained an isolated design aid (removed from the tree 2026-11-19; last present in `515f5be`).

V2 now contains the remaining classic workflows: registry/runner/folder install,
profiles, templates, hygiene/validation/diagnostics, workspaces, preferences and
index maintenance, exact-copy source update/whole-tree rollback, logical tags,
reviewed batch operations, rich metadata editing, persistent scoped history and
full archive recovery. `/` and `/index.html` redirect to `/v2/`, preserving
query/hash; classic remains at `/classic/`. Existing v2 fonts, colours, document
reader, daily navigation and dark theme remain the visual authority. Inspo's
configured HTTPS MCP endpoint supplied recommendations/searches and three
archived captures; it was not enabled globally. UI/UX Craft, Design Taste
Frontend, Better Accessibility and Frontend UI Engineering informed the work.

The backend additions are contained template reads and explicit PATCH optional
field/body clears. Omission preserves values; empty descriptions are rejected.
The shared field guard's complexity budget tightened from 7 to 6. No public
Store method, application CLI command, schema or runtime dependency changed.
Luna/Terra reviews found races and copy-identity problems; fixes bind folder
approval to File identities, use the selected copy's description/scope, send
only changed editor fields and isolate independent read results. Behavioral
and real-HTTP regressions cover these cases. The final narrow Terra review
reported no unresolved defects in those fixes.

All write checks use temporary HOME/data roots. The classic browser suite
passed 38 scenarios / 318 assertions; the expanded v2 suite passed 34 scenarios,
including real template/profile operations, retry and 320/768/1280 layouts in
both themes. The six-viewport classic smoke harness also passed after moving
its probes to `/classic/`. The final current-tree suite passed 1,386 tests on Python 3.12; both smokes,
syntax/compilation, docs, design tokens, complexity, Ruff and the medium/high
Bandit scan passed. The final v2 browser repeat again passed all 34 scenarios. Packaging with the pinned hash-checked
toolchain includes all three new v2 assets in wheel and sdist. Live registry
fetch/commit, actual external runner execution and human screen-reader sign-off
are not claimed. Agent-scope trash has no in-app restore, and the interface
states that limit. No personal skills were changed; no commit or push was made.

The live queue and current delivery state remain in @task.md.
