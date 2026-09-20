# Product baseline evidence — 2026-09-18

**Version 1.0.0**

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

Human usability sessions are intentionally not fabricated by this repository
run. DEL-01 still requires five consent-based task sessions (novice and expert
participants); record task completion, wrong-copy actions, time to first useful
row, focus order, and mobile reachability without collecting skill bodies or
identifying data.

## Acceptance status

- [x] Synthetic empty/small/divergent/malformed/2,000-instance fixtures are
  codified and covered by stdlib unit contracts.
- [x] Startup-critical REST probe routes and timings are recorded in a stable
  JSON schema with no telemetry.
- [x] Browser viewport capture procedure is preserved by the existing harness.
- [ ] Five human usability sessions remain a maintainer/research activity and
  are not claimed complete by automated tests.
