/* ==========================================================================
   Folio sample inventory
   Every record here is illustrative. No skill file is read or written.
   ========================================================================== */

window.FOLIO = (() => {
  "use strict";

  const NAME_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const TODAY = Date.UTC(2026, 9, 25, 12, 0, 0);

  const SCOPES = [
    {
      id: "global",
      label: "Global store",
      short: "Global",
      consumer: "Manager",
      path: "~/.local/share/skills-manager/skills",
      kind: "managed",
      writable: true,
      exists: true,
      count: 402,
      tokens: 96000,
      states: { active: 388, disabled: 10, divergent: 2, malformed: 1, linked: 1 },
    },
    {
      id: "claude-code",
      label: "Claude Code",
      short: "Claude",
      consumer: "Claude Code",
      path: "~/.claude/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 328,
      tokens: 138000,
      states: { active: 301, disabled: 14, divergent: 8, malformed: 2, linked: 3 },
    },
    {
      id: "codex",
      label: "Codex",
      short: "Codex",
      consumer: "Codex",
      path: "~/.codex/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 177,
      tokens: 61000,
      states: { active: 160, disabled: 9, divergent: 4, malformed: 2, linked: 2 },
    },
    {
      id: "cursor",
      label: "Cursor",
      short: "Cursor",
      consumer: "Cursor",
      path: "~/.cursor/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 86,
      tokens: 31000,
      states: { active: 80, disabled: 4, divergent: 1, malformed: 0, linked: 1 },
    },
    {
      id: "opencode",
      label: "OpenCode",
      short: "OpenCode",
      consumer: "OpenCode",
      path: "~/.config/opencode/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 419,
      tokens: 139000,
      states: { active: 386, disabled: 26, divergent: 5, malformed: 1, linked: 1 },
    },
    {
      id: "gemini",
      label: "Gemini",
      short: "Gemini",
      consumer: "Gemini",
      path: "~/.gemini/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 350,
      tokens: 98000,
      states: { active: 330, disabled: 12, divergent: 6, malformed: 1, linked: 1 },
    },
    {
      id: "commandcode",
      label: "Command Code",
      short: "Command",
      consumer: "Command Code",
      path: "~/.commandcode/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 59,
      tokens: 17000,
      states: { active: 55, disabled: 2, divergent: 1, malformed: 0, linked: 1 },
    },
    {
      id: "agents",
      label: "Agents",
      short: "Agents",
      consumer: "Command Code",
      path: "~/.agents/skills",
      kind: "agent",
      writable: true,
      exists: true,
      count: 141,
      tokens: 32480,
      states: { active: 128, disabled: 8, divergent: 3, malformed: 1, linked: 1 },
    },
  ];

  const WINDOWS = [
    { id: "claude", label: "Claude", size: 1000000, note: "1M context" },
    { id: "gpt5", label: "GPT-5", size: 400000, note: "400k context" },
    { id: "gemini", label: "Gemini", size: 2000000, note: "2M context" },
    { id: "haiku", label: "Claude Haiku", size: 200000, note: "200k context" },
  ];

  const TOTAL_TOKENS = SCOPES.reduce((sum, s) => sum + s.tokens, 0);
  const TOTAL_INSTANCES = SCOPES.reduce((sum, s) => sum + s.count, 0);
  const TOTAL_LOGICAL = 642;

  const STATE_META = {
    active: {
      label: "Active",
      tone: "ok",
      mark: "active",
      note: "Every copy is readable and enabled.",
    },
    mixed: {
      label: "Active, one disabled copy",
      tone: "muted",
      mark: "mixed",
      note: "The skill is loadable, but at least one copy is disabled.",
    },
    disabled: {
      label: "Disabled",
      tone: "muted",
      mark: "disabled",
      note: "Every observed copy is disabled.",
    },
    divergent: {
      label: "Divergent",
      tone: "warn",
      mark: "divergent",
      note: "Copies disagree on content. This is attention, not an error.",
    },
    malformed: {
      label: "Malformed",
      tone: "err",
      mark: "malformed",
      note: "At least one copy cannot be parsed as a skill document.",
    },
    linked: {
      label: "Linked outside root",
      tone: "info",
      mark: "linked",
      note: "At least one copy is a symlink the tool refuses to follow.",
    },
    unaddressable: {
      label: "Unaddressable",
      tone: "err",
      mark: "unaddressable",
      note: "The directory name fails the canonical skill name rule.",
    },
  };

  const SEVERITY_META = {
    error: { label: "Error", tone: "err", mark: "malformed" },
    warn: { label: "Warning", tone: "warn", mark: "divergent" },
    info: { label: "Information", tone: "info", mark: "active" },
  };

  function stateOf(skill) {
    const states = (skill.instances || []).map((i) => i.state);
    if (states.includes("malformed")) return "malformed";
    if (!NAME_RE.test(skill.name)) return "unaddressable";
    if (states.includes("divergent")) return "divergent";
    if (states.includes("linked")) return "linked";
    if (states.length && states.every((s) => s === "disabled")) return "disabled";
    if (states.includes("disabled")) return "mixed";
    return "active";
  }

  function scopeById(id) {
    return SCOPES.find((s) => s.id === id);
  }

  function makeInstance(name, scope, state, tokens, opts = {}) {
    const def = scopeById(scope);
    const base = def ? def.path : "~/.local/share/skills-manager/skills";
    return {
      scope,
      scopeLabel: def ? def.label : scope,
      path: `${base}/${name}/SKILL.md`,
      state,
      tokens: Number(tokens) || 0,
      modified: opts.modified || "2026-10-18T09:24:00Z",
      hash: opts.hash || hash(`${name}:${scope}:${tokens}`),
      note: opts.note || "",
      raw: Boolean(opts.raw),
    };
  }

  function hash(input) {
    let h = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
      h ^= input.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    const hex = (h >>> 0).toString(16).padStart(8, "0");
    return `sha256:${hex}${hex.split("").reverse().join("")}${hex}`;
  }

  function titleize(name) {
    return name
      .split("-")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function genericBody(name, description, category) {
    const title = titleize(name);
    return `# ${title}

${description}

## When to use

Use this skill when the task touches ${(category || "this area").toLowerCase()} and the answer has to be checked against the files in the repository. Skip it for a one-line change that the existing tests already cover.

## Workflow

1. Read the current state before proposing a change.
2. Keep the change inside the smallest surface that solves the task.
3. Run the repository checks. Fix what fails before you report done.

## Checks

- The outcome is observable in the files, not only in the summary.
- The change has a rollback path.
- A reviewer can reproduce the result from the evidence.

> This is sample content for the Folio prototype. It is not a real skill document.`;
  }

  const BODY_OVERRIDES = {
    "agent-browser": `# Agent browser

Drive a real browser from a command line so an agent can inspect and operate a page without a screenshot round trip.

## When to use

Use this skill when a task needs a live page: verifying a layout at a breakpoint, reading a value that only exists after JavaScript runs, or walking a signed-in flow that has no API.

Do not use it for static HTML that \`curl\` can read. The browser is the slower tool.

## Setup

1. Start the browser with a private profile.
2. Scope every navigation to the hosts named in the task.
3. Prefer a snapshot over a network trace when the question is about structure.

\`\`\`bash
agent-browser open http://127.0.0.1:8899/ --allowed-domain 127.0.0.1
agent-browser snapshot --compact
\`\`\`

## Working rules

- Read before you click. A snapshot names the target and its role.
- One action per step, then re-read the page. Element refs go stale after a DOM change.
- Never paste a session cookie into a prompt or a log.
- Keep the renderer sandbox on. A local page is still a page.

## Failure modes

- \`net::ERR_CONNECTION_REFUSED\`: the local server is not running.
- A target that disappears: the page re-rendered. Take a fresh snapshot.
- A dialog blocks the page: handle it before the next action.

## Exit condition

Report the URL, the action, and the observed result. A screenshot alone is not evidence that a flow completed.`,
    "accessibility-compliance": `# Accessibility compliance

Review a web interface against WCAG 2.2 AA without inventing a score.

## When to use

Use this skill before a release, after a layout change, or when a keyboard user reports that a flow cannot be completed.

## What to check

- Keyboard: every flow completes without a pointer.
- Focus: \`:focus-visible\` is present and is not obscured by a sticky header or footer.
- Names: every control has an accessible name that matches its visible label.
- Contrast: body text clears 4.5:1. Non-text boundaries clear 3:1.
- Motion: \`prefers-reduced-motion\` disables non-essential movement.
- Reflow: the page survives 320px and 200% zoom without clipping.

## Evidence

Record the selector, the computed value, and the check. A finding without a reproduction is a guess.

\`\`\`css
/* The ring is the floor, not the decoration. */
:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}
\`\`\`

## Report shape

| Finding | Severity | Evidence | After |
| --- | --- | --- | --- |
| Icon-only close button has no name | High | \`button.icon\` exposes no text | Add \`aria-label="Close"\` |
| Focus ring is removed | High | \`outline: none\` with no replacement | Restore a 2px ring |

## What this cannot decide

Whether a flow is understandable. That needs a person and a task.`,
    "add-task": `# Add task

Create a task file in \`.specs/tasks/\` with a stable id, an owner, and one outcome.

## Contract

- File: \`.specs/tasks/<slug>.md\`
- Frontmatter: \`id\`, \`status\`, \`owner\`, \`created\`
- Body: outcome, context, acceptance checks

## Steps

1. Check that the slug is not already present.
2. Write the file with the frontmatter block above.
3. Add the acceptance checks. One check per observable result.
4. Link the task from the current plan, not from a second index.

\`\`\`yaml
id: folio-library-density
status: draft
owner: uday
created: 2026-10-25
\`\`\`

## Done when

Another person can pick up the file and know what "finished" means without asking.`,
    "security-audit": `# Security audit

Find reachable weaknesses in a local service and report them with a reproduction.

## Scope

This skill covers a loopback service, its request policy, and the files it writes. It does not certify a deployment.

## Method

1. Map every route and every filesystem boundary.
2. Check the trust boundary first: host, origin, content type, body limits.
3. Check the write path: path containment, symlink handling, atomic replacement.
4. Check the read path: does a read create or repair state it should not?
5. Record each finding with severity, evidence, and a repair.

## Rules

- Do not run a destructive probe against real data.
- A scanner result is a lead, not a finding.
- Never claim a control is present because a token exists. Point to the line that enforces it.

## Evidence format

\`\`\`text
GET /api/export with Host: attacker.example
Expected: 403
Observed: 200, archive readable

Repair: validate the Host header on every routed verb, reads included.
\`\`\``,
    pdf: `# PDF

Read, extract, and produce PDF files without sending private documents to a network service.

## When to use

Use this skill for a local PDF that needs text, tables, or page images. Use the existing viewer when the task is only to look at a page.

## Read

1. Check whether the file has a text layer.
2. Extract text page by page so the page number survives.
3. Keep tables as tables. A flattened paragraph loses the columns.
4. For a scanned page, render an image and say so.

## Produce

- Keep the original file. Write a new file beside it.
- Name the output with the source name and a suffix.
- Check the page count and the first line after writing.

## Limits

A PDF with no text layer needs OCR, which is a separate tool and a separate decision.`,
    "ui-craft": `# UI craft

Build an interface that makes one decision per screen, then prove the decision with a real state.

## Before coding

- Name the operator and the job.
- Find the existing tokens. Do not invent a second system beside them.
- Write the state list: idle, hover, focus, active, loading, empty, error, disabled, overflow.
- Pick one signature element and build it in the first pass.

## Layout

- One primary action per view.
- Rules and alignment before cards.
- Dense rows for repeated objects. Air in the page head, not in every row.
- A table is a tool. Do not wrap it in a card.

## Color

- One accent, used for selection, focus, and the primary action.
- Status is never color alone.
- Every text pair clears 4.5:1. Every control boundary clears 3:1.

## Finish

- Keyboard path complete.
- Focus visible.
- Reduced motion honored.
- No horizontal overflow at 320px.`,
    "systematic-debugging": `# Systematic debugging

Find the cause before changing the code.

## The loop

1. Reproduce the failure in the smallest environment that still fails.
2. Write down what you expected and what happened.
3. Bisect the path: input, boundary, state, output.
4. Change one variable at a time.
5. Keep the reproduction as a test.

## Rules

- A green test is evidence about the test, not about the change.
- If a gate reports pass about a path it cannot see, the gate is the bug.
- After five failed attempts with one approach, change the approach and write down what you learned.

## Stop condition

You can explain the failure without saying "it seems".`,
    "writing-plans": `# Writing plans

Turn a request into a short, ordered plan that another person can execute.

## Shape

- One sentence of outcome.
- The constraints that cannot move.
- The steps, in order, each with a check.
- The rollback.
- What is explicitly out of scope.

## Rules

- A step that cannot be verified is not a step.
- Group by file ownership when work runs in parallel.
- Put the risky step first, not last.
- Keep the plan short enough to read in one sitting.

## Done when

The plan names the first action and the evidence that ends the task.`,
    "brainstorming": `# Brainstorming

Generate options before choosing one.

## Method

1. Restate the job in one sentence.
2. Write the constraints that cannot move.
3. Produce three genuinely different directions, not three skins of one.
4. For each, name the trade-off and the evidence that would make it right.
5. Choose one. Record why the others lost.

## Rules

- Do not average the options into a fourth.
- A direction that cannot be built with the current constraints is a note, not a candidate.
- The output is a decision, not a list.`,
    "context-budget": `# Context budget

Measure what a skill collection actually costs before an agent is truncated.

## What counts

- Every document the consumer loads, not only the file you edited.
- The whole tree that is concatenated into the window.
- The tool descriptions the consumer adds beside the documents.

## Method

1. Sum the observed documents per root.
2. Compare the sum with the window the consumer uses.
3. Keep the threshold at 100%. A bar that stops at 100% hides the difference between 101% and 121%.
4. Record the estimator. Chars divided by four is a heuristic, not a tokenizer.

## Honesty

This report cannot see model usage, cache hits, or what the consumer actually sends. It measures files on disk.`,
    "code-review": `# Code review

Review a diff for correctness, not for style preferences.

## Order

1. Does the change do what the description says?
2. Does it break an existing contract?
3. Is there a path where it fails silently?
4. Is the test asserting the property or the mechanism?
5. Is there a simpler change?

## Report

- Lead with the highest-risk finding.
- Give the file, the line, and the concrete repair.
- Separate a blocker from a suggestion.
- If you cannot reproduce a concern, say so.`,
    "git-workflow": `# Git workflow

Keep a local branch small, reversible, and easy to review.

## Rules

- One concern per branch.
- Commit after a green check, not before.
- Never rewrite a published branch without a reason written down.
- A commit message says what changed and why. The diff says how.

## Before a pull request

1. Re-run the checks on the current tree.
2. Read the diff as a reviewer.
3. Remove generated files and local scratch data.
4. State what you did not verify.`,
    "mcp-builder": `# MCP builder

Build a small, typed tool surface for a local service.

## Boundaries

- One tool, one job.
- Validate input at the boundary. Do not pass a raw string into a filesystem path.
- Return structured evidence. A prose blob is hard to verify.
- Keep secrets out of the tool result and out of the log.

## Checklist

- The tool has a description that names when to use it.
- Every error has a stable code.
- The server works offline unless the tool is explicitly a network tool.
- A local client can discover the tool without a second config file.`,
    "prompt-engineer": `# Prompt engineer

Write a prompt that produces a checkable result.

## Before writing

- Name the job and the audience.
- Collect the evidence the model may use.
- Decide what the output must contain.
- Decide what the model must not invent.

## Structure

1. One sentence of role and job.
2. The inputs, labelled.
3. The constraints.
4. The output shape.
5. One example of a good result.

## Test

Run the prompt on three inputs, including one that should be refused. If the output is plausible but unchecked, the prompt is not done.`,
    "react-best-practices": `# React best practices

Keep a React surface predictable under real data.

## Rules

- State lives at the lowest owner that needs it.
- Derive values during render. Do not mirror them in state.
- Keys are stable identities, not array indexes for reorderable rows.
- Effects are for synchronising with the outside world, not for deriving data.
- A component that fetches owns its loading, empty, and error states.

## Review

- Does every list have an empty state?
- Does every action have a pending state?
- Does a slow response leave the old value visible or a stale one?`,
    "playwright-expert": `# Playwright expert

Write a browser test that fails for the right reason.

## Rules

- Select by role and name before CSS.
- Wait for the state the user sees, not for a timeout.
- One behaviour per test.
- Isolate data. A test that depends on the previous test is not a test.
- Keep the trace on failure.

## Debug order

1. Read the trace.
2. Check the selector against the accessibility tree.
3. Check the network response.
4. Only then change the test.`,
    "test-master": `# Test master

Choose the smallest test that can fail for the reason you care about.

## Ladder

- A pure function gets a unit test.
- A boundary gets a contract test.
- A user flow gets one end-to-end test.
- A visual decision gets a rendered review, not an assertion on a string.

## Rules

- Assert the property, not the mechanism.
- A test that passes against the broken tree proves nothing.
- Keep one reproduction for every fixed defect.`,
    "typescript-pro": `# TypeScript pro

Use the type system to remove a class of runtime failure.

## Rules

- Model the states, not a bag of optional fields.
- Validate at the boundary. Inside the program, trust the type.
- Prefer a discriminated union to a boolean plus a comment.
- Do not export a type that only exists to silence a cast.
- Read the compiler error before changing the type.`,
    "verify-before-completion": `# Verify before completion

Do not report done until the evidence exists.

## Checklist

- The change is in the file, not only in the plan.
- The check ran on the current tree.
- The failure path was exercised.
- The claim names what was verified and what was not.
- No gate was disabled to get to green.

## Language

Use "added", "fixed", or "changed" only when you can point to the implementation and the observed result. Otherwise say what you attempted.`,
    "docs-writer": `# Docs writer

Write the page a reader needs at the moment they are stuck.

## Rules

- Lead with the answer, then the reason.
- Use the reader's nouns. Do not rename the product in the introduction.
- One procedure per section. Number the steps only when order matters.
- Put the failure modes next to the procedure.
- Date a measurement. An undated number becomes a myth.

## Check

- Can a new reader complete the task without opening the source?
- Does every link resolve?
- Is the version line true?`,
    "design-tokens": `# Design tokens

Give every visual decision one name and one owner.

## Layers

1. Reference values: the raw palette and type scale.
2. Semantic roles: surface, ink, rule, signal, status.
3. Component values: the few tokens a component reads.

## Rules

- A component reads semantic tokens, not raw hex values.
- Every text pair has a measured contrast ratio.
- A token that exists but is not used is a claim without a reader.
- Change the reference, not the component, when the palette moves.`,
    "frontend-design": `# Frontend design

Compose a surface around the job, not around a component library.

## Start

- What is the one decision on this screen?
- What is the artifact the user came to read or change?
- Which state is the default: empty, loading, or populated?

## Build

- Rules before boxes.
- One focal point. The eye should land there before it reads a label.
- A row is a row, not a card inside a card.
- Density is a feature. Do not spend the viewport on padding.

## Finish

- Check the squint test.
- Check 320px.
- Check the keyboard path.
- Remove one element. If the screen still works, it was decoration.`,
    "error-handling": `# Error handling

An error is a recovery path, not a status code with a sentence attached.

## Shape

1. What failed, in the scope the user can see.
2. Why, in plain language, when the cause is known.
3. What to do now.
4. A way to dismiss the message without losing the work.

## Rules

- Do not show the interpreter's own text to a user.
- Do not triple the same error in a banner, a toast, and a field message.
- A retry is scoped to the thing that failed.
- An empty state is not an error.`,
    "incident-response": `# Incident response

Stabilise first. Explain later.

## Order

1. Name the impact in one sentence.
2. Stop the bleeding with the smallest reversible action.
3. Record the timeline as you go.
4. Find the cause after the system is stable.
5. Write the follow-up with an owner and a date.

## Rules

- Do not run an untested fix on the only copy.
- Say what you know, what you suspect, and what you have not checked.`,
    observability: `# Observability

Instrument the question you will ask at 2am.

## Minimum

- One request count, one error count, one latency measure.
- A stable identifier that joins the log line to the request.
- A health signal that fails when the dependency fails.

## Rules

- Do not log a secret, a token, or a full document.
- A dashboard without a threshold is decoration.
- An alert that fires every day is not an alert.`,
    "postgresql-table-design": `# PostgreSQL table design

Design the table around the query, then add the constraints that protect it.

## Rules

- Name the primary key. A table without one is a log.
- Use a real type. A timestamp stored as text is a future bug.
- Add the unique constraint that encodes the business rule.
- Index the columns the query filters and sorts on, not every column.
- Write the migration so it can run on a table with data.

## Review

- Is the nullability honest?
- Is the delete behaviour explicit?
- Does the query plan use the index?`,
    "rag-infrastructure": `# RAG infrastructure

Retrieval quality is a data problem before it is a model problem.

## Pipeline

1. Parse the source with its structure intact.
2. Chunk on meaning, not on a fixed character count alone.
3. Keep the source and the page on every chunk.
4. Retrieve with a hybrid of lexical and vector search.
5. Re-rank before generation.
6. Evaluate with a fixed question set.

## Rules

- A citation the reader cannot open is not a citation.
- Measure recall before you tune the prompt.
- Keep an offline fixture so the pipeline can be tested without a network.`,
    "threat-modeling": `# Threat modeling

Name the asset, the boundary, and the attacker before choosing a control.

## Steps

1. Draw the data flow.
2. Mark every trust boundary.
3. List the assets that would hurt to lose.
4. For each boundary, list what an attacker can send.
5. Choose a control that is enforced by code, not by a comment.
6. Record the residual risk.

## Rule

A control you cannot point to in a request path is a hope.`,
    "data-pipeline": `# Data pipeline

Make every step idempotent and every failure visible.

## Rules

- The input is immutable.
- Each stage writes to a new location.
- A retry produces the same result.
- A partial write is not a success.
- Keep the row count before and after.

## Check

- What happens at 0 rows?
- What happens at 10,000 rows?
- What happens when the source changes shape?`,
    "seo-audit": `# SEO audit

Audit what a crawler can actually read.

## Checks

- One title and one description per page.
- A canonical URL.
- A sitemap that resolves.
- Structured data that matches the visible page.
- Internal links with descriptive text.
- No content hidden behind an interaction that a crawler cannot perform.

## Rules

- Do not promise a ranking.
- A redirect chain is a defect, not a strategy.
- Measure before and after.`,
    "commit-messages": `# Commit messages

A commit message names the change and the reason. The diff names the mechanism.

## Shape

\`\`\`text
scope: imperative summary

Why this change is needed. One short paragraph.
\`\`\`

## Rules

- One concern per commit.
- Do not say "fixes" without naming what was broken.
- Reference the finding or issue when one exists.
- Keep the subject under 72 characters.`,
    "api-design": `# API design

An API is a contract with a stranger who cannot see your code.

## Rules

- One resource, one noun.
- The error shape is the same on every route.
- A paginated list says how many rows exist.
- An invalid parameter is a 400, never a silent default.
- A read does not create state.
- Version the contract when you break it.`,
    "docker-patterns": `# Docker patterns

Keep the image small, the build reproducible, and the runtime boring.

## Rules

- Pin the base image by digest.
- Copy the lock file before the source.
- Run as a non-root user.
- One process per container.
- Do not put a secret in a layer. A deleted layer is still in the image.

## Check

- Does the image build offline from the lock?
- Is the health check real?
- Does the container stop on SIGTERM?`,
    "kubernetes-skill": `# Kubernetes

Declare the desired state, then make the rollout observable.

## Rules

- Set requests and limits.
- Set a readiness probe that reflects the dependency, not the process.
- Use a disruption budget.
- Keep the secret out of the manifest.
- Pin the image tag and the digest.

## Review

- What happens when one replica fails?
- What happens when the node drains?
- Can you roll back with one change?`,
    "dependency-upgrade": `# Dependency upgrade

Upgrade one thing at a time and keep the failure attributable.

## Steps

1. Read the changelog for the breaking changes.
2. Update the lock file.
3. Run the full suite on every supported version.
4. Read the diff in the lock file.
5. Keep the old version available for a rollback.

## Rules

- Do not combine an upgrade with a feature change.
- A green run on one interpreter is not a matrix.
- If the package is unmaintained, record the decision.`,
    "changelog-automation": `# Changelog automation

A changelog is written for the person upgrading, not for the commit graph.

## Rules

- Group by what the user can observe.
- Name the breaking change first.
- Link the migration step.
- Do not paste commit subjects.
- Date the release. Do not claim a release that is not published.`,
    "browser-automation": `# Browser automation

Automate the task, not the screenshot.

## Rules

- Scope the browser to the hosts the task names.
- Read the accessibility tree before clicking.
- Re-read after every DOM change.
- Treat a local page as untrusted input.
- Keep the sandbox on.

## Evidence

Record the URL, the action, the observed state, and the console output.`,
    "skill-builder": `# Skill builder

A skill is a small document with a clear trigger and a checkable outcome.

## Shape

- A name that names the job.
- A description that says when to use it.
- A body with a workflow, the rules that matter, and the failure modes.
- A check that tells the reader the task is done.

## Rules

- One skill, one job.
- Do not restate the whole manual. Link it.
- Write the trigger in the reader's words.
- Include the evidence format.
- Keep the document under the context budget it is meant to save.`,
  };

  function bodyFor(name, description, category) {
    return BODY_OVERRIDES[name] || genericBody(name, description, category);
  }

  const CURATED_DEFS = [
    {
      name: "accessibility-compliance",
      description: "Review a web interface against WCAG 2.2 AA, with evidence for every finding.",
      category: "Quality",
      version: "1.4.0",
      copies: [
        ["claude-code", "active", 2840, { modified: "2026-10-22T09:14:00Z" }],
        ["gemini", "divergent", 2980, { modified: "2026-10-21T16:40:00Z", note: "Steps 3 and 4 disagree with the canonical copy." }],
        ["agents", "active", 2840, { modified: "2026-10-22T09:14:00Z" }],
        ["global", "active", 2840, { modified: "2026-10-22T09:14:00Z" }],
      ],
      validation: {
        valid: true,
        issues: [
          { level: "warn", key: "description", message: "The description does not name the moment to use the skill." },
        ],
      },
      history: [
        { action: "edited in Claude Code", at: "2026-10-22T09:14:00Z", note: "Added the reflow check." },
        { action: "synced from global", at: "2026-10-19T11:02:00Z", note: "Three targets, one skipped." },
        { action: "validated", at: "2026-10-18T16:25:00Z", note: "0 errors, 1 warning." },
      ],
    },
    {
      name: "agent-browser",
      description: "Drive a real browser from a command line so an agent can inspect and operate a page.",
      category: "Automation",
      version: "2.4.1",
      copies: [
        ["global", "active", 2940, { modified: "2026-10-24T10:12:00Z" }],
        ["claude-code", "active", 2940, { modified: "2026-10-24T10:12:00Z" }],
        ["commandcode", "active", 2940, { modified: "2026-10-24T10:12:00Z" }],
        ["agents", "disabled", 2940, { modified: "2026-10-20T08:45:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [
        { action: "synced to agents", at: "2026-10-25T10:12:00Z", note: "1 target, 1 skipped." },
        { action: "edited in global", at: "2026-10-24T10:12:00Z", note: "Added the sandbox rule." },
        { action: "created", at: "2026-10-12T16:20:00Z", note: "Imported from the browser tools folder." },
      ],
    },
    {
      name: "add-task",
      description: "Create a task file with a stable id, an owner, and one checkable outcome.",
      category: "Workflow",
      version: "1.1.0",
      copies: [
        ["claude-code", "linked", 640, { modified: "2026-10-11T14:20:00Z", note: "Symlink to ~/development/notes/add-task, outside the Claude root." }],
        ["agents", "disabled", 640, { modified: "2026-10-09T09:10:00Z" }],
      ],
      validation: {
        valid: true,
        issues: [
          { level: "info", key: "link", message: "One copy is a symlink to a path outside the managed root. It is listed, not followed." },
        ],
      },
      history: [
        { action: "disabled in agents", at: "2026-10-20T08:20:00Z", note: "Kept for reference." },
        { action: "linked in Claude Code", at: "2026-10-11T14:20:00Z", note: "Out-of-root link." },
      ],
    },
    {
      name: ".system",
      description: "An unparsed directory in the Codex root.",
      category: "Uncategorized",
      version: "unknown",
      copies: [
        ["codex", "malformed", 0, { modified: "2026-09-30T07:12:00Z", note: "Frontmatter parse failed at line 2." }],
      ],
      malformed: true,
      addressable: false,
      body: `---
name: .system
description: [unclosed
---

# system

This document was written by a tool that never closed its frontmatter. The loader reports it and does not repair it.
`,
      validation: {
        valid: false,
        issues: [
          { level: "error", key: "frontmatter", message: "Unclosed flow sequence at line 2. The document cannot be parsed." },
          { level: "error", key: "name", message: 'The directory name ".system" does not match the skill name rule.' },
        ],
      },
      history: [
        { action: "observed", at: "2026-10-25T11:58:00Z", note: "Indexed as malformed. Not repaired." },
      ],
    },
    {
      name: "agent-reach",
      description: "Fetch a public page as readable text, with the source and the date kept beside the claim.",
      category: "Research",
      version: "1.3.0",
      copies: [
        ["global", "active", 1440, { modified: "2026-10-17T12:20:00Z" }],
        ["agents", "active", 1440, { modified: "2026-10-17T12:20:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-10-17T12:20:00Z", note: "Initial draft." }],
    },
    {
      name: "context-budget",
      description: "Measure what a skill collection costs before an agent is truncated, and say what the number cannot see.",
      category: "Operations",
      version: "1.2.0",
      copies: [
        ["global", "active", 1560, { modified: "2026-10-23T08:44:00Z" }],
        ["claude-code", "active", 1560, { modified: "2026-10-23T08:44:00Z" }],
        ["opencode", "active", 1560, { modified: "2026-10-23T08:44:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-23T08:44:00Z", note: "Added the estimator note." }],
    },
    {
      name: "security-audit",
      description: "Find reachable weaknesses in a local service and report them with a reproduction.",
      category: "Security",
      version: "3.0.2",
      copies: [
        ["global", "active", 18420, { modified: "2026-10-23T17:44:00Z" }],
        ["claude-code", "active", 18420, { modified: "2026-10-23T17:44:00Z" }],
        ["codex", "divergent", 17680, { modified: "2026-10-18T12:03:00Z", note: "The evidence format section differs." }],
        ["agents", "active", 18420, { modified: "2026-10-23T17:44:00Z" }],
        ["opencode", "disabled", 18420, { modified: "2026-10-15T10:30:00Z" }],
      ],
      validation: {
        valid: true,
        issues: [
          { level: "warn", key: "body", message: "1,842 lines. The document is above the 1,500-line authoring budget." },
        ],
      },
      history: [
        { action: "edited in global", at: "2026-10-23T17:44:00Z", note: "Added the evidence format." },
        { action: "snapshot created", at: "2026-10-23T17:40:00Z", note: "Before the edit." },
      ],
    },
    {
      name: "pdf",
      description: "Read, extract, and produce PDF files without sending private documents to a network service.",
      category: "Documents",
      version: "2.0.0",
      copies: [
        ["global", "active", 4120, { modified: "2026-10-22T14:03:00Z" }],
        ["claude-code", "active", 4120, { modified: "2026-10-22T14:03:00Z" }],
        ["codex", "active", 4120, { modified: "2026-10-22T14:03:00Z" }],
        ["agents", "active", 4120, { modified: "2026-10-22T14:03:00Z" }],
        ["opencode", "active", 4120, { modified: "2026-10-22T14:03:00Z" }],
        ["gemini", "active", 4120, { modified: "2026-10-22T14:03:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [
        { action: "added from registry", at: "2026-10-22T14:03:00Z", note: "anthropics/skills. 8 files, text only." },
      ],
    },
    {
      name: "ui-craft",
      description: "Build an interface that makes one decision per screen and proves it with real states.",
      category: "Design",
      version: "4.2.0",
      copies: [
        ["global", "active", 6120, { modified: "2026-10-20T10:10:00Z" }],
        ["claude-code", "active", 6120, { modified: "2026-10-20T10:10:00Z" }],
        ["agents", "active", 6120, { modified: "2026-10-20T10:10:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [
        { action: "edited in global", at: "2026-10-20T10:10:00Z", note: "Rewrote the finish checklist." },
      ],
    },
    {
      name: "writing-plans",
      description: "Turn a request into a short, ordered plan that another person can execute.",
      category: "Workflow",
      version: "1.6.0",
      copies: [
        ["global", "active", 1820, { modified: "2026-10-16T09:30:00Z" }],
        ["agents", "active", 1820, { modified: "2026-10-16T09:30:00Z" }],
        ["claude-code", "disabled", 1820, { modified: "2026-10-10T13:14:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [
        { action: "disabled in Claude Code", at: "2026-10-17T08:00:00Z", note: "Duplicate of the global copy." },
      ],
    },
    {
      name: "systematic-debugging",
      description: "Find the cause before changing the code, and keep the reproduction as a test.",
      category: "Engineering",
      version: "2.1.0",
      copies: [
        ["global", "active", 2260, { modified: "2026-10-14T15:44:00Z" }],
        ["claude-code", "active", 2260, { modified: "2026-10-14T15:44:00Z" }],
        ["codex", "active", 2260, { modified: "2026-10-14T15:44:00Z" }],
        ["opencode", "active", 2260, { modified: "2026-10-14T15:44:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [
        { action: "synced to four roots", at: "2026-10-15T10:02:00Z", note: "0 skipped." },
      ],
    },
    {
      name: "brainstorming",
      description: "Generate three genuinely different directions before choosing one.",
      category: "Thinking",
      version: "1.3.0",
      copies: [
        ["global", "active", 1240, { modified: "2026-10-09T11:20:00Z" }],
        ["agents", "active", 1240, { modified: "2026-10-09T11:20:00Z" }],
        ["gemini", "divergent", 1310, { modified: "2026-10-07T09:05:00Z", note: "The decision record section differs." }],
      ],
      validation: { valid: true, issues: [] },
      history: [
        { action: "edited in Gemini", at: "2026-10-07T09:05:00Z", note: "Local experiment." },
      ],
    },
    {
      name: "code-review",
      description: "Review a diff for correctness, not for style preferences.",
      category: "Engineering",
      version: "2.0.4",
      copies: [
        ["global", "active", 1640, { modified: "2026-10-21T12:00:00Z" }],
        ["claude-code", "active", 1640, { modified: "2026-10-21T12:00:00Z" }],
        ["codex", "active", 1640, { modified: "2026-10-21T12:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-10-21T12:02:00Z", note: "0 errors." }],
    },
    {
      name: "git-workflow",
      description: "Keep a local branch small, reversible, and easy to review.",
      category: "Engineering",
      version: "1.0.8",
      copies: [
        ["global", "active", 980, { modified: "2026-09-28T09:00:00Z" }],
        ["agents", "active", 980, { modified: "2026-09-28T09:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-09-28T09:00:00Z", note: "Initial draft." }],
    },
    {
      name: "mcp-builder",
      description: "Build a small, typed tool surface for a local service.",
      category: "AI tooling",
      version: "3.1.0",
      copies: [
        ["global", "active", 3280, { modified: "2026-10-19T13:40:00Z" }],
        ["claude-code", "active", 3280, { modified: "2026-10-19T13:40:00Z" }],
        ["commandcode", "active", 3280, { modified: "2026-10-19T13:40:00Z" }],
        ["cursor", "linked", 3280, { modified: "2026-10-02T08:20:00Z", note: "Symlink outside the Cursor root." }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-19T13:40:00Z", note: "Added the offline rule." }],
    },
    {
      name: "prompt-engineer",
      description: "Write a prompt that produces a checkable result.",
      category: "AI tooling",
      version: "2.2.1",
      copies: [
        ["global", "active", 2320, { modified: "2026-10-18T16:20:00Z" }],
        ["agents", "active", 2320, { modified: "2026-10-18T16:20:00Z" }],
        ["codex", "divergent", 2410, { modified: "2026-10-11T11:40:00Z", note: "The test section differs." }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in Codex", at: "2026-10-11T11:40:00Z", note: "Local test prompt." }],
    },
    {
      name: "react-best-practices",
      description: "Keep a React surface predictable under real data.",
      category: "Frontend",
      version: "1.9.0",
      copies: [
        ["global", "active", 2740, { modified: "2026-10-17T10:30:00Z" }],
        ["claude-code", "active", 2740, { modified: "2026-10-17T10:30:00Z" }],
        ["cursor", "active", 2740, { modified: "2026-10-17T10:30:00Z" }],
        ["opencode", "disabled", 2740, { modified: "2026-10-01T09:10:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "synced to cursor", at: "2026-10-17T10:35:00Z", note: "0 skipped." }],
    },
    {
      name: "playwright-expert",
      description: "Write a browser test that fails for the right reason.",
      category: "Testing",
      version: "2.0.0",
      copies: [
        ["global", "active", 3020, { modified: "2026-10-20T14:44:00Z" }],
        ["claude-code", "active", 3020, { modified: "2026-10-20T14:44:00Z" }],
        ["agents", "active", 3020, { modified: "2026-10-20T14:44:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-10-20T14:44:00Z", note: "From the testing notes." }],
    },
    {
      name: "test-master",
      description: "Choose the smallest test that can fail for the reason you care about.",
      category: "Testing",
      version: "1.5.2",
      copies: [
        ["global", "active", 2180, { modified: "2026-10-13T08:20:00Z" }],
        ["codex", "active", 2180, { modified: "2026-10-13T08:20:00Z" }],
        ["agents", "disabled", 2180, { modified: "2026-09-30T10:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "disabled in agents", at: "2026-10-02T09:00:00Z", note: "Superseded by the global copy." }],
    },
    {
      name: "typescript-pro",
      description: "Use the type system to remove a class of runtime failure.",
      category: "Engineering",
      version: "1.8.0",
      copies: [
        ["global", "active", 1940, { modified: "2026-10-12T12:10:00Z" }],
        ["claude-code", "active", 1940, { modified: "2026-10-12T12:10:00Z" }],
        ["cursor", "active", 1940, { modified: "2026-10-12T12:10:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-10-12T12:12:00Z", note: "0 errors." }],
    },
    {
      name: "verify-before-completion",
      description: "Do not report done until the evidence exists.",
      category: "Workflow",
      version: "1.2.0",
      copies: [
        ["global", "active", 1120, { modified: "2026-10-24T09:12:00Z" }],
        ["agents", "active", 1120, { modified: "2026-10-24T09:12:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-24T09:12:00Z", note: "Added the language rule." }],
    },
    {
      name: "docs-writer",
      description: "Write the page a reader needs at the moment they are stuck.",
      category: "Writing",
      version: "1.7.0",
      copies: [
        ["global", "active", 2480, { modified: "2026-10-16T15:30:00Z" }],
        ["claude-code", "active", 2480, { modified: "2026-10-16T15:30:00Z" }],
        ["codex", "active", 2480, { modified: "2026-10-16T15:30:00Z" }],
        ["gemini", "active", 2480, { modified: "2026-10-16T15:30:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "synced to four roots", at: "2026-10-16T15:35:00Z", note: "0 skipped." }],
    },
    {
      name: "design-tokens",
      description: "Give every visual decision one name and one owner.",
      category: "Design",
      version: "2.3.0",
      copies: [
        ["global", "active", 1760, { modified: "2026-10-15T11:00:00Z" }],
        ["claude-code", "active", 1760, { modified: "2026-10-15T11:00:00Z" }],
        ["cursor", "active", 1760, { modified: "2026-10-15T11:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-15T11:00:00Z", note: "Added the measured contrast rule." }],
    },
    {
      name: "frontend-design",
      description: "Compose a surface around the job, not around a component library.",
      category: "Design",
      version: "3.0.1",
      copies: [
        ["global", "active", 3560, { modified: "2026-10-21T09:40:00Z" }],
        ["claude-code", "active", 3560, { modified: "2026-10-21T09:40:00Z" }],
        ["agents", "active", 3560, { modified: "2026-10-21T09:40:00Z" }],
        ["cursor", "active", 3560, { modified: "2026-10-21T09:40:00Z" }],
        ["gemini", "disabled", 3560, { modified: "2026-10-01T09:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "synced to four roots", at: "2026-10-21T09:45:00Z", note: "0 skipped." }],
    },
    {
      name: "error-handling",
      description: "An error is a recovery path, not a status code with a sentence attached.",
      category: "Engineering",
      version: "1.4.0",
      copies: [
        ["global", "active", 1480, { modified: "2026-10-14T10:20:00Z" }],
        ["claude-code", "active", 1480, { modified: "2026-10-14T10:20:00Z" }],
        ["opencode", "active", 1480, { modified: "2026-10-14T10:20:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-10-14T10:20:00Z", note: "From the error audit." }],
    },
    {
      name: "incident-response",
      description: "Stabilise first. Explain later.",
      category: "Operations",
      version: "1.1.0",
      copies: [
        ["global", "active", 1620, { modified: "2026-10-05T18:00:00Z" }],
        ["agents", "active", 1620, { modified: "2026-10-05T18:00:00Z" }],
        ["codex", "active", 1620, { modified: "2026-10-05T18:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-05T18:00:00Z", note: "Added the timeline rule." }],
    },
    {
      name: "observability",
      description: "Instrument the question you will ask at 2am.",
      category: "Operations",
      version: "1.3.0",
      copies: [
        ["global", "active", 1840, { modified: "2026-10-11T09:00:00Z" }],
        ["opencode", "active", 1840, { modified: "2026-10-11T09:00:00Z" }],
        ["gemini", "active", 1840, { modified: "2026-10-11T09:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-10-11T09:05:00Z", note: "0 errors." }],
    },
    {
      name: "postgresql-table-design",
      description: "Design the table around the query, then add the constraints that protect it.",
      category: "Data",
      version: "2.0.0",
      copies: [
        ["global", "active", 2860, { modified: "2026-10-18T13:10:00Z" }],
        ["claude-code", "active", 2860, { modified: "2026-10-18T13:10:00Z" }],
        ["codex", "active", 2860, { modified: "2026-10-18T13:10:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "added from registry", at: "2026-10-18T13:10:00Z", note: "community/postgresql-table-design." }],
    },
    {
      name: "rag-infrastructure",
      description: "Retrieval quality is a data problem before it is a model problem.",
      category: "AI tooling",
      version: "1.6.0",
      copies: [
        ["global", "active", 3180, { modified: "2026-10-19T15:44:00Z" }],
        ["claude-code", "active", 3180, { modified: "2026-10-19T15:44:00Z" }],
        ["gemini", "active", 3180, { modified: "2026-10-19T15:44:00Z" }],
        ["opencode", "divergent", 3260, { modified: "2026-10-09T11:12:00Z", note: "The evaluation section differs." }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in OpenCode", at: "2026-10-09T11:12:00Z", note: "Local evaluation notes." }],
    },
    {
      name: "threat-modeling",
      description: "Name the asset, the boundary, and the attacker before choosing a control.",
      category: "Security",
      version: "1.2.0",
      copies: [
        ["global", "active", 2060, { modified: "2026-10-07T10:00:00Z" }],
        ["codex", "active", 2060, { modified: "2026-10-07T10:00:00Z" }],
        ["agents", "active", 2060, { modified: "2026-10-07T10:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-10-07T10:00:00Z", note: "Initial draft." }],
    },
    {
      name: "data-pipeline",
      description: "Make every step idempotent and every failure visible.",
      category: "Data",
      version: "1.1.0",
      copies: [
        ["global", "active", 2380, { modified: "2026-10-10T09:30:00Z" }],
        ["codex", "active", 2380, { modified: "2026-10-10T09:30:00Z" }],
        ["opencode", "active", 2380, { modified: "2026-10-10T09:30:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-10-10T09:35:00Z", note: "0 errors." }],
    },
    {
      name: "seo-audit",
      description: "Audit what a crawler can actually read.",
      category: "Marketing",
      version: "1.0.5",
      copies: [
        ["global", "active", 1520, { modified: "2026-10-04T10:15:00Z" }],
        ["agents", "active", 1520, { modified: "2026-10-04T10:15:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-10-04T10:15:00Z", note: "Initial draft." }],
    },
    {
      name: "commit-messages",
      description: "A commit message names the change and the reason. The diff names the mechanism.",
      category: "Engineering",
      version: "1.0.4",
      copies: [
        ["global", "active", 620, { modified: "2026-09-26T10:00:00Z" }],
        ["agents", "active", 620, { modified: "2026-09-26T10:00:00Z" }],
        ["claude-code", "active", 620, { modified: "2026-09-26T10:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-09-26T10:05:00Z", note: "0 errors." }],
    },
    {
      name: "api-design",
      description: "An API is a contract with a stranger who cannot see your code.",
      category: "Engineering",
      version: "2.1.0",
      copies: [
        ["global", "active", 1980, { modified: "2026-10-08T13:00:00Z" }],
        ["claude-code", "active", 1980, { modified: "2026-10-08T13:00:00Z" }],
        ["codex", "active", 1980, { modified: "2026-10-08T13:00:00Z" }],
        ["cursor", "active", 1980, { modified: "2026-10-08T13:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "synced to three roots", at: "2026-10-08T13:05:00Z", note: "0 skipped." }],
    },
    {
      name: "docker-patterns",
      description: "Keep the image small, the build reproducible, and the runtime boring.",
      category: "Operations",
      version: "1.4.0",
      copies: [
        ["global", "active", 1740, { modified: "2026-10-02T08:00:00Z" }],
        ["opencode", "active", 1740, { modified: "2026-10-02T08:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-10-02T08:05:00Z", note: "0 errors." }],
    },
    {
      name: "kubernetes-skill",
      description: "Declare the desired state, then make the rollout observable.",
      category: "Operations",
      version: "1.8.0",
      copies: [
        ["global", "active", 2620, { modified: "2026-10-06T14:20:00Z" }],
        ["opencode", "active", 2620, { modified: "2026-10-06T14:20:00Z" }],
        ["codex", "active", 2620, { modified: "2026-10-06T14:20:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-06T14:20:00Z", note: "Added the disruption budget." }],
    },
    {
      name: "dependency-upgrade",
      description: "Upgrade one thing at a time and keep the failure attributable.",
      category: "Engineering",
      version: "1.0.6",
      copies: [
        ["global", "active", 1360, { modified: "2026-09-29T11:00:00Z" }],
        ["claude-code", "active", 1360, { modified: "2026-09-29T11:00:00Z" }],
        ["agents", "active", 1360, { modified: "2026-09-29T11:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "validated", at: "2026-09-29T11:05:00Z", note: "0 errors." }],
    },
    {
      name: "changelog-automation",
      description: "A changelog is written for the person upgrading, not for the commit graph.",
      category: "Writing",
      version: "1.1.0",
      copies: [
        ["global", "active", 1080, { modified: "2026-10-03T09:40:00Z" }],
        ["agents", "active", 1080, { modified: "2026-10-03T09:40:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "created", at: "2026-10-03T09:40:00Z", note: "Initial draft." }],
    },
    {
      name: "browser-automation",
      description: "Automate the task, not the screenshot.",
      category: "Automation",
      version: "1.2.0",
      copies: [
        ["global", "active", 2140, { modified: "2026-10-13T16:00:00Z" }],
        ["claude-code", "active", 2140, { modified: "2026-10-13T16:00:00Z" }],
        ["cursor", "active", 2140, { modified: "2026-10-13T16:00:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "edited in global", at: "2026-10-13T16:00:00Z", note: "Added the evidence rule." }],
    },
    {
      name: "skill-builder",
      description: "A skill is a small document with a clear trigger and a checkable outcome.",
      category: "AI tooling",
      version: "2.0.0",
      copies: [
        ["global", "active", 3640, { modified: "2026-10-17T16:40:00Z" }],
        ["claude-code", "active", 3640, { modified: "2026-10-17T16:40:00Z" }],
        ["agents", "active", 3640, { modified: "2026-10-17T16:40:00Z" }],
      ],
      validation: { valid: true, issues: [] },
      history: [{ action: "synced to three roots", at: "2026-10-17T16:45:00Z", note: "0 skipped." }],
    },
  ];

  const A11Y_VARIANT = BODY_OVERRIDES["accessibility-compliance"].replace(
    "- Reflow: the page survives 320px and 200% zoom without clipping.",
    "- Reflow: the page survives 320px. Zoom is a browser concern, so this copy does not check it."
  );

  const DIVERGENT_VARIANTS = {
    "accessibility-compliance": A11Y_VARIANT,
    "security-audit": BODY_OVERRIDES["security-audit"].replace(
      "Repair: validate the Host header on every routed verb, reads included.",
      "Repair: validate the Host header on mutations. Reads can stay open for local tools."
    ),
    brainstorming: BODY_OVERRIDES.brainstorming.replace(
      "- The output is a decision, not a list.",
      "- The output is a short list. A separate note picks the direction."
    ),
    "prompt-engineer": BODY_OVERRIDES["prompt-engineer"].replace(
      "Run the prompt on three inputs, including one that should be refused. If the output is plausible but unchecked, the prompt is not done.",
      "Run the prompt once. If the output reads well, ship it."
    ),
    "rag-infrastructure": BODY_OVERRIDES["rag-infrastructure"].replace(
      "Measure recall before you tune the prompt.",
      "Tune the prompt first. Recall is a later concern."
    ),
  };

  function makeSkill(def) {
    const skill = {
      name: def.name,
      description: def.description,
      category: def.category || "Uncategorized",
      version: def.version || "1.0.0",
      license: def.license || "MIT",
      allowedTools: def.allowedTools || "Read, Grep, Bash",
      malformed: Boolean(def.malformed),
      addressable: def.addressable !== undefined ? def.addressable : NAME_RE.test(def.name),
      body: def.body || bodyFor(def.name, def.description, def.category),
      variantBody: def.variantBody || DIVERGENT_VARIANTS[def.name] || null,
      validation: def.validation || { valid: true, issues: [] },
      history: def.history || [],
      instances: [],
    };
    skill.instances = (def.copies || []).map(([scope, state, tokens, opts]) =>
      makeInstance(def.name, scope, state, tokens, opts)
    );
    skill.state = stateOf(skill);
    skill.tokens = skill.instances.length
      ? Math.max(...skill.instances.map((i) => i.tokens))
      : Number(def.tokens) || 0;
    skill.totalTokens = skill.instances.reduce((sum, i) => sum + i.tokens, 0);
    skill.copies = skill.instances.length;
    skill.updated = skill.instances
      .map((i) => i.modified)
      .sort()
      .pop() || "2026-10-01T00:00:00Z";
    skill.scopes = [...new Set(skill.instances.map((i) => i.scope))];
    return skill;
  }

  /* ------------------------------------------------------------------------
     Generated inventory: 602 additional logical skills
     ------------------------------------------------------------------------ */

  let seed = 20261025;
  function rnd() {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  }

  function pick(list) {
    return list[Math.floor(rnd() * list.length)];
  }

  function daysAgo(days) {
    return new Date(TODAY - days * 86400000).toISOString();
  }

  const DOMAINS = [
    ["api", "API"],
    ["auth", "authentication"],
    ["billing", "billing"],
    ["browser", "browser"],
    ["cache", "caching"],
    ["ci", "continuous integration"],
    ["cli", "command line"],
    ["cloud", "cloud infrastructure"],
    ["css", "CSS"],
    ["data", "data"],
    ["db", "database"],
    ["deploy", "deployment"],
    ["design", "design"],
    ["docs", "documentation"],
    ["email", "email"],
    ["error", "error handling"],
    ["events", "events"],
    ["feature", "feature delivery"],
    ["frontend", "frontend"],
    ["git", "Git"],
    ["graphql", "GraphQL"],
    ["http", "HTTP"],
    ["infra", "infrastructure"],
    ["jest", "Jest"],
    ["k8s", "Kubernetes"],
    ["llm", "LLM applications"],
    ["logging", "logging"],
    ["mcp", "MCP"],
    ["metrics", "metrics"],
    ["mobile", "mobile"],
    ["node", "Node.js"],
    ["oauth", "OAuth"],
    ["observability", "observability"],
    ["payments", "payments"],
    ["performance", "performance"],
    ["postgres", "PostgreSQL"],
    ["python", "Python"],
    ["rag", "retrieval"],
    ["react", "React"],
    ["redis", "Redis"],
    ["release", "release"],
    ["rust", "Rust"],
    ["search", "search"],
    ["security", "security"],
    ["seo", "SEO"],
    ["sql", "SQL"],
    ["state", "state management"],
    ["testing", "testing"],
    ["typescript", "TypeScript"],
    ["ui", "UI"],
    ["vite", "Vite"],
    ["webhook", "webhooks"],
    ["workflow", "workflow"],
  ];

  const ACTIONS = [
    "audit",
    "patterns",
    "review",
    "migration",
    "hardening",
    "triage",
    "design",
    "builder",
    "debugging",
    "optimization",
    "checklist",
    "playbook",
    "scaffold",
    "contract",
    "runbook",
    "strategy",
    "validation",
    "workflow",
    "instrumentation",
    "testing",
  ];

  const DESC_TEMPLATES = [
    (a, d) => `${titleize(a)} for ${d} work, with a small reviewable change and a check you can rerun.`,
    (a, d) => `A ${a} playbook for ${d} changes: read the current state, make the smallest edit, verify the result.`,
    (a, d) => `Guidance for ${a} in ${d}: evidence first, one outcome, and a rollback path.`,
    (a, d) => `Use when a ${d} task needs ${a} without widening the surface or guessing at intent.`,
    (a, d) => `A short ${a} checklist for ${d}, written for a local repository and a careful operator.`,
    (a, d) => `Review ${d} ${a} against the files in the repository, then report the evidence and the next safe action.`,
  ];

  function randomState() {
    const r = rnd();
    if (r < 0.932) return "active";
    if (r < 0.975) return "disabled";
    if (r < 0.990) return "divergent";
    if (r < 0.996) return "linked";
    if (r < 0.9995) return "malformed";
    return "active";
  }

  const SCOPE_POOL = [
    "claude-code", "claude-code", "claude-code", "global", "global", "agents",
    "codex", "opencode", "gemini", "cursor", "commandcode",
  ];

  const curatedNames = new Set(CURATED_DEFS.map((s) => s.name));
  const GENERATED = [];

  for (const [domain, domainLabel] of DOMAINS) {
    for (const action of ACTIONS) {
      if (GENERATED.length >= 602) break;
      const name = `${domain}-${action}`;
      if (curatedNames.has(name)) continue;
      if (!NAME_RE.test(name)) continue;
      const description = DESC_TEMPLATES[GENERATED.length % DESC_TEMPLATES.length](action, domainLabel);
      const tokens = 420 + Math.floor(rnd() * 7600);
      const copyCount = 2 + Math.floor(rnd() * 3);
      const scopes = [];
      while (scopes.length < copyCount) {
        const scope = pick(SCOPE_POOL);
        if (!scopes.includes(scope)) scopes.push(scope);
      }
      const copies = scopes.map((scope, index) => {
        const state = randomState();
        return [
          scope,
          state,
          state === "malformed" ? 0 : tokens,
          {
            modified: daysAgo(Math.floor(rnd() * 80)),
            note: state === "divergent" ? "This copy differs from the canonical document." : "",
            hash: state === "malformed" ? hash(`${name}:${scope}:broken`) : undefined,
          },
        ];
      });
      const issues = [];
      if (copies.some(([, state]) => state === "malformed")) {
        issues.push({ level: "error", key: "frontmatter", message: "At least one copy cannot be parsed." });
      }
      if (copies.some(([, state]) => state === "divergent")) {
        issues.push({ level: "warn", key: "content", message: "At least one copy differs from the canonical document." });
      }
      GENERATED.push(
        makeSkill({
          name,
          description,
          category: domainLabel,
          version: `${1 + Math.floor(rnd() * 3)}.${Math.floor(rnd() * 10)}.0`,
          tokens,
          copies,
          validation: { valid: issues.every((i) => i.level !== "error"), issues },
          history: [
            { action: "observed", at: daysAgo(Math.floor(rnd() * 30)), note: "Sample inventory record." },
            { action: "validated", at: daysAgo(Math.floor(rnd() * 60)), note: issues.length ? `${issues.length} finding(s).` : "0 errors." },
          ],
        })
      );
    }
    if (GENERATED.length >= 602) break;
  }

  const CURATED = CURATED_DEFS.map(makeSkill);
  const SKILLS = [...CURATED, ...GENERATED];

  /* ------------------------------------------------------------------------
     Quality evidence
     ------------------------------------------------------------------------ */

  const QUALITY = [
    {
      id: "q1",
      severity: "error",
      category: "Parse",
      title: ".system cannot be parsed or addressed",
      evidence: "The frontmatter contains an unclosed flow sequence at line 2. The directory name also fails the canonical name rule.",
      detail: "The document is listed because the filesystem is the source of truth. It cannot be opened by name, and no repair is attempted. The safe action is to move the directory out of the Codex root or fix the frontmatter and rename it.",
      skills: [".system"],
      scope: "codex",
      count: 1,
    },
    {
      id: "q2",
      severity: "error",
      category: "Divergence",
      title: "accessibility-compliance has two content variants",
      evidence: "The Gemini copy omits the 200% zoom check. 14 lines differ from the canonical copy.",
      detail: "A divergent copy is not an error in the parser. It is an attention signal: two agents may behave differently. Choose the copy that should be canonical, then sync it.",
      skills: ["accessibility-compliance"],
      scope: "gemini",
      count: 2,
    },
    {
      id: "q3",
      severity: "warn",
      category: "Presence",
      title: "8 documents cannot be read",
      evidence: "Four roots contain at least one unreadable or unparseable SKILL.md. The index counts them; it does not repair them.",
      detail: "Unreadable documents are surfaced rather than hidden. A tool that silently drops them reports a healthier library than the filesystem holds.",
      skills: [".system"],
      scope: "multiple",
      count: 8,
    },
    {
      id: "q4",
      severity: "warn",
      category: "Containment",
      title: "11 links point outside their scope root",
      evidence: "The symlink target is outside the managed root, so the loader refuses to follow it. The path is reported, not read.",
      detail: "This is deliberate. Following the link would let a write land outside the scope. The repair is to copy the tree in or remove the link.",
      skills: ["add-task", "mcp-builder"],
      scope: "multiple",
      count: 11,
    },
    {
      id: "q5",
      severity: "warn",
      category: "Context",
      title: "security-audit is 18,420 tokens",
      evidence: "One document, 1,842 lines. It is the largest single skill in the inventory.",
      detail: "Size is not a defect by itself. It becomes one when the document is loaded on every task. Split the reference material into a linked file if the whole body is rarely needed.",
      skills: ["security-audit"],
      scope: "global",
      count: 1,
    },
    {
      id: "q6",
      severity: "warn",
      category: "Context",
      title: "The OpenCode root is 70% of a 200k window",
      evidence: "139,000 tokens across 419 instances. At the Claude Haiku window, this root alone leaves 61,000 tokens for everything else.",
      detail: "Switch the budget view to the 200k window to see the exact headroom. The number is an estimate from characters divided by four, not a tokenizer.",
      skills: [],
      scope: "opencode",
      count: 419,
    },
    {
      id: "q7",
      severity: "warn",
      category: "Guidance",
      title: "42 descriptions do not name a use moment",
      evidence: "The first sentence describes the topic but not when to load it. A reader cannot tell the skill from its neighbour.",
      detail: "A useful description names the trigger. 'Review a diff for correctness' is stronger than 'Code review guidance' because it gives the reader a decision.",
      skills: ["brainstorming", "observability"],
      scope: "multiple",
      count: 42,
    },
    {
      id: "q8",
      severity: "info",
      category: "Divergence",
      title: "30 divergent instances across 17 logical skills",
      evidence: "The copies share a name but not a content hash. 17 logical skills have at least one divergent copy.",
      detail: "Divergence is not always wrong. It is a fact that needs a decision. The compare view shows the line-level difference without choosing a winner.",
      skills: ["security-audit", "prompt-engineer", "rag-infrastructure"],
      scope: "multiple",
      count: 30,
    },
    {
      id: "q9",
      severity: "info",
      category: "State",
      title: "85 disabled instances, 12 with no active copy",
      evidence: "A disabled copy is renamed in place. The index keeps it visible so a reader does not mistake it for a missing skill.",
      detail: "The 12 with no active copy are candidates for archive or removal. The tool does not infer that intent.",
      skills: ["test-master", "writing-plans"],
      scope: "multiple",
      count: 85,
    },
    {
      id: "q10",
      severity: "info",
      category: "Duplicates",
      title: "5 exact duplicate groups",
      evidence: "The documents share a content hash inside one root. They are reported as copies, not as separate skills.",
      detail: "An exact duplicate costs context twice. Collapse it only after checking which path each consumer reads.",
      skills: ["pdf", "ui-craft"],
      scope: "multiple",
      count: 5,
    },
    {
      id: "q11",
      severity: "info",
      category: "Provenance",
      title: "2 registry sidecars are stale",
      evidence: "The sidecar records a registry hash that no longer matches the document. The document is still readable.",
      detail: "Provenance is evidence, not authority. A stale sidecar is shown as drift rather than trusted quietly.",
      skills: ["pdf", "postgresql-table-design"],
      scope: "global",
      count: 2,
    },
    {
      id: "q12",
      severity: "info",
      category: "Recovery",
      title: "6 snapshots are retained",
      evidence: "The newest is from 24 October. Each snapshot is a complete tree, not a diff.",
      detail: "A snapshot is applied through a review, not directly. The rollback path is a new review that must be approved.",
      skills: ["security-audit", "accessibility-compliance"],
      scope: "multiple",
      count: 6,
    },
    {
      id: "q13",
      severity: "info",
      category: "Index",
      title: "Last index rebuild was 3 days ago",
      evidence: "The index is a rebuildable cache. The filesystem is the source of truth.",
      detail: "If the index and the filesystem disagree, the filesystem wins. Rebuild the index only after a filesystem change.",
      skills: [],
      scope: "global",
      count: 1,
    },
    {
      id: "q14",
      severity: "info",
      category: "Scope",
      title: "2 agent roots share 34 skills with the global store",
      evidence: "The same content hash appears in the global store and an agent root. That is a copy, not a second skill.",
      detail: "The library groups copies by name. The Instances view keeps each physical copy addressable.",
      skills: ["pdf", "code-review"],
      scope: "multiple",
      count: 34,
    },
  ];

  /* ------------------------------------------------------------------------
     Registry, profiles, recovery
     ------------------------------------------------------------------------ */

  const REGISTRY = [
    {
      id: "r1",
      source: "vercel-labs/agent-skills",
      name: "browser-operator",
      description: "Browser automation CLI for AI agents. Snapshot, click, fill, and read a page without a screenshot round trip.",
      installs: "12.4k",
      files: 8,
      updated: "2026-10-21",
      validation: { errors: 0, warnings: 2 },
      risk: "low",
      riskFindings: ["No shell scripts in the snapshot.", "One documented outbound request to the registry."],
      hash: "sha256:9d2f41c8a7e0b3d6f5128a9c4e7b0d31",
      category: "Automation",
    },
    {
      id: "r2",
      source: "anthropics/skills",
      name: "pdf-reader",
      description: "Read and produce PDFs locally, with a text-layer check before extraction.",
      installs: "9.8k",
      files: 6,
      updated: "2026-10-18",
      validation: { errors: 0, warnings: 0 },
      risk: "low",
      riskFindings: ["No scripts. Text-only snapshot."],
      hash: "sha256:4a1c8e2f6b9d0375c2a8e1f4b6d9c037",
      category: "Documents",
    },
    {
      id: "r3",
      source: "obra/superpowers",
      name: "idea-diverge",
      description: "Three genuinely different directions before one is chosen, with the trade-off written down.",
      installs: "7.2k",
      files: 5,
      updated: "2026-10-16",
      validation: { errors: 0, warnings: 1 },
      risk: "medium",
      riskFindings: ["Contains a Python helper. Read it before running.", "One shell example uses a pipe."],
      hash: "sha256:7c3e9b1a5d8f2046c7a3e9b1d5f82046",
      category: "Thinking",
    },
    {
      id: "r4",
      source: "microsoft/playwright",
      name: "trace-browser-tests",
      description: "Resilient browser tests with role-first selectors and trace-driven failure debugging.",
      installs: "22k",
      files: 9,
      updated: "2026-10-22",
      validation: { errors: 0, warnings: 1 },
      risk: "low",
      riskFindings: ["No shell scripts. One lockfile for the test runner."],
      hash: "sha256:1f5b8d3c7a0e2946b1f5d8c3a7e02946",
      category: "Testing",
    },
    {
      id: "r5",
      source: "community/prompt-lab",
      name: "prompt-contract",
      description: "A prompt structure with three test inputs and an explicit refusal case.",
      installs: "4.1k",
      files: 4,
      updated: "2026-10-11",
      validation: { errors: 0, warnings: 3 },
      risk: "medium",
      riskFindings: ["Contains a shell example with an unquoted variable.", "The example reads an environment variable."],
      hash: "sha256:6b2d9a4f1c7e3058b6d2a9f4c1e73058",
      category: "AI tooling",
    },
    {
      id: "r6",
      source: "community/data-desk",
      name: "schema-by-query",
      description: "Schema design driven by the query, with constraints and migration notes.",
      installs: "3.6k",
      files: 5,
      updated: "2026-10-13",
      validation: { errors: 0, warnings: 2 },
      risk: "low",
      riskFindings: ["SQL examples only. No executable scripts."],
      hash: "sha256:2e8a5c1f9b4d73062e8a5c1f9b4d7306",
      category: "Data",
    },
    {
      id: "r7",
      source: "community/payments",
      name: "stripe-webhooks",
      description: "Verify a webhook signature, deduplicate by event id, and keep the handler idempotent.",
      installs: "2.9k",
      files: 11,
      updated: "2026-10-20",
      validation: { errors: 1, warnings: 4 },
      risk: "high",
      riskFindings: ["Contains a shell script that writes to a config directory.", "A test fixture includes a placeholder secret.", "The handler example retries without a cap."],
      hash: "sha256:8d4b1f7a3c9e20568d4b1f7a3c9e2056",
      category: "Payments",
    },
    {
      id: "r8",
      source: "community/ci-notes",
      name: "github-actions-hardening",
      description: "Pin actions by SHA, scope tokens to the job, and keep release provenance explicit.",
      installs: "1.8k",
      files: 6,
      updated: "2026-10-09",
      validation: { errors: 0, warnings: 2 },
      risk: "medium",
      riskFindings: ["The workflow example uses a repository secret.", "The example writes a file to the runner root."],
      hash: "sha256:5f9c2a7e4b1d80635f9c2a7e4b1d8063",
      category: "Operations",
    },
  ];

  const PROFILES = [
    {
      id: "frontend",
      name: "Frontend stack",
      description: "The design, browser, and test skills used for interface work on a local app.",
      targets: ["claude-code", "cursor"],
      members: [
        { name: "ui-craft", state: "observed" },
        { name: "frontend-design", state: "observed" },
        { name: "design-tokens", state: "observed" },
        { name: "accessibility-compliance", state: "divergent" },
        { name: "playwright-expert", state: "observed" },
        { name: "react-best-practices", state: "observed" },
        { name: "browser-automation", state: "disabled" },
        { name: "web-design-review", state: "missing" },
      ],
    },
    {
      id: "security",
      name: "Security review",
      description: "The threat-model and audit pair used before a release.",
      targets: ["codex", "claude-code"],
      members: [
        { name: "security-audit", state: "divergent" },
        { name: "threat-modeling", state: "observed" },
        { name: "error-handling", state: "observed" },
        { name: "dependency-upgrade", state: "observed" },
        { name: "secret-scanning", state: "missing" },
      ],
    },
    {
      id: "writing",
      name: "Writing desk",
      description: "Planning, documentation, and changelog skills for a release week.",
      targets: ["agents", "claude-code", "opencode"],
      members: [
        { name: "writing-plans", state: "observed" },
        { name: "docs-writer", state: "observed" },
        { name: "changelog-automation", state: "observed" },
        { name: "commit-messages", state: "disabled" },
      ],
    },
  ];

  const SNAPSHOTS = [
    {
      id: "s1",
      at: "2026-10-24T18:42:00Z",
      action: "source update",
      name: "accessibility-compliance",
      scope: "claude-code",
      files: 14,
      hash: "sha256:2c8e5a1b9f4d73062c8e5a1b9f4d7306",
      state: "complete",
    },
    {
      id: "s2",
      at: "2026-10-23T09:18:00Z",
      action: "sync review",
      name: "agent-browser",
      scope: "agents",
      files: 6,
      hash: "sha256:9a4d2f7c1b8e30569a4d2f7c1b8e3056",
      state: "complete",
    },
    {
      id: "s3",
      at: "2026-10-21T14:03:00Z",
      action: "manual snapshot",
      name: "security-audit",
      scope: "global",
      files: 22,
      hash: "sha256:7e1b4c8a2d9f30567e1b4c8a2d9f3056",
      state: "complete",
    },
    {
      id: "s4",
      at: "2026-10-19T11:02:00Z",
      action: "source update",
      name: "ui-craft",
      scope: "global",
      files: 9,
      hash: "sha256:3d7a9f2c5b1e80463d7a9f2c5b1e8046",
      state: "complete",
    },
    {
      id: "s5",
      at: "2026-10-16T15:35:00Z",
      action: "sync review",
      name: "docs-writer",
      scope: "gemini",
      files: 5,
      hash: "sha256:6a2e8c4b1f7d30596a2e8c4b1f7d3059",
      state: "complete",
    },
    {
      id: "s6",
      at: "2026-10-12T16:20:00Z",
      action: "registry review",
      name: "pdf",
      scope: "global",
      files: 8,
      hash: "sha256:4a1c8e2f6b9d03754a1c8e2f6b9d0375",
      state: "complete",
    },
  ];

  const TRASH = [
    {
      id: "t1",
      name: "old-prompt-notes",
      date: "2026-10-24T16:20:00Z",
      size: "12 KB",
      path: "~/.local/share/skills-manager/trash/old-prompt-notes-2026-10-24_16-20-00Z",
    },
    {
      id: "t2",
      name: "legacy-seo",
      date: "2026-10-23T09:05:00Z",
      size: "4 KB",
      path: "~/.local/share/skills-manager/trash/legacy-seo-2026-10-23_09-05-00Z",
    },
    {
      id: "t3",
      name: "tmp-test-skill",
      date: "2026-10-21T18:44:00Z",
      size: "2 KB",
      path: "~/.local/share/skills-manager/trash/tmp-test-skill-2026-10-21_18-44-00Z",
    },
    {
      id: "t4",
      name: "duplicate-agent-browser",
      date: "2026-10-19T11:12:00Z",
      size: "16 KB",
      path: "~/.local/share/skills-manager/trash/duplicate-agent-browser-2026-10-19_11-12-00Z",
    },
    {
      id: "t5",
      name: "draft-incident-runbook",
      date: "2026-10-15T08:30:00Z",
      size: "6 KB",
      path: "~/.local/share/skills-manager/trash/draft-incident-runbook-2026-10-15_08-30-00Z",
    },
  ];

  const RECENT = [
    { name: "agent-browser", action: "Synced to agents", at: "2026-10-25T10:12:00Z" },
    { name: "accessibility-compliance", action: "Edited in Claude Code", at: "2026-10-24T18:42:00Z" },
    { name: "security-audit", action: "Snapshot created", at: "2026-10-24T15:06:00Z" },
    { name: "verify-before-completion", action: "Edited in global", at: "2026-10-24T09:12:00Z" },
    { name: "pdf", action: "Added from registry", at: "2026-10-22T14:03:00Z" },
  ];

  return {
    NAME_RE,
    SCOPES,
    WINDOWS,
    TOTAL_TOKENS,
    TOTAL_INSTANCES,
    TOTAL_LOGICAL,
    STATE_META,
    SEVERITY_META,
    SKILLS,
    CURATED,
    QUALITY,
    REGISTRY,
    PROFILES,
    SNAPSHOTS,
    TRASH,
    RECENT,
    stateOf,
    scopeById,
    makeInstance,
    bodyFor,
    hash,
    titleize,
  };
})();
