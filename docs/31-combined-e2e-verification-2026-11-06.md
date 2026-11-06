# Combined E2E Verification — 2026-11-06

**Version 1.0.0**

**AI manifest**: Consolidated continuation report for frontend `7d225dc` and
completed backend `fbe8ec2`, merged normally into `ui/prototype-final`.
Historical findings retain their IDs. Browser interactions, API/CLI regression
checks, packaging and human accessibility coverage are distinguished below.
No release or human accessibility sign-off is claimed.

## Identity and boundaries

**[SPEC]** The frontend worktree started clean at `7d225dc`. The backend
session was idle with a clean worktree at `fbe8ec2`; its normal merge applied
without conflicts. The shared JSON transport in `fe46552` is retained, as are
both histories. Main, releases, remotes and the dirty original design checkout
were not changed. Runtime dependencies, CLI/Store surfaces, SQLite schema and
filesystem authority remain unchanged.

**[SPEC]** Browser writes use isolated HOME/data fixtures. The optional runner
allocates a private directory, starts the server on an OS-selected loopback
port, and stops its server after the run. Chrome's renderer sandbox stays on.
Localhost binding is the unauthenticated service's only security boundary;
no port was forwarded, tunneled or published.

## Evidence provenance and reproduction

**[NOTE]** The handoff's `evidence/session-evidence.zip` preserves historical
CLI/API reports and `scratchpad/e2e-ui/t1.mjs` through `t24.mjs`, fixtures and
screenshots. Its UI `REPORT.md` is a 231-byte stub. Detailed browser findings
were recovered from archived parent/subagent transcripts. The historical
467-check CLI and 532-check API runs predate backend integration; they are not
combined-tree results. The old runners were inspected but not rerun unchanged:
they contain fixed ports, absolute paths and shared temporary sentinels.
Backend-only evidence remains in @docs/30-backend-continuation-2026-11-06.md.

**[SPEC]** Fresh browser checks are reproducible with the developer-only
[fixture launcher](../tools/e2e_v2/run.py) and
[assertion runner](../tools/e2e_v2/browser.cjs). Installed tooling for this run:
Linux, Chrome 157.0.8103.38, Node 22.22.3 and Playwright 1.61.0. Playwright is
an optional external developer tool, not a package/runtime dependency.

```bash
# NODE_PATH is needed only if Playwright is outside Node's normal module path.
NODE_PATH=/path/to/node_modules CHROME_BIN=/path/to/trusted/chrome \
  python3 tools/e2e_v2/run.py --output-dir /private/evidence-directory

# Actual browser zoom requires an isolated X11 display and xdotool.
NODE_PATH=/path/to/node_modules CHROME_BIN=/path/to/trusted/chrome \
  BROWSER_TEST_HEADED=1 xvfb-run -a \
  -s '-screen 0 1440x1080x24 -nolisten tcp' \
  python3 tools/e2e_v2/run.py --output-dir /private/evidence-directory
```

The launcher retains only synthetic fixtures and results under a fresh run
folder. It never deletes a supplied output directory. Results are assertions
with a nonzero failure exit. Do not point the JavaScript helper at a real
skills service. The checked-in evidence selection is under
[combined-2026-11-06](../.specs/evidence/combined-2026-11-06/verification.json).
Full scratch output is retained locally at `/tmp/skillsmgr-parent-verification`;
older exploratory browser scripts are not the acceptance runner.

## Frontend findings

**[SPEC]** The table separates functional fixes from documentation corrections
and unsupported rendering features. “Retested” means fresh combined-tree
browser evidence, supplemented by the executed model/transport contracts.

| ID | Historical symptom and reproduction | Current disposition and evidence |
|---|---|---|
| D1 | Inbox offered replacement of non-UTF-8 `damaged-one`, then failed and exposed decoder/path details | Retested: “Show me how” preserves exact bytes and advises keeping the original. Backend force sync can retain binary snapshots; this screen keeps manual repair because text Undo cannot restore them. Red-first regressions also cover mixed malformed/binary targets and refused-link repair sources. |
| D2 | Dirty editor → another screen → discard stayed on the old skill | Retested: Keep editing preserves the editor; Discard completes navigation to Home. |
| D3 | Fix an Inbox item, then Undo; disk reverted but queue/count did not | Retested for divergent text and malformed frontmatter: exact prior bytes and the Inbox item return; fixed count returns to zero. |
| D4 | Press Enter on an evenly split item with no source selected | Retested: primary remains disabled; no sync is issued and bytes stay unchanged. |
| D5 | Opening Edit left focus on the document body | Retested: Description receives focus. |
| D6 | Map counted non-skills and said “1 copy differ” | Retested: map total equals shelf total excluding `.system`; singular wording uses “differs”. |
| D7 | Acknowledged notes counted as fixes; Home and Inbox disagreed | Retested: note acknowledgement leaves “0 fixed”; Home count tracks the same queue. Empty summaries describe remaining Inbox items and explain that hidden notes return after reload. |
| D8 | New skill focused the hidden submit control | Retested: visible Name field receives focus; creation reaches the real fixture filesystem. |
| D9 | Single-location trash/share dialogs required an extra selection | Retested: sole target is selected, cancellation preserves files, Add to agent creates the selected copy. New-copy sync explicitly has no text Undo. |
| D10 | Markdown italics/links, tables and nested lists displayed literally | Partially fixed and retested: italics render; link labels and addresses render as inert text; hostile HTML stays escaped. Tables and nested-list hierarchy remain unsupported; no general Markdown conformance is claimed. |
| D11a | Invalid archive exposed gzip/library exception text | Retested: invalid archive gives actionable backup guidance. Injected traceback/path failures are sanitized on initial load and in toasts; partial-sync reasons use the same formatter. |
| D11b | Recovery called folder mtime the removal time | Wording correction, retested: label is “last changed”. No actual removal timestamp was added or inferred. |
| D12 | Phone dark map used white rows with near-white text | Retested with actual dark theme: theme surfaces are used; sampled normal row text exceeds 4.5:1. This is sampled contrast, not a full accessibility audit. |
| D13 | Long agent paths widened mobile Home | Retested with real fixture paths over 200 characters: no document overflow in the phone matrix. |
| D14 | Top classic-tools link was under 24px high | Retested: the top link meets the 24px target threshold. |

**[NOTE]** The favicon no longer causes the historical missing-icon request.
Copy letters identify distinct text, majority remains a suggestion, and ties
require a choice. Refused links stay distinct from damaged documents and
non-skills. No recency, runtime usage, safety or reliable loading is inferred.

## Integration corrections and limits

**[SPEC]** Native declarations now appear in a read-only partial-settings
section in v2 detail. Browser fixtures cover Claude `off`, OpenCode `deny`,
invalid and unavailable settings. Missing settings and Codex's deferred TOML
observation remain explicit. “File enabled” switches only rename documents;
the panel never turns declarations into effective loading or writes settings.
Invalid/unavailable sources say “Declaration unknown”, rather than claiming
absence of a rule.

**[SPEC]** Sync also copies file enabled state and companion files. The UI now
discloses that behavior before sync/share. Undo captures the target's prior
file state, temporarily enables it for text restore when necessary, and
reapplies its prior state afterward. Browser checks cover both enabled source
→ disabled target and disabled source → enabled target, including exact text
and filename restoration. Failure cleanup is covered by executed method
regressions; Inbox refreshes even after an Undo error.

**[SPEC]** Undo is withheld if any successful target lacks known prior state,
a uniquely identified fresh readable snapshot, or complete snapshot evidence.
New destinations, binary snapshots and uncertain/ambiguous history cannot
produce a misleading partial Undo button. Pre-sync history failure aborts
before mutation; post-sync history failure reports unavailable Undo while
preserving the successful sync. These branches have executed regressions.

**[NOTE]** Undo restores document text and file enabled state only. Companion
files are not restored by this text snapshot endpoint. Multi-target Undo uses
separate REST requests, so a later failure can leave earlier targets restored;
the UI refreshes and reports the error. External writers and changes after
review are not made transactional by the frontend. Broader locking/identity
limits and binary manual recovery are documented in
@docs/30-backend-continuation-2026-11-06.md.

## Additional finding from this continuation

**[SPEC] C1 (P2), fixed and retested:** actual 400% Chrome zoom reduced the
CSS viewport to 320px and exposed horizontal overflow in Recovery. Its grid
required a 320px column inside a narrower padded page. The grid now caps its
minimum at the available width; controls shrink and action labels wrap. The
same browser assertion was red before the fix and is retained in the runner.
This does not change the selected design or API.

## Coverage and check results

**[SPEC]** The browser fixture covers Home, shelf, detail, Sync map, Inbox and
Recovery at desktop 1280×900 and phone 390×844 in both themes (24 combinations).
Create, edit, preview, save, sync, Undo, toggle, share, trash restore, archive
import/export, cancellation, stale-file refusal and a delayed double-click are
asserted separately. Empty and one-record shelves are checked with synthetic
list responses. Screen layouts are measured for document overflow and
captured; that measurement cannot prove all content is unclipped.

**[SPEC]** Accessibility checks include initial form/editor focus, modal Tab
containment, navigation/cancellation, disabled-action keyboard behavior and a
visible focus indicator under Chromium forced-colors emulation. Actual Chrome
zoom is driven through desktop keyboard input on isolated X11; it is accepted
only when device-pixel ratio confirms 200%/400% and CSS width shrinks accordingly.
CSS-only magnification from the older scratch pass is not counted as browser
zoom evidence.

**[SPEC]** Final combined-tree results:

| Check | Result |
|---|---|
| Python 3.10.20, 3.11.15, 3.12.3, 3.13.13, 3.14.3 | 1,337 tests, OK on each interpreter |
| Durable browser runner | 24 assertion groups passed; 24 viewport/theme/screen combinations; actual 200%/400% zoom across all six screens and create dialog |
| Classic harness | Six widths (320/400/640/900/1280/1440) and four synthetic failure/empty scenarios passed |
| Store/web smoke scripts | Both passed |
| Complexity | 721 functions, 16 files, passed; no existing baseline increased |
| Documentation, design tokens, compilation and JS syntax | Passed |
| Ruff 0.16.8 F821/F822/F823 and Bandit 1.9.4 | Passed; Bandit has existing suppression-comment warnings, no findings |
| Pinned hash-verified wheel/sdist build and archive inspection | Passed; Vue hash, 25 UI files, two example files, license and exclusions checked |
| Clean wheel install | Passed; built wheel UI bytes also matched the source |
| Automatic clean sdist check | UNAVAILABLE: fresh checker environment lacks setuptools |
| Separate clean sdist install | Passed with pinned build tools seeded, no build isolation, and all 27 UI/example files compared to source |

**[NOTE]** Exact logs, source hashes, sampled contrast, zoom measurements and
artifact hashes are recorded in the evidence manifest. These are local
verification artifacts, not a release. The fresh API/CLI evidence is the
combined regression suite and both smokes; the old 467/532 totals are not reused.

**[SPEC]** R1/S1 streamed archive limits, R2/S2 intake-sidecar stripping,
R5/S3 private bounded locks, R9/S4 JSON-only POST policy and R14 malformed-input
handling run in the combined regression suite. Source-update approval,
replay/stale checks, archive recovery, native evidence, validation/Unicode
advisories and mutation races are exercised by their regression tests.
Classic and v2 bodyless POSTs are additionally exercised in the browser.

**[NOTE]** Earlier red runs are retained as diagnosis, not final passes:
parallel suites first collided through an upload test's shared `/tmp` glob;
per-interpreter TMPDIR then invalidated a test that specifically requires a
shared temporary root. The upload test now asserts that its own rejected call
allocates no staging directory, instead of observing other processes. Final
runs use the normal temporary-root environment. Early browser probes had
stale-document, theme-selection and target-selector errors; the durable runner
asserts actual theme and forces a fresh document for fixture observations.

## Review against the current diff

**[SPEC]** Hostile-input review retained backend containment, byte/depth caps,
JSON request policy, private locks and clean error handling. New display
paths escape skill/settings data. Mixed binary targets and refused-link repair
sources were reproduced red-first before the stricter repair predicate.

**[NOTE]** Empty/one-record browser states and missing/corrupt files were
exercised; 10,000 rendered items remain unverified. Snapshot discovery refuses
uncertain or multiple fresh IDs. Double-click suppression and one stale-file
scenario were exercised; disconnects and arbitrary external writers remain
outside the guarantee. New temporary-enable logic uses `finally` to restore
file state on failed text restore. Multi-target and companion-file rollback
limits are explicit above. The implementation stays on existing endpoints;
no new API or inferred loading model was needed.

## Unverified and pending decisions

**[?]** Orca is installed, but no end-to-end spoken screen-reader session was
validated. Chromium accessibility/focus checks are not that validation.
Human perceptual review, comprehensive contrast/touch testing, other browser
engines, Windows execution, DNS-rebinding browser experiments, arbitrary
external-writer coordination, disconnected multi-step mutations and a
10,000-item rendered UI run remain unverified. Only the named stale and
double-click browser scenarios are asserted; no exhaustive race claim is made.

**[NOTE]** v2 stays at `/v2/`; classic remains at `/`. Install, Profiles,
Quality, Workspaces and Settings are still classic-only and were not all
manually exercised through every workflow. Agent-folder trash restore,
bodyless list projection (R3), Codex TOML, sidecar installation binding,
symlink policy and docs/29 maintainer decisions remain pending. No new API,
marketplace, release or automatic disabling was introduced to hide those gaps.
