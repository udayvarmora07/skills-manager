# Prototype C — Reconcile

**Status:** awaiting decision. Prototypes A and B are untouched at
`../2026-10-06-warm-instrument/` and `../2026-10-07-document-inspector/`.
Nothing in `skillsmgr/` has been modified.

Open `index.html` directly. Params: `?shot=1` (full-page capture),
`&view=queue|diff`, `&theme=light|dark`.

## The thesis — a third one, not a restyle

| | Core unit | Primary act |
|---|---|---|
| A — Warm Instrument | a row you inspect | browse |
| B — Document Inspector | a document you read | understand |
| **C — Reconcile** | **a disagreement you resolve** | **fix** |

A and B both assume you arrive wanting to *look at* a skill. Nobody arrives
that way. You arrive because codex and gemini are giving you different answers
and you cannot work out why.

Measured, not asserted: **286 of 639 skill names (45%) have copies whose
content hashes differ.** 1,412 files are involved. 21 of those groups are read
by every agent installed. The defect is invisible from the filesystem — every
copy is a valid, readable `SKILL.md`, and each agent is faithfully obeying its
own. There is no error, no warning, no crash. That is precisely why it needs a
tool.

So the app's centre of gravity is a **queue of things that are wrong**, each
one a job with a stated cost, a preview, an explicit resolution and a snapshot
you can roll back to. Browsing survives as a nav item, not as the product.

## The idea I would argue is genuinely novel here

**Each side of the diff is labelled by which agent reads it, not by file path.**

```
SIDE A · selected     codex  · no-merge policy     ~/.codex/skills/…/SKILL.md
SIDE B               gemini · extension < user     ~/.gemini/skills/…/SKILL.md
```

Every other tool in this space shows you two files. This shows you two
*behaviours*, and puts the precedence evidence next to the name that produced
it. It converts an abstract "diff" into a sentence you can reason about: *these
two agents are not disagreeing with you, they are disagreeing with each other.*

The resolution footer is deliberately not a winner-picker. It offers **keep A /
keep B / merge**, with a preview of affected files and a named snapshot. And the
glossary states plainly which version is better advice — then says the judgement
is the user's, not the tool's. The tool stays honest without being useless.

## Visual language — also new

- **Ledger**: warm paper, ink rules, tabular figures. Structure comes from
  hairlines and a 2px ledger rule under the table, not from cards and shadows.
- **The diff holds the only colour in the interface.** Sage for added, brick for
  removed. There is no brand accent competing with what "changed" means, because
  on this screen "changed" is the entire subject. One sober navy is reserved for
  navigation and selection only.
- **Type**: Archivo for the interface (a grotesque with real character), IBM
  Plex Mono for every identifier, path and figure.
- No gradients, no glow, no emoji, no purple, no rounded-tile icon grids.

## Trade-offs, stated plainly

C is **opinionated and narrower**. It assumes you want things fixed. Someone who
just wants to read a skill, or browse a catalog, is worse served here than in B.
It also front-loads the interface with a queue that reads like a defect list —
which is accurate, but it is a less welcoming first impression than A's.

## Defects found and fixed during this build

1. **`.gloss b` was `display:block`**, so the inline emphasis in
   *"gemini's version is the better advice"* broke into its own line mid-sentence.
   Split into `.gloss-h` (the block heading) and `b` (inline).
2. **The sticky resolution footer could cover the last diff lines.** Added
   `z-index` and `padding-bottom: 96px` on the column so content always scrolls
   clear. Note: `?shot=1` sets `overflow:visible`, which defeats
   `position:sticky`, so capture mode renders the footer `static` — the sticky
   behaviour itself is **not verified by these captures**.
3. A scripted edit was aimed at the wrong prototype directory (B, not C). It
   reported no change and B was verified unmodified afterwards.

## Known gaps — the honest list

- **Two screens.** Queue and diff. Library, Install, Quality, Recovery and
  Profiles are nav items with no design behind them.
- **No responsive states at all.** A side-by-side diff is the hardest layout in
  the app and it collapses at narrow widths; that work is entirely undone.
- **No modal or dialog treatment**, so the plan for demoting the existing 16
  modals is unproven.
- **The "303 unreadable" and "304 disabled" jobs are stubs** — only the
  divergence queue is designed end to end.
- **No human perceptual review.** These captures prove it renders and that the
  information hierarchy is legible. They do not prove it is good.
