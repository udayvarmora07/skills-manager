# Backend Continuation and Integration — 2026-11-06

**Version 1.0.0**

**AI manifest**: Implementation and triage record for the Codex continuation
of `claude/research-roadmap-c0a574`, starting clean at `2929fd5`. The original
dirty design checkout and the separate frontend worktree were not edited.
This is backend evidence; combined UI verification remains the parent's job.

## Completed implementation

**[SPEC]** R14 catches decoder recursion, bounds JSON nesting to 64 containers,
and guards project user expansion/resolution on workspace and doctor/explain
routes. R6 retains the compatibility mapping error with portability guidance,
adds one warning for non-spec keys and a 1,536-character combined description
lint, and discloses aliases under physical findings with explicit bounds. R4
adds fresh, partial JSON-native settings evidence to scoped records; R10 adds
bounded escaped hidden-Unicode/bidi/tag evidence to advisory risk scans.

**[SPEC]** Native evidence does not change enabled/disabled state and never
establishes effective loading. See
@docs/12-agent-root-discovery-2026-09-08.md for sources, ordering, limits and
unobserved settings. Unicode evidence scans name, description, body,
compatibility and allowed-tools; it does not scan arbitrary companion files
or nested metadata. An empty scan does not establish safety.

## Parent findings: disposition on the current backend

| Finding | Reproduction and disposition |
|---|---|
| P1 scoped edit/toggle race | Reproduced deterministically before fix. Read/validate/write is inside one canonical physical-directory `SKILL.md` lock; toggle and restore share it. Thread storms, separate-process aliases and clean repeated-toggle errors covered. Document symlinks are refused for mutations so renames cannot change their lock identity; directory aliases remain supported under containment. |
| P1 damaged target blocks force sync | Reproduced before fix. Preserve exact original document bytes in the normal snapshot directory before replacement, including a disabled global target. A binary snapshot is recoverable manually at `<data>/snapshots/SCOPE/NAME/ID.md`; automatic text restore refuses undecodable bytes. Sync keeps its existing source-state semantics. |
| Sync rollback/cleanup | Fault injection found successful installation could be destroyed after partial backup deletion. Installation rollback and post-install cleanup are now separate. Cleanup failure leaves installed data intact and retains backup evidence; another sync refuses to discard that backup. |
| P2 scoped search aborted on outside symlink | Reproduced through CLI with flat Claude and aggregate scopes. Flagged/unaddressable matches retain their scan observation without attempting a forbidden detail read. Good matches survive and outside content is not read. |
| P2 doctor advised wrong UTF-8 repair | Reproduced invalid-name and escaping-link rows mixed with a real decode failure. Loader now identifies actual encoding failures explicitly; scoped doctor only includes those in `undecodable_documents`. |
| Over-declared Content-Length hang | Reproduced with headers plus two bytes and a socket timeout. Handler now returns 413 without draining and closes the connection, preventing leftover-byte reuse. |
| Scoped non-UTF8 raw/detail read | Reproduced. Raw uses the lossy read/report reader; detail keeps malformed/decode evidence without logging a strict decoder exception containing document bytes. Writes still refuse lossy rewrites. |
| History zero / blank window | Reproduced. `limit=0` and explicitly blank context windows now return 400. Existing positive caps/defaults remain. |
| Bare `db` | Reproduced. Missing ACTION is now argparse usage error 2 before bootstrap. |
| Export destination | Reproduced replacement of an existing file and directory errno. Explicit file replacement remains supported and is now documented; directory destinations receive a clean error without temp-file/errno disclosure. |
| Malformed archive roundtrip | Reproduced in two temporary stores: export can preserve malformed source bytes, but import preflight refuses them before installing anything. Documentation now distinguishes whole-import preflight from per-skill commit `skipped` results. |
| `scopes --no-tokens --json` | Reproduced. Totals are now omitted in JSON too. Docs no longer promise faster scanning; document estimation still occurs. |
| `tokens --text @missing` | Reproduced. Missing/unreadable/non-UTF8 file input now errors instead of estimating the path literal. |
| `view --scope all` | Reproduced. Docs corrected to require an exact scope; no ambiguous name winner introduced. |
| `--json` placement | Reproduced root-parser rejection; docs now call it a command flag placed after the command. |
| `add --name` mismatch | Reproduced. Docs explain target-name selection still requires matching frontmatter; it does not rewrite names. |
| Global `view --json` tokens | Reproduced absence; docs distinguish global Store records from enriched agent detail. |
| Invalid web UI port | Reproduced. Parser now enforces 0–65535 before Store bootstrap or bind. |
| Doctor aggregate headline / project | Reproduced existing behavior; docs explicitly limit aggregate health to the global Store and project context to `--explain`. Headline wording is still historical; named-scope/hygiene checks are needed for agent health. |
| Templates with broken skills layout | Template listing is independent of the skills component. API docs narrow the previous “every route” claim. No new global layout check is added to this independent read. |

**[NOTE]** The historical reports' “not bugs” remain intentional: request
security, containment refusals, read purity, source-update approval/replay/stale
checks, staged-candidate behavior, and disabled-state handling were not relaxed.
The supplementary suspicion about invalid template bytes inside full archives
was not a reproduced report finding and remains unconfirmed; no policy change
was made for it.

## Verification

**[SPEC]** Final source-tree verification completed locally on Linux:

| Check | Result |
|---|---|
| Full unittest suite on Python 3.10.20, 3.11.15, 3.12.3, 3.13.13, 3.14.3 | 1,324 tests, OK on each interpreter |
| Compilation, docs/source consistency, design tokens | Passed |
| Complexity ratchet | 721 functions across 16 files, passed; only lowered/deleted stale baselines |
| Store and web smoke scripts | Both passed after final source edits |
| Ruff 0.16.8 F821/F822/F823 | Passed |
| Bandit 1.9.4 | No findings; existing suppression-comment warnings remain |
| Pinned hash-verified wheel and sdist build | Passed; artifacts stayed in a temporary build environment |
| Package-data inspection | Both archives passed, including Vue hash, 25 UI files, two example files and excluded-file policy |
| Clean wheel install and full asset probe | Passed |
| Automatic clean sdist gate | UNAVAILABLE: its fresh Python 3.12 venv lacks setuptools |
| Separate clean sdist install with pinned build requirements seeded | Passed offline/no-build-isolation install and the complete Vue/example/fonts probe, run outside the repository |

The complete ladder was rerun on the final source tree after the sync
policy-refusal regression was added. Both new concurrency test isolation and
the changed oversized-body contract were corrected after earlier red suite
runs; those earlier runs are not presented as final passes. No thresholds,
checks or tests were disabled. All changes were reviewed against the hostile
input/concurrency/rollback/corrupt-data checklist. The binary-snapshot and
locking limits below remain explicit, rather than inferred away by the tests.

Implementation commits, in branch order:

| Commit | Batch |
|---|---|
| `8019fee` | R14 JSON/project handling |
| `b91e0df` | R6 portability and physical alias visibility |
| `2fd7795` | R10 Unicode evidence |
| `daa9e3d` | R4 JSON native observations |
| `f1e08ed` | Scoped mutation/sync recovery and raw reads |
| `fa167ea` | CLI findings and contract corrections |
| `c475f93` | Prompt HTTP rejection and strict parameters |

## Remaining decisions and integration

**[SPEC]** Codex TOML is deferred pending D-1; Python >=3.10 and dependencies
stay unchanged. R3 bodyless list projection, install/path/HMAC sidecar binding,
directory-symlink policy and docs/29 D-2–D-10 remain maintainer decisions.
Other research recommendations were not silently approved by this work.

**[NOTE]** Locking remains advisory. Separate data roots do not coordinate on
one agent folder. Source-update's directory lock differs from document mutation
locks; direct writers are not claimed to coordinate with source-update apply.
Recursive name lookup can be ambiguous during directory replacement. These
limits require a broader locking/identity design; the tests here do not prove
arbitrary external writers safe. Native settings omit several higher-priority
sources. Windows execution and human UI accessibility were not checked locally.

**[SPEC]** Parent integration must preserve both histories: merge this completed
backend branch into `ui/prototype-final` only after both writers are idle.
R9 requires frontend `fe46552` (shared JSON Content-Type header). Parent also
has `459ca84` and `7d225dc`, absent from this backend branch. Resolve shared
task/progress/docs/baseline changes carefully; do not replace them wholesale.
No main merge, reset, force push or release was performed here.

The parent must rerun the full ladder on the combined tree and exercise both
classic and v2: bodyless POSTs; scoped mixed edit/toggle/restore; damaged-copy
force-sync and byte recovery; native-state evidence and unchanged toggles;
unknown-key/compatibility/length lint; Unicode advisory evidence; search with
refused entries; malformed input/413; archive recovery and source-update
approval, replay, stale checks and disabled state. Backend-only tests cannot
prove either UI handles the new evidence or R9 correctly.
