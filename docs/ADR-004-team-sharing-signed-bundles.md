# ADR-004 — Team Sharing: Signed Bundles and Draft → Review → Publish

**Version 1.0.0**

**AI manifest:** Design-only decision record for issue #11 (team sharing of
skill bundles). It defines the trust model, the prospective format, and the two
blocking decisions, and it deliberately implements **nothing**: no bundle
format, no signing code, no CLI command, no REST route, no `Store` method, no
schema change. Threat-model deltas are recorded in
`skills-manager-threat-model.md` (T-13, T-14, R-6, R-7).

## Status

Proposed — September 11, 2026. Design record only. Implementation is blocked on
two maintainer decisions (§6) and needs its own approval under locked
constraint 5 before any code exists.

## Context

Today's sharing primitives are single-user and unauthenticated:

| Existing | What it gives | What it does not give |
|---|---|---|
| `export` / `import` (`Store.export`, `Store.import_`) | A complete archive: `manifest.json` + `skills/<name>/…`, with budgets, traversal guards, staged commit and content hashes | Any proof of *who* produced it, or that it was reviewed |
| `sync NAME --from/--to` | Copy one skill between local scopes | Distribution beyond the machine |
| `install SOURCE` (`npx skills add …`) | Ecosystem install with a trust gate and audit links (ADR-003) | Team-internal curation or approval |

Issue #11 asks for signed bundles and a draft → review → publish flow. The
recorded verdict (TODO Milestone 11 L5) requires a **design-only ADR plus a
threat-model delta before any bundle format** is implemented. This ADR is that
artifact.

## Decision

### 1. What "signed" can and cannot mean here

The CLI is stdlib-only (locked constraint 3) and the product ships zero runtime
dependencies (locked constraint 4). That rules out the shapes people usually
reach for first:

- **Ed25519 / ECDSA signatures** — no public-key signing or verification exists
  in the standard library (`hashlib` has no signature API; `cryptography`,
  `pynacl`, and OpenSSL bindings are third-party). Rejected without an explicit
  dependency decision.
- **X.509 / PKI / key servers** — needs an ecosystem the product does not have
  and a lifecycle (rotation, revocation) a local-first tool cannot administer.

What remains available with `hashlib`/`hmac` alone is **shared-secret
integrity**:

| Option | Primitives available in stdlib | Guarantees | Verdict |
|---|---|---|---|
| `hmac.new(key, payload, sha256)` over the canonical manifest + per-file digests | `hmac`, `hashlib`, `secrets` (key generation) | *Authenticity within a group that shares the key* and *integrity*: a bundle cannot be modified without the key | **Preferred** for the team case (§2) |
| Unsigned SHA-256 manifest (already shipped) | `hashlib` | Integrity against accident/corruption only; no authenticity | Keep as the default for single-user export/import |
| Asymmetric signatures | None in stdlib | Author identity verifiable by anyone holding only a public key | Blocked (§6 Q1) |

The honest framing matters: an HMAC bundle proves *a holder of the team key
produced it*, not *a specific named human produced it*. Any UI or docs wording
that implies the latter would be false, so the design forbids it.

### 2. Trust model for the HMAC option (if approved)

- **One key per team/group**, generated locally (`secrets.token_bytes(32)`),
  never generated or escrowed by the tool, never transmitted by the tool.
- **Key distribution is the group's problem**, out of band. The tool can print a
  key fingerprint and refuse to guess where a key comes from.
- **Key lives outside the data dir** (env var or a path the user supplies), so
  `export --full`/backup can never leak it into a bundle.
- **Verification is explicit**: importing a signed bundle without
  `--trust-key`/equivalent must not silently fall back to unsigned behavior;
  the import reports *unverified* and the caller decides, mirroring the
  registry bridge's `trust_confirmed` gate (ADR-003).
- **Failure is fail-closed**: a bundle that declares a signature but fails
  verification is refused before staging, like any other unsafe archive.

### 3. Bundle format sketch (prospective, not implemented)

Extending the existing archive instead of inventing a second container:

```text
manifest.json          # existing: app, version, created, skills[], full
manifest.sig           # NEW (optional): {"algo": "hmac-sha256", "key_id": "<fingerprint>",
                       #                    "mac": "<hex>"} over a canonical byte string
skills/<name>/SKILL.md # unchanged
```

Canonicalization must be specified before code: a deterministic serialization of
`manifest.json` (sorted keys, no whitespace variance) plus each member's
normalized path and SHA-256, so the MAC covers names *and* contents. Anything
less lets an attacker move a signature between bundles or swap file bodies.

### 4. Draft → review → publish as a state machine, not a service

The product has no server, no accounts, and no network. The stages therefore map
onto filesystem state and existing seams:

| Stage | Existing seam | Prospective addition |
|---|---|---|
| Draft | a skill in the local store, plus the existing `validate`/eval signals (ADR-003) | a `draft` marker or a staging dir name; no schema change (`SCHEMA_VERSION` frozen) |
| Review | `diff_skills()`, `diff_three_way()`, `provenance_summary()`, `risk_scan()`, `validate --evals` — all read-only, all already shipped | a review summary artifact written **beside the bundle** (file), never a DB row |
| Publish | `Store.export(full=…)` → archive | signing step + a published-bundle naming convention |

Deliberate omissions: no internal index, no registry service, no approval
database, no user identity. Those are the parts that would turn a local tool into
a multi-tenant service, and they need their own ADR if they are ever wanted.

### 5. What a team bundle is *not*

- Not an integrity boundary for the *installing* user's machine: a signature
  says "the team key holder produced this", never "this content is safe to run".
  Import keeps every existing safety check (traversal guards, member budgets,
  symlink rejection, staged commit).
- Not a substitute for the registry bridge's per-skill audit links (ADR-003) or
  for `risk_scan()`.
- Not a license to skip review: verification is about transport, review is about
  content, and the design keeps them separate so neither implies the other.

### 6. Blocking decisions (maintainer)

1. **Crypto scope:** accept HMAC/shared-secret team signing (§1 preferred row),
   or approve a vendored/optional asymmetric dependency (Ed25519 via
   `cryptography`/`pynacl`) with the packaging and constraint-4 consequences
   that implies? Without one of these, nothing ships.
2. **Distribution:** is the bundle just a file the team passes around (out of
   scope for the tool), or does the tool need a fetch/publish surface talking to
   a network service? The second is a network feature and inherits the
   deferral recorded for the registry bridge (#3).
3. Secondary: should a signed bundle be allowed to carry run metadata (eval
   results, review notes), or stay content-only? Carrying run data risks turning
   an optional advisory artifact into a claim of approval.

## Consequences

- Issue #11 has a written, reviewable design and an explicit blocker list; no
  code, format, or CLI surface exists yet, so no locked constraint has moved.
- The single-user path is unchanged: `export`/`import` keep unsigned archives
  with content hashes, and nothing in the product reads a signature today.
- A future implementation must add: canonicalization spec, key handling, the
  verification gate, threat-model rows T-13/T-14, and its own tests including a
  tamper corpus (flipped byte, swapped member, moved signature, wrong key,
  truncated archive).
- The honest limit of shared-secret signing (group authenticity, not individual
  identity) is recorded here so documentation cannot overclaim it later.

## Alternatives rejected

- **Sign with a key checked into the repo** — gives no authenticity (anyone with
  the repo has the key); would create false confidence.
- **Trust-on-first-use with no key at all** — a hash is not a signature; the
  shipped SHA-256 content hash already covers accidental corruption.
- **Confine sharing to a hosted service** — contradicts local-first, stdlib-only
  posture and adds an attacker-controlled network surface.
