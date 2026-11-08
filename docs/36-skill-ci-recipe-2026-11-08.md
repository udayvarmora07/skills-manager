# Skill CI Recipe — 2026-11-08

**Version 1.0.0**

**AI manifest**: A documented recipe (docs/29 row 25) for checking `SKILL.md` folders on every pull request with commands this tool already ships. It adds no CLI command, no GitHub Action to maintain, and no dependency. The script block below is executed by `tests/test_skill_ci_recipe.py`, so the documented exit codes are tested, not asserted.

## What it checks, and what it does not

**[SPEC]** For each skill folder, `skills-mgr validate --path DIR` checks the name rule, the frontmatter/directory name match, the required description, length limits, body size, and relative references. Any error makes the run exit 1. Warnings are printed but never fail the run.

**[SPEC]** It does **not** run the advisory risk scan, the hygiene report, or `doctor --explain`. Those read the skills *installed* on a machine, not a folder in a repository. Advisory findings are never meant to gate anything. Eval runs (`validate --evals`) stay advisory as well, so this recipe does not use them as a gate.

**[NOTE]** The tool keeps a private data directory even for a path check. The script points `SKILLS_MANAGER_DATA` at a fresh `mktemp -d` directory, which is owner-only. That keeps a runner's shared or group-writable home out of the data-root trust check (SEC-19) and leaves nothing behind.

## The script

**[SPEC]** Save it as `scripts/check-skills.sh` in the repository that holds the skills. Its one argument is the folder that holds one sub-folder per skill (default `skills`). `SKILLS_MGR` overrides the command, which is how the test runs it against this checkout.

<!-- skill-ci-script:begin -->
```bash
#!/usr/bin/env bash
set -euo pipefail
root="${1:-skills}"
mgr="${SKILLS_MGR:-skills-mgr}"
SKILLS_MANAGER_DATA="$(mktemp -d)"
export SKILLS_MANAGER_DATA
trap 'rm -rf "$SKILLS_MANAGER_DATA"' EXIT
status=0
found=0
for dir in "$root"/*/; do
  [ -f "$dir/SKILL.md" ] || [ -f "$dir/SKILL.md.disabled" ] || continue
  found=$((found + 1))
  $mgr validate --path "$dir" || status=1
done
if [ "$found" -eq 0 ]; then
  echo "no skill folders found under $root" >&2
  exit 1
fi
exit "$status"
```
<!-- skill-ci-script:end -->

**[SPEC]** Exit codes: `0` when every skill folder validates, `1` when any folder has an error or when no skill folder is found. Finding none is treated as a failure so that a mistyped root cannot pass silently.

## GitHub Actions workflow

**[NOTE]** The action SHAs are the ones this repository reviewed on 2026-11-07 (`.github/workflows/ci.yml`). Pin your own copy the same way and review it when you update. The package is `skill-control-plane` on PyPI; 1.0.1 is the latest published release as of 2026-11-08, and it supports Python ≥ 3.10.

```yaml
name: skills
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: python -m pip install "skill-control-plane==1.0.1"
      - run: bash scripts/check-skills.sh skills
```

**[NOTE]** For machine-readable output, run `skills-mgr validate --path DIR --json` per folder instead. The JSON carries `valid` and each skill's `errors` and `warnings`, and the exit code is the same.

## Optional: compare with the reference validator

**[NOTE]** The Agent Skills reference validator `skills-ref` is stricter in some places and looser in others. It accepts NFKC Unicode names, which this tool deliberately rejects (R18, @docs/35-open-decisions-resolved-2026-11-07.md). `tests/test_skills_ref_oracle.py` pins the known differences. To see both verdicts, run `skills-ref` in a separate step; never let one replace the other silently.
