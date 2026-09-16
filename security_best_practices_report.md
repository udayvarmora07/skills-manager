# Security Best Practices Report — skills-manager

**Date:** 2026-09-12 (first issued 2026-09-08; ZIP hardening round 2026-09-10; deep-audit rounds 2026-09-11 and 2026-09-12) · **Scope:** `skillsmgr/` (stdlib Python backend, Vue 3 vendored frontend), plus the build/release configuration its artifacts depend on · **Method:** code audit plus hermetic adversarial tests; findings verified in source and live local requests. **Revision note:** the read-path request policy (`SEC-1`), the `doctor?explain` disclosure boundary (`SEC-2`/`SEC-3`), CLI terminal-output sanitization (`CLI-3`) and the `HEAD`/`OPTIONS`/`TRACE` response contract (`BUG-9`) are now covered below, and every control is cited by **symbol name** rather than `file.py:line` — the line numbers in the previous revision had mostly drifted onto unrelated code (each citation was checked before replacing it). This revision adds the vendored-asset integrity assertion (`SEC-9`), the published-artifact member policy (`SEC-13`), the upload name-conflict contract (`SEC-6`), and the pinned/hash-verified build toolchain (`SEC-8`); one control is recorded as an accepted trade-off rather than a mitigation — `script-src 'unsafe-eval'` (`SEC-4`), reasoned in `docs/08-web-ui.md`.

## Executive summary

The project is a localhost-only tool with a small attack surface and several controls already in place: loopback-only bind enforcement, a pre-handler Host/Fetch-Metadata/Origin/Referer policy on **every** method including reads, JSON content-type enforcement, security response headers on every response (the unrouted-verb `405` included), bounded wildcard search, bounded frontmatter parsing, allowlisted shell construction, body/upload caps, bounded tar/ZIP preflight, strict manifests, staged per-skill import recovery, an XSS-safe markdown renderer, terminal-output sanitization for untrusted skill fields, a disclosure boundary on the `doctor?explain` diagnostic, and generic 500s with stderr logging. The previously reproduced cross-origin purge, wildcard exhaustion, parser recursion, and archive-safety gaps are fixed and covered by regressions. Remaining items are hardening notes, including supply-chain execution via `/api/install` with `run:true`.

## Critical findings

None. No remote code execution, injection, authentication bypass, or data-loss path was found that an attacker can reach.

## High findings

- **H-1 — Supply-chain code execution via `/api/install` (`run:true`).** Impact: installing a third-party skill repo executes its npm postinstall scripts on the user's machine.
  - Verified controls: `source`/`agents`/`skills` values are allowlist-validated (`re.fullmatch(r"[A-Za-z0-9_@./:+-]+")`, leading-`-` rejected) in the install branch of `WebAppHandler._route_post`; the command is built as a list (no shell); `uvx` is rejected through the closed runner set `insights._INSTALL_RUNNERS`; `subprocess.run` has `timeout=120`; the default response is dry-run (`executed: false`) and execution requires an explicit `run: true`; the frontend gates this behind its confirm dialog before calling `/api/install`.
  - Recommendation: keep the confirm gate; consider showing the exact command string in the confirm dialog (already returned) and documenting that `run:true` trusts the source repo.

## Medium findings

- **M-1 — ZIP import uses a manual safety policy.** ZIP has no `tarfile.data_filter` equivalent, so every member is preflighted for canonical paths, layout, types, duplicates, and resource budgets before explicit contained-path extraction. Symlink-bit entries are rejected. This avoids relying on `ZipFile.extractall` for untrusted archives.
- **M-2 — Archive budgets are conservative by policy.** Tar and ZIP input are bounded to 25 MiB compressed, 16 MiB expanded, 8 MiB per member, 200 members, 512-character paths, 16 nesting levels, and a 1000:1 compression ratio. Separate local imports can still consume disk, which is accepted local-user behavior.
- **M-3 — Error responses can leak absolute filesystem paths** (e.g. `StoreError` text containing data-dir paths reaches loopback JSON clients). Acceptable for a localhost tool with no remote users, but worth noting.
  - Recommendation: no change required; if the bind default ever changes, sanitize paths from API errors first.

## Low / informational

- **L-1 — No authentication on the REST API.** By design: the server binds `127.0.0.1` by default and rejects any non-loopback bind host (`WebAppServer.__init__`), and it is a local desktop tool. Any local process/user can call it. Do not expose the port; no change needed while loopback-only. Note that the absence of auth is *not* the read-path control: a browser page is rejected by the `Host`/Fetch-Metadata/`Origin`/`Referer` policy, which now covers `GET`/`HEAD` too (`SEC-1`).
- **L-2 — No TLS.** Per standard guidance for localhost dev tools, not reported as a defect. Do not add HSTS or `Secure` cookies here.
- **L-3 — No rate limiting.** Acceptable on loopback; the expensive paths are bounded by constants rather than by rate (`webapp.MAX_BODY_BYTES` = 25 MB, `web_upload.MAX_UPLOAD_PARTS` = 200, `webapp.MAX_QUERY_LEN` = 200, `webapp.MAX_HISTORY_LIMIT` = 200). What these bounds do **not** provide is per-request work reduction: several GET routes rescan the filesystem on every call (`SEC-10`, still **OPEN**).
- **L-4 — Browser launched via `subprocess.Popen`** (`webapp._open_browser`, stdio to DEVNULL). The URL is constructed from local host/port constants, not user input. Safe as-is.
- **L-5 — `Store.add` copies with `shutil.copytree`** (`Store._add_unlocked`) using the default `symlinks=False`, so a link is dereferenced into real content inside the store. `add` takes a **local, user-chosen** path, so this is the documented install behaviour rather than an intake boundary; the intake boundaries are stricter — `archive.validate_members`/`validate_zip_members` reject symlink members, `scopes._copy_skill_tree` copies links as links and refuses escaping ones, and `export`/`tree_content_hash` do not follow links (SCOPE-1, STORE-9). The validator still only *warns* on an out-of-root link target mentioned in a document (`validator._check_links`).

## Verified controls (passing)

| Control | Location |
|---|---|
 | Loopback bind and non-loopback rejection | `WebAppServer.__init__` |
 | Host/Origin/Referer/Fetch-Metadata gate on **every** method, reads included (SEC-1) | `web_security.validate_request` → `WebAppHandler._validate_request` |
| `HEAD` mirrors `GET` (headers only); `OPTIONS`/`TRACE` → JSON `405` + `Allow` + security headers (BUG-9) | `WebAppHandler._send`, `_head_safe_body`, `_unsupported_method` |
 | Defensive security response headers | `WebAppHandler._send_security_headers` |
| Request body cap + `Content-Length` validation (400/413, oversize → 400 verified live) | `webapp.MAX_BODY_BYTES`, `WebAppHandler._read_body` |
 | Query length and wildcard complexity caps | `search.MAX_SEARCH_LENGTH`, `search.MAX_WILDCARD_STARS`, `webapp.MAX_QUERY_LEN` |
 | Frontmatter size/key/collection/scalar/nesting caps | `frontmatter.MAX_DOCUMENT_CHARS`, `MAX_KEYS`, `MAX_COLLECTION_ITEMS`, `MAX_SCALAR_LENGTH`, `MAX_NESTING_DEPTH` |
 | Tar/ZIP archive budgets (per-member **and** total compression ratio), strict manifest, staged import recovery | `archive.MAX_ARCHIVE_*`, `archive.validate_members`, `archive.validate_zip_members`, `archive.validate_manifest`, `Store.import_` |
 | Failed staging copy never deletes the existing skill directory | `archive.commit_staged_skill` |
 | Full-import trash/templates installed as one rolled-back transaction, malformed metadata rejected pre-mutation, restored trash reconciled in the index | `archive.restore_full_payload`, `archive._rollback_full_install` |
| History limit clamp (limit=99999 → ≤200 verified) | `webapp.MAX_HISTORY_LIMIT` |
| Import filename traversal blocked (`../evil.tar.gz` → 400, empty → 400, ZIP valid/malformed content handled safely) | `WebAppHandler._route_put` import branch |
| Multipart folder-upload part/size caps; a name that is both a file and a directory in one upload is a clean 400 in either part order, and no raw Python exception text becomes the client's error message | `web_upload.parse_multipart`, `web_upload._stage_path`, `web_upload.MAX_UPLOAD_PARTS`, `web_upload.MAX_UPLOAD_BYTES` |
| Vendored `vue.global.prod.js` pinned to the exact upstream release by sha256 + size, verified in the source tree and inside both built artifacts, before the optional build step; `.gitattributes` keeps the file byte-stable across platforms | `check_package_data.VUE_SHA256`/`VUE_SIZE`/`VUE_VERSION`/`VUE_UPSTREAM_URL`, `check_package_data.verify_vendored_vue`, `verify_vendored_bundle` |
| Published artifacts exclude `tests/`, `docs/`, `.env`, databases and bytecode; the sdist is pruned via `MANIFEST.in`, and every archive member is inspected | `check_package_data.unexpected_members`, `check_package_data._canonical_member`, `MANIFEST.in` |
| Build toolchain pinned exactly and hash-verified (`--require-hashes`, `--no-isolation`), so attested bytes do not depend on a floating backend; no install from an index inside the `contents: write` release job | `pyproject.toml` `[build-system]`, `requirements-build.txt`, `.github/workflows/release.yml` |
| Install runner/source/agent/skill allowlists, list-form exec, timeout | `WebAppHandler._route_post` install branch, `insights._INSTALL_VALUE_RE`, `insights._INSTALL_RUNNERS` |
| Static file jail (`is_relative_to`, `..` → 404 verified), `/api/` excluded from the static path | `WebAppHandler._serve_static` |
| Generic 500 + stderr log, no tracebacks to clients | `WebAppHandler._handle_exception` |
| Tar `filter="data"` on modern Python (capability-detected; the independent pre-validator is the real defence) | `archive.extract_members` |
| Skill-name validation on `sync_skill` | `scopes.sync_skill`, `path_safety.safe_skill_path` |
| Unknown-scope rejection | the `unknown scope` guard shared by the scope entry points in `scopes.py` |
| XSS-safe markdown: `esc()` first, `https?` links only, `rel="noopener"`, no `v-html`/`innerHTML` | `webui/domain.js` `esc`, `renderMarkdown` |
| Untrusted skill fields sanitized before terminal output (C0/C1/DEL, separators, format chars, lone surrogates → `?`); `--json`/`view --raw` deliberately exempt | `cli_output.sanitize_text`, `truncate`, `render_table` |
| `doctor?explain` disclosure boundary: paths outside the manager's data dir redacted (`paths_redacted: true`); an out-of-boundary `project` is not walked; the walk is bounded by entries/depth, not result count | `effective.explain` (`allowed_root`), `effective.MAX_WALK_ENTRIES`/`MAX_WALK_DEPTH`, `webapp._doctor_payload` |
| JSON body must be an object, else 400 | `web_serialization.parse_json_object` |

## Verification performed

```bash
python3 -m py_compile skillsmgr/*.py smoke_*.py   # COMPILE_OK
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests   # 607 tests, OK
PYTHONDONTWRITEBYTECODE=1 python3 smoke_store.py  # ALL STORE SMOKE TESTS PASSED
PYTHONDONTWRITEBYTECODE=1 python3 smoke_web.py    # ALL WEB SMOKE TESTS PASSED
PYTHONDONTWRITEBYTECODE=1 python3 check_docs.py   # DOCUMENTATION/SOURCE CONSISTENCY PASSED
```

Live probes against a hermetic store on an ephemeral loopback port (2026-09-11):

```bash
# HEAD /api/skills           -> 200, Content-Length of the GET entity, empty body
# OPTIONS /api/skills        -> 405, Allow: GET, HEAD, POST, PATCH, PUT, DELETE,
#                               CSP + nosniff + DENY + no-referrer + CORP present,
#                               body {"error": "method not allowed"}
# GET with Host: evil.example-> 403 {"error": "invalid Host header"}   (reads gated)
# GET /api/doctor?explain=commandcode&project=/etc
#                            -> resolution "project-outside-managed-roots",
#                               paths_redacted true, project never walked
```

```bash
# REST edge matrix, all as expected:
# traversal import→400, empty body→400, ZIP content validates or fails safely,
# bad archive→400, oversize Content-Length→400, 300-char query→400,
# wildcard exhaustion→400, archive budget/manifest/name mismatch/ZIP probes
# fail closed,
# hostile Origin/Referer/Fetch-Metadata/Host→403, form mutation→415,
# history clamp ok,
# PATCH name ignored, disable/enable ok, static ..→404, unknown skill→404
```

Report written to `security_best_practices_report.md`. Findings use numeric IDs (H-1, M-1…M-3, L-1…L-5) for reference.
