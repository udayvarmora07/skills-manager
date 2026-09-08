# ADR-001 — Localhost Mutation Token Decision

**Version 1.0.0**

**AI manifest:** Decision record for the localhost state-changing request boundary.

## Status

Accepted — September 8, 2026.

## Context

The web UI is a single-user local tool. It binds to a loopback address, has no
cookies or browser sessions, and supports local CLI/test clients that may not
send browser-only headers. State-changing requests already pass loopback Host,
`Sec-Fetch-Site`, Origin/Referer, and JSON content-type checks.

## Decision

**Do not add a per-process mutation token.**

The current boundary is sufficient for the intended browser threat model:

- non-loopback binds are rejected;
- cross-site browser mutations are rejected before route handlers;
- no ambient cookie/session credential is available for a cross-site page to
  attach;
- local non-browser clients remain supported without a secret-distribution
  problem.

A mutation token would add a new secret lifecycle and client contract without
  protecting against another local process, which is already inside the accepted
  OS-level trust boundary.

## Consequences

- Keep the existing Host, Fetch Metadata, Origin/Referer, content-type, and
  security-header checks centralized in `skillsmgr/webapp.py`.
- Do not expose or reverse-proxy the server without a new authentication and
  threat-model decision.
- Revisit this ADR if sessions/cookies, remote access, non-loopback binding, or
  multi-user behavior is introduced.

## Verification

`tests/test_webapp.py` covers hostile Origin, Referer, Fetch Metadata, Host,
content type, every mutating method, same-origin behavior, loopback binding, and
security response headers.