# UI-UX Complete Test Report — skills-manager v2

**Date:** 2026-10-14
**Target:** `redesign/ui-v2` at `/home/uday-varmora/overnight-ui/worktree` (commit `cfd8bd5`)
**App:** skills-manager local web UI (`skillsmgr/webui/` + `skillsmgr/webapp.py`)
**Server:** `http://127.0.0.1:8791` via `.redesign/dev.sh` (isolated HOME + data, seeded: 48 skills global, 96 logical / 105 instances / 8 scopes in sandbox runs)
**Mode:** report-first, no repo fixes applied (probe skills created during testing were purged; screenshots only)

## Method

Testing used four layers, all executed — not claimed:

| Layer | What was used |
|---|---|
| Skills | `playwright-expert`, `test-master`, `frontend-accessibility`, `frontend-performance`, `frontend-security` (loaded via Skill tool) |
| Subagents | `test-automation-engineer` (10 real-user journeys), `ui-designer` (design-system audit), `frontend-developer` (interaction/responsive/performance), `application-security-engineer` (frontend + localhost boundary), `persona-walkthrough-specialist` (3 cognitive walkthroughs) |
| MCP servers | `agent-browser` (`agent_browser_open`, `agent_browser_snapshot`, `agent_browser_click`, `agent_browser_screenshot`, `agent_browser_close`) on session `ui-audit`; venv Playwright 1.63 Chromium (`--no-sandbox`); `curl` transport probes; `node` renderer replay |
| Gates + harnesses | `check_design_tokens.py`, `check_docs.py`, `.redesign/check_coverage.py`, `.redesign/check_inventory.py`, `node --check`, `python -m unittest` (stdlib + `tests/e2e/` one-process-per-module), `browser_harness.py` equivalents, `smoke_web.py` |

Screenshots captured: `/tmp/opencode/audit-overview-1280.png`, `/tmp/opencode/audit-library-1280.png` (MCP), plus `.redesign/evidence/` suites from prior runs. Both reviewed: Overview and Library render dense/calm in dark theme, no slop, no overflow.

## Executive summary

- **Automated gates:** design tokens PASS, docs PASS, coverage PASS (69 rows), frontend contracts (145 tests) OK, sampled E2E (135 tests across 12 modules) OK with zero console errors and zero overflow at 390–1920px. Two gate-level failures exist and are both test/inventory hygiene, not app regressions (see §2).
- **Real-user journeys (10/10 PASS):** first-scan, library browse/search/filter/detail, create/edit/validate, disable/enable+undo, trash/restore, batch plan-review, install read-only, recovery/snapshots, palette + shortcuts, settings persistence.
- **Design:** contract holds. `check_design_tokens.py` green; anti-slop clean; shell dims hold (48px topbar, 24px statusbar, 56px rail, drawer <761px). Deviations found are uncovered ground (measure token, grid shadow, rail default-closed, radii aliases).
- **Interaction:** dialogs (16 `data-modal` keys), toasts (4s/8s), skeletons, filtered-empty, offline banner, focus trap/return all verified. Two real traps: double-click New skill closes its own dialog; offline strip only fires on the Library path.
- **Security:** no Critical/High exploitable finding. Renderer escapes first, localhost boundary (Host/Fetch-Metadata/Origin, no CORS, JSON-only mutations, traversal/upload guards) holds. One Low hardening item (`:href` allowlist).
- **Personas:** new user trusts read-only honesty + attention queue but is confused by jargon and spooked by probe-purge history; power user commits (density, plan review) but needs side-by-side diff; cautious user trusts batch review but will not single-purge today.
- **Top fixes:** touch-target floors, double-click guard, grid shadow, inventory classification, settings-test comment bug, single-purge confirm, sync defaults (exclude source).

## 1. Scope

Views (9): `overview`, `skills` (Library list/grid + Instances), `profiles`, `install`, `recovery`, `workspaces`, `quality`, `settings`, `trash` (door inside Recovery, no rail button — kept per 0.1 decision).

Dialogs (16 `data-modal`): `skill`, `remove`, `purge`, `validate`, `doctor`, `stats`, `history`, `templates`, `newtemplate`, `import`, `sync`, `batch`, `update`, `deleteProfile`, `commands`, `help`. (`dialog:install` removed in 5.2b — routes to view.)

States: loading/skeleton, empty/first-run, filtered-empty, error+retry, offline strip, toasts (ok/error/undo), stale-response guard, mobile overlay/sheet.

Shortcuts: `Ctrl/Cmd+K` palette, `/` search, `?` help, `Esc` menu/modal, `Tab` trap, `j/k` + arrows in Library, palette Arrow/Home/End/Enter.

Preferences (local-only): `skillsmgr-theme`, `skillsmgr-text-size`, `skillsmgr-locale`, `skillsmgr-scope`, `skillsmgr-library-mode`, `skillsmgr-browse-mode`, `skillsmgr-budget-window`, `skillsmgr-first-scan-dismissed`.

## 2. Automated gates (measured)

| Gate | Result | Evidence |
|---|---|---|
| `check_design_tokens.py` | PASS | 26/26 palette values match `DESIGN.md`; 6 rem steps consumed (230 decls, 3 declared exceptions); space/radius/motion bounds hold; no third palette; no gradient/blur tokens; fonts 6 faces + licence |
| `check_docs.py` | PASS | `DOCUMENTATION/SOURCE CONSISTENCY PASSED` |
| `.redesign/check_coverage.py` | PASS | 69 required rows, every claimed test exists, no orphan e2e file |
| `.redesign/check_inventory.py` | FAIL (hygiene) | 3 webui-reading files unclassified: `tests/test_redesign_site.py`, `tests/test_redesign_trash_pane_list.py`, `tests/test_redesign_trash_purge_once.py`; untracked `site/`, `tests/e2e/test_site.py` |
| `node --check app.js domain.js` | PASS | both syntax OK |
| `tests/test_redesign*.py` (626) | 1 FAILURE (test bug) | `tests/test_redesign_settings_layout.py:121` — `assertNotIn("scroll", side.lower())` where `settings_sidepanel_block()` (`tests/test_redesign_settings_layout.py:73`) slices 3000 chars including the 7.4f HTML comment containing "scrolls". Fails on a correct tree; `settings_detail_block()` strips comments, the sidepanel helper does not |
| `test_frontend_seam_contracts` + `test_webui_contracts` + `test_g8_ui_structure_contracts` (145) | OK | Ran 145 tests OK |
| E2E sampled (135 across 12 modules) | OK | `test_overview_summary` + `test_shell_chrome` + `test_library_chrome` (30) OK; `test_trash_door` + `test_trash_pane_blank` + `test_trash_purge_row` + `test_command_palette` + `test_detail_tabs` (64) OK; `test_font_render` + `test_icon_render` + `test_dark_render` + `test_forced_colors` + `test_a11y` (41) OK |
| Live static probe | PASS | 9 views, 15 modals, 5 inline `:style` (numeric meter widths only), 0 inline handlers, 0 `<form>`, 0 `v-html`, 138 `aria-label`, 110 `role=`, 52 `tabindex`, 0 emoji-range chars |
| Live overflow sweep | PASS | `scrollWidth-clientWidth = 0` at 390/768/1100/1280/1440/1920, light+dark; 0 console errors; 0 failed requests |

## 3. Real-user E2E (Playwright Chromium, venv)

All 10 journeys PASS, zero console errors and zero failed requests in every journey. Probe skills (`e2e-probe-*`, `xss-probe-*`) created and purged; seeded trash count unchanged.

| # | Journey | Result | Notes |
|---|---|---|---|
| J1 | First-run / Overview scan | PASS | `h1=['Overview']`, Rescan refreshes, skip-link Tab order sane |
| J2 | Library browse/search/filter/detail | PASS | `getByPlaceholder('Search skills')`, All/Active/Disabled, 5 detail tabs render, keyboard search works |
| J3 | Create/edit/validate | PASS | `#f-name/#f-desc/#f-body` create → edit → save persists; Validate modal focuses `#v-name`; Esc closes |
| J4 | Disable/enable + undo | PASS | Disable → Enable + Undo toast; Undo restores |
| J5 | Trash/restore/purge | PASS | Remove → confirm → Move to trash; Recovery per-row Restore works; purge-all not clicked (would destroy seeds) |
| J6 | Batch operations | PASS w/ note | Bulkbar + plan-review (`Review disable batch`, exact targets, plan hash, `Execute exact plan`); no Undo after execute (finding F-07) |
| J7 | Install/registry | PASS | Curated/Browse/Search switch, read-only posture, zero writes |
| J8 | Recovery/snapshots | PASS | Trash table, `Purge all 3`, import/export, history+snapshots modal |
| J9 | Palette + shortcuts | PASS | `Ctrl+K` 24 commands, combobox focus, ArrowDown, Esc, `?` help; `disab` keyword miss (finding F-08) |
| J10 | Settings | PASS | Theme Dark/Light → `data-theme`, Large → `data-text-size`, locale `en-GB` persists after reload |

Cross-cutting: focus moves to `#f-name`/`#v-name`/combobox/drawer Close on open; every modal Esc-dismissable; toasts 4s plain / 8s undo bracketed empirically; API seam ~8 calls per 10 view-navs (in-flight dedup working).

## 4. Visual / design-system audit

`check_design_tokens.py` green. MCP screenshots confirm Overview + Library dark at 1280 read as one product: teal accent, bone ground, hairlines not shadows, sentence case, no gradients/glow/glass/emoji/hero-cards.

Passes: pills dot+label (`skillsmgr/webui/index.html:1362`), selection 2px marker + tint (`skillsmgr/webui/styles.css:1582`), diff mono + tint + sign glyph (`skillsmgr/webui/index.html:681`), stepper Fetch→Review→Commit with `aria-current`, row actions are text buttons, 16 icon-only buttons all carry `aria-label`.

Deviations (all in ground the gate does not cover): F-03 (grid shadow), F-04 (measure token), F-05 (rail default), F-10 (radii/height drift), F-11 (nav double-announce), plus table-header uppercase vs sentence-case (`skillsmgr/webui/styles.css:2236`).

## 5. Interaction / responsive / performance

Verified: 16 widths × themes zero overflow; drawer trigger only <761px, opens 269–300px with scrim, Esc closes; rail exactly 56px ≥768; Library Back `← Back to Library` mobile-only; 16 dialogs open/focus-trap/Esc/focus-return; dirty-editor Esc raises discard confirm; empty-name submit shows inline `Name is required.`; filtered-empty → reset restores 96 rows; banner `position:fixed bottom:48px`, layout-top delta 0px; FCP 552ms, heap 18MB.

Issues: F-02 (double-click), F-06 (offline scope), F-09 (cache + payload weight), F-07 (undo asymmetry), plus `.brand` 20px tall ≤390px and 7/24 coarse targets <44px (advisory).

## 6. Security audit (frontend + localhost boundary)

Verdict: no Critical/High exploitable finding.

- CSP is exactly `default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'` (`skillsmgr/webapp.py:842`). 0 inline scripts, 0 handlers, 0 forms, 0 `javascript:` URIs; all scripts same-origin; only 2 `v-html` sinks, both through escaped `renderMarkdown`.
- Renderer (`skillsmgr/webui/domain.js:53`, `domain.js:399`) escapes first, links allowlisted `https?://`. 6 stored-XSS payloads (script, img-onerror, svg-onload, `javascript:` link, quote-breakout, iframe/form) all neutralized live and via `node` replay.
- Transport (`skillsmgr/web_security.py:24`, `skillsmgr/webapp.py:998`): evil Host → 403, `Sec-Fetch-Site: cross-site` → 403, evil Origin/Referer → 403, no CORS headers ever, JSON-only mutations (415), traversal `../` → 400, multipart `../../` → 400 naming the part, limits (`25MB`, 200 parts, `limit≤500`) enforced.
- Install runner allowlisted, `shell=False` (`skillsmgr/cli_handlers.py:1336`); localStorage is 8 UI prefs only, no tokens/bodies; every sampled response carries `nosniff/DENY/no-referrer/same-origin/CSP/no-store`; `TRACE/OPTIONS` → 405 JSON.
- Hardening: F-12 (`:href` allowlist), `unsafe-eval` accepted trade-off (SEC-4, needs precompiled Vue to drop), `Server` version banner, static-404 plain-text deviation, missing `Permissions-Policy`.

## 7. Accessibility

- Structure: skip link first, 1 visible `h1` per view, `nav`+`main` landmarks, 16 `role="dialog"` with `aria-modal`, 9 `aria-live="polite"` regions, `inert` on background (8 sites), 34 `.focus()` managers, `:focus-visible` 18 rules.
- Inputs: 0 unlabeled on Overview/Library/Profiles/Recovery/Workspaces/Quality; Install has 1, Settings has 5 unlabeled inputs in probe (needs per-control triage — labels may be `aria-labelledby` missed by probe heuristic; verify manually).
- Contrast: token gate asserts all text pairs ≥4.5:1, controls ≥3:1; dark sweep (1777 pairs in prior 6.1b run) 0 failures.
- Keyboard: `/`, `Ctrl+K`, `?`, `Esc`, `Tab` trap, `j/k`/arrows verified in Library and palette; destructive dialogs focus cancel first.
- Touch: fails 24px minimum on chips/checkboxes/brand (F-01); coarse 44px gaps on topbar/text-buttons (advisory).
- Screen reader: nav double-announce (F-11); palette search misses action keywords (F-08); validate modal does not prefill known skill name.

## 8. Persona walkthroughs (qualitative, no writes)

- **Mara (new user):** confidence 6/10. Read-only honesty line and attention queue delight; jargon (roots/instances/divergent/unaddressable), token math without verdict framing, and probe-purge rows in Recent activity hurt trust. Statusbar local-first line should surface higher.
- **Devon (power user, 100+ skills):** relevance 9/10, commits. Loves scope menu density, palette, plan-review batch. Blocked by no side-by-side divergent diff, tag/batch Remove label collision, selection-vs-visible contradiction, all-scopes-prechecked sync.
- **Priya (cautious operator):** clarity 8/10, will not purge today. Safe defaults + batch review trusted; single purge one-click path and `Global→Global` sync noise break the safety story. Delete-profile dialog voice ("No skill is changed on disk") is the model.

## 9. Findings catalog

| ID | Severity | Finding | Repro / location | Fix |
|---|---|---|---|---|
| F-01 | Medium | ~120/145 Library controls under WCAG 2.2 2.5.8 24px; `.brand` 20px ≤390px | Measure `getBoundingClientRect()` on `button,a,input[type=checkbox]`; `skillsmgr/webui/styles.css:4217` | `min-height:24px` chips, padded checkbox hit-area, brand floor |
| F-02 | Medium | Double-click New skill opens then closes its dialog | `dblclick(.topbar-new)` → 0 `[data-modal="skill"]`; `skillsmgr/webui/index.html:2162`, `skillsmgr/webui/app.js:4444` | 300ms overlay grace or debounce `openCreate` |
| F-03 | Medium | Grid cards cast elevation shadow, gate blind | `skillsmgr/webui/styles.css:1746` `.skill-grid > li { box-shadow: var(--shadow) }` | Drop shadow, add selector to gate shadow list |
| F-04 | Medium | `--measure:68ch` never read; prose 72ch/82ch | `skillsmgr/webui/styles.css:148`, `styles.css:2633`, `styles.css:2162` | Wire token or amend contract |
| F-05 | Medium | Rail hides scope switcher + token share by default; no 240px stage | `skillsmgr/webui/styles.css:1124`, `skillsmgr/webui/app.js:445` | Default-open on wide screens or amend contract |
| F-06 | Medium | Single purge least-guarded destructive path; empty-trash same | `data-modal="remove"`, `data-modal="purge"` | Type-to-confirm or second explicit checkbox before enabling permanent delete |
| F-07 | Medium | Sync pre-checks all scopes incl. source | Sync picker, `skillsmgr/webui/app.js` | Pre-check all except source; persist last targets |
| F-08 | Low | Offline strip only on Library path | `skillsmgr/webui/app.js:3183` vs `app.js:3241` | Set `offline=true` on all transport failures or document per-pane contract |
| F-09 | Low | `no-store` on immutable assets + heavy payloads | `skillsmgr/webapp.py:748`; `index.html` 238KB, `app.js` 252KB, `styles.css` 228KB, `/api/skills` 212KB, `/api/doctor` 159KB; 8 long tasks max 728ms | Immutable caching for fingerprinted assets; slim/paginate APIs; trim comments |
| F-10 | Low | Radii/height drift: `--radius-xs:4px`, modal 16px vs 12px, `.btn-sm` 26px vs 28px, 36px fields vs 32px, `.btn-danger` filled red vs spec | `skillsmgr/webui/styles.css:126`, `styles.css:3040`, `styles.css:872`, `styles.css:861` | Fold aliases onto 6/8/12 scale; reconcile danger variant |
| F-11 | Low | Nav buttons double-announce ("Library Library") | MCP snapshot refs e9–e16; `data-tip` + visible label | `aria-label` on button or `aria-hidden` on one source |
| F-12 | Low | Unsanitized `:href` on adapter link | `skillsmgr/webui/index.html:1904`, `skillsmgr/webui/app.js:310` | Allowlist `https?`, gate `v-if` on sanitized value |
| F-13 | Low | Palette misses action keywords (`disab` → no results); Validate modal does not prefill; no Undo after batch execute; undo success silent | Palette matcher; `data-modal="validate"`; `app.js:4191` | Keyword aliases; prefill from selection; batch undo or receipt toast; "Restored …" toast |
| F-14 | Hygiene | Inventory gate red; settings scroll test red on correct tree | `.redesign/check_inventory.py`; `tests/test_redesign_settings_layout.py:73`, `:121` | Classify 3 files + remove/track `site/`; strip comments in sidepanel helper or scope assertion to controls |
| F-15 | Info | `Server` banner, static-404 plain text, no `Permissions-Policy`, local paths by design | `skillsmgr/webapp.py:1027`, headers | Trim banner; JSON 404 for static; add `Permissions-Policy`; document path exposure |

## 10. Verified clean (do not regress)

Tokens, anti-slop, pills/selection/diff/stepper, 48/24 chrome, drawer/rail/back behavior, 16 dialogs focus lifecycle, toast timings + cap, skeletons + `aria-busy`, error branches with Retry, request dedup (~8 calls / 10 navs), themes, XSS renderer, localhost gates, traversal/upload/install guards, read-only honesty copy, trash-first defaults, batch plan review.

## 11. Not verified

Non-Chromium engine, real screen-reader pass, 200%/400% zoom, reduced-motion runtime, post-execute receipts, rollback confirm path, selection-loss repro, side-by-side diff (does not exist), full `verify.sh` to completion in one run (exceeds 900s harness ceiling; verified by hand in slices).

## 12. Recommended order

1. F-01 + F-02 + F-03 + F-14 (small, real UX/test traps). 2. F-06 + F-07 (safety asymmetry — the trust-breaking pair). 3. F-08 + F-09 (offline contract + payload/cache diet). 4. F-04/F-05/F-10/F-11/F-12 (contract reconciliation). 5. F-13 polish + persona quick wins (scope label in Remove dialog `in {{ scope-label }}`, qualify `Disable in {{ scope-label }}`, sanitize first-run activity, gloss diagnostics, verdict-frame token band).

## Appendix — commands run

```bash
cd /home/uday-varmora/overnight-ui/worktree
python3 check_design_tokens.py
python3 check_docs.py
python3 .redesign/check_coverage.py
python3 .redesign/check_inventory.py
node --check skillsmgr/webui/app.js && node --check skillsmgr/webui/domain.js
PYTHONDONTWRITEBYTECODE=1 HOME=$(mktemp -d) SKILLS_MANAGER_DATA=$(mktemp -d) python3 -m unittest discover -s tests -p "test_redesign*.py"
.redesign/dev.sh reset && .redesign/dev.sh start  # http://127.0.0.1:8791
source /home/uday-varmora/overnight-ui/venv/bin/activate
python3 -m unittest tests.e2e.test_overview_summary tests.e2e.test_shell_chrome tests.e2e.test_library_chrome
python3 -m unittest tests.e2e.test_trash_door tests.e2e.test_trash_pane_blank tests.e2e.test_trash_purge_row tests.e2e.test_command_palette tests.e2e.test_detail_tabs
python3 -m unittest tests.e2e.test_font_render tests.e2e.test_icon_render tests.e2e.test_dark_render tests.e2e.test_forced_colors tests.e2e.test_a11y
```

MCP: `agent_browser_open` → `agent_browser_snapshot` → `agent_browser_click(Library)` → `agent_browser_screenshot` (Overview + Library) → `agent_browser_close`.
