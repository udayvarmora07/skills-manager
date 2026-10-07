# Prototype B — Document Inspector

**Status:** awaiting decision. Prototype A is untouched at
`../2026-10-06-warm-instrument/`. Nothing in `skillsmgr/` has been modified.

Open `index.html` directly. Params: `?shot=1` (full-page capture),
`&theme=light|dark`.

## What is actually different from A

Not the palette — the same warm ivory/copper and IBM Plex. The **organising
idea**:

| | A — Warm Instrument | B — Document Inspector |
|---|---|---|
| Core unit | a row you inspect | the `SKILL.md` itself |
| Columns | nav rail · list · detail | scope **tree** · document · **inspector rail** |
| Navigation | nav + separate scope list | one tree — browse and select in the same structure |
| Reading | a card near the bottom | full-width prose at 15px/1.68, 68ch measure |
| Facts | a stat strip + wide table | a spec sheet rail: Actions / Metadata / Observed / Copies |
| Density | ~40px rows, keyboard-first | ~30px tree rows, comfortable, less on screen |
| Teaching | explanations in callouts | explanations **inline with the sentence**, plus glossaries |

The spine of B: *the document is what the agent loads.* A skill is not a
database row with a body attached — it is a text file that gets concatenated
into a context window. So B puts the file at the centre and demotes everything
else to apparatus around it.

Both prototypes keep the same spine of honesty: no invented winner column,
`undocumented-precedence` stays a real answer, and the 121%/119%/111% scope
overflow is surfaced rather than buried.

## Trade-off, stated plainly

B buys readability and approachability and pays for them in capacity.

- **A** shows ~11 rows at once and answers "what needs attention" fastest.
- **B** shows the whole argument of one skill and teaches the concepts better,
  but you see one document, not a list.

They are not really competitors — A's Overview is better for triage, B's detail
is better for understanding. The open question is which one is the app's centre
of gravity.

My read: **A's Overview + B's detail.** A's budget hero is the best thing either
has produced; B's reading column is the second best. They compose, because they
differ in view rather than in system.

## Defect found and fixed during this build

The scope tree carried a 26px budget bar next to each percentage
(`opencode ▬ 121%`). At that size it does not read as a meter — it reads as a
stray dash, and three scopes had it while four did not, which looks like missing
data rather than a deliberate omission. Removed; the percentage is the whole
fact, and the chart already lives on the Overview.

## Known gaps

- One screen only. The tree's "Views" list is a stub — Overview, Quality,
  Recovery, Install and Profiles are named, not drawn.
- No modal or dialog treatment at all, so the plan for demoting A's 16 modals to
  panels is still unproven here.
- No responsive states below 1080px, where the inspector rail drops out entirely.
- **No human perceptual review.** Same caveat as A.
