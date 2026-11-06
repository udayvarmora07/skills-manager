# DESIGN: Folio

**The design contract for the Folio prototype.** Every token, measured ratio,
and refused default is recorded here so a later pass can change the interface
without changing its argument by accident.

This is a frontend-only prototype for the Skills Manager. It is not the shipped
web UI and does not share its styles, markup, or sample data.

## The premise

A skill is not a row. It is a document that gets concatenated into a model's
context window, and the same logical skill can exist as several physical copies
in several agent roots. The product's job is to make that legible:

1. What can each agent load?
2. Where does each copy live?
3. Do the copies agree?
4. What does it cost in context?

The interface is a reading room, not a dashboard. One index rail, one catalogue,
one document sheet, one evidence ledger. The visual material is ruled paper, a
single ink, one chartreuse signal, and four status colours that mean what they
say.

## The one accent

Chartreuse (`--signal`) is reserved for selection, focus, the active marker, and
the thin rule that marks a choice. It is never body text on paper. Its contrast
against the light ground is about 1.2:1, so the label is always ink, the active
row is also a sheet, and the marker is a rule beside a word. The chartreuse is
repeated in the brand mark, the page kicker, the active navigation item, the
selected catalogue row, the selected palette item, and the focus halo.

**Measured:** signal ink `#171b0e` on signal `#c9f24d` is 13.58:1 (light);
`#11150a` on `#d7ff5f` is 16.17:1 (dark). Signal text `#3d4a12` on the signal
wash is 8.77:1; the dark pair is 13.11:1.

## Palette

### Light

| Token | Hex | Role | Measured |
|---|---|---|---|
| `--paper` | `#eff0ec` | page ground | - |
| `--sheet` | `#fbfbf7` | raised paper | - |
| `--paper-deep` | `#e7e9e3` | rail and status strip | - |
| `--ink` | `#141712` | primary text | 15.80:1 on paper |
| `--ink-2` | `#3c423a` | secondary prose | 9.03:1 on paper |
| `--ink-3` | `#5b6259` | labels and metadata | 5.50:1 on paper |
| `--ink-4` | `#62695f` | quiet labels | 4.95:1 on paper, 4.63:1 on the rail, 5.46:1 on a sheet |
| `--control` | `#7a8176` | form boundaries | 3.51:1 on paper, 3.87:1 on a sheet |
| `--ok` | `#2c6a3f` | success text | 6.25:1 on a sheet |
| `--warn` | `#7a5500` | warning text | 6.47:1 on a sheet |
| `--err` | `#a62a22` | error text | 6.80:1 on a sheet |
| `--info` | `#2f5568` | linked/containment text | 7.73:1 on a sheet |
| `--signal` | `#c9f24d` | selection accent | fill/marker only |
| `--signal-strong` | `#b4e32f` | accent rule | fill/marker only |

Status text on its own wash measures 5.47:1 (ok), 5.81:1 (warn), 5.81:1 (err),
and 5.81:1 (info) in light; 8.21:1, 8.15:1, 7.01:1, and 8.21:1 in dark.

### Dark

| Token | Hex | Role | Measured |
|---|---|---|---|
| `--paper` | `#0c0e0b` | page ground | - |
| `--sheet` | `#14170f` | raised paper | - |
| `--paper-deep` | `#090b08` | rail and status strip | - |
| `--ink` | `#f0f3ea` | primary text | 17.27:1 on paper |
| `--ink-2` | `#c8cec1` | secondary prose | 12.05:1 on paper |
| `--ink-3` | `#9aa292` | labels and metadata | 7.35:1 on paper |
| `--ink-4` | `#7c8475` | quiet labels | 4.67:1 on a sheet, 5.09:1 on the rail |
| `--control` | `#7c8475` | form boundaries | 4.67:1 on a sheet |
| `--ok` | `#8fc79a` | success text | 9.32:1 on a sheet |
| `--warn` | `#e0b35f` | warning text | 9.30:1 on a sheet |
| `--err` | `#f08a7e` | error text | 7.45:1 on a sheet |
| `--info` | `#8ec5d8` | linked/containment text | 9.60:1 on a sheet |
| `--signal` | `#d7ff5f` | selection accent | fill/marker only |

The two boundary values are not decoration. `--rule` and `--rule-2` are
decorative hairlines; `--control` is the only token used for an input, select,
textarea, search field, or command field boundary. WCAG 1.4.11 asks 3:1 of that
boundary, and it gets 3.51:1 or more. The quiet text token is the darkest value
that still reads as quiet and stays above 4.5:1 on every surface it is used on.

## Type

| Face | Role | Source |
|---|---|---|
| **Instrument Sans** 400-700 | interface, headings, labels | `assets/fonts/`, SIL OFL |
| **Newsreader** 300-700 | document prose | `assets/fonts/`, SIL OFL |
| **JetBrains Mono** 400-600 | names, paths, hashes, figures | `assets/fonts/`, SIL OFL |

- UI text is 14px with 12px metadata and a 10.5px micro floor. Nothing that a
  reader must act on is below 10.5px.
- The page title is `clamp(30px, 3.4vw, 46px)`, weight 600, tracking `-0.04em`.
  Compact views use `clamp(26px, 2.4vw, 34px)`.
- Document prose is 17.5px / 1.68, measured at 68ch. It steps to 16.5px on
  mobile. The serif is not decorative: it is the reading surface.
- Every identifier, path, hash, token count, and date is mono with
  `font-variant-numeric: tabular-nums`.
- All three faces are vendored, never fetched. The OFL licence files ship beside
  the WOFF2 files.

## Space, radius, rules

- Spacing rhythm: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48. The shell uses 64px for
  the masthead and 28px for the status strip; the rail is 232px at its widest.
- Radii: 2px badges and marks, 4px controls and buttons, 6px sheets and document
  cards, 8px panels, 12px dialogs. A 16px radius is reserved for nothing; the
  prototype does not round everything into pills.
- Rules are 1px hairlines. The only heavy rules are the 3px chartreuse active
  marker, the 3px status edge on a banner, and the 2px tab underline.
- The ground is flat. There is no decorative grid, noise, or gradient; the
  material comes from the paper and sheet values, not from a pattern.

## The three signature components

### 1. The context ruler

The ruler is the product's most consequential observation, so it leads the
Overview and owns the Context view.

- The axis is **0 to 125%**, not 0 to 100%. A root at 111% and one at 121% must
  render as different bars, not both clamp full.
- The 100% mark is a labelled vertical threshold. The fill is a status colour:
  ok under 80%, warn from 80 to 100%, error above 100%. A root at 306.2% is
  visibly an error, and the number is not rounded away.
- The fill is `transform: scaleX(...)` on a 8px track, never a width animation.
- The total is described as an estimate, not a bill: "characters ÷ 4, not a
  tokenizer." The screen does not claim to know the consumer's own instructions,
  tool descriptions, cache hits, or model tokenizer.
- The small root tracks in the rail and the budget table share the token, the
  status palette, and the same 100% semantics. They are not a second chart.

### 2. The document sheet

The catalogue is a list beside a sheet, not a grid of cards.

- The sheet begins with a frontmatter table, then the rendered prose. The first
  Markdown H1 is stripped because the room already prints the name; echoing it
  would be a decorative duplicate.
- The observation margin sits beside the prose on wide detail panes: state,
  copies, tokens, modified, content hash, physical path. On narrower panes a
  container query moves it below the prose as a two-column proof block. The
  prose never gives up its measure to keep the margin.
- The malformed state does not pretend to render a document. It shows the exact
  parse issue and the raw bytes, and says nothing was repaired.
- Copies are a table of physical paths, never a deduplicated list. Divergence is
  reported; the interface does not choose a winner.
- The compare view is a line diff. Added and removed lines carry a visible `+`
  or `−` as well as colour. The footer states that the copy a person syncs is
  the decision, not the diff.

### 3. The state vocabulary

State is a grammatical system, not a traffic light.

| State | Mark | Word used | Priority |
|---|---|---|---|
| active | filled square | Active | baseline |
| disabled | half square | Disabled | after active |
| mixed | half square, dashed | Active + disabled | some active, some disabled |
| divergent | diagonal split | Divergent | above disabled |
| malformed | crossed square | Malformed | highest document state |
| linked | square with an out arrow | Outside root | containment refusal |
| unaddressable | slashed square | Unaddressable | name rule |

- The words are always present. The mark is a scanning aid, not the status.
- `linked` is not `malformed`. A symlink the tool refuses to follow is a
  deliberate containment refusal with a different remedy; the interface says so.
- The logical state is a priority over the physical states, and the copies tab
  shows each physical state independently. A skill with one disabled copy is
  active, not disabled.
- Quality is an evidence ledger: parser flags, physical copies, hashes,
  validation issues, and context size. There is no combined score, no safety
  verdict, and no invented winner. The "unavailable signals" panel names usage,
  freshness, trust, and usefulness as things the ledger cannot show.

## Layout

- **Desktop, 1080px and up:** 232px index rail, fluid stage. The catalogue is a
  400px list beside a document room. The Context split is 1.4 / 0.9. Quality is
  1.5 / 0.7. Install is 1.1 / 0.9.
- **1080px and below:** the rail becomes a drawer with a header, a brand, and an
  explicit close button. The page keeps one column of task.
- **820px and below:** catalogue and document become separate full-height
  states. The mobile document hides the catalogue chrome, keeps the back action
  in the breadcrumb, and moves the state and actions below the title. The
  document sheet gets the full width and its own scroll.
- **720px and below:** page actions move below the title and the lede so the
  explanation is read before the controls. The list header becomes Skill and
  Tokens. Touch controls step up to 40px; compact segmented controls stay at
  34px inside a generously spaced bar.
- **520px and below:** tables scroll inside their own `table-wrap`; the catalogue
  row keeps the name, description, state word, scope chips, and tokens without
  turning into a card grid.
- The mobile page head order is kicker, title, lede, actions. The desktop order
  is kicker, title and actions, lede.

## Motion

- 120ms for paint, 160ms for overlay cards, 200ms for the drawer, 500ms for the
  ruler fill. The curve is `cubic-bezier(0.2, 0.7, 0.2, 1)`; no overshoot, no
  spring, no entrance animation on content that was already there.
- The ruler and the drawer use transforms. The skeleton is a 1.4s linear
  shimmer. The toast slides 6px and fades.
- `prefers-reduced-motion: reduce` disables every animation and transition,
  including the shimmer and smooth scroll. The app reads the same query for the
  trust panel's scroll.

## Accessibility

- One `h1` per view, landmarks for the masthead, rail, main, and status. A skip
  link targets the main stage. View navigation moves focus to the heading only
  when it was a navigation action.
- Every control has an accessible name. Icon buttons carry a label; catalogue
  rows carry a full name, copy count, state, and description; the palette is a
  labelled combobox and listbox; the tabs are real tabs with arrow-key support.
- State is glyph plus word. The diff is `+`/`−` plus colour. The selected row is
  a chartreuse rule plus a sheet plus the text, not colour alone.
- Dialogs use `role="dialog"`, `aria-modal`, a focus trap, `inert` and
  `aria-hidden` on the app behind, Escape, and focus restoration. The destructive
  confirmation focuses the safer close control first.
- Toasts are a polite live region. Errors are field-level and focused; the create
  form sets `aria-invalid` and the field's error is directly under it.
- All text pairs are measured at 4.5:1 or better in both themes; control
  boundaries are measured at 3:1 or better. The quiet token is not below 4.5:1
  on any surface it is used on.
- Type size, theme, and regional formatting are local settings. The document is
  still `lang="en"` because there is no translated interface to claim.

**Still open:** human usability review, a screen-reader pass, forced-colors mode,
200% and 400% zoom, and a non-Chromium engine. The captures in `.shots/` are
Chromium at 1440 and 390; they do not stand in for those checks.

## Refused defaults

These were considered and left out on purpose:

- The card grid as the catalogue. Documents are a list and a sheet here.
- Warm cream plus copper or vermilion. The palette is a cool bone ground with
  one chartreuse signal, measured.
- Navy and cyan, purple gradients, glass panels, neon glows, and decorative
  status dots.
- A tracked, all-caps eyebrow above every heading. Labels are sentence case;
  a data-table header may keep its caps because that is a table convention.
- Pill-shaped everything. Badges and chips are pills; controls, sheets, and
  dialogs have their own radii.
- A single quality score, a trust badge that implies a scan, or a summary that
  elects a winner between consumers.
- An icon-only control without a label, a form error detached from its field,
  and a colour-only state.
- Em dashes in interface prose. Sentences use periods, commas, and colons.

## Voice

Names the object: skill, document, copy, root, catalogue, context. Names the
observation: observed, divergent, malformed, linked, unaddressable. Names the
consequence: "the copy you sync is the decision", "the mark is an estimate, not
a bill", "nothing was repaired." It does not say seamless, effortless, or
everything in one place. It does not exclamation. It uses numerals for data and
words only for rhetorical counts.

## Files

The contract is implemented in `styles.css` (tokens, components, responsive),
`core.js` (state, formatting, marks), `views.js` and `views2.js` (screens),
`overlays.js` (dialogs and palette), and `app.js` (actions and focus). The
sample inventory is `data.js`. The font licences are in `assets/fonts/`.
