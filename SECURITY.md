# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |
| < 1.0 | ❌ |

## Reporting a vulnerability

**Do not open a public issue for security reports.** Use
[private vulnerability reporting](https://github.com/udayvarmora07/skills-manager/security/advisories/new)
(or email the maintainer) with:

- What you found and where (file + line if possible).
- Steps to reproduce (localhost-only is fine).
- What you think the impact is (RCE, data loss, traversal, XSS…).

Expect an acknowledgement within 72 hours and a fix or mitigation plan within 14 days. We will credit reporters unless you ask otherwise.

## Scope notes

- The web UI binds `127.0.0.1` by design and has no authentication. Reports that assume a remote attacker against the default bind are out of scope — unless you found a way to rebind it or escape loopback.
- TLS/HSTS/`Secure`-cookie findings against the localhost server are out of scope.
- In scope and appreciated: archive/folder intake traversal, XSS via skill bodies, command injection via `install`, name/scope confusion reaching outside skill dirs, symlink escapes, and any way an unauthenticated request can read data it should not (for example a DNS-rebinding page reaching a read route). See [`skills-manager-threat-model.md`](skills-manager-threat-model.md) for the modeled paths (T-1…T-16).

## Localhost browser boundary

The web UI remains loopback-only. In addition, **every** request — `GET` and
`HEAD` as well as `POST`, `PATCH`, `DELETE`, and `PUT` — validates the configured
loopback `Host` and port, rejects `Sec-Fetch-Site: cross-site`, and rejects
mismatched `Origin` or `Referer` origins before invoking Store or scope handlers.
Reads are gated deliberately: a DNS-rebinding page whose origin *is* the rebound
host could otherwise read the skill corpus and download the full archive
(`SEC-1`, closing the F-1 half of issue #14). `OPTIONS` and `TRACE` are not routed
and receive a JSON `405` carrying `Allow` and the full security-header set.
JSON mutation endpoints require `application/json`; archive and multipart imports
use their explicit content types. The server rejects non-loopback bind hosts and
emits defensive CSP, framing, MIME, referrer, and cross-origin resource headers
on every response.

Two disclosure limits are worth knowing when you file a report:

- `GET /api/doctor?explain=…` is confined to the manager's data directory: every
  path outside it is returned as `<redacted>` (`paths_redacted: true`), and an
  out-of-boundary `project` is rejected with `project-outside-managed-roots`
  **without being walked** (`SEC-2`/`SEC-3`).
- CLI text output sanitizes untrusted skill fields (descriptions, categories) so
  a hostile archive cannot spoof `list`/`view`/`stats` through escape sequences
  (`CLI-3`). `--json` and `view --raw` are deliberately exempt because they emit
  stored bytes; a report about raw escape sequences *in those two outputs* is
  expected behaviour, not a finding.

Archive intake supports tar and ZIP by content sniffing. Both formats enforce
compressed-size, expanded-size, per-member-size, member-count, path-length,
nesting-depth, and compression-ratio budgets; validate the versioned manifest and
extracted frontmatter names; and stage each skill before replacement. ZIP uses
explicit contained-path extraction and rejects symlink-bit entries because it has
no equivalent safe tar filter. Failed replacements restore the previous
destination, while partial success is explicitly returned as imported/skipped.

## Developer launchers and repository hygiene

The dev-only `browser_harness.py` keeps Chrome's renderer sandbox enabled and
binds its temporary DevTools endpoint explicitly to `127.0.0.1` on an
OS-selected ephemeral port. `browser_harness.py` and the optional
`desktop_launcher.py` share `skillsmgr.launcher_security.trusted_executable()`:
unsafe PATH matches are skipped, and POSIX executable files and parent
directories must pass ownership and write-permission checks. The CDP endpoint
is an intentionally local, unauthenticated developer seam; it is not exposed
by the product server or a public bind.

The repository ignores local `.env` files, databases, private-key material
(`*.pem`/`*.key`), and `.netrc` credentials. This is a preventive repository
boundary; it does not protect files already tracked by Git.

## Data-root trust boundary

`SKILLS_MANAGER_DATA` and `XDG_DATA_HOME` are operator-controlled overrides,
not a sandbox boundary. `paths.data_dir()` resolves the selected base and the
manager-owned `skills-manager` directory, rejects filesystem roots, regular
files, non-writable roots, roots owned by another user, and non-sticky
group/other-writable directories, and fails closed instead of falling back to
another environment value. New manager-owned directory components are created
with owner-only permissions. Explicit `Store(data_dir=...)` injection remains
an internal/test seam and must receive an equivalently trusted directory.
