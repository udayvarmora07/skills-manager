# Design-Partner Pilot Kit — Skills Manager

**Version 1.0.0**

**AI manifest**: The recruitment-ready artifacts the design-partner pilot
requires *before* any session runs — the session protocol, a written consent
form, and a de-identified note template. It is **not** participant evidence and
contains **no** participant data. The pilot itself needs humans: five to eight
consented operators (see @docs/17-adoption-and-distribution.md §Design-partner
brief). Nothing here was produced by an agent acting as a participant, and no
figure in this repository may be derived from it. Created 2026-10-06.

## What this document is, and what it is not

**[SPEC]** This is the *preparation*. The exit conditions in
@docs/17-adoption-and-distribution.md require "the protocol, consent form,
de-identified notes, and dated screenshots" to be **reviewed** before the pilot
publishes anything. Three of those four exist or are created here; the fourth
(dated screenshots) is produced by `browser_harness.py --screenshots-dir`.

**[NOTE]** The sessions themselves are not automatable and were not run. A
usability session needs a person who maintains skills, a moderator who can
watch without leading, and written consent from both the participant and the
person who owns the skills in the fixture. An agent can prepare the room; it
cannot sit in it. Any claim of a completion rate, a task-success rate, or a
conversion number derived from this document would be fabricated.

## Cohort

**[SPEC]** Five to eight consented operators who maintain skills across **at
least two agent consumers**, including at least one novice to skills-manager and
at least one expert who already maintains several roots. Both matter: a cohort
of experts measures a tool that already fits them, and a cohort of novices
measures a first-run experience that is otherwise never observed.

Screen for the diversity dimension first — multi-root maintainers, recursive
project layouts, and people who have hit a divergent copy — before screening
for familiarity.

## Fixture

**[SPEC]** Disposable, synthetic or participant-owned skills only.

- A scratch `SKILLS_MANAGER_DATA` directory the participant can inspect and
  delete afterwards. **The participant is told where it is and told to delete
  it**, rather than discovering a temporary directory later.
- Seeded to exercise the pilot workflow: an active skill, a disabled skill, a
  **deliberately divergent copy** across two scopes, and one malformed
  document. The divergent copy is the load-bearing fixture — divergence is the
  thing this tool claims to help with, so it must be observed, not described.
- One skill owned by the participant, if they agree, because "can I trust this
  with my real work" is itself a finding.

**[?]** Fixture size is a real open question this pilot should answer rather
than assume: three skills and three hundred skills are different products. If
time allows, run at least one session at each size and record the difference.

## Pilot workflow

**[SPEC]** Each task is given verbatim, with no coaching after the first
unstated one. Record task outcome, observed errors, viewport, date and
environment only.

| # | Task | What it is meant to reveal |
|---|---|---|
| 1 | Inventory your skill roots | whether the detected roots match what the participant actually has |
| 2 | Find the divergent copy of *X* | whether the physical target is identifiable without an operator |
| 3 | Explain why those two copies differ | whether divergence is comprehensible or merely coloured |
| 4 | Validate *X* and say what the issues mean | whether findings read as actionable |
| 5 | Sync *X* to one named scope | whether the target is unambiguous at the moment of mutation |
| 6 | Restore *X* from history or trash | whether recovery is findable unaided |

**[SPEC]** **Do not** run registry fetch, hosted backup, or team governance as
pilot tasks. They are discussion topics, not promises; a pilot that stalls on
an unbuilt feature produces no usable signal about the parts that are built.

## Success signals

**[SPEC]** From @docs/17-adoption-and-distribution.md, unchanged in substance:

- a participant can identify the physical target;
- a participant can explain a divergence;
- a participant can complete validation;
- a participant can recover a mutation without an operator intervening.

**[SPEC] Record failures and uncertainty.** A pilot that reports only successes
is worthless and, for a tool whose entire pitch is trustworthy evidence,
self-defeating. A task the participant could not complete is the most valuable
row in the table.

## Stop conditions

**[SPEC]** Stop the pilot, and say so in the write-up, if any of these occur:

- a mutation target is ambiguous about which physical copy it will affect;
- a recovery path is unclear to the participant;
- the UI suggests that popularity, registry origin, or an upstream vendor is
  proof of safety;
- a participant cannot tell whether a change has been written yet.

The first three are product defects, not usability findings. The last is the
tool's central promise failing.

---

# Consent form

**Participants must read and sign this before any session.** Print it, or send
it in advance and collect the signed copy before starting.

> **Skills Manager design-partner pilot — informed consent**
>
> **What this is.** A 45–60 minute session observing you use a local tool for
> managing AI-agent skill files. We are testing the tool and its wording, not
> you. There are no right answers.
>
> **What is recorded.** Task outcomes, errors you hit, your screen size, the
> date, and your operating system version. A screen recording may be made of
> the shared screen and will be kept only if you tick the box below.
>
> **What is NOT recorded.** Your skill contents, file contents, prompts,
> credentials, API keys, account details, or any network traffic. The tool runs
> entirely on your machine and sends nothing anywhere.
>
> **The fixture.** Everything happens in a disposable directory we create and
> name for you. You may inspect it at any time and you should delete it when we
> ask you to. If you prefer to use your own skill files for any task, tell us
> and we will use a copy, never the original.
>
> **Your skill files are read by the tool, not by us.** We may see filenames
> and directory layout incidentally on screen. If any of that is sensitive, tell
> the moderator and we will skip that task or redact it before any note is
> written.
>
> **Recording.** ☐ Yes, you may screen-record this session. ☐ No, notes only.
> ☐ Yes, screen-record, but not the parts I mark as sensitive.
>
> **Withdrawal.** You may stop at any point without giving a reason, and you may
> ask for your notes to be deleted afterwards. Withdrawal does not affect any
> other arrangement with you.
>
> **How your data is used.** Notes are de-identified before they are written
> down: no name, no employer, no machine identifier. Findings may be quoted in
> the project's public documentation in aggregate. We will not attribute any
> statement to you without checking the wording with you first.
>
> **The honest bit.** This tool makes claims about trustworthy local evidence.
> If it does not deliver them for you, that is the most useful thing you can
> tell us, and we will report it as a finding rather than as a preference.
>
> Name (optional, for withdrawal contact): ______________________
> Signature: ______________________  Date: ____________

**[NOTE]** If a participant declines the consent form, the session does not run.
There is no version of this that proceeds without it.

---

# Session note template

**[SPEC]** One note per session. De-identified **at the point of writing** —
never write the name, employer or machine identifier into a note and remove it
later.

```markdown
# Session <id> — <YYYY-MM-DD>

Environment: <os + version> · <browser + version> · viewport <WxH> ·
Python <version> · <date of the commit under test>

Participant: <cohort label: novice | expert | multi-root maintainer>

Fixture: <N synthetic skills> · <scopes seeded> · divergent copy: yes/no ·
malformed document: yes/no

| # | Task | Outcome | Observed error | Verbatim quote (if any) |
|---|---|---|---|---|
| 1 | Inventory roots | pass / partial / blocked | | |
| 2 | Find the divergent copy | | | |
| 3 | Explain the divergence | | | |
| 4 | Validate X | | | |
| 5 | Sync X to one scope | | | |
| 6 | Recover X | | | |

## Where the participant paused without being asked to
<the moments that cost time or confidence — these are the findings>

## What the participant expected to happen, and what happened instead
<expectation mismatches; the most useful single column in this table>

## Could the participant tell whether a change had been written yet?
yes / no / uncertain — <evidence>

## Did any stop condition fire?
<which, and what was done about it>

## Moderator's own notes, flagged as such
<never mixed into the participant's observations>
```

**[SPEC]** "Blocked" is a legitimate outcome and must not be smoothed into
"partial". A participant who cannot complete a task without help is the
measurement.

## Aggregating after the pilot

**[SPEC]** With five or more sessions, report per-task pass counts **and** the
failure list. Do not publish a single satisfaction score: at this sample size
it would imply a precision nobody has. Do not convert task outcomes into a
percentage without stating `n` next to it — a "67% success rate" from five
sessions reads as precision and is closer to noise.

**[?] `[?]` What counts as "the pilot succeeded"?** The repo's own gates say
publish only after the artifacts are reviewed; they do not define a numeric
threshold. Setting one now, before any data exists, would be inventing the
result in advance. Propose the threshold when the sessions are run.
