# Security Best Practices Report — skills-manager

**Date:** 2026-09-04 · **Scope:** `skillsmgr/` (stdlib Python backend, Vue 3 vendored frontend) · **Method:** code audit against Python/JS web security practices; findings verified in source, not assumed.

## Executive summary

The project is a localhost-only tool with a small attack surface and several controls already in place: loopback bind, allowlisted shell construction, body/upload caps, tar `filter="data"`, an XSS-safe markdown renderer, and generic 500s with stderr logging. No critical exploitable vulnerability was found. Remaining items are hardening notes (defense in depth), not emergencies. Two low-severity residual risks deserve attention: unfiltered tar fallback on old Pythons, and supply-chain execution via `/api/install` with `run:true`.

## Critical findings

None. No remote code execution, injection, authentication bypass, or data-loss path was found that an attacker can reach.

## High findings

- **H-1 — Supply-chain code execution via `/api/install` (`run:true`).** Impact: installing a third-party skill repo executes its npm postinstall scripts on the user's machine.
  - Verified controls (`skillsmgr/webapp.py:514-577`): `source`/`agents`/`skills` values are allowlist-validated (`re.fullmatch(r"[A-Za-z0-9_@./:+-]+")`, leading-`-` rejected); command is built as a list (no shell); `uvx` rejected; `subprocess.run` has `timeout=120`; default response is dry-run (`executed: false`, `webapp.py:564`) and execution requires explicit `run:true`; frontend gates this behind `runInstall(confirm)` (`skillsmgr/webui/app.js:308-326`).
  - Recommendation: keep the confirm gate; consider showing the exact command string in the confirm dialog (already returned) and documenting that `run:true` trusts the source repo.

## Medium findings

- **M-1 — Tar extraction falls back to unfiltered `extractall` on old Pythons** (`skillsmgr/store.py:814-816`). `filter="data"` blocks absolute paths and `..` members on Python ≥ 3.12; the `except` fallback re-enables classic slip on older interpreters.
  - Recommendation: declare a minimum supported Python (≥ 3.12) or refuse tar import when `filter=` is unavailable instead of falling back silently.
- **M-2 — Archive import accepts any member layout; symlink members only neutralized by `filter="data"`.** Same code region as M-1; on current Python this is handled, but there is no independent member allowlist (e.g. only `<name>/SKILL.md`).
  - Recommendation: pre-validate tar members (reject absolute paths, `..`, symlinks/hardlinks) before extraction so safety does not depend solely on interpreter version.
- **M-3 — Error responses can leak absolute filesystem paths** (e.g. `StoreError` text containing data-dir paths reaches loopback JSON clients). Acceptable for a localhost tool with no remote users, but worth noting.
  - Recommendation: no change required; if the bind default ever changes, sanitize paths from API errors first.

## Low / informational

- **L-1 — No authentication on the REST API.** By design: the server binds `127.0.0.1` by default (`skillsmgr/webapp.py:778-779, 816`) and is a local desktop tool. Any local process/user can call it. Do not expose the port; no change needed while loopback-only.
- **L-2 — No TLS.** Per standard guidance for localhost dev tools, not reported as a defect. Do not add HSTS or `Secure` cookies here.
- **L-3 — No rate limiting.** Acceptable on loopback; the expensive paths (25 MB body cap `webapp.py:39`, 200 upload parts `webapp.py:40-41`, 200-char query cap `webapp.py:293`, history clamp `webapp.py:372`) already bound resource use.
- **L-4 — Browser launched via `subprocess.Popen`** (`skillsmgr/webapp.py:804-807`, stdio to DEVNULL). URL is constructed from local host/port constants, not user input. Safe as-is.
- **L-5 — `Store.add` copies with `shutil.copytree`** (`skillsmgr/store.py`, `add`). Default `symlinks=False` copies file contents rather than recreating links. Safe default; validator additionally warns on out-of-root link escapes (`skillsmgr/validator.py:234-238`).

## Verified controls (passing)

| Control | Location |
|---|---|
| Loopback bind by default | `skillsmgr/webapp.py:778-779, 816` |
| Request body cap + `Content-Length` validation (400/413, oversize → 400 verified live) | `skillsmgr/webapp.py:39, 108-118` |
| Query length cap (300-char query → 400 verified) | `skillsmgr/webapp.py:41, 293` |
| History limit clamp (limit=99999 → ≤200 verified) | `skillsmgr/webapp.py:42, 372` |
| Import filename traversal blocked (`../evil.tar.gz` → 400, empty → 400, zip → 400 verified) | `skillsmgr/webapp.py:709-743` |
| Multipart folder-upload part/size caps | `skillsmgr/webapp.py:741-743` |
| Install runner/source/agent/skill allowlists, list-form exec, timeout | `skillsmgr/webapp.py:514-577` |
| Static file jail (`is_relative_to`, `..` → 404 verified) | `skillsmgr/webapp.py:192` |
| Generic 500 + stderr log, no tracebacks to clients | `skillsmgr/webapp.py:174` |
| Tar `filter="data"` on modern Python | `skillsmgr/store.py:814` |
| Skill-name validation on `sync_skill` | `skillsmgr/scopes.py:282, 452` |
| Unknown-scope rejection | `skillsmgr/scopes.py:150` and peers |
| XSS-safe markdown: `esc()` first, `https?` links only, `rel="noopener"`, no `v-html`/`innerHTML` | `skillsmgr/webui/app.js:15, 47-110` |
| JSON body must be an object, else 400 | `skillsmgr/webapp.py:120-135` |

## Verification performed

```bash
python3 -m py_compile skillsmgr/*.py smoke_*.py   # COMPILE_OK
python3 smoke_store.py                            # ALL STORE SMOKE TESTS PASSED
python3 smoke_web.py                              # ALL WEB SMOKE TESTS PASSED
```

```bash
# REST edge matrix, all as expected:
# traversal import→400, empty body→400, zip→400, bad archive→400,
# oversize Content-Length→400, 300-char query→400, history clamp ok,
# PATCH name ignored, disable/enable ok, static ..→404, unknown skill→404
```

Report written to `security_best_practices_report.md`. Findings use numeric IDs (H-1, M-1…M-3, L-1…L-5) for reference.
