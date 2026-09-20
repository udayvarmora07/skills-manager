# ADR-005 — Registry Network Browsing, Fetching, and Provenance

**Version 1.1.0**

**AI manifest:** Decision record for the network half of registry issue #3:
bounded skills.sh catalog reads, authenticated requests, cache behavior,
credential-free review artifacts, separate commit approval, validated snapshot
materialization, and filesystem provenance.

## Status

Accepted — September 16, 2026; review/commit separation added September 20,
2026. This ADR succeeds the deferred network scope in
@docs/ADR-003-registry-bridge-and-eval-harness.md. It keeps the offline preview
contract intact and adds network behavior only behind the existing `install`
CLI and `POST /api/install` surfaces.

## Context

The skills.sh API documents catalog, search, curated, detail, and audit routes
under `/api/v1/skills`; detail responses can include a complete file snapshot
and a content hash. Authenticated reads use a Vercel OIDC bearer token. See the
[skills.sh API documentation](https://www.skills.sh/docs/api) and the
[skills.sh CLI documentation](https://www.skills.sh/docs/cli).

The manager must remain a local-first stdlib tool. A registry integration must
therefore preserve the locked constraints: the filesystem remains authoritative,
SQLite remains schema version 1 and rebuildable, the web backend remains
stdlib-only and loopback-bound, and no new CLI command or `Store` method is
introduced.

## Decision

### Existing surfaces

The CLI extends `install` with read/fetch/review-commit modes:

```text
install --browse [--page N] [--per-page N] [--view all-time|trending|hot]
install --search QUERY
install --curated
install --fetch SOURCE [--registry-hash HEX]
install --fetch --review REVIEW_ID --trust-confirmed
```

The web UI sends the same operations through `POST /api/install`. Browse,
search, curated, and the first `--fetch SOURCE` request are read operations.
Fetch validates the complete snapshot and writes a private, expiring,
credential-free review artifact under `<data>/registry-reviews/`; it does not
touch the managed Store. A separate `--fetch --review REVIEW_ID
--trust-confirmed` transaction revalidates the stored snapshot, installs it
through the existing `Store.add()` seam, and marks the review single-use. The
REST equivalent is `{fetch: true, source: ID}` followed by `{fetch: true,
review_id: ID, trust_confirmed: true}`. Trust confirmation remains an intent
gate, not a claim that the remote skill is safe.

### Requests, auth, and cache

- Only documented `https://skills.sh` API URLs are constructed or accepted.
  Redirects, credentials, custom ports, non-JSON responses, oversized bodies,
  and non-2xx responses fail closed with a clean `RegistryError`/`StoreError`.
- The token is read from the explicit client token, then
  `SKILLS_MANAGER_REGISTRY_TOKEN`, then `VERCEL_OIDC_TOKEN`. It is sent only as
  `Authorization: Bearer …`; it is never written to output, cache, or
  provenance. The cache key uses a one-way token scope so authenticated and
  anonymous responses cannot collide without persisting the credential.
- Cache entries are private owner-readable JSON files below
  `<data>/registry-cache/`, written with an atomic replace and bounded by size
  and server `Cache-Control: max-age` (capped at one hour). Fresh cache hits are
  automatic; expired entries are used only with `--allow-stale` or
  `allow_stale: true`, and the response reports `miss`, `fresh`, `refreshed`, or
  `stale` in `_registry.cache_state`.
- Cache is an optimization, not trust evidence. A stale result is labeled stale
  in both the response and provenance.

### Snapshot integrity and materialization

Fetched responses are bounded to text files, a root `SKILL.md`, canonical
POSIX-relative paths, maximum file/count/total sizes, and one path per file.
The supplied registry hash is checked against the skills.sh-compatible sorted
path/content hash. The manager also records an explicit length-framed local
snapshot hash to make the on-disk manifest unambiguous. A caller-supplied
`--registry-hash` is compared before installation.

Validated files are written to a private temporary tree, with owner-only file
permissions. The first transaction stores the bounded snapshot and inspection
evidence in an owner-only review artifact; the second transaction revalidates
and atomically commits through the existing `add()` API. Symlink ancestors,
final symlink destinations, traversal, and a remote `.skillsmgr-provenance.json`
are rejected. Review artifacts expire after 24 hours and the commit path makes
them single-use; the commit path performs no network request and never reads a
credential.

The registry's human-readable frontmatter `name` may differ from its canonical
slug. For installation, the manager normalizes only that root `name` field to
the validated slug required by the existing Store invariant and records the
normalization in provenance; the verified remote hash remains separate from the
local framed snapshot hash.

### Provenance

Every successful registry fetch writes a credential-free
`.skillsmgr-provenance.json` sidecar inside the installed skill directory. It
records the registry id/source/slug, page and API URLs, remote and registry
hashes, local framed snapshot hash, hash-verification state, fetch time, cache
state, and a per-file SHA-256/byte manifest. Loader and Store records expose a
validated `registry_provenance` observation. If the sidecar is malformed or no
longer matches the local files, the record exposes
`registry_provenance_error` and is marked malformed; the filesystem is not
silently treated as the fetched bytes.

Before `Store.add` is reached, the complete staged text is validated and
passed through the advisory `risk_scan()` seam. Validation errors fail closed;
warnings and heuristic findings are returned as evidence and never become a
safety certification.

## Consequences

- Users can discover skills without leaving the manager, inspect a complete
  validated snapshot before mutation, and commit it into the global store with
  reviewable provenance.
- Offline preview remains network-free and continues to report trust and hash
  status conservatively. Network fetch is explicit and global-only; agent
  scopes remain managed by the existing scope operations.
- The cache and sidecar are filesystem artifacts, not SQLite data. `db rebuild`
  and `db resync` continue to derive the index from the filesystem.
- This is provenance and integrity evidence, not malware scanning, signature
  verification, or a safety certification. Users must review source, audit
  links, and fetched content before relying on a skill.
- Network availability, API auth, rate limits, and upstream response changes
  remain external failure modes and are surfaced as clean errors. No token is
  persisted to recover from them.

## Verification

Hermetic registry contracts cover URL/auth policy, cache isolation and stale
fallback, response and snapshot limits, hash comparison, symlink/traversal
defense, atomic materialization, sidecar validation/reconciliation, and secret
non-persistence. CLI/REST integration contracts cover the existing install
surface, global-only fetch, explicit trust, loader visibility, and UI payloads.
The final verification ladder is recorded in @docs/06-progress-log.md.
