# TODO — skills-manager (next-session checklist)

> Start a new chat with the prompt in `PLAN.md`, then work this list top to bottom.
> Notation: `[ ]` todo, `[/]` doing, `[x]` done.

## 0. Pre-publish blockers (must do before `git push`)

- [x] Replace `YOUR-USER` in `README.md` (3×), `pyproject.toml` (5×), `CONTRIBUTING.md` (1×) with your GitHub username → `udayvarmora07`
- [x] Replace `security@example.com` in `SECURITY.md` with a real contact → private advisories link
- [x] Re-run verification: `python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py && python3 -m unittest discover -s tests && python3 smoke_store.py && python3 smoke_web.py` → 43 OK, both PASS
- [x] `git init && git add -A && git commit -m "feat: OSS launch v1.0.0" && git tag v1.0.0`
- [x] Create GitHub repo, `git remote add origin <url>`, `git push -u origin main --tags` → `udayvarmora07/skills-manager`, CI green
- [ ] Publish to PyPI: `python3 -m build && twine upload dist/*` (BLOCKED: needs PyPI API token; `dist/` built, name `skills-manager` confirmed free)
- [x] Confirm CI badge green on first push; fix `ci.yml` if red → green (run 33914953774)

## 1. v1.1 — Spec-lint+ (ROADMAP.md "Next")

- [x] Name regex incl. no-consecutive-hyphens (already enforced by `NAME_RE`) + description keyword/use-context scoring (`validator.description_score` + warnings)
- [x] Body length + token warnings (`MAX_BODY_TOKENS=5000`); `scripts/`/`references/`/`assets` layout checks
- [x] Cross-scope dedup: same-name detect (`scopes.find_duplicates()`), descriptions-differ flag, one-command converge via existing sync (doctor modal Sync… buttons)
- [x] Token budget view in CLI + UI (verified already complete): `tokens --scope all` aggregate + `largest`, `/api/stats?window=` + `/api/tokens`, frontend budget bar + window selector
- [x] Rollback: snapshot on edit/sync + `restore --snapshot` (ASK issue #1 opened — no code until approved)
- [x] One-command migration: full-library export/import incl. trash + templates (ASK issue #2 opened — no code until approved)

## 2. v1.2+ — Ecosystem

- [ ] Registry bridge: browse `skills.sh` → install into chosen scope (needs ASK: new command)
- [ ] Eval harness: per-skill before/after prompt tests
- [x] Zip-import support (shipped 2026-09-05, M5)
- [x] Tar-fallback hardening via allowlist (shipped 2026-09-05, M5; refusal superseded)
- [x] Out-of-root link escapes → error (shipped 2026-09-05, M5; missing-file stays warning)

## 3. Ambitious (exploring — issue-first, no code until approved)

- [ ] VS Code extension over existing REST API
- [x] Desktop entry (shipped 2026-09-05, M5: `assets/skills-manager.desktop`; `pywebview` wrapper superseded)
- [x] Live markdown preview editor + shortcut cheatsheet modal (shipped 2026-09-05, M5)
- [ ] Team sharing: signed bundles, draft → review → publish
