# Threat Model — skills-manager

**Date:** 2026-09-12 · **Version:** 1.4 · **Scope:** `skills-mgr` CLI + local web UI (`skillsmgr/webapp.py`, `skillsmgr/webui/`), `Store` + `scopes` data layer, plus the build/release configuration its artifacts depend on. **1.4** adds the supply-chain paths closed by audit batch 5 — a sha256-pinned vendored bundle, a hash-verified pinned build toolchain, no index install under a write-capable release job, and an archive gate that inspects every member (`SEC-7`, `SEC-8`, `SEC-9`, `SEC-13`, all `FIXED`) — plus `T-18`/`R-9`, the `script-src 'unsafe-eval'` trade-off recorded as accepted rather than silently relaxed (`SEC-4`). **1.3** re-based every mitigation on the post-audit tree: the request policy now guards reads (`SEC-1`), the `doctor?explain` disclosure is confined (`SEC-2`/`SEC-3`), CLI terminal output is sanitized (`CLI-3`), and `HEAD`/`OPTIONS`/`TRACE` no longer bypass the response headers (`BUG-9`). Source citations were switched from `file.py:line` (which had drifted onto unrelated code) to symbol names. Prior: updated for the read-path Host finding (issue #14) and the prospective team-bundle design (ADR-004).

## 1. System overview

```text
Browser (Vue 3, vendored, no build) ── JSON REST + static ─▶ webapp.py (127.0.0.1:8765)
CLI (argparse, stdlib-only) ──────────────────────────────▶ Store / scopes ─▶ filesystem + SQLite index
```

- Source of truth: filesystem (`<data>/skills/<name>/SKILL.md`). SQLite is a rebuildable index. Agent scopes (`~/.agents/skills`, etc.) are written directly on disk.
- Trust posture: single-user localhost tool. No accounts, no sessions, no remote users by default.

## 2. Assets

| # | Asset | Why it matters |
|---|---|---|
| A-1 | User's skill corpus (`<data>/skills/`) | Primary work product; loss/corruption is the main impact |
| A-2 | Agent skill dirs (`~/.agents/skills`, `~/.claude/…`) | Live config consumed by other CLIs (`commandcode`, Claude Code); corruption affects those tools |
| A-3 | Trash + backups (`<data>/trash/`, `<data>/backups/`) | Recovery path; purge is irreversible |
| A-4 | Local code execution context | `install --run` and browser-open cross into execution; compromise runs as the user |

## 3. Trust boundaries

- **B-1 Loopback HTTP** (`127.0.0.1:8765`): any local process or user can call the API. There is no auth boundary inside the machine — by design. Browser-oriented requests additionally pass Host, Fetch Metadata, Origin, and Referer checks (`web_security.validate_request`, called from `WebAppHandler._validate_request` by `do_GET`/`do_HEAD`/`do_POST`/`do_PATCH`/`do_PUT`/`do_DELETE`) — on **every** method, reads included (`SEC-1`).
- **B-2 Archive/folder intake** (`PUT /api/import`, multipart upload, `Store.import_`, `Store.add`): untrusted bytes → filesystem writes. Highest-risk boundary; mitigated by basename/type checks, size/part caps, independent tar validation plus `filter="data"`, and ZIP member preflight with explicit contained-path extraction and symlink-bit rejection.
- **B-3 Skill-body rendering** (SKILL.md → `renderMarkdown` → DOM): untrusted markdown → browser. Mitigated by escape-first renderer, `https?`-only links, no raw HTML.
- **B-4 Ecosystem install** (`/api/install`, `install` command): remote repo name → local `npx skills add` execution. Mitigated by allowlists, list-form exec, default dry-run, UI confirm.
- **B-5 Scope dirs**: writes escape the manager's data dir into agent config dirs. Mitigated by known-scope registry and unknown-scope rejection.

## 4. Attackers & capabilities

| Attacker | Capability | In scope? |
|---|---|---|
| Remote network attacker | None while loopback-only (no port exposure) | Only if user rebinds/forwards the port |
| Local malware / other local user | Full API access (no auth) | Accepted risk for a desktop tool; OS permissions are the boundary |
| Malicious skill archive / SKILL.md | Path traversal, XSS, symlink escape, oversized payload | Yes — primary modeled attacker |
| Malicious skill repo (install) | Postinstall script execution if user runs install | Yes — requires explicit user action |

Out of scope: TLS/HSTS/`Secure` cookies (localhost tool), CSRF tokens (no sessions/cookies), user enumeration, DoS from remote (no remote).

## 5. Abuse paths & mitigations

| Path | Mitigation | Residual |
|---|---|---|
| T-1 Archive path traversal (`../../evil`, absolute members) | Independent tar/ZIP member validation, canonical resolved containment, `filter="data"` on Python ≥ 3.12 plus guarded tar fallback, and explicit ZIP regular-file/directory extraction; ZIP symlink bits rejected | None known in supported formats |
| T-2 Oversized archive/body exhausting memory/disk | 25 MB body cap + `Content-Length` validation; 200 upload parts; tar/ZIP compressed/expanded/member/path/nesting/ratio budgets | Disk-fill by many separate local imports remains accepted local-user behavior |
| T-3 Stored XSS via skill body | Escape-first renderer (`domain.js:esc`), `https?` links only with `rel="noopener"` (`domain.js:renderMarkdown`), no `v-html` | None known |
| T-4 Command injection via install params | Allowlist regex + no-leading-dash on source/agents/skills (`WebAppHandler._route_post` install branch); list-form `subprocess.run`; runner closed set (`insights._INSTALL_RUNNERS`); default dry-run | T-4R: postinstall scripts of the installed repo still run — inherent to the feature; keep confirm gate |
| T-5 Skill-name traversal (`../../x`) reaching outside skill dirs | `validator.NAME_RE` + `validator.MAX_NAME` enforced on create/add/sync through `path_safety.safe_skill_path`/`path_safety.contained_entry`, and by the name guards in `scopes.py` | None known |
| T-6 Static-file escape (`/static/../secret`) | `resolve()` + `is_relative_to` jail (`WebAppHandler._serve_static`); the `/api/` namespace is excluded from that path and an unknown one is a JSON 404, never a static fallthrough | None known |
| T-7 Scope confusion (write to unintended dir) | Known-scope registry; an unknown scope id raises `StoreError("unknown scope ...")` in every scope entry point; trash lives per-scope-base, verified | None known |
| T-8 Symlink escape inside skill dirs | Validator warns on out-of-root link targets (`validator._check_links`); `scopes._copy_skill_tree` copies links **as links** and refuses a tree holding an escaping link, and `export`/`tree_content_hash` no longer follow links (SCOPE-1, STORE-9); `Store.add` still copies a local source directory with the default (dereferencing) `copytree` | Warning-only for link *targets mentioned in a document* (does not block); acceptable, could be blocking. `add` is a local, user-chosen path, so dereferencing there is documented behaviour rather than an intake boundary |
| T-9 Error-message path disclosure | Generic 500s with stderr logging (`WebAppHandler._handle_exception`); the `doctor?explain` report redacts every path outside the manager's data directory (`effective.REDACTED_ROOT`/`REDACTED_PROJECT`); other `StoreError` texts still include paths | Accepted on loopback; sanitize if ever bound non-local. The read diagnostic is the one place that previously leaked **foreign** paths and absolute `data_dir` values, and it is closed |
| T-10 Accidental data loss (purge, remove) | Trash-by-default; purge requires explicit flag; UI undo toast for trash | Purge is irreversible by design; confirm dialogs cover it |
| T-11 Cross-origin browser mutation | Loopback-only bind plus pre-handler Host, `Sec-Fetch-Site`, Origin, Referer, and content-type checks; security headers | Any local process can still call the API directly; OS trust boundary remains |
| T-12 Archive manifest/content mismatch or partial replacement | Strict versioned manifest, canonical name/path/frontmatter checks, staged per-skill commit, rollback of replaced destination, explicit imported/skipped report | Filesystem-first resync remains the recovery path after a process failure |
| T-13 Forged or tampered team bundle accepted as reviewed (prospective — ADR-004) | **Design only; no code exists.** The design requires an explicit verification gate (a bundle that declares a signature and fails verification is refused before staging, never silently downgraded to unsigned), a canonical MAC input covering member names *and* contents, and a key stored outside the data dir so `export --full`/backup cannot carry it | Not mitigated today because nothing reads a signature; a future implementation must not let "verified" imply "safe to run" (ADR-004 §5) |
| T-14 Read-path DNS rebinding: a page whose host resolves to loopback can read skill data (issue #14 F-1) | **MITIGATED (SEC-1, 2026-09-11).** The pre-handler `Host`/`Sec-Fetch-Site`/Origin/Referer policy now runs on `GET` and `HEAD` too, so a rebound hostname produces a `403 invalid Host header` for reads as well as mutations; `tests/test_web_client_contracts.py` pins the closed behaviour. No CORS headers are served, so an ordinary cross-origin response was never readable | Residual: the `Host` allowlist holds the exact bound host and port, so a client configured with the equally-loopback name `localhost` is rejected on every request (issue #14 **F-2**, still open and tracked). Option "accept the rebound-browser case" was not taken; option "add a token" stays rejected by ADR-001 |
| T-15 Unauthenticated `GET /api/doctor?explain=…` walks a caller-chosen directory and discloses the user's real agent-skill inventory, home directory and `data_dir` (SEC-2, SEC-3) | **FIXED.** The HTTP layer always passes a disclosure boundary of the manager's data directory plus only those extra roots the operator configured at server construction — a request cannot widen it (`_doctor_payload(..., diagnostics_roots)`, `webapp._diagnostics_roots`): paths outside it become `<redacted>` with `paths_redacted: true`, and an out-of-boundary `project` returns `project-outside-managed-roots` **without being walked at all**; the walk itself is bounded by entries visited and depth reached (`effective.MAX_WALK_ENTRIES`/`MAX_WALK_DEPTH`), not only by result count. The CLI deliberately passes no boundary and stays fully transparent | No disclosure residual. Effort residual: the diagnostic still performs a bounded filesystem scan per unauthenticated GET, the same class as **SEC-10** (full rescan per request), which stays **OPEN** |
| T-16 Terminal injection: a hostile skill description/category (from an imported archive or a foreign scope directory) spoofs `list`/`view`/`stats` output or corrupts column widths (CLI-3) | **FIXED.** Every printed cell passes through `cli_output.sanitize_text()`: C0/C1 controls and DEL (ESC included), Unicode line/paragraph separators, format characters, and lone surrogates become `?`; `render_table()`/`truncate()` sanitize as well, and colors are applied after sanitizing | `--json` and `view --raw` emit the stored bytes **unsanitized by design** — they are data, not a rendered view. Piping either to a live terminal re-exposes the raw payload |
| T-17 A tampered vendored frontend dependency or a poisoned build/release toolchain ships code that runs with the user's privileges: a 158 KB minified same-origin `vue.global.prod.js` could be replaced by any PR, the release toolchain was resolved fresh from PyPI on every run, and the write-capable release job executed a distribution fetched from an index (SEC-7, SEC-8, SEC-9) | **FIXED 2026-09-12.** The vendored bundle is pinned to its exact upstream release by sha256 + size and verified in the source tree and inside both built artifacts before the optional build step (`check_package_data.verify_vendored_vue`/`verify_vendored_bundle`, `VUE_UPSTREAM_URL`, `VUE_SHA256`); `.gitattributes` marks the file `-text` so EOL translation cannot break the hash. The build backend is exact-pinned in `pyproject.toml` and the outer toolchain is locked with hashes in `requirements-build.txt`, installed `--require-hashes` and used via `--no-isolation` in CI and the release job. No install from an index happens inside a `contents: write` job, and post-publish PyPI verification runs in a `contents: read` job. The published sdist no longer carries `tests/` (SEC-13) and every archive member is inspected (`check_package_data.unexpected_members`) | A Vue bump is now a deliberate, reviewable one-line change instead of an invisible one, but it is still a same-repository edit: the hash pins *what* shipped, not *who* wrote it, so checking the version against the upstream URL stays a human step. PEP 518 cannot carry hashes in `[build-system] requires`, so the isolated backend is pinned by version only — the hash-verified venv plus `--no-isolation` is what removes the floating resolution |
| T-18 CSP would not contain a future HTML-injection sink, because `script-src` allows `'unsafe-eval'` (SEC-4) | **ACCEPTED TRADE-OFF — documented and pinned, deliberately not fixed.** The vendored bundle is the runtime+compiler build and `app.js` passes no `template:`/`render:`, so Vue compiles `index.html`'s in-DOM markup with `Function(code)()`; `'unsafe-inline'` is absent from `script-src`, so an injected `<script>` or `onerror=` is still blocked, and no injection sink exists today (`domain.js` escapes before rendering) | Real cost: if the hand-rolled Markdown renderer ever grows an injection bug, CSP will not contain it. Removing the directive needs precompiled render functions, i.e. a build step, which locked constraint 4 forbids. Recorded in `docs/08-web-ui.md`, tracked as `ACCEPTED` in `docs/13-audit-remediation-status-2026-09-11.md`, pinned by `tests/test_audit_batch5_contracts.py` |

## 6. Risk register

| ID | Risk | Likelihood | Impact | Priority |
|---|---|---|---|---|
| R-1 | Unfiltered tar fallback on old Python (T-1R) | Low (most envs ≥ 3.12) | High (arbitrary write) | Guarded fallback implemented; ZIP has independent manual extraction |
| R-2 | Malicious repo postinstall on `install --run` (T-4R) | Low (needs explicit run) | High (code exec as user) | Keep confirm + docs |
| R-3 | Port rebound to LAN/forwarded, exposing unauthenticated API | Low | Medium (local data + skill writes) | Rejected by default; document "never expose" |
| R-4 | Link-escape warning ignored (T-8) | Low | Low | Consider blocking |
| R-5 | Path disclosure in errors (T-9) | Low | Low | Fix only if bind changes |
| R-6 | Team bundle signed with a shared secret is mistaken for individual authorship (T-13, prospective) | Medium (wording drift is easy) | Low | Blocked on ADR-004 §6; the ADR forbids claiming individual identity and requires the group-authenticity limit in any UI/doc text |
| R-7 | Rebound browser page reads local skill corpus through the read path (T-14) | Low (needs a visited page plus a rebinding-capable setup) | Medium (disclosed skill metadata and full document bodies) | **CLOSED 2026-09-11 (SEC-1)** — Host-on-reads was chosen and implemented; reads and mutations are both rejected with 403. Only issue #14 F-2 (the `localhost` alias) remains open, and it over-rejects rather than under-rejects |
| R-8 | A tampered vendored asset or build toolchain executes in every user's app or in the attested release (T-17) | Low (requires repository or index compromise) | High (code execution as the user; for the release path, attacker code under a write-capable token) | **CLOSED 2026-09-12 (SEC-7, SEC-8, SEC-9, SEC-13)** — sha256-pinned vendored bundle, hash-locked exact build toolchain, no index install under `contents: write`, inspect-every-member archive gate. Residual is human review of a deliberate Vue bump and PEP 518's inability to hash the isolated backend |
| R-9 | CSP fails to contain a future injection bug because `script-src` allows `'unsafe-eval'` (T-18) | Low (no injection sink exists; `'unsafe-inline'` is absent) | High if an injection sink is ever introduced (same-origin access to every local endpoint) | **ACCEPTED 2026-09-12 (SEC-4)** — the fix needs a build step, which locked constraint 4 forbids. Mitigations: keep the Markdown renderer escape-first, never add `'unsafe-inline'` to `script-src`, and revisit if the UI ever ships precompiled render functions |

## 7. Recommendations (ordered)

1. Keep archive budgets and the strict manifest/content contract synchronized with any future full-library migration work.
2. Keep the install confirm gate and show the exact command (already returned by the API) in the dialog; document that running install trusts the source.
3. Keep the loopback-only bind and the pre-handler browser request checks on **every** method (reads included); never expose/reverse-proxy without adding auth.
4. Keep the out-of-root link warning a warning (issue #7 verdict, now pinned by
   `tests/test_link_severity_contracts.py`); promotion would hard-fail legitimate
   monorepo/sibling-skill links and needs an allowlist key first.
5. Issue #14 is decided and half-implemented: `Host` **is** validated on reads
   (F-1, closed by SEC-1). What remains is F-2 — the `Host` allowlist accepts only
   the exact bound host and port, so the equally-loopback name `localhost` is
   rejected on every request when the bind is `127.0.0.1`. Either add the alias to
   the allowlist (a small, deliberate widening) or document it as intended; do not
   leave it unstated.
6. Re-run this model when: a new network listener is added, auth is introduced, or
   import accepts a new format (including the prospective signed bundle, ADR-004).
