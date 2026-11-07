# External Skill Scanner (SkillSpector) Implementation Plan

**Goal:** Show security findings from NVIDIA SkillSpector, when the user has it
installed and asks for it, in the review steps that already exist: registry
fetch and "Update from folder". Then extend this project's own stdlib
`risk_scan()` with a small set of rewritten static checks, so that some of this
coverage also exists without the external tool.

**Order (maintainer choice, 2026-11-06):** Phase A (external hook) first, then
Phase B (stdlib patterns).

**Status:** Phase A shipped 2026-11-06 (`skillsmgr/external_scan.py`; D-A and
D-B accepted as proposed; the maintainer also asked for the LLM stage, built as
bring-your-own-key from the environment). Phase B shipped 2026-11-07 as nine
single-purpose stdlib checks in `insights.risk_scan()` (body, description and
an optional in-memory `files` listing; no filesystem read, no new dependency,
CLI command, route or Store method), with the warning-context downgrade rule
and red-first coverage in `tests/test_risk_scan_phase_b.py`. D-C remains open.

## Constraints this plan keeps

- The CLI stays stdlib-only and the web UI keeps no build step and no runtime
  dependency. SkillSpector is an **optional external program**, discovered and
  run like the existing `npx` runner. It is never imported or vendored.
- No new CLI command, no Store method, no SQLite change. Phase A adds one
  opt-in flag to two existing commands and one opt-in body field to two
  existing REST routes. These are surface changes, so they go into
  `docs/03-cli-surface.md` and `docs/08-web-ui.md` in the same commit.
- Findings stay **advisory**. No result from the external tool blocks, allows
  or changes an install, an update or `valid`. This is the existing rule for
  `risk_scan()` and the hygiene report.
- Nothing runs unless asked. The default behaviour of every flow is unchanged.

## What was verified (2026-11-06, local)

- `skillspector` 2.12.0 is installed at `~/.local/bin/skillspector`, which links
  into a uv tool environment.
- `skillspector scan DIR --format json --no-llm` on a three-line hostile
  fixture finished with exit 1. Score was 66, with `recommendation:
  DO_NOT_INSTALL` and three HIGH findings: AR1 ("Never refuse" in the
  description), PE3 (`~/.ssh/id_rsa`) and SC2 (`curl … | bash`).
- Top-level JSON keys: `skill`, `risk_assessment {score, severity,
  recommendation, max_issue_severity}`, `components`, `issues[]`,
  `suppressed_count`, `metadata {skillspector_version, llm_requested, …}`,
  `execution_successful` and `analysis_completeness {coverage_percent,
  is_complete, status, …}`.
- Fields on each issue: `id`, `category`, `pattern`, `severity`, `confidence`,
  `location {file, start_line, …}`, `finding`, `explanation`, `remediation`,
  `code_snippet`, `match_fingerprint`.
- Exit codes: 0 and 1 both mean the scan completed (1 means score > 50).
  2 means an error.
- **There is no offline switch for SC4.** It sends declared dependency names to
  `api.osv.dev` even with `--no-llm`. The only related setting is
  `SKILLSPECTOR_OSV_TIMEOUT`. See decision D-B.
- A skill is required to have `SKILL.md`, so a staged **disabled** candidate
  (`SKILL.md.disabled`) cannot be scanned as-is.

Not verified: behaviour on large trees, on Windows/macOS, or with
`--inspect-dependencies` (not planned).

## Phase A — optional external scanner hook

### A1. `skillsmgr/external_scan.py` (new private module)

One public function, `skillspector_evidence(candidate: Path) -> dict`, and
nothing else exported.

- **Discovery:** `launcher_security.trusted_executable("skillspector")`. An
  unsafe or missing match returns `{"status": "unavailable", "reason": …}`. It
  never raises into the caller.
- **Invocation:** an argv list with no shell: `[exe, "scan", <dir>, "--format",
  "json", "--no-llm"]`.
  - **Never** pass `--transitive`, `--use-shipped-baseline`, `--recursive`,
    `--baseline` or a URL. Only the private staged candidate directory is
    scanned.
  - A candidate's own `.skillspector-baseline.yaml` is ignored by SkillSpector
    by default, and the hook keeps it that way.
- **Environment:** pass a minimal environment (`PATH`, `HOME`, `LANG`, `TMPDIR`)
  so no `*_API_KEY` or provider variable reaches the tool. This is defence in
  depth on top of `--no-llm`.
- **Bounds:**
  - wall-clock timeout of 120 s, also passed as
    `SKILLSPECTOR_MAX_WORKFLOW_SECONDS`;
  - stdout capped at 2 MiB;
  - stderr is kept only as a 2 KiB diagnostic, never shown raw.
- **Disabled candidates:** copy the staged tree into a private temporary
  directory, rename `SKILL.md.disabled` to `SKILL.md`, and scan that copy.
  Clean it up in a `finally`.
- **Parsing:** use the existing bounded JSON loader (`web_serialization`
  nesting limit). Keep a whitelist only:
  - scanner `version`;
  - `score`, `severity`, `recommendation`;
  - `coverage_percent`, `is_complete`, `status`;
  - for each issue: `id`, `category`, `pattern`, `severity`, `confidence`,
    `file`, `line`, `finding`, `explanation`, `remediation`.

  Strings are truncated to 500 characters and the issue list is capped at 200,
  with an `omitted` count. `code_snippet` is dropped: it is untrusted skill
  text, and the location is enough.
- **Outcomes:** `completed`, `unavailable`, `timeout`, `error` (exit 2,
  non-JSON or schema mismatch) or `incomplete` (`is_complete: false`).
  Every outcome carries:
  - `"policy": "advisory-only; third-party heuristic evidence, not a safety
    verdict"`;
  - `"tool": "SkillSpector"`;
  - `"egress": "dependency names may be sent to api.osv.dev"`.
- **Binding:** record the candidate tree hash that was scanned. A stale review
  is already rejected by the existing hash checks, so the evidence cannot
  outlive its bytes.

### A2. Wire into the two existing review chokepoints

| Flow | Function | Where the evidence goes |
|---|---|---|
| Registry fetch review (CLI `install --fetch`, `POST /api/install {fetch}`) | `cli_handlers._prepare_registry_skill` | `inspection["external_scan"]`, persisted in the private review artifact |
| Update from folder / snapshot (CLI `update preview`, `POST /api/source-updates/reviews*`) | `source_update._prepare_from_source`, beside `source_lock._validation_evidence` | `preview["external_scan"]` |

Both run only when the request opts in. The scan happens **before** the review
is written, against the staged copy. It never runs on commit or apply, so an
approval does not re-run the tool.

### A3. Opt-in surface

- CLI: `--external-scan` on `install --fetch` and `update preview`. When the
  scan was skipped, the human output prints one line saying so.
- REST: an `external_scan: true` body field on `POST /api/install` (fetch) and
  on both source-update review routes. For the multipart route, this is a form
  field.
- v2 UI:
  - Tools → Settings gets a local preference, "Run SkillSpector during
    reviews", off by default, with the egress note beside it.
  - The registry and source-update review panels show a separate "SkillSpector
    (external, advisory)" section: worded status pill, findings grouped by
    severity, file:line, explanation and remediation.
  - Text is escaped as usual, with no `v-html` additions.

### A4. Tests (red-first)

- A fake `skillspector` script in a temporary PATH directory covers:
  - completed, incomplete and exit-2 runs;
  - a timeout (sleeps);
  - oversized stdout and non-JSON output;
  - a hostile `finding` containing ESC/bidi characters, which must be
    sanitised in CLI text output;
  - an unsafe PATH entry (world-writable directory), which must be skipped;
  - a disabled candidate.
- Assert the minimal environment: the fake tool dumps its environment and no
  `ANTHROPIC_API_KEY` may appear.
- Without the flag, assert the tool is never invoked, in both flows.
- Assert that results never change `valid`, readiness or `may_install`.
- An optional integration test, skipped when `skillspector` is absent, runs the
  real tool on the hostile fixture and expects AR1/PE3/SC2.
- Run `smoke_web.py` and `smoke_store.py`, the complexity ratchet (new functions
  ≤ 15), `check_docs.py`, and the full suite on every available interpreter.
- Run the v2 browser suite with the fake tool on PATH.

## Phase B — stdlib patterns in `insights.risk_scan()`

Written fresh (not copied regexes; SkillSpector is Apache-2.0), with this
project's own finding ids, as additional single-purpose scanners. Every finding
keeps the existing `why` + `evidence` shape and stays advisory.

| New check | Analogue | Notes |
|---|---|---|
| Remote script piped to a shell (`curl`/`wget … \| sh/bash`, `iex (iwr …)`) | SC2 | body + bundled scripts |
| Decoded payload executed (`base64 -d \| sh`, `eval(atob(…))`, `exec(b64decode(…))`) | SC3 | |
| Credential paths (`~/.ssh/`, `.aws/credentials`, `.env`, keychains) | PE3 | |
| Refusal / disclaimer suppression wording | AR1–AR3 | English only; documented limit |
| Persistence (`crontab`, systemd user units, shell rc writes, LaunchAgents) | RA2 | |
| Shipped `__pycache__` / `.pyc` | SC8 | file listing, no read |
| Whitespace padding hiding text | P9 | run-length threshold |
| Description that triggers on almost anything, or shadows a built-in command | TR1/TR2 | description field only |
| `exec`/`eval`/`__import__`/`subprocess`/`os.system` in bundled `.py` | AST1–5 | stdlib `ast`, bounded file size and count |

Each check needs a red-first test, a false-positive guard test (for example,
documentation that *mentions* `curl | bash` inside a "do not do this" sentence
is still reported, but at low severity with the reason given), and a measured
hygiene-report run on a real library before and after, so the noise level is a
number rather than a claim.

## Open decisions (needed before Phase A step 3)

- **D-A — show SkillSpector's score/recommendation?** The proposed default is to
  show it labelled "reported by SkillSpector", never as this tool's verdict and
  never gating. The alternative is to show findings only.
- **D-B — OSV egress.** The tool cannot be told to skip OSV. Options:
  - accept it, with the warning beside the opt-in (proposed);
  - only run on candidates with no dependency manifest;
  - wait for an upstream offline flag.
- **D-C — Quality / hygiene integration** (scan every installed skill on
  demand) needs a new route or a new hygiene parameter. Deferred to after
  Phase A ships.
