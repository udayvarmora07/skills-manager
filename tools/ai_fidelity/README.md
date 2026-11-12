# Trigger simulation fidelity harness

This development-only script compares an existing saved-prompt trigger-test result
with Claude Code `Skill` tool events. It reuses a saved simulator result; explicit
agent execution may call the maintainer's configured provider and spend its account.
Those calls do not use the Skills Manager AI usage ledger or caps. The prompt set and run must both be for `claude-code`, match exactly by prompt
text and expected skill, and contain a complete, untied simulation. All joins are
validated before the first N prompts are selected in saved order; this convenience
sample is not random. Default execution is a dry run and starts
no child process:

```sh
python3 tools/ai_fidelity/run.py --prompt-set /path/to/prompt-set.json \
  --simulation /path/to/trigger-test-run.json
```

Only a maintainer who is present should explicitly start the agent. The following
is an example, not an instruction to run it automatically:

```sh
python3 tools/ai_fidelity/run.py --prompt-set /path/to/prompt-set.json \
  --simulation /path/to/trigger-test-run.json --cwd /path/to/working-directory \
  --limit 5 --timeout 30 --max-budget-usd 0.10 --run-agent --maintainer-present
```

Each invocation has at most two turns and an approximate per-call spend limit.
The agent's client-side budget estimate can overshoot and can differ from the
bill. The script sends the original prompt through stdin and uses stream JSON;
it restricts built-in tools to `Skill`, requires an empty strict MCP configuration,
denies MCP tools, and does not persist sessions. It does not use bare mode, which
would disable skill discovery. Its timeout and output limits use POSIX process
groups; execution is unavailable on other platforms.

**This is not a sandbox.** Native configuration, hooks, project settings and
dynamic skill behavior may have side effects, including running code. Use only a
working directory, settings and skills the maintainer has inspected and trusts.
See the [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
for flag and version behavior. The observed agent's configuration and restricted
tool context may differ from a normal interactive session.

A conclusive case requires a successful terminal event and a matching successful
`tool_result` for every observed `Skill` invocation. A successful run with no
Skill call counts as none. Failed, missing, malformed, timed-out or oversized
streams are inconclusive and excluded from agreement; multiple calls are shown in
order. Agreement compares the first successful Skill call, not the full set of loaded skills.
The report counts multiple-call cases separately. Model prose is never evidence.
Legacy saved simulations do not contain a listing snapshot. A14 snapshots are
fingerprint-checked and reported when present; the native agent's listing and
configuration are still not captured for equality checks. These comparisons alone do
not establish fidelity under normal use.

The JSON report contains hashes rather than prompt text, and does not retain raw
transcripts or stderr. Hashes of predictable prompts are not anonymous. Reports
still contain skill names and model labels; treat them as potentially sensitive.
