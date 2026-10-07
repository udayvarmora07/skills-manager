# Prototype — Warm Instrument

**Status:** awaiting maintainer decision. Nothing here ships; nothing in
`skillsmgr/` has been touched.

Open `index.html` directly in a browser (`file://` works — there is no build
step and no server). Query params: `?shot=1` relaxes the fixed viewport for a
full-page capture, `&view=overview|library`, `&theme=light|dark`.

## The three decisions, and why

**Direction: Warm Instrument.** The evidence in
`.specs/audit-2026-10-04/UI-UX-AGENT-RESOURCE-LIST.md` §13 is that the dominant
complaint is *recognisability* ("all looks the same", 6.1% of comments; "screams
AI", 6.4%), an order of magnitude above any individual feature. The existing
ivory + copper palette is already outside the default set, so replacing it with
dark slate + one status hue would have moved the tool *toward* the most
recognisable dev-tool look of 2026. The defect is execution, not palette: 28
custom properties, a 9-step spacing scale, one radius, `system-ui`, and no type
ramp.

**Priority: dense core + Learn layer.** Dense-only excludes the newcomers this
was requested for; guided-only taxes the people who keep the tool in their
daily loop. The Overview carries the orientation, and every non-obvious term in
the detail view carries a short explanation attached to it rather than behind a
`?`.

**Typography: IBM Plex Sans + IBM Plex Mono.** The single highest-ranked
anti-slop lever, and it fixes something practical: `system-ui` renders
differently per platform, which is a correctness problem for a tool whose job is
comparing skill copies. To be vendored as static assets (like Vue), never fetched
at runtime.

## The finding that drove the Overview

Measured against a 1M-token context window from real scope data:

| scope | instances | tokens | % of window |
|---|---|---|---|
| opencode | 519 | 1,210,856 | **121.1%** |
| codex | 480 | 1,189,659 | **119.0%** |
| gemini | 450 | 1,110,822 | **111.1%** |
| agents | 122 | 404,077 | 40.4% |
| commandcode | 60 | 53,305 | 5.3% |
| claude-code | 329 | 45,204 | 4.5% |
| global | 5 | 13,444 | 1.3% |
| **total** | **1,965** | **4,027,367** | **402.7%** |

Three roots individually exceed a whole context window. That is the most
operationally consequential thing this tool knows, so the Overview leads with it
instead of with skill counts.

The bar axis runs 0–125% so the 100% line sits at 80% of the track. On a 0–100%
axis, 111% and 121% both render as a full bar and the chart hides its own point.

## Defects found and fixed during the build

- Budget bars rendered 111% and 121% identically (axis capped at the threshold).
- `.attn-t`/`.attn-s` were inline, so every panel read `Divergent groupsSame
  name, different content`.
- The facts grid was `auto-fit`, leaving an empty cell at any width that did not
  divide the item count evenly — it now uses an explicit 3-column grid for its
  six facts.
- An `LIBRARY · SELECTED SKILL` eyebrow above the H1 was an unnecessary label;
  replaced with a path breadcrumb.

## Constraints this holds to

- Vendored Vue 3, hand-written CSS, no build step, no new runtime dependency —
  locked constraint 4. `pip install skill-control-plane` still needs no toolchain.
- The REST API and Store surface are unchanged. This is a frontend and token
  change only.
- Zero emoji, zero gradients, zero glow, no `rounded-2xl`/`shadow-lg` on
  everything, no cards nested in cards, no sparkle motif, no purple.
- `tabular-nums` on every number; status is always square + colour + word, never
  colour alone; 120 ms on paint properties only, no bounce/elastic easing.
- No fabricated metrics. Every number above is measured, not illustrative.

## Known gaps — deliberate, not overlooked

- Only three of ten views are drawn. Install, Quality, Recovery, Workspaces,
  Profiles and Trash are not.
- No modals. The shipped app has 16; the redesign's plan is to demote most of
  them to panels rather than redraw dialogs.
- No responsive/mobile states. The shipped app has six viewports pinned.
- **No human perceptual review.** The rendered captures are evidence that it
  draws, not evidence that it is good.
