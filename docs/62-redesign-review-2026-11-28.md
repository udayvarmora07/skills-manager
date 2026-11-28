# Redesign Review — Paper build at Phase 5 (2026-11-28)

**Version 1.0.0**

**AI manifest**: An in-depth, read-only review of the Paper redesign on `main`
at `3c67c42` (Phases 0–4 landed, Phase 5 Advanced directory and Doctor
landed). Five parallel reviews covered design fidelity, UX, frontend code,
backend data safety, and process and docs. Findings are ranked within each
section. Each finding is labelled **verified**, meaning it was reproduced in
the running fixture app or confirmed by reading the code, or **reported**,
meaning one reviewer saw it and nobody re-checked it independently. This file
records findings only. It changes no behaviour. Fix work belongs in @task.md.

## Fix results

**[NOTE]** Batch 1 is commit `6e0fa71`. Batch 2 is the commit titled
`fix(webui): finish Paper before-launch review fixes`. The original
observations are retained in the following sections.

| Finding | Disposition |
| --- | --- |
| Re-review leftovers | Skill copies uses clearer wording and plurals, rejects an existing new-profile name before posting, and has Advanced phone touch targets. Five focused comparison runs under CPU load did not reproduce the retry timeout. The confirmation surface is deferred to Phase 8 review (Q12). |
| Disclosure chevron | Fixed in Batch 1. Browser and stylesheet checks cover size, rotation, reduced motion and the tool-findings exception. |
| First launch | Fixed in Batch 1. The detected folder paths and welcome card match the approved structure. A delayed inventory read confirms the scanning state. |
| Classic-view links | Fixed in Batch 1. Old bookmarks resolve to the Paper table, retaining filters. The Skill page's Read copy picker distinguishes same-name folders. Exact tool links survive reload. |
| Doctor counts and evidence wording | Fixed in Batch 1. The index result names its scope, and broader findings explain their relationship to the two attention counts. A link opens Needs attention when there are issues. |
| Why opens on a missing copy | Reproduced with three present copies. Fixed in Batch 1. Existing-copy failures take precedence and the Skill page is linked. |
| State and notices carry over | Reproduced for backup previews, review errors, download announcements and Undo on the Reader → Editor transition. Fixed in Batch 1. Late read results cannot restore the old screen state. Failed writes remain visible after navigation. |
| Unknown place and `f` shortcut | Fixed in Batch 2. Unknown filters show all places on desktop and a valid place on phones. The shortcut shares the button's error guard. |
| Needs attention replacement source | Reproduced on a one-step repair. Fixed in Batch 2. The action identifies the source before writing. |
| New skill errors and starter overwrite | Reproduced with failed writes and edited instructions. Fixed in Batch 2, including late template reads. |
| Phone targets and New skill / Editor rows | Fixed in Batch 2. The affected touch targets meet 44 px at 390 and 600 px. Folder paths stay readable without crowding the Editor status. |
| Place, Sort, and column options controls | Fixed in Batch 2. The toolbar and column controls use chevrons, with keyboard access and focus return. |
| Terminology and copy | Fixed in Batch 2. Mixed destinations are places, tracking refers to agents, and the shared folder uses its board name. Advanced links and headings agree. Why and Trash use plain wording. The Skill page retains the list-space percentage without internal setting names or token counts. |
| Trash restore path, disabled action, and Recent changes time | Fixed in Batch 2. Restore identifies the saved date and destination, and the button explains why library trash cannot be emptied. The history times align with the card's right inset. |
| No-op backup | Not reproduced. The existing preview disables Load backup when all entries are skipped. A full archive with a catalog addition remains loadable. Both cases have an automated check. |
| Title left edges at 1,440 px | Deferred. The approved boards center distinct 1,440, 1,280 and 1,040 px page widths, which yield title positions of 40, 120 and 240 px. Aligning them needs a board decision. |
| Recent changes only shows library events | Deferred. This is the documented history scope. The empty state names it. |
| Safari popovers | The real Safari symptom remains unverified. Batch 2 closes popovers on focus or pointer activity outside the active control. Firefox verified dismissal and keyboard operation with a simulated null `relatedTarget`. |
| 10,000-skill performance and unbounded lists | Fixed in Batch 2. Square evidence is reused per row. Needs attention and Trash render an initial 50 rows and disclose additional batches, moving focus to the new content. |

**[NOTE]** Deferred scope includes Phase 5 S10/S11/S14–S19, the four backend
hardening notes, the handoff and archive decision, Phase 7 removal and doc
cleanup, and Phase 8 acceptance. S9 maintainer review remains open. The
screen-reader, physical-phone, actual Safari, and pixel-overlay checks remain
open. The checked-in boards were compared by markup, copy, and widths.

## Follow-up fixes

**[NOTE]** The remaining screen fixes below are in the commit titled
`fix(webui): resolve remaining Paper review findings`.

| Finding | Disposition |
| --- | --- |
| Browser smoke waits for the retired view | Fixed in `7b69ebe`. The populated probe dismisses the welcome card and checks the Paper table and its Needs attention count. |
| Bulk tags, profile assignment and exact-copy tools are unreachable | Fixed in `e7879f0`. The maintainer chose Advanced → Add skills → Skill copies. The page restores checked file actions, tag filtering and editing, and adding selections to profiles. A followed link stays read-only. |
| Create and permanent removal confirmations disappear | Fixed in `7cba8af`. An action's confirmation stays visible and in the live region on its destination. A manual screen change clears old success feedback. |
| Needs attention keeps outdated repair guidance after a failed write | Fixed. A return visit reads the current folders and recalculates available repairs. |
| New skill hides a place after a failed write | Fixed. A return visit reads which places are writable. |
| Doctor and New skill chevrons | Fixed. Full report shows its disclosure chevron, and the New skill dialog action shows a chevron. |
| Project name and mark vary across screens | Fixed. The screens use **This project** with its board mark. The Read copy picker includes each project copy's folder. |
| 390 px targets and Skills checkbox placement | Fixed. The affected targets meet 44 px at 390 and 600 px. Skills keeps the selection checkbox beside the skill name. |
| Quality mentions missing evidence and the characters-per-token formula | Fixed. Quality explains incomplete checks and identifies the text-length estimate in plain language. |
| Skill panel and welcome rows are misaligned | Fixed. The Skill panel disclosures share an inset. Welcome counts and paths use aligned columns. |
| Retired `route.view` branches | Fixed. Old bookmarks still open the Paper table with their filters. The wider classic-code cleanup remains in Phase 7. |

## Scope and evidence

**[NOTE]** Sources: the approved boards in `designs/final/`, @DESIGN.md,
`design/tokens.json`, @docs/61-redesign-build-spec-2026-11-27.md and its
`docs/redesign-build/` detail, @requirements.md, @ux-brief.md,
@design-brief.md and @build-progress.md. The app ran from
`tools/e2e_v2/run.py --pilot` against a sandboxed fixture home. It was
checked at 390, 1280, 1440 and 1920 px in light and dark themes, using both
the keyboard and the mouse.

**[NOTE]** The current tree passed the full suite on Python 3.12: 2,557 tests,
OK, 13 skipped. `smoke_store.py` and `smoke_web.py` passed. The focused
web UI contracts passed 182 tests. No `var(--x)` reference in `skillsmgr/webui/` lacks a
declaration.

**[?]** This pass did not cover: Python 3.11, 3.13 or 3.14; the Chromium e2e
suite; Safari and Firefox; a physical phone; a screen reader; Windows and
macOS paths; file-changed-on-disk (F8); and a slow or offline save. The
boards could not be rendered from `file://` because `support.js` is not in
the repository. The fidelity comparison therefore used the board source
(markup, copy and widths), not pixel overlays.

## What is in good shape

**[NOTE]**
- The benchmark task (find a skill, turn off Codex only, Undo) takes about
  six actions and gives the right result.
- The grid has a single tab stop. The arrow keys move between squares, Enter
  opens the panel, and Escape returns focus.
- The unsaved-edit guard works for both Cancel and browser Back.
- Typography, navigation, the side panel (392 px wide, correct shadow, accent
  primary), the toast and dark-mode parity match the design system.
- There is no horizontal scroll at 390 px.
- Backend: no new endpoints and no new public Store methods were added.
  `SCHEMA_VERSION` is unchanged. Imports are stdlib only.
  - Origin, Host and `Sec-Fetch-Site` guards return 403 as expected.
  - Traversal, symlink, zip-bomb, oversized-archive and replayed `plan_id`
    attempts were all refused.
  - Undo did not overwrite a copy the user had changed after the action.
- Frontend: `v-html` is used only for static icons and for `markdown-it` with
  `html:false`. Nineteen hostile route hashes were handled safely. The
  stale-response guards, the double-submit guards and the listener cleanup
  are all in place.

## Fix now

**[SPEC]** These are visible defects on screens that already shipped:

1. **Every disclosure chevron renders as a 6 px speck** *(verified)*.
   - Cause: `skillsmgr/webui/styles.css:835-836` (classic) changes the size,
     border and rotation of the mask chevron declared at
     `skillsmgr/webui/system.css:161`. It wins because `index.html:12-15`
     loads `styles.css` after `system.css`.
   - Affected: the Skill page, Editor metadata, Trash History, and the
     Settings and tool rail groups.
2. **The first-launch screen (A03 panel 1 / A16) does not match its board**
   *(verified)*.
   - The card, the left-aligned rows with mono paths, the "Tip" band and the
     accent "Show my skills" button are all missing.
   - Rows are centred (`layout.css:326`). Paths are blank because
     `screen-skills.js:238` passes `path: ''`.
   - This is the first screen a new user sees.
3. **New screens link into the classic UI** *(verified)*.
   - "Exact instances" (`screen-skills.js:355`) goes to
     `#/skills?view=instances`. That shelf uses older terms such as
     "Needs care" and "Shelf".
   - `?view=agents` and `?view=map` still render the classic Agents overview
     and Sync map inside the new shell. Two paths lead there: the shelf links
     (`index.html:328`, `app.js:1720`) and the legacy redirects
     (`router.js:62-64`).
4. **Doctor contradicts itself** *(verified)*.
   - A green "No index issues reported" pill
     (`tool-center.js:87`) covers only the SQLite index. Next to it, the card
     reports "23 findings · 7 errors".
   - Its counts do not match the Skills table or Needs attention, and it has
     no link to Needs attention.
5. **"Why isn't it running?" starts with a non-problem** *(reported)*. A skill
   that works in three of four agents opens on "There's no copy in OpenCode".
   The banner has no link, and the only action is Check again.
6. **Messages and state carry over to other routes**.
   - *(verified)* `restoredTrash` is set at `app.js:2133` and never cleared,
     so the "restored" banner returns on every visit to Trash.
   - *(reported)* The backup preview and import state (`app.js:1052-1059`)
     persist. `attentionError` keeps the Needs attention buttons disabled
     until Check again.
   - *(reported)* A success toast and its Undo stay visible on the next page.
     The live region keeps repeating "Backup download started."

## Fix before launch

**[SPEC]**

- **Unknown `?agent=` value** *(verified by reading)*. `currentAgent` falls
  back to the first agent (`screen-skills.js:51-58`). The table then shows one
  wrong column, with a blank selector.
- **`f` shortcut skips a guard** *(verified by reading)*. `attentionFix`
  (`app.js:1010-1013`) does not check `attentionError`, although the Fix
  button does. After a failed fix, a single key retries it with no recheck.
- **Needs attention never names its source** *(reported)*. It replaces a copy
  in one click, while the table panel names the source ("comes from Claude
  Code").
- **Jargon and inconsistent terms** *(reported)*.
  - Jargon: `skillListingBudgetFraction` and "tokens" on the Skill page, raw
    trash paths in the Restore dialog, "Evidence gaps" in Doctor, and
    "eval assertions" and "selection rates" in Advanced.
  - The same thing has different names on different screens: "places" and
    "agents"; three names for the shared folder; "Where agents look" opens a
    page titled "Workspaces"; "Connection" opens "AI settings".
- **Trash & backups** *(reported)*.
  - Recent changes shows library events only, not toggles, fixes or agent
    edits.
  - "Empty library trash" is disabled without saying why.
  - A backup that would change nothing still offers Load backup.
- **Phone targets** *(verified)*. Row checkboxes are 13 px. Breadcrumbs and
  editor toolbar buttons are 22–36 px, against the 44 px target.
- **Classic controls on new screens** *(verified)*. The Place and Sort filters
  are native selects, and the column-options trigger is a "▼" text glyph.
  Copy drifts from the boards on Trash, Why and the Advanced cards.
- **Layout glitches** *(verified)*.
  - New skill: the checkbox, agent mark and label stack on separate lines.
  - Editor "Save to": the row collides with its "Not here" label.
  - Trash "Recent changes": the time column is inset.
  - Content widths differ between Skills, Needs attention and Trash.
- **New skill** *(reported)*. `previewError` and `outcome.error` bypass
  `friendly()`. Picking a template replaces the typed instructions without
  asking.
- **Safari popovers** *(plausible, untested)*. The agent menu and project
  picker close on `focusout` (`screen-skills.js:275, 322`). Safari passes a
  null `relatedTarget` on a button click. The e2e suite runs Chromium only.
- **Performance at 10,000 skills** *(measured in a model bench)*.
  - Each `tableRows` recompute takes about 0.4 s and runs twice per toggle,
    because `squareStatus` recomputes `squareCamps` for every cell.
  - The Trash and Needs attention lists render with no limit.

## Backend notes

**[NOTE]** None of these blocks the redesign:

- **Stale-edit protection is opt-in on the server** *(verified by reading,
  `webapp.py:631-648`, `:1932-1942`)*. Edit, snapshot restore and
  `DELETE /api/skills/<n>` without `expected` run with no hash check. The
  shipped UI always sends `expected`. Requiring it, or an explicit Undo flag,
  would make the server fail closed.
- **`/api/stats` and `/api/doctor` can return 500 on a damaged index**
  *(reported, pre-existing)*. This happens when the index file exists but has
  none of the expected tables (`no such table: skills`).
- **`rename_new_directory` needs the `renameat2` no-replace flag**
  (`atomic_io.py:132-149`). It fails safely on filesystems that lack it, but
  Trash restore would then error there.
- **The Editor stages copies inside the live agent skills folder**
  (`editor_copy.py:300-374`). After a crash, a full copy remains where an
  agent with recursive discovery might load it.

## Process and documents

**[NOTE]**

- **The AiTooltip skills match upstream.** All twelve skills in
  `.claude/skills/` are byte-identical to upstream `e200967`. The extra local
  skills are `uxui-workflow`, `logo-design` and an 85-byte `implicit` stub.
- **Spec coverage.**
  - Implemented: S1, S2, S5–S9, S12, S13.
  - Partial: S3 and S4, restyled in `index.html` and `app.js` rather than in
    a screen module.
  - Missing: S10 (tool pages still use the classic `tool-center`), S11
    (Settings still shows "Connected" without a test, `ai-center.js:551`)
    and S14–S19 (What to track).
- **Phase 5 landed before review.** It is on `main` while
  @build-progress.md says "ready for the maintainer's review".
- **The handoff package was committed in `3c67c42`**: 169 files and 27.6 MiB
  in a public repository, including a 13.7 MB zip that duplicates the
  folder.
  - The progress log records this as the maintainer's request.
  - The Q8 row in `docs/redesign-build/09-open-questions-and-risks.md` still
    says to keep `handoff/` out of git.
  - The package is stale: design system v11, "Skills Manager", 14 screens.
    Q9 planned to regenerate it after Phase 2.
- **Stale statements in the docs.**
  - `project-status.html` said Phase 4 was in progress. It has been
    refreshed.
  - `requirements.md`, `ui-progress.md`, `task.md` and the progress log are
    still titled "Skills Manager".
  - `docs/SESSION-CONTEXT.md` cites 1,232 tests.
  - The README still describes Sync map, Inbox and Recovery.
- **Test gaps.**
  - No visual-regression check runs against the boards.
  - No automated check covers first launch (F9), tracking flows T2–T9, the
    44 px targets, an accessibility engine, or the Settings "Connected"
    rule.
  - `check_package_data.py` does not exclude `handoff/`, `designs/` or
    `branding/` from the wheel or sdist. They are not in the package today.
