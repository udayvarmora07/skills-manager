# Pre-Merge Checklist — Skills Manager

**Version 1.1.0**

**AI manifest:** Maintainer checklist for selective worktree replay and local
changes. A change is not ready to merge merely because its branch tests pass.

## Scope and provenance

- [ ] Read `AGENTS.md`, the relevant warm docs, the current `TODO.md`, and the
      latest progress-log entry.
- [ ] State the user outcome, invariant, non-goals, and affected public seams.
- [ ] Classify every incoming change as `main`, `worktree-only`,
      `approved-not-integrated`, or `speculative`.
- [ ] Do not cherry-pick overlapping `store.py`, `webapp.py`, tests, or tracking
      docs without manual conflict review.
- [ ] Confirm no candidate worktree or `/home/uday-varmora/skills-manager/.autogit`
      was modified unintentionally.

## Source and artifact integrity

- [ ] `git status --short --untracked-files=all` was inspected before and after.
- [ ] `git diff --name-only` and `git diff --stat` contain only intended files.
- [ ] `git diff --check` passes.
- [ ] No untracked `__pycache__`, `build/`, `dist/`, `.egg-info/`, database,
      archive, or local skill files are being treated as source changes.
- [ ] If packaging is involved, build once from a clean tree, test those exact
      artifacts, and record the artifact hashes before publication.

## Contract and safety gates

- [ ] Filesystem remains the source of truth; SQLite schema and `SCHEMA_VERSION`
      are unchanged unless an approved issue/ADR says otherwise.
- [ ] No new CLI command, CLI flag, Store method, runtime dependency, public
      network bind, or data-model change was introduced without approval.
- [ ] Every untrusted skill name is checked by the canonical name primitive.
- [ ] Every filesystem path derived from user input is resolved and contained
      before read, write, rename, move, copy, restore, or delete.
- [ ] URL-decoded REST names and CLI names are rejected before path construction.
- [ ] Destructive operations have a regression test and a clear recovery or
      irreversible-policy decision.
- [ ] Errors surface as clean `StoreError`/`SkillNotFound`/HTTP responses, not
      raw tracebacks or misleading success responses.

## Verification ladder

- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py check_*.py`
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 smoke_store.py`
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 smoke_web.py`
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 check_docs.py` (header facts for every
      `docs/*.md`, valid local links **and anchors**, table cell counts, and
      CLI/REST/`Store` surface parity, so an undocumented command, endpoint,
      method or file cannot land)
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 check_complexity.py` (ratchet flat; a
      failure on a function the change did not touch means the tree is shared —
      see `AGENTS.md`, *Concurrent writers*)
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 check_package_data.py`
      (`UNAVAILABLE` when the optional `build` tooling is absent is standing
      behaviour, not a regression)
- [ ] `node --check skillsmgr/webui/app.js` **and** `node --check
      skillsmgr/webui/domain.js` when frontend code or package data changed.
- [ ] `PYTHONDONTWRITEBYTECODE=1 python3 -m skillsmgr --help`
- [ ] Hermetic temporary-data and temporary-HOME runs cover changed destructive
      paths; no test relies on real user skills.
- [ ] If the UI changed, run the supported browser click-through and inspect
      console errors, failed requests, focus behavior, and narrow viewport state.

## Documentation truth

- [ ] Owning module/API documentation matches current source signatures and
      behavior.
- [ ] `TODO.md` marks only verified work as `[x]`; deferred or approval-gated
      work remains `[!]`/`[ ]`.
- [ ] `task.md` records the completed slice and exact verification evidence.
- [ ] `docs/06-progress-log.md` receives a newest-first dated entry.
- [ ] Historical evidence files remain append-only; current truth is corrected in
      the owning document instead of rewriting history.
- [ ] Published counts (tests, complexity functions, command inventory) were
      re-derived by running the gate in this change, not copied from another doc.
- [ ] Source citations use symbol names rather than `file:line`, and any finding
      ID closed in behavior is reflected in
      `docs/13-audit-remediation-status-2026-09-11.md`.
