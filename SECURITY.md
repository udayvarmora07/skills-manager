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
- In scope and appreciated: archive/folder intake traversal, XSS via skill bodies, command injection via `install`, name/scope confusion reaching outside skill dirs, symlink escapes. See [`skills-manager-threat-model.md`](skills-manager-threat-model.md) for the modeled paths (T-1…T-12).

## Localhost browser boundary

The web UI remains loopback-only. In addition, every state-changing HTTP method
(`POST`, `PATCH`, `DELETE`, and `PUT`) validates the configured loopback `Host`
and port, rejects `Sec-Fetch-Site: cross-site`, and rejects mismatched `Origin`
or `Referer` origins before invoking Store or scope handlers. JSON mutation
endpoints require `application/json`; archive and multipart imports use their
explicit content types. The server rejects non-loopback bind hosts and emits
defensive CSP, framing, MIME, referrer, and cross-origin resource headers.

Archive intake supports tar and ZIP by content sniffing. Both formats enforce
compressed-size, expanded-size, per-member-size, member-count, path-length,
nesting-depth, and compression-ratio budgets; validate the versioned manifest and
extracted frontmatter names; and stage each skill before replacement. ZIP uses
explicit contained-path extraction and rejects symlink-bit entries because it has
no equivalent safe tar filter. Failed replacements restore the previous
destination, while partial success is explicitly returned as imported/skipped.
