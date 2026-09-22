# Skill Hygiene Report Implementation Plan

**Version 1.0.0**

**AI manifest**: Implementation-ready specification for one complete feature: a deterministic, read-only Skill Hygiene Report covering malformed skills, exact instruction duplicates, same-name drift, bounded near-duplicate candidates, broken references, weak activation descriptions, context-cost hotspots, and source-lock drift across observed scopes. This is a GPT-5.6 Luna Max handoff. Read `AGENTS.md`, `docs/SESSION-CONTEXT.md`, `docs/18-project-improvement-audit-2026-09-22.md`, and this file before editing. Do not begin while the safe source-update implementation is still writing shared CLI, REST, UI, test, or documentation files.

## Handoff status and implementation agent

**[NOTE]** Selected feature: **Deterministic Skill Hygiene Report**.

Recommended implementation model: `gpt-5.6-luna` with maximum reasoning. The
feature spans domain analysis, the existing `doctor` CLI/REST surface, the
Quality UI, and tests, but it remains strictly read-only.

This plan intentionally avoids a new CLI command, public `Store` method,
SQLite schema change, runtime dependency, model call, telemetry stream, or
automatic cleanup action. It extends the existing `doctor` command with one
flag and enriches the existing Quality view.

**[SPEC]** Before implementation, confirm that the source-update task has
stopped writing the shared tree. Re-read the current versions and diffs of all
files named under Expected File Changes. If another writer is active, wait or
use a separate worktree; never edit the same shared files concurrently.

## Why this feature

**[NOTE]** Users with large skill libraries repeatedly need answers to these
questions:

- Which copies are byte-for-byte or instruction-for-instruction duplicates?
- Which same-name copies have drifted?
- Which differently named skills probably overlap?
- Which skills reference files that are missing or escape their directory?
- Which descriptions are unlikely to activate reliably?
- Which skills consume unusually large context budgets?
- Which source locks show local drift or cannot be read?
- Which observations are unavailable rather than healthy?

The project already exposes much of the raw evidence through `loader.py`,
`observations.py`, `validator.py`, `source_lock.py`, `tokens.py`,
`scopes.py`, Doctor, and Quality. The missing product layer is a bounded,
explainable synthesis that helps a user decide what to inspect next without
silently changing files.

## User outcome

**[SPEC]** A user can run:

```text
skills-mgr doctor --hygiene --scope all
skills-mgr doctor --hygiene --scope all --json
```

or open Quality in the local web UI and receive a deterministic report that:

1. inventories the exact observed physical instances included in the scan;
2. groups actionable evidence by category and severity;
3. explains every duplicate or similarity signal;
4. distinguishes hard validation failures from best-practice warnings;
5. never collapses independent evidence into a single quality score;
6. recommends existing manual/product surfaces for follow-up; and
7. explicitly lists evidence the manager cannot currently observe.

The report does not delete, merge, disable, sync, edit, quarantine, install, or
update anything.

## Goals

**[SPEC]** The implementation must:

1. Scan `global`, one named scope, or the deduplicated observed instances from
   `all` using the existing scope layer.
2. Collapse alias observations that resolve to the same physical path before
   counting duplicate content.
3. Preserve distinct same-name instances in recursive scopes.
4. Report invalid, malformed, unreadable, unaddressable, conflicting-document,
   and missing-document evidence already exposed by the loader/validator.
5. Detect exact document duplicates and exact instruction-body duplicates.
6. Report same-name identical copies separately from same-name divergent
   copies.
7. Produce bounded, deterministic near-duplicate candidates across different
   names using local explainable text features.
8. Reuse validator results for missing, unresolvable, and out-of-root
   references rather than reimplementing path parsing.
9. Reuse `description_score()` for activation-description observations.
10. Reuse token estimates and documented validator thresholds for context-cost
    evidence.
11. Reuse `source_lock_status()` for source-lock state without treating a
    missing lock as a defect.
12. Isolate one unreadable/broken instance as degraded evidence rather than
    aborting the complete report.
13. Return stable JSON and sanitized terminal output.
14. Integrate the report into the existing Quality view without creating a new
    navigation destination.
15. Remain performant and bounded for inventories up to 10,000 observed
    instances.

## Non-goals

**[SPEC]** Do not implement:

- Automatic deletion, merge, disable, rename, sync, edit, or update.
- A cleanup-plan mutation endpoint.
- A new top-level CLI command.
- A new public `Store` method.
- SQLite persistence, caching, migrations, or schema changes.
- Embeddings, LLM similarity, external APIs, or network requests.
- Usage/invocation tracking or inferred unused-skill claims.
- Remote freshness or available-update claims.
- Dependency readiness, MCP installation, or executable discovery.
- Trust, malware, usefulness, correctness, or effective-load verdicts.
- Cross-language semantic equivalence.
- A combined health/quality score, letter grade, or percentage.
- A recommendation to remove a copy without showing every involved exact
  physical instance.

## Evidence vocabulary

**[SPEC]** Use these terms consistently:

| Term | Meaning |
|---|---|
| Observation | One record returned by the current filesystem/scope scan |
| Physical instance | One deduplicated resolved skill directory |
| Logical name group | Physical instances whose observed canonical names match |
| Exact document duplicate | Distinct physical instances with the same complete primary-document hash |
| Exact instruction duplicate | Distinct physical instances with the same non-empty normalized body hash |
| Divergent name group | Same observed name with more than one document hash |
| Near-duplicate candidate | Differently named instances whose bounded local text features exceed the documented threshold |
| Finding | One independent evidence item with category, severity, explanation, instances, and recommendation |
| Unavailable signal | A question the scan cannot answer from current evidence |
| Degraded scan | A partial result in which one bounded analysis could not be completed |

Allowed severities are `error`, `warning`, `info`, and `unavailable`. Near
duplicates always use `info` with `confidence: heuristic`; they are never
presented as confirmed duplicates.

## Hard invariants

**[SPEC]** The feature must preserve these invariants:

- Filesystem data remains authoritative.
- All operations are read-only.
- Scope roots and observed paths come from the existing scope adapter, not
  user-supplied path traversal.
- Web diagnostics stay within the server's existing diagnostic boundary.
- One unreadable instance cannot hide healthy instances.
- Same-path aliases do not inflate physical-instance or duplicate counts.
- Same-name recursive instances with distinct physical paths remain distinct.
- Validation errors and warnings keep their existing severity.
- Out-of-root references remain warnings according to the existing issue-7
  decision; this task does not promote them to errors.
- Token estimates remain estimates and retain their method.
- Missing source-lock evidence means `unavailable`, not unsafe or stale.
- Similarity is an advisory prioritization signal, not semantic identity.
- Untrusted descriptions, paths, validation messages, and source metadata are
  sanitized before terminal display and escaped in the browser.

## Report schema

**[SPEC]** `hygiene_report()` returns JSON-safe data with this top-level shape:

```json
{
  "version": 1,
  "scope": "all",
  "policy": "read-only evidence; no combined score or automatic cleanup",
  "summary": {
    "observed_records": 0,
    "physical_instances": 0,
    "logical_names": 0,
    "errors": 0,
    "warnings": 0,
    "informational": 0,
    "unavailable": 0,
    "finding_count": 0,
    "findings_returned": 0,
    "findings_truncated": false
  },
  "category_counts": {},
  "findings": [],
  "largest_instances": [],
  "unavailable_signals": [],
  "degraded": [],
  "limits": {}
}
```

Each finding has:

```json
{
  "id": "stable-16-hex",
  "category": "divergent-name",
  "severity": "warning",
  "confidence": "observed",
  "title": "demo differs across 2 physical copies",
  "explanation": "The observed primary-document hashes are not equal.",
  "evidence": {},
  "instances": [],
  "recommendation": "Inspect both copies and use the existing diff/update or sync workflow deliberately.",
  "automatic_action": false
}
```

Finding ids are the first 16 lowercase hexadecimal characters of a SHA-256
digest over canonical JSON containing category and sorted physical instance
identities. The id must be stable across scan order and must not contain a raw
absolute path.

An instance embedded in a finding contains only:

```text
name
scope
scope_label
consumer
physical_path or path
disabled
addressable
malformed
content_hash
metadata_hash
tokens
tokens_method
```

Do not return bodies, full frontmatter, environment data, or source-lock file
contents inside the hygiene report.

## Analysis categories

### Structural and validation evidence

**[SPEC]** Emit one instance-level finding when any of these are observed:

- malformed frontmatter;
- invalid or missing required fields;
- unreadable/non-UTF-8 primary document;
- both `SKILL.md` and `SKILL.md.disabled` present;
- no primary document in a visible global-store husk;
- an unaddressable directory name;
- a scope entry that escapes through a symlink; or
- validator error-level issues.

Use `error` for validator errors, unreadable content, conflicting documents,
missing documents, and escaping filesystem identity. Use `warning` for an
unaddressable but otherwise readable name because the user can still inspect it
on disk even though product mutations refuse it.

Do not run validation twice for the same deduplicated physical instance.

### Exact duplicate evidence

**[SPEC]** Produce distinct categories:

1. `same-name-identical`: same observed name, distinct physical paths, same
   complete primary-document `content_hash`.
2. `exact-document-duplicate`: different observed names, distinct physical
   paths, same complete primary-document `content_hash`.
3. `exact-instruction-duplicate`: different names and different complete
   document hashes, but the same non-empty normalized instruction-body hash.

Normalization for instruction-body hashing is deliberately narrow:

```text
convert CRLF and CR to LF
remove trailing horizontal whitespace on each line
remove leading and trailing blank lines
ensure one terminal newline
```

Do not case-fold, remove punctuation, reorder sections, collapse internal
whitespace, or strip Markdown. Exact instruction duplicates must remain exact
apart from line-ending and trailing-space normalization.

Exclude empty bodies from instruction-duplicate groups. Groups require at
least two distinct physical instances. Alias observations of one physical path
never create a group.

### Same-name drift

**[SPEC]** `divergent-name` groups contain the same observed name at distinct
physical paths with at least two `content_hash` values.

Evidence includes:

- every exact instance;
- sorted unique document hashes;
- differing active/disabled states;
- differing versions, descriptions, metadata hashes, and token estimates;
- a statement that consumer precedence/effective load is not inferred; and
- existing operations that may help the user inspect or deliberately converge
  copies.

Do not select a canonical winner.

### Near-duplicate candidates

**[SPEC]** Near-duplicate analysis is deterministic, local, bounded, and
explainable. It compares differently named, readable, non-empty records after
exact-duplicate groups have been identified.

Text normalization:

1. Unicode NFKC.
2. Case-fold.
3. Replace `_`, `.`, and `-` in names with spaces.
4. Extract Unicode alphanumeric token sequences.
5. Retain tokens of two or more characters.
6. Deduplicate tokens within each field for Jaccard comparison.

Feature sets:

- `name_tokens`: normalized name tokens plus character trigrams from the
  normalized joined name when its length permits.
- `description_tokens`: tokens from at most the first 1,024 characters of the
  description.
- `heading_tokens`: tokens from Markdown headings in at most the first 16,384
  body characters.

Do not use full-body bag-of-words similarity. Boilerplate instructions would
create excessive false positives and unnecessary CPU/memory use.

Candidate generation uses an inverted index over name features and description
tokens. Ignore a posting feature when it appears in more than 64 physical
instances. A pair becomes a scoring candidate when it shares at least one name
feature or two description tokens.

Score using weighted Jaccard values:

```text
similarity = 0.50 * name_similarity
           + 0.35 * description_similarity
           + 0.15 * heading_similarity
```

Emit a near-duplicate candidate only when:

```text
similarity >= 0.78
and
(name_similarity >= 0.50 or description_similarity >= 0.80)
```

The output includes the total score, each component, shared name features,
shared description tokens capped at 20, and the reason it qualified. Results
sort by descending score and then stable physical identity.

Bounds:

- 10,000 physical instances per report.
- 100,000 candidate pairs scored.
- 500 near-duplicate findings returned.
- 64 instances per inverted-index posting.

When an input or candidate bound is reached, stop deterministically, set the
relevant truncation flag, and append a degraded record. Never silently sample
with randomness.

### Broken and escaping references

**[SPEC]** Call `validate_skill()` once per readable addressable physical
instance and classify existing warning messages:

- missing target: message contains `does not exist`;
- unresolvable target: message contains `cannot be resolved`;
- out-of-root target: message contains `escapes the skill directory`;
- missing layout mention: message contains `body mentions` and
  `does not exist`.

Preserve the original issue level, key, and message in evidence. Do not create a
second path parser or change validator wording merely to simplify the report.
If validator issue types later gain stable codes, migrate the hygiene
classifier to those codes in a separate backward-compatible change.

Collapse repeated identical reference messages within one instance, but never
collapse the same problem across distinct physical instances.

### Activation-description evidence

**[SPEC]** Reuse `validator.description_score()` and existing validation
warnings. Emit `activation-description` when one or more apply:

- description is missing/invalid through normal validation;
- description lacks a use context;
- description contains known vague filler; or
- description is shorter than the validator's existing recommendation.

Evidence includes `has_use_context`, sorted filler hits, word count, and the
relevant validator messages. Do not invent an activation probability or
quality score.

### Context-cost evidence

**[SPEC]** Return two kinds of context evidence:

- `context-over-limit` warning when validator reports body tokens above
  `MAX_BODY_TOKENS` or body lines above `MAX_BODY_LINES`.
- `largest_instances`, a separate observation list of the 20 largest physical
  instances by token estimate even when none exceeds a limit.

Each record retains token count, token method, character count where available,
scope, physical path, and disabled state. Do not claim disabled means unused or
zero cost in every consumer. Do not use percentage-of-window as a universal
defect because consumers have different windows.

### Source-lock evidence

**[SPEC]** For each safely addressable physical directory, call
`source_lock_status()` once.

Map status as follows:

| Source-lock state | Hygiene treatment |
|---|---|
| `changed` | Warning: installed tree differs from recorded content hash |
| `inaccessible` | Warning: source evidence cannot be read or current tree cannot be manifested |
| `known-verified` | Information only; verified hash evidence exists, not a safety verdict |
| `known-unverified` | Information only; source identity exists without verified digest |
| `local-only` | Information only |
| `missing` | Unavailable signal, not a warning |

Never expose raw sidecar contents. Return only state, bounded error text, source
kind/value/revision when validated and already public-safe, checked time, and
content hashes. Do not claim that a remote update exists.

### Explicitly unavailable evidence

**[SPEC]** Every report contains these unavailable signals unless another
existing authoritative surface supplied them for the same physical instance:

- invocation count and last-used time;
- unused/stale-by-usage status;
- remote freshness or available update;
- publisher identity or signature trust;
- semantic correctness/usefulness;
- precedence-resolved effective load for arbitrary consumers;
- external binary, credential, MCP, or runtime readiness.

Wording must explain that unavailable means not observed, not that the skill is
healthy or defective.

## Domain architecture

**[SPEC]** Create `skillsmgr/hygiene.py`. Keep it independent from CLI, HTTP,
and Vue. It may read observed skill directories, but it must not write files,
SQLite, caches, or history.

Required public functions:

```python
class HygieneError(ValueError): ...

def normalize_instruction_body(body: str) -> str: ...

def near_duplicate_candidates(
    records: list[dict],
    *,
    max_pairs: int = 100_000,
    max_results: int = 500,
) -> dict: ...

def hygiene_report(
    records: list[dict],
    *,
    scope: str,
    max_instances: int = 10_000,
) -> dict: ...
```

Keep filesystem inspection behind private helpers so pure duplicate/similarity
logic can be tested from hand-built records. `hygiene_report()` deep-copies or
constructs output records; it never mutates the input list or its dictionaries.

Suggested private decomposition:

```text
_physical_identity
_deduplicate_physical_instances
_public_instance
_stable_finding_id
_validation_findings
_exact_duplicate_findings
_divergent_name_findings
_normalized_features
_near_duplicate_index
_reference_findings
_description_findings
_context_findings
_source_lock_findings
_unavailable_signals
_summary
```

Do not move unrelated registry, update, bundle, or risk functions into this
module.

## CLI contract

**[SPEC]** Extend the existing `doctor` command:

```text
skills-mgr doctor [--hygiene] [--json] [--scope SCOPE]
```

Rules:

- Without `--hygiene`, behavior and output remain byte-for-byte compatible
  except for unrelated concurrent changes already accepted by the project.
- `--hygiene` accepts `global`, `all`, or one known scope.
- It is mutually exclusive with `--explain`; return a clean exit-1 error when
  both are supplied.
- The ordinary doctor report remains present. Hygiene appears under a
  `hygiene` key in JSON and after the ordinary doctor sections in text.
- Text output prints summary, errors/warnings, duplicate/drift groups,
  near-duplicate candidates, reference issues, description issues, context
  hotspots, source evidence, degraded sections, and unavailable signals.
- Sanitize every untrusted displayed value through the existing terminal output
  helper.
- An empty hygiene report exits 0.
- Findings do not make the command exit nonzero; exit status describes whether
  the command completed, not whether the library is pristine.
- A total scan failure exits 1. Per-instance failures return a degraded report
  and exit 0.

Do not add `--fix`, `--delete`, `--merge`, `--disable`, or interactive prompts.

## REST API contract

**[SPEC]** Extend the existing read endpoint:

```text
GET /api/doctor?scope=all&hygiene=1
```

Behavior:

- Without `hygiene=1`, preserve the existing payload.
- With `hygiene=1`, add `hygiene` using the same scope semantics as CLI.
- Reject an unknown scope with the existing clean JSON 400 behavior.
- Reject `hygiene=1` combined with `explain=` to match the CLI contract.
- Return no-store and the existing security headers.
- Never accept a filesystem path for hygiene analysis.
- For HTTP, scan only records returned by the already configured scope roots;
  the request cannot widen `diagnostics_roots`.
- A complete hygiene failure appends a named `degraded` entry and returns a
  machine-visible unavailable hygiene payload rather than omitting the key.
- Bound error text and never serialize tracebacks.

No new endpoint or mutation verb is needed.

## Web UI contract

**[SPEC]** Enrich the existing Quality destination. Do not create another nav
item or a single quality score.

### Loading and state

- Quality requests `/api/doctor?scope=<active>&hygiene=1` when opened and when
  the active scope changes.
- Keep `qualityHygiene`, `qualityHygieneLoading`, and
  `qualityHygieneError` distinct from the existing Library records.
- Do not recompute near duplicates in JavaScript.
- A failed hygiene request does not erase the existing per-record Quality
  observations.
- Provide an explicit Retry action.

### Overview

Display:

- physical instances scanned;
- errors;
- warnings;
- exact duplicate groups;
- divergent name groups;
- near-duplicate candidates;
- broken-reference instances;
- activation-description findings;
- context-over-limit findings;
- source-lock drift/unavailable counts; and
- degraded/unavailable evidence.

These are independent metric cards or definition-list facts. Do not sum them
into a score because one instance may contribute to several categories.

### Findings

- Group findings by category with severity and confidence labels.
- Search matches title, explanation, name, scope, consumer, and recommendation.
- Filters include `all`, `error`, `warning`, `info`, and `unavailable`.
- Each finding expands to show exact instances and structured evidence.
- Near-duplicate entries show total and component similarities with an explicit
  heuristic label.
- Duplicate/drift entries provide navigation to the existing Library exact
  instances. They do not execute a mutation.
- Reference and description findings link to the existing Validate action for
  the selected addressable instance.
- Source-change findings may link to the safe update review action only if that
  feature is present and the instance is addressable/writable; otherwise show
  inspection guidance.
- Largest-instance observations remain separate from defect findings.
- Unavailable signals are visibly distinct from zero findings.

### Accessibility and responsive behavior

- Findings are operable with keyboard alone.
- Expand/collapse controls expose `aria-expanded` and an accessible name.
- Severity and confidence do not rely on color.
- Loading, errors, retry, and refreshed results use the existing live region.
- Focus returns predictably after closing detail or moving to Library.
- At 320 and 400 pixels, evidence wraps without page-level horizontal overflow.
- Large text, reduced motion, light/dark themes, and existing locale formatting
  continue to work.

## Determinism and ordering

**[SPEC]** The same input records and filesystem state must produce the same
report except for pre-existing per-record observation timestamps, which should
not be copied into finding ids or ordering.

Order findings by:

1. severity: error, warning, info, unavailable;
2. category using a fixed documented category order;
3. normalized title;
4. finding id.

Order instances by normalized name, scope, and physical path. Sort every token,
hash, issue message, feature, and degraded entry placed into output. Do not
depend on set/dict iteration order even though modern Python preserves insertion
order.

## Performance and resource limits

**[SPEC]** The implementation must remain bounded:

| Resource | Limit |
|---|---:|
| Physical instances analyzed | 10,000 |
| Near-duplicate candidate pairs scored | 100,000 |
| Near-duplicate findings returned | 500 |
| Total findings returned | 2,000 |
| Instances embedded per one group finding | 100 |
| Shared features returned per pair | 20 |
| Description characters analyzed | 1,024 per instance |
| Body characters inspected for headings | 16,384 per instance |
| Largest-instance observations | 20 |
| Bounded error/message/evidence string | 512 characters |

Summary/category counts should represent all findings discovered before a
return cap. If analysis stops because a computational bound is reached, the
summary must say it is partial. `findings_truncated` cannot imply an exact total
when candidate generation itself was truncated.

Suggested performance gates on generated hermetic data:

- 100 instances: p95 below 150 ms after fixture creation.
- 1,000 instances: p95 below 1.5 seconds.
- 10,000 record-only instances with filesystem checks disabled/mocked: below 5
  seconds and bounded memory.

Treat these as local regression budgets, not public universal performance
claims. Record machine/runtime context with results.

## Degraded behavior

**[SPEC]** Continue safely when one bounded component fails:

| Failure | Required report behavior |
|---|---|
| One validator read raises | Add instance-specific degraded entry; continue other instances |
| Source-lock read is malformed | Add source evidence warning; continue |
| One path disappears during scan | Add degraded entry; do not retry indefinitely |
| Near-duplicate pair cap reached | Return deterministic prefix, set truncation/degraded evidence |
| Total finding cap reached | Return deterministic prefix and exact truncation flag |
| One scope scan fails | Preserve other scope results and name failed scope in degraded evidence when existing scope layer can expose it |
| Entire record acquisition fails | Hygiene payload is unavailable; ordinary Doctor behavior remains explicit |
| UI hygiene fetch fails | Existing Quality observations remain; show retryable error |

Do not use broad exception swallowing without a diagnostic record. Do not print
raw tracebacks or environment paths beyond the already observed skill paths.

## Expected file changes

**[SPEC]** Reconfirm these paths against the current tree after the preceding
source-update task finishes.

### Create

- `skillsmgr/hygiene.py` — bounded report engine and deterministic similarity.
- `tests/test_hygiene_contracts.py` — pure/domain/filesystem/performance
  contracts.

### Modify

- `skillsmgr/cli_parser.py` — add `doctor --hygiene` and parser exclusivity.
- `skillsmgr/cli_handlers.py` — acquire scope records, attach report, render
  sanitized text/JSON.
- `skillsmgr/webapp.py` — attach hygiene to `_doctor_payload()` through a small
  helper without increasing route complexity materially.
- `skillsmgr/webui/app.js` — Quality report loading, filters, search, navigation,
  retry, and summary state.
- `skillsmgr/webui/index.html` — accessible summary and evidence UI.
- `skillsmgr/webui/styles.css` — small responsive finding styles.
- `tests/test_cli_contract.py` — parser, compatibility, JSON/text, sanitization,
  scope, and error contracts.
- `tests/test_webapp.py` and `tests/test_web_scopes.py` — REST scope/security/
  degraded behavior.
- `tests/test_web_client_contracts.py` — request and state behavior.
- `tests/test_webui_contracts.py` — UI source/accessibility behavior.
- `smoke_web.py` — one read-only hygiene report and Quality load.
- `docs/02-modules.md` — module inventory and public functions.
- `docs/03-cli-surface.md` — `doctor --hygiene` behavior.
- `docs/08-web-ui.md` — REST query and Quality state/actions.
- `docs/README.md` — register this plan if it was deliberately left unindexed
  during concurrent source-update work.
- `docs/SESSION-CONTEXT.md` — new file, common command, limits, gotchas.
- `README.md` — concise hygiene capability after all evidence passes.
- `task.md` and `docs/06-progress-log.md` — implementation phases and exact
  verification evidence.

### Prefer not to modify

- `skillsmgr/store.py`: no Store method or database behavior is needed.
- `skillsmgr/scopes.py`: existing `scan_scope()` and `list_all()` should supply
  records; change only if a demonstrated missing evidence field cannot be
  derived safely elsewhere.
- `skillsmgr/validator.py`: reuse it; do not change issue severity/wording for
  this feature.
- `skillsmgr/source_lock.py`: reuse `source_lock_status()`.
- `skillsmgr/insights.py`: avoid turning the existing mixed helper module into
  another large subsystem.
- Any schema, migration, dependency, release, archive, or registry file.

## Implementation phases

### Phase 0 serialize and establish baseline

**[SPEC]** Before editing:

1. Confirm no writer is active on shared files.
2. Re-read `AGENTS.md`, session context, this plan, and current relevant diffs.
3. Register this plan in `docs/README.md` if not already registered.
4. Add an in-progress task section and progress-log entry.
5. Preserve every unrelated uncommitted change.
6. Run current validator, scope, insights, CLI, REST, and Quality tests.

Baseline gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_insights_contracts \
  tests.test_scope_contracts \
  tests.test_cli_contract \
  tests.test_webapp \
  tests.test_webui_contracts
```

### Phase 1 red-first hygiene contracts

**[SPEC]** Create failing tests for normalization, alias collapse, exact
duplicates, divergent names, deterministic similarity, reference reuse,
description evidence, context evidence, source-lock mapping, degradation,
ordering, caps, and input immutability before writing `hygiene.py`.

Tests must include adversarial Unicode, empty bodies, huge generic feature
postings, same-name recursive copies, alias scopes sharing one physical path,
missing files, permission errors, symlinks, and shuffled input orders.

### Phase 2 domain engine

**[SPEC]** Implement `hygiene.py` in small pure/helper functions. First make
record-only analysis pass, then add isolated filesystem validation and
source-lock inspection. Avoid nested all-pairs comparison.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_hygiene_contracts \
  tests.test_insights_contracts \
  tests.test_scope_contracts \
  tests.test_link_severity_contracts
```

### Phase 3 Doctor CLI and REST

**[SPEC]** Add `--hygiene`, scope acquisition, text/JSON serialization, REST
query enrichment, and degraded behavior. Preserve ordinary Doctor output and
exit semantics when the flag/query is absent.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_hygiene_contracts \
  tests.test_cli_contract \
  tests.test_webapp \
  tests.test_web_scopes
python3 -m skillsmgr doctor --hygiene --scope all --json
```

Use a temporary isolated data/home environment for the manual CLI invocation;
do not scan or mutate unrelated real user directories during tests.

### Phase 4 Quality UI

**[SPEC]** Add report loading, independent summary facts, grouped findings,
severity filter, search, exact-instance navigation, retry, and unavailable/
degraded states. Do not reproduce similarity calculations in JavaScript.

Phase gate:

```bash
node --check skillsmgr/webui/app.js
node --check skillsmgr/webui/domain.js
node --check skillsmgr/webui/preferences.js
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_web_client_contracts \
  tests.test_webui_contracts \
  tests.test_webapp
python3 browser_harness.py
```

Browser evidence must include empty, clean, exact duplicate, divergent,
near-duplicate, broken-reference, degraded, and mobile-width states.

### Phase 5 performance and full verification

**[SPEC]** Add generated bounded performance fixtures, update documentation,
run package checks, and record final current-tree evidence.

Final ladder:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
python3 smoke_store.py
python3 smoke_web.py
node --check skillsmgr/webui/app.js
node --check skillsmgr/webui/domain.js
node --check skillsmgr/webui/preferences.js
PYTHONDONTWRITEBYTECODE=1 python3 check_docs.py
PYTHONDONTWRITEBYTECODE=1 python3 check_complexity.py
PYTHONDONTWRITEBYTECODE=1 python3 check_package_data.py
python3 browser_harness.py
git diff --check
```

Build wheel and source archive using the pinned hash-verified build toolchain in
a temporary environment and confirm `hygiene.py` is shipped while tests, docs,
databases, caches, and evidence artifacts are not.

## Test strategy

### Pure normalization and grouping

**[SPEC]** Cover:

- LF/CRLF/trailing-space normalization and preservation of meaningful internal
  whitespace/case/punctuation.
- Empty-body exclusion.
- Same physical path under multiple aliases counted once.
- Distinct recursive same-name paths retained.
- Exact document groups, exact instruction groups, same-name-identical groups,
  and divergent groups remain separate.
- Input order permutations produce identical canonical results.
- Inputs are not mutated.

### Near-duplicate analysis

**[SPEC]** Cover:

- clear rename/description overlap qualifies;
- similar boilerplate with dissimilar names/descriptions does not qualify;
- heading-only similarity cannot qualify by itself;
- exact duplicates are not repeated as near duplicates;
- same-name drift is not repeated as cross-name near duplicates;
- Unicode NFKC/casefold behavior is deterministic;
- high-frequency postings are ignored;
- candidate-pair and result caps are deterministic;
- scores/components round to a fixed precision for JSON stability;
- shuffled input yields identical output;
- a 10,000-record synthetic fixture cannot trigger quadratic pair growth.

### Filesystem evidence

**[SPEC]** Cover:

- validation error and warning preservation;
- missing, unresolvable, escaping, encoded, fragment/query, punctuation, and
  existing references through the current validator;
- unreadable/disappearing files degrade one instance only;
- both primary documents and global husks;
- source locks missing, local-only, verified, unverified, changed, malformed,
  oversized, and symlinked;
- no sidecar content or credential-shaped value leaks unexpectedly;
- source-lock missing is unavailable, not warning;
- no filesystem writes occur, using before/after tree manifests in tests.

### CLI contracts

**[SPEC]** Cover:

- `--hygiene` parser/help.
- Mutual exclusion with `--explain`.
- `global`, one agent scope, `all`, unknown scope, and custom `--data-dir`.
- Ordinary Doctor JSON/text unchanged without the flag.
- Stable JSON schema and deterministic text section order.
- Terminal sanitization of names, messages, descriptions, paths, and
  recommendations.
- Findings do not cause nonzero exit; acquisition failure does.
- Per-instance degradation exits zero with visible evidence.

### REST and security contracts

**[SPEC]** Cover:

- query off/on compatibility;
- Host/Origin rejection and security/no-store headers;
- unknown scope and `explain` conflict;
- request cannot supply arbitrary scan paths;
- source paths are confined to observed scope records;
- total failure returns explicit unavailable/degraded hygiene;
- one record failure preserves remaining report;
- no raw traceback or unbounded error text;
- concurrent identical requests return consistent evidence without mutation.

### UI and browser contracts

**[SPEC]** Cover:

- loading, empty, clean, findings, degraded, unavailable, and request-error
  states;
- independent metric facts and absence of score/grade wording;
- severity filtering and search;
- expanded evidence and exact-instance navigation;
- heuristic label and components for near duplicates;
- broken-reference route to Validate;
- retry does not erase existing Quality observations;
- escaped untrusted text;
- accessible names, `aria-expanded`, live announcements, focus lifecycle,
  keyboard use, reduced motion, theme, large text, and mobile layout;
- no console errors, failed requests, warnings, or page-level horizontal
  overflow in the browser harness.

### Performance contracts

**[SPEC]** Separate fixture creation time from analysis time. Warm up once,
measure multiple runs with `time.perf_counter()`, record median/p95, and avoid
fragile single-run assertions on shared CI. Enforce structural bounds in every
environment; enforce generous time ceilings only where the existing suite has
stable precedent.

## Acceptance criteria

**[SPEC]** The task is complete only when all applicable items are checked with
test or manual evidence.

- [ ] HY-01: `doctor --hygiene` supports global, one known scope, and all
  observed scopes without adding a new command.
- [ ] HY-02: Ordinary Doctor behavior remains compatible when hygiene is not
  requested.
- [ ] HY-03: Alias observations of one physical path are counted once.
- [ ] HY-04: Distinct recursive same-name physical instances are preserved.
- [ ] HY-05: Structural/validation errors reuse current loader and validator
  evidence and severity.
- [ ] HY-06: Same-name-identical, divergent-name, exact-document, and exact-
  instruction groups follow the documented contracts.
- [ ] HY-07: Near-duplicate candidates use the documented deterministic,
  explainable, bounded algorithm and are labelled heuristic.
- [ ] HY-08: Reference findings reuse validator results and preserve the
  existing out-of-root warning decision.
- [ ] HY-09: Activation-description evidence uses `description_score()` and
  contains no invented probability/score.
- [ ] HY-10: Context evidence uses existing token/line thresholds and keeps
  largest-instance observations separate from defects.
- [ ] HY-11: Source-lock missing is unavailable, changed/inaccessible is
  warning, and verified state is not presented as a safety verdict.
- [ ] HY-12: Usage, freshness, trust, usefulness, readiness, and arbitrary
  effective-load evidence remain explicitly unavailable.
- [ ] HY-13: No combined quality/health score or automatic cleanup action is
  exposed.
- [ ] HY-14: Report ordering, ids, scores, grouping, truncation, and degraded
  evidence are deterministic.
- [ ] HY-15: One broken instance or scope cannot silently remove all other
  evidence.
- [ ] HY-16: Input, candidate-pair, finding, group-instance, feature, string,
  and output limits are enforced and reported.
- [ ] HY-17: CLI text sanitizes untrusted evidence and JSON follows the stable
  schema.
- [ ] HY-18: REST cannot widen scan roots and retains existing request security.
- [ ] HY-19: Quality presents independent evidence, filtering, search, exact-
  instance navigation, retry, degradation, and unavailable states accessibly.
- [ ] HY-20: The feature performs no filesystem, SQLite, cache, history, or
  network mutation.
- [ ] HY-21: No runtime dependency, build step, schema change, public Store
  method, or new top-level command is added.
- [ ] HY-22: Focused tests, full suite, smoke checks, docs/complexity/package
  gates, browser harness, package builds, and `git diff --check` pass on the
  final current tree.
- [ ] HY-23: Module, CLI, REST, UI, session-context, README, task, and progress
  documentation match the verified shipped behavior.
- [ ] HY-24: Generated 100/1,000/10,000-record evidence demonstrates bounded
  candidate growth and records runtime context without making universal claims.

## Definition of done

**[SPEC]** The feature is done only when:

1. `skillsmgr/hygiene.py` is the sole owner of hygiene analysis policy.
2. CLI, REST, and UI consume the same report rather than reimplementing rules.
3. Every acceptance criterion is linked to automated or explicit manual
   evidence.
4. Existing Doctor and Quality behavior remains functional when the feature is
   unavailable or not requested.
5. The final full verification ladder is green on the final current tree.
6. Wheel and source archive contents are correct.
7. No unrelated concurrent change was overwritten.
8. `task.md` and `docs/06-progress-log.md` record exact final commands, test
   counts, performance context, and any unavailable optional check.

## Implementation cautions for Luna Max

**[SPEC]** During implementation:

- Use `apply_patch` for source edits.
- Do not begin until the active source-update writer has finished or the task is
  moved to a separate worktree.
- Do not reset, checkout, stash-pop, or overwrite current user changes.
- Do not read or write SQLite directly for this feature.
- Do not create a cache to meet performance targets.
- Do not implement O(n squared) comparison over the complete inventory.
- Do not use Python's randomized `hash()` for ids, feature hashes, or ordering.
- Do not silently discard records lacking a name/hash/path; represent degraded
  evidence when possible.
- Do not infer that disabled means unused.
- Do not infer missing source lock means untrusted.
- Do not infer equal bodies mean equal runtime requirements or usefulness.
- Do not turn similarity into a delete recommendation.
- Do not duplicate validator path parsing or change issue severity.
- Do not expose bodies in the report merely to make UI comparison easy.
- Do not add complexity to the existing large route/handler functions when a
  small helper can own the feature branch.
- Do not update a complexity baseline to excuse a new function above budget.
- Re-run the complete ladder after all concurrent tree changes have settled.

## Open decisions

**[?]** No new-command or Store-method approval is required by this design.

If implementation evidence shows that a new public Store method, persistent
usage database, filesystem mutation, validator severity change, or new CLI
command is necessary, stop and request owner approval. Do not expand the task
silently.

