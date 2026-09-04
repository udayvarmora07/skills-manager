# TODO — skills-manager (next-session checklist)

> Start a new chat with the prompt in `PLAN.md`, then work this list top to bottom.
> Notation: `[ ]` todo, `[/]` doing, `[x]` done.

## 0. Pre-publish blockers (must do before `git push`)

- [ ] Replace `YOUR-USER` in `README.md` (3×), `pyproject.toml` (5×), `CONTRIBUTING.md` (1×) with your GitHub username
- [ ] Replace `security@example.com` in `SECURITY.md` with a real contact
- [ ] Re-run verification: `python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py && python3 -m unittest discover -s tests && python3 smoke_store.py && python3 smoke_web.py`
- [ ] `git init && git add -A && git commit -m "feat: OSS launch v1.0.0" && git tag v1.0.0`
- [ ] Create GitHub repo, `git remote add origin <url>`, `git push -u origin main --tags`
- [ ] Publish to PyPI: `python3 -m build && twine upload dist/*` (or `pipx install` path)
- [ ] Confirm CI badge green on first push; fix `ci.yml` if red

## 1. v1.1 — Spec-lint+ (ROADMAP.md "Next")

- [ ] Name regex incl. no-consecutive-hyphens + description keyword/use-context scoring (`validator.py` + `smoke_store.py` cases)
- [ ] Body length + token warnings; `scripts/`/`references/` layout checks
- [ ] Cross-scope dedup: same-name/similar-description detect, diff, one-command converge
- [ ] Token budget view in CLI + UI (`tokens --scope all` surfaced per skill)
- [ ] Rollback: snapshot on edit/sync + `restore --snapshot` (needs constraint-5 ASK: new flag)
- [ ] One-command migration: full-library export/import incl. trash + templates (needs constraint-5 ASK)

## 2. v1.2+ — Ecosystem

- [ ] Registry bridge: browse `skills.sh` → install into chosen scope (needs ASK: new command)
- [ ] Eval harness: per-skill before/after prompt tests
- [ ] Zip-import support (needs ASK: CLI-surface change)
- [ ] Tar-fallback refusal on Python < 3.12 (threat-model R-1, needs ASK: behavior change)
- [ ] Out-of-root link warning → error (threat-model R-4, needs ASK)

## 3. Ambitious (exploring — issue-first, no code until approved)

- [ ] VS Code extension over existing REST API
- [ ] `pywebview` desktop wrapper
- [ ] Live markdown preview editor + shortcut cheatsheet modal
- [ ] Team sharing: signed bundles, draft → review → publish
