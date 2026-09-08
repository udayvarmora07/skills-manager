# Security Best Practices Report — skills-manager

**Date:** 2026-09-08 · **Scope:** `skillsmgr/` (stdlib Python backend, Vue 3 vendored frontend) · **Method:** code audit plus hermetic adversarial tests; findings verified in source and live local requests.

## Executive summary

The project is a localhost-only tool with a small attack surface and several controls already in place: loopback-only bind enforcement, pre-handler mutation-origin checks, JSON content-type enforcement, security response headers, bounded wildcard search, bounded frontmatter parsing, allowlisted shell construction, body/upload caps, bounded tar preflight, strict manifests, staged per-skill import recovery, an XSS-safe markdown renderer, and generic 500s with stderr logging. The previously reproduced cross-origin purge, wildcard exhaustion, parser recursion, and archive-safety gaps are fixed and covered by regressions. Remaining items are hardening notes, including supply-chain execution via `/api/install` with `run:true`.

## Critical findings

None. No remote code execution, injection, authentication bypass, or data-loss path was found that an attacker can reach.

## High findings

- **H-1 — Supply-chain code execution via `/api/install` (`run:true`).** Impact: installing a third-party skill repo executes its npm postinstall scripts on the user's machine.
  - Verified controls (`skillsmgr/webapp.py:514-577`): `source`/`agents`/`skills` values are allowlist-validated (`re.fullmatch(r"[A-Za-z0-9_@./:+-]+")`, leading-`-` rejected); command is built as a list (no shell); `uvx` rejected; `subprocess.run` has `timeout=120`; default response is dry-run (`executed: false`, `webapp.py:564`) and execution requires explicit `run:true`; frontend gates this behind `runInstall(confirm)` (`skillsmgr/webui/app.js:308-326`).
  - Recommendation: keep the confirm gate; consider showing the exact command string in the confirm dialog (already returned) and documenting that `run:true` trusts the source repo.

## Medium findings

- **M-1 — ZIP import is intentionally unsupported.** Content sniffing rejects ZIP archives before tar parsing. Adding ZIP would require a separate approval decision and the same preflight/commit guarantees.
- **M-2 — Archive budgets are conservative by policy.** Tar input is bounded to 25 MiB compressed, 16 MiB expanded, 8 MiB per member, 200 members, 512-character paths, 16 nesting levels, and a 1000:1 compression ratio. Separate local imports can still consume disk, which is accepted local-user behavior.
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
 | Loopback bind and non-loopback rejection | `skillsmgr/webapp.py:852-875` |
 | Mutation Host/Origin/Referer/Fetch-Metadata gate | `skillsmgr/webapp.py:162-230` |
 | Defensive security response headers | `skillsmgr/webapp.py:101-116` |
| Request body cap + `Content-Length` validation (400/413, oversize → 400 verified live) | `skillsmgr/webapp.py:39, 108-118` |
 | Query length and wildcard complexity caps | `skillsmgr/search.py:15-38`, `skillsmgr/webapp.py:41, 293` |
 | Frontmatter size/key/collection/scalar/nesting caps | `skillsmgr/frontmatter.py:31-121` |
 | Tar archive budgets, strict manifest, and staged import recovery | `skillsmgr/store.py:63-218, 981-1100` |
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
# oversize Content-Length→400, 300-char query→400, wildcard exhaustion→400,
# archive budget/manifest/name mismatch/ZIP probes fail closed,
# hostile Origin/Referer/Fetch-Metadata/Host→403, form mutation→415,
# history clamp ok,
# PATCH name ignored, disable/enable ok, static ..→404, unknown skill→404
```

Report written to `security_best_practices_report.md`. Findings use numeric IDs (H-1, M-1…M-3, L-1…L-5) for reference.
