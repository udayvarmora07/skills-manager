/* Demo data for the "Clear" prototype. Every name, path, count and date here
   is illustrative. Nothing is read from or written to disk. */
window.CLEAR_DATA = (function () {
  const agents = [
    { id: "library", name: "Your library", short: "LB", hue: 222, path: "~/.local/share/skills-manager/skills", window: 1000000, note: "The copy Skills Manager keeps for you" },
    { id: "claude-code", name: "Claude Code", short: "CC", hue: 24, path: "~/.claude/skills", window: 200000 },
    { id: "codex", name: "Codex", short: "CX", hue: 160, path: "~/.codex/skills", window: 400000 },
    { id: "cursor", name: "Cursor", short: "CU", hue: 280, path: "~/.cursor/skills", window: 200000 },
    { id: "gemini", name: "Gemini", short: "GE", hue: 200, path: "~/.gemini/skills", window: 1000000 },
    { id: "opencode", name: "OpenCode", short: "OC", hue: 340, path: "~/.config/opencode/skills", window: 200000 },
  ];

  // state per copy: "on" | "off" | "broken"
  // same `v` means identical content; different `v` means the copies differ.
  const S = (name, description, category, tokens, copies, extra) =>
    Object.assign({ name, description, category, tokens, copies }, extra || {});

  const skills = [
    S("code-review", "Reviews a diff for bugs, risky changes and missing tests before you merge.", "Engineering", 2140,
      [["library", "on", 2], ["claude-code", "on", 2], ["codex", "on", 1], ["cursor", "on", 2]],
      { updated: "2 hours ago" }),
    S("write-commit-message", "Turns your staged changes into a short, clear commit message.", "Git", 620,
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1], ["gemini", "on", 1]],
      { updated: "Yesterday" }),
    S("api-design", "Helps you design consistent REST endpoints, errors and pagination.", "Engineering", 3880,
      [["library", "on", 1], ["claude-code", "on", 1]], { updated: "3 days ago" }),
    S("release-notes", "Drafts release notes from merged pull requests, grouped by type.", "Writing", 1310,
      [["library", "on", 1], ["claude-code", "on", 1], ["cursor", "off", 1]], { updated: "Last week" }),
    S("sql-helper", "Explains slow queries and suggests indexes for Postgres and SQLite.", "Data", 2950,
      [["claude-code", "on", 1], ["codex", "broken", 1]],
      { updated: "4 days ago", problem: "The Codex copy has a broken header, so Codex skips it." }),
    S("frontend-a11y", "Checks components for keyboard, contrast and screen-reader problems.", "Design", 4420,
      [["library", "on", 1], ["claude-code", "on", 1], ["cursor", "on", 1], ["opencode", "on", 1]], { updated: "Last week" }),
    S("test-writer", "Writes focused unit tests for the function you point it at.", "Engineering", 1870,
      [["library", "on", 3], ["claude-code", "on", 3], ["codex", "on", 2], ["gemini", "on", 3], ["opencode", "on", 3]],
      { updated: "Today" }),
    S("docker-basics", "Builds small, safe Dockerfiles and compose setups.", "Ops", 2210,
      [["library", "off", 1], ["codex", "off", 1]], { updated: "2 weeks ago" }),
    S("explain-error", "Reads a stack trace and explains the most likely cause in plain words.", "Engineering", 880,
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1], ["cursor", "on", 1], ["gemini", "on", 1], ["opencode", "on", 1]],
      { updated: "3 days ago" }),
    S("pr-description", "Writes a pull-request description: what changed, why, and how to test it.", "Git", 940,
      [["library", "on", 1], ["claude-code", "on", 1]], { updated: "Yesterday" }),
    S("security-check", "Looks for leaked secrets, injection risks and unsafe defaults.", "Security", 5120,
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1]], { updated: "5 days ago" }),
    S("migration-planner", "Plans database migrations that can be rolled back safely.", "Data", 3370,
      [["claude-code", "on", 1]], { updated: "2 weeks ago" }),
    S("brand-voice", "Keeps product copy friendly, short and consistent.", "Writing", 1160,
      [["library", "on", 1], ["gemini", "on", 1]], { updated: "Last month" }),
    S("k8s-debug", "Walks through why a Kubernetes pod is crashing or pending.", "Ops", 6890,
      [["claude-code", "on", 1], ["opencode", "on", 2]], { updated: "Last week" }),
    S("Design Notes", "Personal notes saved in a folder with an unusual name.", "Design", 420,
      [["cursor", "broken", 1]],
      { updated: "Last month", problem: "The folder name has spaces and capital letters, so agents can't load it by name." }),
    S("refactor-safely", "Refactors code in small steps and keeps tests green between them.", "Engineering", 2480,
      [["library", "on", 1], ["claude-code", "on", 1], ["codex", "on", 1], ["cursor", "on", 1]], { updated: "Today" }),
    S("changelog-keeper", "Updates CHANGELOG.md in the Keep a Changelog style.", "Writing", 760,
      [["library", "off", 1]], { updated: "2 months ago" }),
    S("perf-profiler", "Finds the slow part of a page or script and suggests a fix.", "Engineering", 3010,
      [["library", "on", 1], ["claude-code", "on", 1], ["gemini", "on", 1]], { updated: "4 days ago" }),
    S("onboarding-guide", "Explains this codebase to a new teammate, folder by folder.", "Writing", 7450,
      [["claude-code", "on", 1]], { updated: "Last week" }),
    S("regex-builder", "Builds and explains regular expressions with examples.", "Engineering", 540,
      [["library", "on", 1], ["codex", "on", 1], ["cursor", "on", 1], ["gemini", "on", 1]], { updated: "3 weeks ago" }),
  ];

  const trash = 4;

  const activity = [
    { when: "Today, 10:42", what: "test-writer was updated in 4 agents", kind: "sync" },
    { when: "Today, 09:15", what: "refactor-safely was added to Cursor", kind: "add" },
    { when: "Yesterday", what: "docker-basics was turned off", kind: "off" },
    { when: "Yesterday", what: "old-linter-rules was moved to the trash", kind: "trash" },
    { when: "3 days ago", what: "Backup saved (20 skills)", kind: "backup" },
  ];

  const bodies = {
    "code-review": `# Code review

Use this skill when someone asks you to **review a change**, a pull request, or a diff before it is merged.

## What to look at

1. Does the change do what the description says?
2. Could it break something that worked before?
3. Are there tests for the new behaviour?
4. Is anything risky: secrets, deletes, migrations?

## How to answer

- Start with the most serious problem.
- Point to the exact file and line.
- Suggest a fix, not just the problem.
- Keep praise short and specific.

> If the diff is very large, ask which part matters most before reviewing everything.
`,
  };

  const defaultBody = (s) => `# ${s.name.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase())}

${s.description}

## When to use it

Use this skill when the request matches the description above. If it does not, ignore this skill.

## Steps

1. Read the request and the files it mentions.
2. Do the smallest useful thing first.
3. Explain what you changed and why, in plain words.

## Notes

- Keep answers short.
- Ask one clear question if something is missing.
`;

  return { agents, skills, trash, activity, bodies, defaultBody };
})();
