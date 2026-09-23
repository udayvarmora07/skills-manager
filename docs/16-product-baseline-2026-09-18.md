# Product baseline evidence — 2026-09-23

**Version 1.2.0**

**AI manifest**: Reproducible DEL-01 evidence for the proposed product/UX
delivery plan. This document contains synthetic local fixtures and bounded
timings only; it contains no user content and introduces no telemetry.

## Scope

The baseline harness is `baseline_harness.py`. It uses the existing Store and
loopback Web UI server, creates a disposable temporary workspace, probes the
startup-critical REST routes, and removes the workspace afterward. Run it with:

```text
python3 baseline_harness.py --fixture all --output /tmp/skillsmgr-baseline.json
```

The report records Python/platform, fixture shape, response item counts, route
keys, per-route elapsed milliseconds, and total elapsed time. It does not set
performance targets before the first measurement.

## Fixture contract

| Fixture | Purpose | Expected shape |
|---|---|---|
| `empty` | New installation | 0 skills and explicit empty state |
| `small` | Normal daily library | 12 active deterministic skills |
| `divergent` | Logical grouping | one global copy, one identical agent copy, one divergent agent copy, plus one global-only skill |
| `malformed` | Honest failure state | one valid document and one malformed frontmatter document |
| `large` | Scale probe | 2,000 active deterministic skills |

The large fixture is synthetic and deliberately repeats a short description so
the measurement isolates filesystem/list/rendering cost rather than private or
realistic skill content. The divergent fixture uses temporary `.agents/skills`
and `.claude/skills` roots under its temporary `HOME`.

## First machine baseline

The fixture plan and harness were added on 2026-09-18. The initial contract
verification is **5 unittest tests OK**. A Python 3.12.3 POSIX run took 11.49 s
end to end and observed the expected row counts: empty 0, small 12,
divergent 4, malformed 2, and large 2,000. On that run, the large fixture's
route timings were 889 ms for `/api/scopes`, 1,542 ms for the merged skills
list, 1,554 ms for stats, and 3,739 ms for doctor. Run output is generated on
demand so timings retain the host/date context and are not presented as
portable targets.
The required browser viewport matrix remains the separate
`python3 browser_harness.py` check at 320, 400, 640, 900, and 1280 pixels.

## Current synthetic refresh — 2026-09-20

The all-fixture baseline was refreshed against the current build with:

```text
python3 baseline_harness.py --fixture all \
  --output .specs/evidence/del-11-2026-09-20-run3/baseline.json
```

The dated report records the expected row shapes: empty `0`, small `12`,
divergent `4`, malformed `2`, and large `2,000`, with no telemetry or private
user-content access. The same current-build evidence directory contains the
five local automated viewport PNGs from the browser harness. These artifacts
are reproducible local evidence only; they are not external screenshots or
participant research results.

Human usability sessions are intentionally not fabricated by this repository
run. DEL-01 still requires five consent-based task sessions (novice and expert
participants); record task completion, wrong-copy actions, time to first useful
row, focus order, and mobile reachability without collecting skill bodies or
identifying data.

## Full-inventory refresh — 2026-09-23

The startup routes were measured against disposable inventories of 100, 1,000,
and 10,000 real `SKILL.md` files using:

```text
python3 baseline_harness.py --full-inventory \
  --output benchmarks/full-inventory-2026-09-23.json
```

Fixture creation and SQLite resync are outside per-request timings and listed
separately. The run used Python 3.12.3 on Linux 6.17.0-1030-oem, x86_64, with
8 reported CPUs. Each document was 160 bytes; fixture totals were 16,000,
160,000, and 1,600,000 bytes. Created file counts matched 100, 1,000, and
10,000. Peak process RSS was 150,691,840 bytes. OS page cache was not flushed:
"cold" resets the Store wrapper and Web UI server per measured request within
one Python process; "warm" reuses one server per route after one unmeasured
request. Routes ran in declaration order, cold then warm. Each reported p95
uses nearest rank `sorted[ceil(0.95 * n) - 1]` and requires 20 successful
samples; the median uses `statistics.median`.

| Skills | Mode | `/api/scopes` | Merged list | Stats | Doctor | Hygiene |
|---:|---|---:|---:|---:|---:|---:|
| 100 | cold | 38.53 / 84.27 (20) | 105.79 / 122.83 (20) | 104.31 / 137.84 (20) | 178.14 / 191.80 (20) | 340.27 / 512.94 (20) |
| 100 | warm | 56.48 / 79.12 (20) | 102.60 / 142.99 (20) | 92.16 / 119.59 (20) | 146.15 / 158.55 (20) | 243.29 / 300.40 (20) |
| 1,000 | cold | 309.55 / 350.94 (20) | 596.23 / 662.08 (20) | 625.78 / 655.43 (20) | 1,247.35 / 1,509.25 (20) | 2,062.73 / 2,190.20 (20) |
| 1,000 | warm | 287.95 / 310.58 (20) | 612.34 / 662.45 (20) | 677.10 / 745.24 (20) | 1,295.74 / 1,393.44 (20) | 2,083.26 / 2,232.56 (20) |
| 10,000 | cold | 3,060.41 / 3,472.14 (20) | 9,177.08 / 11,961.12 (20) | 10,181.80 / 11,114.18 (20) | 19,555.03 median (11; p95 unavailable) | not run |
| 10,000 | warm | not run | not run | not run | not run | not run |

Cells show `median ms / p95 ms (successful samples)`. The 10,000-skill
measurement reached its 900-second total budget after the cold Doctor route
had produced 11 samples. The report marks its remaining Doctor samples, all
Hygiene samples, and every warm sample `not_run` with the runtime-budget
reason; it does not treat missing samples as fast responses. Its original
measurement took 906.28 seconds because a request already in flight crossed
the 900-second deadline by 6.28 seconds (within the 60-second request timeout).
The harness now reserves the full timeout before starting a request. Fixture
counts, sample order, per-sample status, route response keys, and the bounded
failure are preserved in the JSON report. No 10,000-skill Hygiene result is
claimed.

The first route-level bottleneck is the diagnostics path at 10,000 skills:
Doctor's partial median is 19.56 seconds (11 samples), while the merged list
and Stats have complete cold medians of 9.18 and 10.18 seconds. This locates
the slow surface but does not attribute it to a specific function. **Proposed
measurement budget for a complete 10,000-skill matrix:** rerun intentionally
with `--runtime-limit-s 3600`, retaining the 60-second per-request timeout and
20-sample minimum. This is a one-hour evidence budget, not a product latency
target or a claim that current performance passes. No user-facing latency
budget existed before the measurement; a product SLO still needs maintainer
review.

## First-scan browser evidence — 2026-09-23

`python3 browser_harness.py --screenshots-dir /tmp/skillsmgr-final-browser-2026-09-23-verified/screenshots`
exercised the populated first-scan guide, Skip/Restart, read-only Codex
explanation, exact writable-instance update-preview destination, and Overview
at 320 × 700, 400 × 800, 640 × 900, 900 × 800, 1280 × 900, and 1440 × 900.
It also ran synthetic scope-failure, inventory-failure, unavailable-root, and
empty-inventory scenarios. The populated fixture also confirmed the existing
attention queue exposes both malformed/unaddressable and divergent-copy
observations. All viewport and scenario runs reported no
console/runtime errors, warnings, failed requests, or horizontal overflow;
all skip/restart/explanation checks passed, and empty-state actions opened the
existing Create surface. The automated navigation-to-settled-scan time had a
955 ms median across the six populated viewport runs. This is synthetic
browser evidence with pre-seeded fixtures, not a human participant result or
the five-minute usability target.

## Acceptance status

- [x] Synthetic empty/small/divergent/malformed/2,000-instance fixtures are
  codified, covered by stdlib unit contracts, and refreshed in the dated
  `del-11-2026-09-20-run3/baseline.json` report.
- [x] Startup-critical REST probe routes and timings are recorded in a stable
  JSON schema with no telemetry.
- [x] Browser viewport capture procedure is preserved by the existing harness.
- [ ] Five human usability sessions remain a maintainer/research activity and
  are not claimed complete by automated tests.
