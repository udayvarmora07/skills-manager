# UI evidence — G8 structural changes, 1.0.2 release candidate

**Captured 2026-10-06 · commit `f11549a` · Chromium via `browser_harness.py` (dev-only CDP probe)**

## What these are

Dated captures of the local web UI at six viewports, taken from the tree that
became the **1.0.2** release candidate. They exist to make a specific reviewer's
review reproducible: what the shipped Overview and Library looked like, at the
commit that shipped them.

**[NOTE] These are not participant evidence and not a usability result.** They
are renderings of a synthetic fixture — active, disabled, divergent, malformed
and unaddressable instances seeded through the tool's own filesystem behaviour.
No human evaluated this UI. @docs/25-design-partner-pilot-kit.md records the
protocol for that; it has not been run.

## Provenance

- Tool: `skillsmgr/webui/` served by `python3 -m skillsmgr webui` on loopback.
- Command: `PYTHONDONTWRITEBYTECODE=1 python3 browser_harness.py --screenshots-dir <this dir>`
- The harness isolates `HOME` **and** `SKILLS_MANAGER_DATA`, keeps Chrome's
  sandbox enabled, binds its CDP listener to `127.0.0.1`, and discovers Chrome
  through `launcher_security.trusted_executable()`.
- It reported `passed: true` with **0** console errors, **0** runtime errors,
  **0** failed requests and **no horizontal overflow** at any viewport.

## Captures

| file | bytes | sha256 |
|---|---|---|
| `viewport-1280x900.png` | 169,373 | `eb744f9989cd84d2001276d4ccb0fd7914569b399602827de40904b857debb6f` |
| `viewport-1440x900.png` | 170,906 | `c7cbc2cde60c2222df77ddaa42486f58bbd818f690952993c8b2282019390d33` |
| `viewport-320x700.png` | 44,399 | `6670d58bb3bf7cffc86498893973596760c7ff6b5da6e979f05dd8bb5adead77` |
| `viewport-400x800.png` | 58,275 | `0470c5c60c2c915ba75fa7a579d4e5df3b6da47f74ffdb15505cfb23ab037cdf` |
| `viewport-640x900.png` | 77,604 | `8c590723a246a2177786ecd12c442e7397a2d089f0f3ec941b6490dd86d17794` |
| `viewport-900x800.png` | 121,509 | `8397d712761c9d025d954b93df28fe8b9de8dd1f40603379ce2a44ef4af3ea61` |

## What the captures show

The §G8 structural changes are visible at 1440x900:

- The Overview hero is gone. The view opens on an `h1` plus a one-line status
  (`5 skills · 3 active · 4 need attention`) and then the **attention queue**.
- The duplicate "Observed state" panel is gone; its counts are folded into the
  existing definition list (`Logical skills`, `Active instances`, `Observed
  copies`, `Malformed`).
- The first-run / attention-needed card moved below the queue. In the
  pre-change build "Create your first skill" sat at Y=888px on a 900px-tall
  viewport; the measured change is Y=224px.

## Not covered

**[?]** System Chrome on Linux only. No Firefox, Safari, or any non-Chromium
engine. No forced-colors or high-contrast mode. No 200%/400% zoom. No screen
reader. No human perceptual review. These gaps are why the human pilot in
@docs/25-design-partner-pilot-kit.md exists and has not been substituted for.
