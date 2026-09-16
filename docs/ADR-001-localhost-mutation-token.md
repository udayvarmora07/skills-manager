# ADR-001 — Localhost Mutation Token Decision

**Version 1.1.0**

**AI manifest:** Decision record for the localhost state-changing request boundary.

## Status

Accepted — September 8, 2026.

**Update (2026-09-11).** After this decision was taken, the same policy was
extended to **every** request rather than only to state-changing methods:
`web_security.validate_request()` is now called by `do_GET` and `do_HEAD` too, so
a DNS-rebinding page cannot use the read routes (SEC-1, closing the F-1 half of
issue #14). That widening **supports** this decision rather than reopening it —
the boundary is now strictly larger, and no token is needed to make a browser page
rejectable. The F-2 `localhost`-alias over-rejection remains a tracked nuisance,
not a reason to add a secret.

## Context

The web UI is a single-user local tool. It binds to a loopback address, has no
cookies or browser sessions, and supports local CLI/test clients that may not
send browser-only headers. Requests already pass loopback Host, `Sec-Fetch-Site`,
Origin/Referer, and — for mutations — JSON content-type checks. (As of
2026-09-11 the first three run on reads as well; see *Status*.)

## Decision

**Do not add a per-process mutation token.**

The current boundary is sufficient for the intended browser threat model:

- non-loopback binds are rejected;
- cross-site browser requests, reads included, are rejected before route handlers;
- no ambient cookie/session credential is available for a cross-site page to
  attach;
- local non-browser clients remain supported without a secret-distribution
  problem.

A mutation token would add a new secret lifecycle and client contract without
  protecting against another local process, which is already inside the accepted
  OS-level trust boundary.

## Consequences

- Keep the existing Host, Fetch Metadata, Origin/Referer, content-type, and
  security-header checks centralized in `skillsmgr/web_security.py` (called from
  `WebAppHandler`), applied to **every** method.
- Do not expose or reverse-proxy the server without a new authentication and
  threat-model decision.
- Revisit this ADR if sessions/cookies, remote access, non-loopback binding, or
  multi-user behavior is introduced.

## Verification

`tests/test_webapp.py` covers hostile Origin, Referer, Fetch Metadata, Host,
content type, every mutating method, same-origin behavior, loopback binding, and
security response headers. `tests/test_web_client_contracts.py` covers the
read-path half of the same policy (`GET`/`HEAD` rejection, `OPTIONS`/`TRACE` →
JSON `405`).
