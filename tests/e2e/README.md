# `tests/e2e/` — browser tests that no automated gate runs

**Read this before treating any green run as evidence about this directory.**

## The fact

This directory has **no `__init__.py`**. Python's test discovery does not recurse
into a subdirectory without one, so:

```bash
python3 -m unittest discover -s tests      # the documented command, and what CI runs
```

**collects nothing from here.** It does not skip these tests, does not report
them, and does not fail if they rot. Nothing in `.github/workflows/` references
Playwright or this directory either.

There were 9 files and ~1,000 lines here as of 2026-10-11. None of it has ever
been executed by a gate.

## Why it is like this, and why that is not the bug

Deliberate: the CI `unit` job must not launch a browser. That decision is sound
and should stay. **Adding `__init__.py` would be the wrong fix** — it would pull
browser work into the unit job.

## The bug

The *absence* was never reported anywhere. `.redesign/STATE.md` claimed
"`verify.sh` runs it separately, where it surfaces as an explicit skip" — it does
not; `verify.sh` contains no reference to `e2e` at all. And
`tests/e2e/test_font_render.py` claimed its tests were "skipped loudly, never
silently passed" — under the documented command they are not skipped, they are
invisible. Two claims with no reader, which is the failure class this repository
keeps recording.

So a browser test here reads exactly like coverage and delivers none. That is how
`2f70c32 ui(1.1): … prove the face actually renders` came to have no automated
evidence behind it.

## How to run them

```bash
cd ~/overnight-ui/worktree
.redesign/dev.sh reset && .redesign/dev.sh start      # isolated HOME + data dir, :8791
~/overnight-ui/venv/bin/python3 -m unittest discover -s tests/e2e -t . -v
```

`-t .` sets the top-level directory so the modules import cleanly.

**A `skipped` result here means the evidence was NOT produced.** It is a green
exit code standing in for a missing measurement. Treat it as unknown, not as a pass.

## What would actually close this

In rough order of value:

1. **A CI job that runs this directory**, on a runner with Playwright available
   and the dev server started. That is the real fix; it needs approval because it
   adds CI surface.
2. **Fail-closed reporting in the meantime** — a `check_ci_mirror`-style gate
   that asserts CI *names* this directory, so the day someone adds the job the
   gate stops complaining, and until then the absence is stated rather than
   inferred. This is the cheap half and it is doable inside `.redesign/`.
3. Keeping this `README.md` accurate. It is the only artefact that reaches the
   merge and states the gap.

What is **not** the fix: adding `__init__.py`, or relaxing the unit job to
tolerate browser failures.

## Which contracts have a stdlib half

For the two defects this directory was built to catch, a cheaper half exists and
does run:

- **faces declared / files shipped / none restricted away from ASCII** —
  `tests/test_redesign_contracts.py`, always runs.
- **sprite symbols resolve, every call site has a symbol** —
  `tests/test_redesign_contracts.py::IconSpriteTests`, always runs.

What those halves **cannot** do is observe the browser: that the woff2 files
contain Latin glyphs, that a face actually changes rendered width, that an icon
paints pixels rather than being transparent, that no console error occurs. Those
are the claims only this directory can settle, and they are currently unsettled.
