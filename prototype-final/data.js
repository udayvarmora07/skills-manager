/* Demo data for the final prototype. Every name, path, count and date is
   illustrative. Nothing is read from or written to disk. */
window.SM_DATA = (function () {
  // `limit` = how many tokens the agent can read at once (demo values).
  const agents = [
    { id: "claude-code", name: "Claude Code", initials: "CC", color: "#d97757", path: "~/.claude/skills", limit: 200000 },
    { id: "codex", name: "Codex", initials: "CX", color: "#2f6f5e", path: "~/.codex/skills", limit: 400000 },
    { id: "cursor", name: "Cursor", initials: "CU", color: "#1b1d22", path: "~/.cursor/skills", limit: 200000 },
    { id: "gemini", name: "Gemini", initials: "GE", color: "#3d7be0", path: "~/.gemini/skills", limit: 1000000 },
    { id: "opencode", name: "OpenCode", initials: "OC", color: "#b04a7a", path: "~/.config/opencode/skills", limit: 200000 },
  ];
  const library = { id: "library", name: "Your library", initials: "LB", color: "#55585f", path: "~/.local/share/skills-manager/skills" };

  // Category order and look for the shelf.
  const categories = [
    { id: "Engineering", tint: "#e5eefc", ink: "#2c5ae9" },
    { id: "Design", tint: "#efe8fb", ink: "#6d3fd6" },
    { id: "Data & Ops", tint: "#e1f1f6", ink: "#0e7490" },
    { id: "Writing", tint: "#fdebe1", ink: "#c2552d" },
    { id: "Git", tint: "#e3f3e8", ink: "#1c7a47" },
    { id: "Security", tint: "#fff1d6", ink: "#a2510a" },
  ];

  // [name, description, category, icon, tokens, updated, copies[[agent, state, version]], extra]
  // state: on | off | broken. A lower version than the newest means "older copy".
  const raw = [
    ["code-review", "Reviews a change for bugs, risky edits and missing tests before you merge it.", "Engineering", "lens", 2140, "2 hours ago",
      [["library", "on", 2], ["claude-code", "on", 2], ["codex", "on", 1], ["cursor", "on", 2]]],
    ["test-writer", "Writes focused unit tests for the function you point it at.", "Engineering", "flask", 1870, "Today",
      [["library", "on", 3], ["claude-code", "on", 3], ["codex", "on", 2], ["gemini", "on", 3], ["opencode", "on", 3]]],
    ["explain-error", "Reads an error message and explains the most likely cause in plain words.", "Engineering", "bulb", 880, "3 days ago",
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1], ["cursor", "on", 1], ["gemini", "on", 1], ["opencode", "on", 1]]],
    ["refactor-safely", "Improves code in small steps and keeps tests passing in between.", "Engineering", "steps", 2480, "Today",
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1], ["cursor", "on", 1]]],
    ["perf-profiler", "Finds the slow part of a page or script and suggests a fix.", "Engineering", "gauge", 3010, "4 days ago",
      [["library", "on", 1], ["claude-code", "on", 1], ["gemini", "on", 1]]],
    ["api-design", "Helps you design consistent web APIs: names, errors and paging.", "Engineering", "plug", 3880, "3 days ago",
      [["library", "on", 1], ["claude-code", "on", 1]]],
    ["regex-builder", "Builds and explains search patterns with examples.", "Engineering", "brackets", 540, "3 weeks ago",
      [["library", "on", 1], ["codex", "on", 1], ["cursor", "on", 1], ["gemini", "on", 1]]],
    ["frontend-a11y", "Checks screens for keyboard, contrast and screen-reader problems.", "Design", "eye", 4420, "Last week",
      [["library", "on", 1], ["claude-code", "on", 1], ["cursor", "on", 1], ["opencode", "on", 1]]],
    ["Design Notes", "Personal notes saved in a folder with an unusual name.", "Design", "pen", 420, "Last month",
      [["cursor", "broken", 1]],
      { problem: "The folder name has spaces and capital letters. Agents look skills up by a simple lowercase name, so none of them can find this one.", fix: "Rename to design-notes", fixKind: "rename" }],
    ["sql-helper", "Explains slow database queries and suggests fixes.", "Data & Ops", "db", 2950, "4 days ago",
      [["claude-code", "on", 1], ["codex", "broken", 1]],
      { problem: "The top of Codex's copy is damaged, so Codex skips this skill.", fix: "Replace with the working copy", fixKind: "replace" }],
    ["k8s-debug", "Walks through why a Kubernetes app is crashing or stuck.", "Data & Ops", "cube", 6890, "Last week",
      [["claude-code", "on", 1], ["opencode", "on", 2]]],
    ["migration-planner", "Plans database changes that can be safely undone.", "Data & Ops", "list", 3370, "2 weeks ago",
      [["claude-code", "on", 1]]],
    ["docker-basics", "Builds small, safe Docker setups.", "Data & Ops", "box", 2210, "2 weeks ago",
      [["library", "off", 1], ["codex", "off", 1]]],
    ["release-notes", "Drafts release notes from merged pull requests, grouped by type.", "Writing", "doc", 1310, "Last week",
      [["library", "on", 1], ["claude-code", "on", 1], ["cursor", "off", 1]]],
    ["brand-voice", "Keeps product wording friendly, short and consistent.", "Writing", "quote", 1160, "Last month",
      [["library", "on", 1], ["gemini", "on", 1]]],
    ["onboarding-guide", "Explains a codebase to a new teammate, folder by folder.", "Writing", "map", 7450, "Last week",
      [["claude-code", "on", 1]]],
    ["changelog-keeper", "Updates CHANGELOG.md in the Keep a Changelog style.", "Writing", "clock", 760, "2 months ago",
      [["library", "off", 1]]],
    ["write-commit-message", "Turns your staged changes into a short, clear commit message.", "Git", "commit", 620, "Yesterday",
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1], ["gemini", "on", 1]]],
    ["pr-description", "Writes a pull-request description: what changed, why, and how to test it.", "Git", "merge", 940, "Yesterday",
      [["library", "on", 1], ["claude-code", "on", 1]]],
    ["security-check", "Looks for leaked passwords, unsafe inputs and risky defaults.", "Security", "shield", 5120, "5 days ago",
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1]]],
  ];

  const skills = raw.map(([name, description, category, icon, tokens, updated, copies, extra]) => ({
    name, description, category, icon, tokens, updated,
    copies: copies.map(([agent, state, v]) => ({ agent, state, v })),
    ...(extra || {}),
  }));

  // Text of specific versions. Older versions differ so Compare/Inbox have
  // something real to show. Other skills use a generic body.
  const texts = {
    "code-review": {
      2: `Use this skill when someone asks you to review a change, a pull request, or a diff before it is merged.

## What to look at

1. Does the change do what the description says?
2. Could it break something that worked before?
3. Are there tests for the new behaviour?
4. Is anything risky: passwords, deletes, database changes?

## How to answer

- Start with the most serious problem.
- Point to the exact file and line.
- Suggest a fix, not just the problem.
- Keep praise short and specific.

> If the change is very large, ask which part matters most first.`,
      1: `Use this skill when someone asks you to review a change, a pull request, or a diff before it is merged.

## What to look at

1. Does the change do what the description says?
2. Could it break something that worked before?
3. Is anything risky?

## How to answer

- List every problem you find.
- Point to the exact file and line.
- Keep praise short and specific.`,
    },
    "test-writer": {
      3: `Write focused unit tests for the function the user points at.

## Steps

1. Read the function and the files it uses.
2. List the normal case, the edge cases and one failure case.
3. Write one test per case, with a name that says what it checks.
4. Run the tests and report what passed.

## Rules

- Never change the function to make a test pass.
- Use the test tools the project already uses.`,
      2: `Write focused unit tests for the function the user points at.

## Steps

1. Read the function.
2. Write tests for the normal case and the edge cases.
3. Run the tests.

## Rules

- Use the test tools the project already uses.`,
    },
    "k8s-debug": {
      2: `Help the user find out why a Kubernetes app is crashing or stuck.

## Steps

1. Ask which app and which environment.
2. Check recent events and the last 50 log lines.
3. Look for the common causes: memory, image, settings, secrets, health checks.
4. Explain the cause in one sentence, then the fix.

## Safety

- Never delete or restart anything without asking first.`,
      1: `Help the user find out why a Kubernetes app is crashing or stuck.

## Steps

1. Check recent events and logs.
2. Look for common causes.
3. Explain the fix.`,
    },
  };

  const genericText = () => `## When to use it

Use this skill when the request matches the description above. If it doesn't, ignore this skill.

## Steps

1. Read the request and the files it mentions.
2. Do the smallest useful thing first.
3. Explain what you changed and why, in plain words.

## Notes

- Keep answers short.
- Ask one clear question if something is missing.`;

  const activity = [
    { when: "Today, 10:42", text: "test-writer was updated in 4 agents" },
    { when: "Today, 09:15", text: "refactor-safely was added to Cursor" },
    { when: "Yesterday", text: "docker-basics was turned off everywhere" },
    { when: "3 days ago", text: "A backup of 20 skills was saved" },
  ];

  return { agents, library, categories, skills, texts, genericText, activity, suggestedSpace: 20 };
})();
