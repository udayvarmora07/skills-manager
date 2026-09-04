# Threat Model — skills-manager

**Date:** 2026-09-04 · **Version:** 1.0 · **Scope:** `skills-mgr` CLI + local web UI (`skillsmgr/webapp.py`, `skillsmgr/webui/`), `Store` + `scopes` data layer.

## 1. System overview

```
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

- **B-1 Loopback HTTP** (`127.0.0.1:8765`): any local process or user can call the API. There is no auth boundary inside the machine — by design.
- **B-2 Archive/folder intake** (`PUT /api/import`, multipart upload, `Store.import_`, `Store.add`): untrusted bytes → filesystem writes. Highest-risk boundary; mitigated by basename/type checks, size/part caps, tar `filter="data"`.
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
| T-1 Archive path traversal (`../../evil`, absolute members) | `filter="data"` on Python ≥ 3.12 (`store.py:814`); import basename + tar-type check (`webapp.py:709-743`) | T-1R: unfiltered fallback on old Pythons (`store.py:816`) — set min Python or refuse |
| T-2 Oversized archive/body exhausting memory/disk | 25 MB body cap + `Content-Length` validation (`webapp.py:39, 108-118`); 200 upload parts (`webapp.py:40-41`) | None known; disk-fill by many imports is accepted local-user behavior |
| T-3 Stored XSS via skill body | Escape-first renderer, `https?` links only, `rel="noopener"`, no `v-html` (`app.js:15, 47-110`) | None known |
| T-4 Command injection via install params | Allowlist regex + no-leading-dash on source/agents/skills; list-form `subprocess.run`; runner closed set (`webapp.py:514-543`) | T-4R: postinstall scripts of the installed repo still run — inherent to the feature; keep confirm gate |
| T-5 Skill-name traversal (`../../x`) reaching outside skill dirs | `NAME_RE` + `MAX_NAME` enforced on create/add/sync (`validator.py`, `store.py`, `scopes.py:282, 452`) | None known |
| T-6 Static-file escape (`/static/../secret`) | `resolve()` + `is_relative_to` jail (`webapp.py:192`) | None known |
| T-7 Scope confusion (write to unintended dir) | Known-scope registry; unknown scope → `StoreError` (`scopes.py:150`); trash lives per-scope-base, verified | None known |
| T-8 Symlink escape inside skill dirs | Validator warns on out-of-root link targets (`validator.py:234-238`); `copytree` copies contents by default | Warning-only (does not block); acceptable, could be blocking |
| T-9 Error-message path disclosure | Generic 500s (`webapp.py:174`); some `StoreError` texts include paths | Accepted on loopback; sanitize if ever bound non-local |
| T-10 Accidental data loss (purge, remove) | Trash-by-default; purge requires explicit flag; UI undo toast for trash | Purge is irreversible by design; confirm dialogs cover it |

## 6. Risk register

| ID | Risk | Likelihood | Impact | Priority |
|---|---|---|---|---|
| R-1 | Unfiltered tar fallback on old Python (T-1R) | Low (most envs ≥ 3.12) | High (arbitrary write) | **Fix next** |
| R-2 | Malicious repo postinstall on `install --run` (T-4R) | Low (needs explicit run) | High (code exec as user) | Keep confirm + docs |
| R-3 | Port rebound to LAN/forwarded, exposing unauthenticated API | Low | Medium (local data + skill writes) | Document "never expose" |
| R-4 | Link-escape warning ignored (T-8) | Low | Low | Consider blocking |
| R-5 | Path disclosure in errors (T-9) | Low | Low | Fix only if bind changes |

## 7. Recommendations (ordered)

1. Resolve R-1: require Python ≥ 3.12 for tar import or refuse when `filter=` is unsupported (one `if` in `store.py` import path).
2. Keep the install confirm gate and show the exact command (already returned by the API) in the dialog; document that running install trusts the source.
3. Document "binds loopback only — do not expose/reverse-proxy without adding auth" in `docs/08-web-ui.md` locked rules (one line).
4. Optionally promote the out-of-root link warning to a validation error.
5. Re-run this model when: a new network listener is added, auth is introduced, or import accepts a new format.
