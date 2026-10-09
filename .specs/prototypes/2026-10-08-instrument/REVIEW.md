# Instrument — a redesign prototype for Skills Manager

**Date:** 2026-10-08/09 · **Status:** prototype, awaiting approval · **Applied to the app:** no

This is a **complete new front-end direction** for the Skills Manager web UI.
Nothing in `skillsmgr/` has been touched. The point of this pass is to agree a
direction *before* a 1,755-line `index.html` and a 2,005-line `styles.css` are
rewritten against it.

---

## What this direction is

The shipped UI is honest and dense, and it reads as an **admin panel**. The
reason is not the palette — it is three things:

1. **2:1 type contrast.** 26px display over 13px body. A page set entirely in
   one type family at one size reads flat however good the colour is.
2. **No depth model.** Every region is separated by a `1px` border, which makes
   chrome and content the same visual weight.
3. **A saturated dial.** The context-budget ring showed 403% on a 0–125% scale,
   so it rendered *full* — the exact lie the shipped `DESIGN.md` warns about for
   bars. The prototype now draws the **worst single root** (121%), which fits,
   and states the 4.03M total as a number rather than an arc.

This direction keeps the shipped design's **soul** — cool bone ground, one
reserved signal ink, status that is never colour alone, honesty about what the
tool cannot observe — and rebuilds the **body**: a real depth model, a 5.3:1
type scale, and one signature component that only this product could have.

### The five structural changes

| # | Change | Why |
|---|---|---|
| 1 | **Navigation recedes, content elevates.** Sidebar on the recessed canvas; content on the raised surface; cards lift above it. | Chrome louder than work is what makes an app read as a template. |
| 2 | **5.3:1 type scale** (52px hero → 11px micro), tracked per Apple's optical table. | Scale contrast is the single cheapest way to make a page feel art-directed. |
| 3 | **The instrument.** A ring for the worst root + a shared-axis ledger of all seven. | No competitor has this data, so nothing else in the world looks like this. |
| 4 | **Depth instead of borders.** Tinted layered shadows + a 1px inset top highlight (the one Liquid Glass trick that is implementable in plain CSS). | Materials read as surfaces; outlines read as boxes. |
| 5 | **Concentric radius** — inner = outer − padding. | A square inner corner inside a round outer one reads as a rendering bug. |

---

## Screens

Thirteen surfaces, all built from one shared shell (`build.py`) so two
screenshots can never disagree about what the navigation looks like.

| File | Surface |
|---|---|
| `01-overview.html` | The instrument, attention queue, observed metrics |
| `02-library.html` | Tri-pane: ledger rows, filters, skill detail |
| `03-document.html` | `SKILL.md` as a document reader, with frontmatter |
| `04-quality.html` | Validity, duplication, hotspots, and the signals that are unavailable |
| `05-install.html` | Registry search + the explicit trust gate |
| `06-recovery.html` | Trash, snapshots, archive transfer |
| `07-profiles.html` | Desired sets and the enable plan |
| `08-workspaces.html` | Consumer roots and documented precedence |
| `09-settings.html` | Appearance, reading, safety |
| `10-trash.html` | Trash |
| `11-palette.html` | Command palette |
| `12-create.html` | Create-skill dialog with live validation |
| `13-review.html` | Review-first update with a real diff |

Rendered at **1440 light**, **1440 dark**, and **400 mobile** (`shots/`).

---

## What is measured, not asserted

`check_tokens.py` re-derives every claim from the shipped token file. Run it:

```bash
python3 check_tokens.py              # 48 checks
python3 check_tokens.py --selfcheck  # proves the gate has teeth
```

It checks, and the selfcheck proves each by deliberate mutation:

- every ink step clears **7:1** on its own surface, in both themes
- every status colour clears **4.5:1** on its *own wash* — a status mark
  nobody can read is not a status mark
- every boundary clears **3:1** (WCAG 1.4.11, the *non-text* threshold)
- every tracking value matches **Apple's published optical tracking table** at
  that step's size
- each theme's two surfaces actually differ, or the depth model is decoration

`--selfcheck` breaks six rules one at a time, asserts the gate goes red each
time, then restores the file and asserts it is green again. **6/6 caught.**

### Two defects the gate found before anyone saw them

- **`--rule-strong` measured 1.43:1 light / 1.75:1 dark.** It is the only edge
  on a checkbox and on a secondary button, so that is a WCAG 1.4.11 failure —
  and the same defect the shipped stylesheet was fixed for once already. Raised
  to 3.16:1 / 3.33:1 as solid values.
- **The hero tracked `-0.033em`.** Apple's table crosses zero at 12pt: body
  type tracks *negative*, display type tracks *positive*. `-0.026em` is Apple's
  published value for **14pt body copy**, applied to a 31px display. Corrected
  to `+0.006em`.

### A bug in the gate itself

`check_tokens.py --selfcheck` could never prove it restored the file, because
the failure accumulator was module-level and never reset — a second call
reported the *previous* run's failures against the restored file. A gate that
answers about the wrong state is worse than no gate. Fixed with `_reset()`.

---

## Sources

**Apple** — [HIG Typography](https://developer.apple.com/design/human-interface-guidelines/typography)
for the optical tracking table and the macOS type scale; [Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
for the content-layer/functional-layer split and the one published number
(35% dim); [SwiftUI `ConcentricRectangle`](https://developer.apple.com/documentation/swiftui/concentricrectangle)
for the concentric-radius definition; [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
for the 12pt/24pt padding rule and control sizes; [Color](https://developer.apple.com/design/human-interface-guidelines/color)
for semantic colour roles.

Two findings worth keeping: **Apple's HIG publishes no 4pt grid, no radius
numbers, no shadow values and no motion durations.** Those are convention, not
specification, and this prototype does not attribute its own choices to the HIG.

**Density** — IBM Carbon's data-table row heights (48px default, 32/24/64)
verified from `@carbon/styles@1.117.0`. Fluent 2 and Atlassian were checked and
have **no density mode at all** — all three are spacing-scale systems. If this
project wants a density axis, it is building something none of those three
provides.

---

## What this prototype does **not** prove

Stated plainly, because a green render is not a sign-off:

- **No human perceptual review.** No non-Chromium engine, no forced-colors
  mode, no 200%/400% zoom, no screen reader. Chrome rendered it; that is all.
- **No interaction.** These are static screens. Focus order, focus rings, the
  modal focus trap, keyboard navigation and screen-reader output are **unbuilt**.
- **No performance measurement.** The shipped app's D1 read-path work stands;
  nothing here has been profiled.
- **No accessibility audit.** The contrast gate covers colour only. Roles,
  names, live regions and heading order are unverified.
- **Not a second source of truth for the app.** `build.py` exists so the
  thirteen screens share one shell *inside the prototype*. If this direction is
  adopted, the real `index.html`/`app.js` keep their structure and only the
  token and layer vocabulary changes.

## The four defects this pass found and fixed

Recorded because the class matters more than the instances:

1. **A `@font-face` mapped the Plex *Mono* file to the `Plex Sans` family** at
   weight 400. Every 400- and 500-weight string on every screen rendered as
   monospace, and it looked like a design choice rather than a bug. Caught by
   reading a screenshot, not by a test.
2. **The sidebar meters saturated** — three over-budget roots all rendered at
   exactly 80% width, i.e. identical. The same lie as the dial, in a component
   nobody was looking at.
3. **The responsive block set a three-area grid against a two-row track**,
   which put the sidebar in the vertical middle of the phone.
4. **A filter bar with four controls on one row** wrapped `1,163 copies` onto
   two lines.

---

## How to review this

Open `screens/` in a browser, or look at `shots/`. The three questions that
decide it:

1. **Does the instrument read as the most important thing on the page?** If the
   context-budget dial is not the first thing your eye lands on, the hierarchy
   is wrong.
2. **Is a 638-row ledger still scannable?** Density is a requirement here, not
   a compromise.
3. **Does the depth model survive your own screen?** Put this on a real
   monitor. If the raised cards read as flat, the shadows need to move.

If the answer to any of those is no, say which one and it gets fixed before it
is applied to the app.
