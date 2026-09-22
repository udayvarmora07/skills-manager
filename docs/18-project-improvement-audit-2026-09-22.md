# Project Improvement Audit and Competitive Roadmap

**Version 1.0.0**

**AI manifest**: Dated, evidence-backed audit of the complete skills-manager repository and documentation surface as inspected on 2026-09-22. It records engineering health, product gaps, competitor capabilities, community demand, user scenarios, and a prioritized improvement roadmap. Treat measurements and competitor observations as dated evidence rather than permanent specifications. Load this document before planning product-positioning, source-update, onboarding, cleanup, distribution, or adoption work.

## Executive conclusion

**[NOTE]** `skills-manager` is technically stronger than its current adoption
suggests. Its local-first design, filesystem-as-truth model, recovery controls,
multi-agent scope support, zero-dependency runtime, and unusually thorough
testing are meaningful strengths.

The project should not begin another broad feature batch yet. Its highest-value
next move is to turn the existing safety foundations into one obvious workflow,
repair trust-breaking defects and documentation inconsistencies, and gather
real-user evidence before expanding its scope.

The recommended product promise is:

> A local, inspectable, reversible system that tells users what their agents
> actually load and lets them safely converge, update, and clean up their skill
> estate.

At the audit date, the project was over-invested in internal engineering
evidence relative to discoverability, onboarding, user feedback, source-update
workflows, and product positioning.

## Audit scope and method

**[NOTE]** The audit covered the tracked repository and documentation corpus,
current architecture and public surfaces, historical audit and decision
records, tests, smoke checks, packaging, browser behavior, static analysis,
public competitors, specification discussions, issue trackers, and community
posts. Historical documents were treated as dated records rather than current
truth.

Only free and open-source tooling and public sources were used. No tracked
project file was changed during the research phase. The repository already
contained unrelated uncommitted changes in `store.py`, `scopes.py`, the web UI,
tests, task tracking, and progress documentation; the findings therefore refer
to that current working-tree snapshot.

## Engineering health

**[NOTE]** The core implementation is mature for a project at this adoption
stage. The filesystem remains authoritative, SQLite is rebuildable, the CLI
runtime is stdlib-only, the local server has deliberate request-boundary
controls, and the product supports more agent scopes than many focused tools.

The following checks passed:

- Store smoke test.
- REST smoke test.
- JavaScript syntax checks.
- Six-viewport browser harness at 320, 400, 640, 900, 1280, and 1440 pixels,
  with no reported console errors, failed requests, warnings, or horizontal
  overflow.
- Complexity ratchet at its current baseline.
- Vendored Vue integrity verification.
- Wheel and source-archive builds through the pinned, hash-verified build
  toolchain.
- Wheel and source-archive package-content checks.
- Dependency vulnerability audit, with no known vulnerabilities reported.
- `git diff --check`.

The full suite executed 839 tests. One documentation-contract test failed
because the checker traversed Markdown inside a local
`.mimocode/node_modules` tree. Product-function tests otherwise passed. The
measured statement coverage was approximately 82 percent.

### Recovery-path defect

**[NOTE]** A forced rollback failure reproduced a real defect in
`skillsmgr/archive.py`. `_rollback_full_install()` calls `_diagnose()` when it
cannot restore a previous payload, but that symbol is not imported. The
resulting `NameError` masks the original rollback failure. This code executes
precisely when a destructive recovery operation is already failing, so it is a
P0 correctness issue even though the normal-path suite does not reach it.

Required correction:

1. Import the intended diagnostic function explicitly.
2. Add a regression that forces `move()` to raise `OSError` during rollback.
3. Assert that the original recovery condition is reported without a secondary
   exception.
4. Verify that the previous payload location remains visible in the diagnostic.

### Documentation gate is workspace-sensitive

**[NOTE]** `check_docs.py::_all_markdown()` recursively selects every Markdown
file except paths containing `.git`, `.autogit`, or `dist`. Developer tools,
vendored trees, virtual environments, and other generated directories can
therefore break the project gate without changing tracked documentation.

The checker should use one of these models:

- Inspect Git-tracked Markdown plus an explicit set of intentionally untracked
  project documents.
- Restrict traversal to first-party documentation roots.
- Maintain a robust generated/vendor-directory exclusion contract.

The tracked-file model is the least surprising for a repository consistency
gate.

### Static-analysis findings

**[NOTE]** Ruff reported 167 findings. Many are formatting, unused imports, or
low-priority cleanup, but the undefined rollback diagnostic demonstrates the
value of a narrow correctness gate. Start with `F821`, `F822`, and `F823`
rather than attempting a disruptive repository-wide style rewrite.

Bandit reported no high-severity findings, three medium findings, and fifteen
low findings. The reported tar extraction and dynamic SQL sites appear bounded
by member validation, `data_filter`, generated placeholder text, and parameter
binding. Review them manually, add focused security regressions, and attach
documented suppressions where the behavior is intentional.

Mypy reported numerous boundary-type errors. Do not enable global strict mode
immediately. Add types incrementally around REST request and response payloads,
registry manifests, archive structures, catalog metadata, and scope adapters.

### Packaging maintenance

**[NOTE]** Wheel and source archive builds passed. Setuptools emitted a
deprecation warning for the TOML-table license form and the MIT license
classifier. Move to an SPDX license expression and appropriate `license-files`
metadata before the announced February 2027 removal date.

### Maintainability hotspots

**[NOTE]** The complexity ratchet prevents further accidental growth, but it
does not make the existing hotspots inexpensive to change.

| Area | Approximate size or complexity | Recommended treatment |
|---|---:|---|
| `webapp._route_get` | 325 lines, complexity 95 | Extract resource handlers behind a small explicit dispatch table |
| `webapp._route_post` | 197 lines, complexity 76 | Separate parsing, authorization, domain call, and serialization |
| `Store._edit_unlocked` | 116 lines, complexity 36 | Extract validation, backup, write, and reindex phases |
| `Store.import_` | 141 lines, complexity 34 | Split planning, staging, commit, and rollback paths |
| `skillsmgr/webui/app.js` | About 2,100 lines | Split by view and action using static scripts or native modules; retain the no-build constraint |
| `skillsmgr/store.py` | About 2,500 lines | Move cohesive private services out without changing the public Store API |

Coverage improvements should concentrate on recovery behavior and low-covered
boundaries such as `cli_handlers`, `atomic_io`, `webapp`, `source_lock`, and
`registry`, rather than chasing a repository-wide percentage.

## Largest product gap

**[NOTE]** Some of the strongest future-facing code is not accessible through
a coherent user workflow. `source_lock.py`, `backup_sync.py`, and `bundles.py`
provide roughly 1,300 lines of provenance, comparison, synchronization, and
sharing foundations, but the CLI, REST API, and web UI do not expose a complete
source-aware update, two-way sync, or approved-bundle journey.

The recommended flagship workflow is:

```text
Discover sources
  -> identify drift and duplicates
  -> preview exact changes
  -> explain risks and missing requirements
  -> create a snapshot
  -> apply
  -> validate the effective installation
  -> undo if necessary
```

This workflow would connect the project's existing strengths: effective
resolution, provenance, validation, history, backup, atomic writes, and
recovery. Exposing it may require a new CLI command or Store method and
therefore requires explicit approval under `AGENTS.md`.

## Competitive landscape

**[NOTE]** The README statement that nobody owns the skill-management problem
is no longer accurate. The market now includes direct managers, desktop control
centers, package managers, governance tools, and the increasingly capable
official ecosystem CLI.

| Competitor | Strongest advantage | Lesson for skills-manager |
|---|---|---|
| [xingkongliang skills-manager](https://github.com/xingkongliang/skills-manager) | Mature desktop experience, broad tool support, marketplace, Git installs, presets, workspaces, backup and sync, auto-update | Users value easy installation, visible updates, and multi-device workflows |
| [iamzhihuix skills-manage](https://github.com/iamzhihuix/skills-manage) | Broad platform support and downloadable releases | Download-and-run packaging can matter more than architectural elegance |
| [mode-io skill-manager](https://github.com/mode-io/skill-manager) | Skills, MCP servers, commands, canonical storage, and security scanning | The category may broaden, but expanding too early would dilute the current advantage |
| [Flow Forge Lab skills-manager](https://github.com/Flow-Forge-Lab-Team/skills-manager) | Guided onboarding, project recommendations, manifests, diffed updates, and Git sync | First-run guidance and visible update semantics are high-value features |
| [abubakarsiddik31 skill-manager](https://github.com/abubakarsiddik31/skill-manager) | Simple local desktop dashboard | Low-friction presentation can outperform deeper internals |
| [egebese skill-manager](https://github.com/egebese/skill-manager) | Project-stack relevance and activation decisions | Users want fewer relevant active skills, not merely more installed skills |
| [skillctl](https://pypi.org/project/skillctl/) | Agent-oriented structured output and next actions | The manager should be straightforward for agents themselves to operate |
| [Vercel skills CLI](https://github.com/vercel-labs/skills/blob/main/src/cli.ts) | Install, use, remove, list, find, update, lockfile, and experimental sync | The current comparison table must be refreshed; single-target and no-update claims are becoming stale |

The project should not compete primarily on the number of supported tools, the
largest marketplace, or the most polished desktop shell. Its most defensible
position is safety and explainability:

- Local and offline operation.
- No runtime dependency chain.
- Filesystem truth.
- Cross-agent effective-resolution evidence.
- Safe mutation, history, and rollback.
- Explainable validation instead of opaque model judgment.
- Privacy-conscious governance.

## Community demand

**[NOTE]** Issue trackers, specification discussions, and community posts show
several recurring needs. Community posts are anecdotal rather than population
measurements, but the patterns recur across independent sources.

### Safe and visible updates

Users want to know where a skill came from, whether upstream changed, what an
update changes, whether the change is suspicious, and how to undo it. Relevant
ecosystem discussions include:

- [Signature verification RFC](https://github.com/vercel-labs/skills/issues/617)
- [Trusted publisher proposal](https://github.com/vercel-labs/skills/issues/318)
- [Provenance discussion](https://github.com/vercel-labs/skills/issues/1391)
- [Update failure caused by path-case mismatch](https://github.com/vercel-labs/skills/issues/1220)
- [Private repository privacy concern](https://github.com/vercel-labs/skills/issues/1593)

### Installation versus activation

Installed, versioned, enabled, project-active, and effectively loaded are
different states. Users need to control activation without uninstalling the
source material. [Vercel skills issue 2010](https://github.com/vercel-labs/skills/issues/2010)
describes this separation directly.

The UI should display these states explicitly:

1. Installed in the library.
2. Enabled for a consumer.
3. Activated for a project.
4. Effective after precedence and shadowing rules.

### Skill overload and cleanup

Recurring complaints include exact and near duplicates, stale skills, broken
references, never-used skills, conflicting instructions, scope drift, and
context-budget bloat. Examples include community discussions about
[managing more than 100 skills](https://www.reddit.com/r/claudeskills/comments/1vodzt5/i_built_a_tool_to_manage_my_100_ai_coding_skills/),
[deduplication and cleanup](https://www.reddit.com/r/claudeskills/comments/1vshgvs/built_a_free_tool_to_dedupeclean_up_your_claude/),
and [excess skills degrading results](https://www.reddit.com/r/ClaudeCode/comments/1t4cy2y/what_do_you_do_when_you_have_too_much_skills/).

Add deterministic local analysis for:

- Exact duplicates and body fingerprints.
- Near-duplicate names and descriptions.
- Broken relative links and missing referenced files.
- Divergent copies across scopes.
- Stale source revisions.
- Potential instruction conflicts.
- Skills installed but never activated.

Usage evidence should remain opt-in and local. Prefer importing local invocation
records or explicit user annotations over telemetry.

### Dependency readiness

The Agent Skills specification does not yet define a complete dependency model,
but the ecosystem is discussing binaries, MCP servers, credentials, and other
capabilities:

- [Agent Skills specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx)
- [Dependency proposal](https://github.com/agentskills/agentskills/issues/485)
- [MCP dependency discussion](https://github.com/agentskills/agentskills/discussions/195)

The product can provide an evidence-based readiness view without inventing a
false standard:

- Declared requirements.
- Inferred executable names.
- MCP requirements.
- Environment variables or credentials.
- Available, missing, and unknown status.
- Evidence source for every conclusion.

### Provenance and local customization

The ecosystem contains extensive reuse and project-specific modification. That
supports source tracking plus overlays or bindings instead of opaque copied
files. See [From Registry to Repository](https://arxiv.org/abs/2607.00911).

## User questions and operating scenarios

**[NOTE]** The following scenarios turn broad market requests into product
acceptance questions.

| Scenario | Current answer | Needed improvement |
|---|---|---|
| I have 100 skills; which should I remove? | Inventory and token analysis help, but there is no complete stale, duplicate, conflict, or usage answer | Cleanup report covering duplicates, broken references, inactive skills, drift, and local usage evidence |
| Upstream changed a skill; should I update? | Registry review exists, but there is no complete installed-source update flow | Provenance lock, update check, directory diff, risk review, snapshot, apply, validate, and undo |
| Two laptops have diverged | Archive export and import work | User-facing Git synchronization with an explicit conflict preview |
| A team wants an approved bundle | Bundle and HMAC foundations exist | Approval workflow, signer identity, policy status, and auditable evidence |
| A skill needs an MCP server or executable | Validation is not a complete readiness check | Dependency and capability matrix with evidence |
| Can an AI agent manage the manager safely? | JSON-oriented surfaces exist, but no complete agent workflow exists | Bundled management skill, documented schemas, dry-run defaults, and safe next actions |
| Which copy actually loads? | Effective resolution is already a strong capability | Put it prominently in onboarding, the overview, and marketing |
| Will it work with 10,000 skills? | Current load evidence uses smaller inventories | Reproducible 100, 1,000, and 10,000 skill benchmarks with cold and warm p95 budgets |
| Does it work well on Windows and WSL? | Cross-platform intent exists, but UX evidence is limited | Windows and WSL installation, path, locking, rename, and cross-filesystem tests |
| Can I remain fully offline? | Yes; local operation is a major strength | Make offline and privacy guarantees part of the primary positioning |
| What happens if another process edits a skill? | Atomic writes and current concurrency work help | Multi-process soak tests, stale-view messaging, and explicit conflict results |
| Can I trust a later update as much as the original install? | Revalidation pieces exist, but no end-to-end update gate exists | Re-run provenance, policy, structural, and safety checks for every candidate update |

## Prioritized roadmap

### P0 next seven days

**[NOTE]** These items protect trust and improve public credibility without
expanding the product surface.

1. Fix the undefined rollback diagnostic and add a forced-failure regression.
2. Make the docs checker operate on tracked or explicitly first-party Markdown.
3. Add a small, high-signal undefined-name lint gate.
4. Review the existing Bandit findings and document intentional suppressions.
5. Move packaging license metadata to an SPDX expression.
6. Replace the README claim that nobody owns the category with an honest
   comparison.
7. Add a strong screenshot or short demonstration near the top of the README.
8. Release a metadata-corrected package version. The
   [current PyPI page](https://pypi.org/project/skill-control-plane/) still
   contains publication-era wording even though version 1.0.1 is published.
9. Align the contribution policy with repository permissions. At the audit
   date, [GitHub issue creation](https://github.com/udayvarmora07/skills-manager/issues)
   was restricted even though contributors were instructed to open an issue.
10. Triage the visible dependency-update pull requests.

### P1 next two to six weeks

**[NOTE]** Productize the source-aware convergence workflow before creating
more foundations.

1. Expose provenance, update checking, whole-directory diffing, risk review,
   snapshot, apply, validation, and undo as one journey.
2. Clarify installed, enabled, project-active, and effective states.
3. Add deterministic duplicate, drift, and stale-reference inspection.
4. Add a first-run flow that scans, explains scopes, shows effective conflicts,
   and recommends safe first actions.
5. Publish an agent-facing management skill with dry-run-first structured
   operations.
6. Benchmark inventories of 100, 1,000, and 10,000 skills.
7. Recruit five to ten design partners across Claude Code, Codex, Cursor,
   Gemini CLI, and OpenCode communities.

Suggested validation gates, not current metrics:

- A new user reaches a useful scan result in under five minutes.
- Every update displays provenance and an exact diff.
- Every mutating batch creates a recoverable checkpoint.
- Forced rollback failures remain visible without secondary exceptions.
- Most design partners can explain installed versus effective after onboarding.

### P2 after user evidence

**[NOTE]** Build these only when design-partner evidence confirms the need.

- Multi-device Git synchronization with conflict resolution.
- Local, opt-in usage evidence and pruning recommendations.
- Internationalization, beginning with the language indicated by actual user
  demand.
- Signed desktop packages when installation friction is demonstrated.
- Team governance and approval workflows with team design partners.
- Adjacent MCP-server or command management only if users consistently request
  a broader extension manager.

## Features to defer

**[NOTE]** Do not prioritize the following in the next feature cycle:

- A Tauri or Electron rewrite.
- A hosted SaaS control plane.
- A public marketplace.
- Model-dependent validation or security scanning.
- More scope adapters solely to increase the supported-tool count.
- Default usage telemetry.
- Broad MCP-server and command management.
- More foundation modules without an exposed user workflow.

The codebase already contains more underlying capability than the product
exposes. Another subsystem would increase maintenance and documentation cost
without addressing adoption.

## Positioning and naming

**[NOTE]** The project currently has three public identifiers:

- GitHub repository: `skills-manager`.
- PyPI distribution: `skill-control-plane`.
- CLI entry point: `skills-mgr`.

Multiple unrelated projects use `skills-manager`, and the phrase `Skill Control
Plane` is also used commercially. This fragments search results and complicates
word-of-mouth adoption. Choose a distinctive project brand while retaining
`local AI agent skill control plane` as the descriptive subtitle. Preserve the
CLI name as a compatibility alias if the public brand changes.

Recommended positioning:

> The safest local control plane for understanding exactly which skills are
> installed, which ones actually load, how copies have drifted, what an update
> will change, and how to undo it.

## Documentation improvements

**[NOTE]** The documentation is comprehensive but expensive to navigate and
maintain. Consolidate repeated current-state facts while retaining dated ADRs
and evidence records.

Recommended changes:

- Separate current truth from historical audit records more visibly.
- Generate volatile counts instead of repeating them manually.
- Maintain one current capabilities matrix.
- Add task guides for cleaning up a large library, reviewing an update, moving
  to a new computer, and resolving cross-agent drift.
- Move large historical screenshot evidence out of the normal clone if it is
  not needed for release verification.
- Label internal foundations as planned or experimental rather than shipped
  workflows.
- Ensure release claims always match reproducible current-tree evidence.

## Final recommendation

**[SPEC]** Use this priority order when converting this audit into work:

1. Protect recovery correctness and restore a reliable verification gate.
2. Correct public metadata, positioning, contribution access, and onboarding
   evidence.
3. Expose the existing source-lock and recovery foundations as one safe update
   and convergence workflow.
4. Validate that workflow with real users and measurable acceptance gates.
5. Add synchronization, internationalization, desktop packaging, team
   governance, or adjacent extension management only after user evidence.

## Open questions

**[?]** The following decisions require owner approval or user evidence:

- What distinctive public brand should replace or qualify the generic
  `skills-manager` name?
- Should the first source-update surface be CLI-first, web-first, or delivered
  as a thin vertical slice across both?
- Which five to ten users will form the first design-partner cohort?
- Should usage evidence be imported from consumer logs, recorded explicitly by
  users, or deferred until consumers expose stable invocation events?
- Which platform produces the most installation friction in actual user
  interviews?
- Do teams value signed bundles enough to justify an identity and approval
  model beyond the existing shared-secret foundation?

