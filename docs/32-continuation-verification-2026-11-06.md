# Continuation Verification — Classic Screens, Scale, Screen Reader (2026-11-06)

**Version 1.0.0**

**AI manifest**: Closes three verification gaps that @docs/31-combined-e2e-verification-2026-11-06.md
left open on `ui/prototype-final` after merge `c00062b`: end-to-end coverage of
the classic-only screens (Settings, Profiles, Quality, Workspaces, Install), a
synthetic 10,000-instance rendering run, and a screen-reader investigation with
Orca. Records the defects each found, their fixes and retests, and exactly what
remains unverified. No release, push, API change or human accessibility
sign-off is claimed.

## Boundaries

**[SPEC]** Every run used private HOME and data roots (mode 700), an
OS-selected or private loopback port, and headless or virtual-display Chrome
with its renderer sandbox on. Nothing touched the maintainer's live skills.
Install checks never ran a package manager, fetched, searched or committed:
the browser aborted such requests. Localhost binding is the unauthenticated
service's only security boundary; no port was forwarded, tunnelled or published.
No CLI command, public Store method, schema, runtime dependency or REST route
changed.

## 1. Classic-only screens

**[SPEC]** New developer-only tool: [classic launcher](../tools/e2e_classic/run.py)
and [assertion runner](../tools/e2e_classic/classic.cjs), modelled on
`tools/e2e_v2`. Playwright is an optional external developer tool, not a
dependency.

```bash
NODE_PATH=/path/to/node_modules CHROME_BIN=/path/to/trusted/chrome \
  python3 tools/e2e_classic/run.py --output-dir /private/evidence-directory
```

| Screen | Scenarios | Assertions | Result after fixes |
|---|---|---|---|
| Settings | 5 | 40 | pass |
| Profiles | 9 | 74 | pass |
| Quality | 7 | 41 | pass |
| Workspaces | 3 | 34 | pass |
| Install | 6 | 75 | pass |
| Cross-cutting | 7 | 48 | pass |

Two consecutive full runs: 37 scenarios, 312 assertions, 0 failures
(`.specs/evidence/continuation-2026-11-06/e2e-classic/`). Coverage includes
profile preview states against disk, plan targets limited to observed
instances, stale/widened/tampered plan rejection, byte-identical skills after
profile delete, read-only Quality (whole-tree hash unchanged), Workspaces
containment and redaction, and Install's offline preview and trust blockers.

| ID | Finding | Disposition |
|---|---|---|
| C-1 | Batch review dialog returned focus to the topbar on Escape instead of its opener | Fixed: `openBatch()` records the opener like every other dialog. Retested in Profiles and the Library batch bar. |
| C-2 | Selecting a skill in Quality replaced the Skill Hygiene Report with no way back short of a reload | Fixed: a "Hygiene report" button, re-clicking Quality, and phone "Back to Quality" return to it. Retested. |
| C-3 | A Profiles scenario timed out intermittently | Test race, not a product defect: the test mutated disk before the batch plan existed, so the planner correctly refused. The test now waits for the plan; Profiles passed 3/3 afterwards. |

**[NOTE] Observed, not changed (P3):** the batch plan hash binds targets but
not their before-state or sync source content, so a target already enabled is
reported "already-set" and a sync copies content edited after review. Enter in
the Workspaces project field does nothing. The classic Install dialog does not
display trust blockers that the API returns. These are recorded for the
maintainer; changing plan binding is a contract decision.

## 2. Synthetic 10,000-instance run

**[SPEC]** Fixtures of 100, 1,000 and 10,000 instances (10k: 4,757 logical
skills, 331 groups with a differing copy, 96 malformed, 43 disabled), three
runs each, fresh browser per run. The host was under memory pressure, so
absolute times are pessimistic. Scripts and raw data:
`.specs/evidence/continuation-2026-11-06/perf10k/`.

| 10,000 instances | Ready ms (median) | Heap MB | DOM nodes | Worst stall ms |
|---|---|---|---|---|
| v2 Home | 9,201 | 56.2 | 226 | 247 |
| v2 Skills | 11,642 | 58.4 | 7,348 | 219 |
| v2 Inbox | 12,507 | 56.2 | 282 | 262 |
| Classic Library | 6,025 | 100.4 | 55,765 | 1,484 |

**[SPEC]** No crash, console error, failed request, or main-thread stall over
5 s occurred. This closes "10,000 rendered items remain unverified".

**[NOTE] Where the time goes.** `GET /api/skills?scope=all` is 56.7 MB at
10,000 instances (`body` is 63.8% of it) and takes about 9 s; v2 then renders
in under 0.45 s. `/api/scopes` rescans every root for token totals (3.7 s) and
competes with the list request. The classic Library renders every row (55,765
nodes) and a typed search key costs about 0.5 s, against 42 ms in v2, which
caps each group at 48 cards.

**[?] Decisions, not silent changes.** A body-less list projection (R3 in
@docs/28-project-review-and-recommendations-2026-11-06.md) would cut the
payload to about 36%. Letting `/api/scopes` skip token totals needs a new
parameter. Capping classic rows changes the classic Library's documented
"exact visible-set" behaviour. All three stay maintainer decisions.

## 3. Screen reader (Orca 46.1)

**[SPEC]** Orca ran with its debug transcript against Chrome
(`--force-renderer-accessibility`) inside an isolated virtual display and
private D-Bus/AT-SPI bus; keys were driven with xdotool. Speech-dispatcher
used a dummy module, so the evidence is what Orca **sent to speech**, not what
a person heard. A Playwright/CDP accessibility audit covered all eight v2
routes at 1280 and 390 px. The classic UI was spot-checked by CDP only.

| ID | Defect (v2) | Severity | Disposition |
|---|---|---|---|
| SR-1 | Enter on Inbox "Open skill" ran the fix instead of navigating (global Enter shortcut excluded buttons but not links) | P0 | Fixed: shortcuts never fire from a link, button, field or summary. Browser regression added. |
| SR-2 | "Skip to content" set the hash to `#main`, which the router read as Home | P1 | Fixed: the skip link focuses the page heading without routing. Regression added. |
| SR-3 | Undo toast expired after 9 s, before keyboard reach | P1 | Fixed: 20 s, and it pauses while focused or hovered (WCAG 2.2.1). Regression added. |
| SR-4 | Brand link unnamed at 900 px and narrower | P1 | Fixed: accessible name "Skills Manager home". Regression added. |
| SR-5 | Single-key `s` shortcut swallowed by browse mode | P2 | Mitigated: Inbox keys act only when focus is on the page, never on a control. A way to turn shortcuts off is not added. |
| SR-6 | Switch names omitted which copy differs | P2 | Fixed: name includes "copy B, differs from most places". |
| SR-7 | Duplicate "Fix it", "Open", "Peek" names | P2 | Fixed: names include the item. |
| SR-8 | "Show all skills" dropped focus to the document | P2 | Fixed: focus moves to search. |
| SR-9 | Hidden submit was a tab stop; Enter on an invalid name was silent | P2 | Fixed: not focusable; the error is announced. |
| SR-10 | Bottom-nav Inbox spoken as "6Inbox" | P2 | Fixed: "Inbox, 6 items". |
| SR-11 | Peek label flipped while also reporting pressed | P3 | Fixed: constant accessible name with `aria-pressed`. |
| SR-12 | Shelf groups created landmarks named "D", "L"… | P3 | Fixed: labelled groups, "Skills starting with D". |
| SR-13 | Sidebar labels were bold text, not headings | P3 | Fixed: headings with the same appearance. |
| SR-14 | Orca 46 did not speak `aria-current` | P3 | Not changed: the attribute is present; this is a screen-reader limitation. |
| SR-15 | Some targets under 24 px | P3 | Fixed for summaries, breadcrumb links, inline links and map checkboxes. |
| SR-16 | Sync map hub came before the agent nodes in focus order | P3 | Fixed: nodes first. |

After the fixes the v2 browser suite passed 27/27 in two consecutive runs and
the unslop scan stayed clean.

**[NOTE] Human walkthrough for real spoken sign-off (about 5 minutes, with a
throwaway data directory and Orca).** 1) Tab through Home's header and
landmarks; toggle the theme and hear its name. 2) Tab to each "Fix it" and
confirm each says what it fixes. 3) Press `/`, type "same", choose "Needs
care", hear the count and "pressed". 4) Open a skill with differing copies and
Tab to its switches; hear which copy differs; toggle one and reach Undo.
5) Press `?`, then Escape; focus returns. 6) New skill: type "Bad Name" and hear
the error. 7) Sync map: open the red agent and Tab through Peek buttons.
8) Inbox: Tab to "Open skill" and press Enter; it must open the skill and
change nothing. 9) At phone width, Tab to the logo and the bottom-nav Inbox.
10) Use "Skip to content" on a skill page and stay on that page.

## Still unverified

**[?]** A heard screen-reader session and human perceptual sign-off;
braille; other screen readers and browser engines; Windows; real phones;
exhaustive contrast and touch coverage; Ctrl-C exit codes; DNS-rebinding
browser experiments; disconnected multi-step mutations and arbitrary external
writers. Native settings evidence stays partial (Codex TOML is decision D-1).
v2 remains at `/v2/` and classic at `/`.
