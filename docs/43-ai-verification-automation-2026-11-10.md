# AI verification automation — 2026-11-10

**Version 0.1.0**

**AI manifest**: Development-only, no-paid-calls verification entry point and its
integration into the existing CI unit and package jobs. See @docs/42-ai-cli-ci-2026-11-09.md
for the AI CLI contract and @docs/41-ai-fidelity-study-2026-11-09.md for the
limits of the saved native study.

## Local use

**[SPEC]** From the repository root, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_ai.py
```

The default runs the focused AI CLI, feature, fidelity and automation tests,
checks the saved synthetic study hashes and accounting, and invokes the study
fixture in its no-send default mode. `--tests` or `--evidence` run either part.
Failures return nonzero; these checks do not run a native agent or call a real
provider. Test subprocesses use a temporary HOME, strip ambient credentials,
and have bounded output/runtime with process-group cleanup. The tests use an unauthenticated fake provider on 127.0.0.1: localhost
binding is its only security boundary. The port is never forwarded or published.

For an already-built wheel, run the separate artifact probe:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_ai.py --artifact /absolute/path/to/package.whl
```

The probe creates a temporary virtual environment, installs the specified wheel
with `--no-index --no-deps`, checks that the imported package comes from that
virtual environment, and runs the installed CLI from a separate temporary
working directory with a clean HOME and environment. An isolated fake provider
supports a no-send estimate, a baseline, and a deliberately failed regression
gate. It checks the manager does not initialize SQLite and that the wheel does
not ship the development harness, study evidence or tests. Only trusted wheels
should be supplied: executing an installed package is not a sandbox. Bounded
subprocess output and process-group cleanup require POSIX.

## CI integration and limits

**[SPEC]** The existing Python unit matrix runs the automation contracts and
an additional `--evidence` no-send check. The existing package job builds once
with the pinned hash-verified toolchain and probes that exact wheel. Ruff's
existing pinned gate covers the runner and fidelity tools. There is no paid
agent invocation, provider credential or new third-party action. These targeted
checks do not replace the existing full test, smoke, packaging, docs, complexity,
UI or cross-platform jobs. Saved evidence proves only internal consistency of
the recorded two-case study, not general agent fidelity.

Manual workflow dispatch becomes available after this workflow change reaches
the default branch. A newer run cancels superseded CI for
the same pull request; main pushes and manual runs retain independent groups.
Unit and package jobs have explicit 30- and 20-minute deadlines, in addition
to the developer runner's per-process time and output bounds. The installed
wheel probe must pass before the distribution artifacts are uploaded.

The trigger and cancellation rules follow GitHub's
[manual-dispatch reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)
and [concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
