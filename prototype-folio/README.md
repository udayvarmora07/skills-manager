# Folio

**Skills Manager, as a reading room.** A frontend-only UI/UX prototype for this
repository, built from scratch. It shares no code, markup, styles, or sample data
with the shipped web UI or the other prototypes in the repository.

**Open `index.html`.** No build, no server, no package manager, no network. The
fonts are in `assets/fonts/`; every icon is inline SVG; all data is generated in
the page. If a browser restricts local files, run `python3 -m http.server 8899`
in this folder and open `http://127.0.0.1:8899/`.

---

## The premise

The product answers three questions about a local library of AI coding-agent
skills:

1. What can each agent actually load?
2. Where does each physical copy live?
3. Do the copies agree?

Most tools answer those with a table and a status dot. Folio treats the skill as
what it is: a document read into a context window. So the interface is a reading
room. An index rail, a catalogue beside a paper-like document sheet, a context
ruler, and an evidence ledger. The point is to make the answer legible before it
is interactive.

The one accent is chartreuse, used for selection, focus, and the active marker.
The instrument is set in Instrument Sans, the reading surface in Newsreader, and
every identifier, path, hash, and figure in JetBrains Mono.

## What to try

**Overview.** Start at the briefing. The three items are a sorted extract of the
61 attention items; `All 61` opens the filtered catalogue and aligns the detail
to the first item. The context card is the same ruler as the Context view.

**Catalogue.** Filter by state or root, search, sort, and open a document. The
list and the document sheet scroll independently on desktop. The document room
has four tabs:

- **Document**: frontmatter, rendered prose, and the observation margin.
- **Copies**: every physical path, its state, its token count, and a compare
  action for a divergent copy.
- **Validation**: the local rules and the exact issue list.
- **History**: the local record for this document.

**Compare.** Open `accessibility-compliance` from Attention, choose Copies, and
press Compare on the Gemini row. Toggle Split and Unified. Added and removed
lines carry a visible `+` or `−` as well as colour.

**Context.** Switch the window between Claude 1M, GPT-5 400k, Gemini 2M, and
Claude Haiku 200k. The same library moves from 61.2% to 306.2%; the ruler, the
headroom, and every root badge change with it.

**Quality.** Filter the evidence ledger by severity and root. The side panel is
deliberately about what the ledger cannot show: usage, freshness, trust, and
usefulness.

**Profiles.** Preview an enable plan. The plan separates observed, disabled,
divergent, and missing members, and the button names the outcome rather than
overclaiming a bulk write.

**Install.** Select a registry item, read the source, files, validation, risk
evidence, and snapshot hash, then confirm the review. The commit is blocked when
validation has an error, even with the checkbox checked.

**Recovery.** Restore a trash item, review a snapshot, export the library, or
import an archive. A purge is a separate, irreversible confirmation.

**Settings.** Light, dark, or system; standard or large text; system, en-US,
en-GB, or en-IN formatting. The state previews (live, loading, empty, error) are
here too, and the preview strip above the page says when the sample data is only
in memory.

**Command palette.** `Ctrl`/`Cmd` + `K` or the top search field. It searches
navigation, actions, and the catalogue. Arrow keys move, Enter runs, Escape
returns focus.

## Keyboard

| Keys | Action |
|---|---|
| `Ctrl` / `Cmd` + `K` or `/` | Open the command palette |
| `?` | Open the shortcut sheet |
| `n` | New skill |
| `t` | Toggle light and dark |
| `g` then `o` / `l` / `c` / `q` / `p` / `i` / `r` / `s` | Overview, Catalogue, Context, Quality, Profiles, Install, Recovery, Settings |
| `j` / `k` | Move the catalogue selection |
| `ArrowLeft` / `ArrowRight` on a document tab | Switch tabs |
| `Esc` | Close the top layer, the drawer, or the mobile document |

## Sample data

Everything is synthetic and lives in `data.js`. There is no backend, no file
access, no registry request, and no persistence. Create, edit, sync, install,
restore, and purge change the in-memory sample only; a reload restores the
inventory. The numbers are internally consistent at the aggregate level: 642
logical skills, 1,962 observed instances across eight roots, and 612,480
estimated tokens. The sample is a demonstration, not a claim about your machine.

The state marks are observations, not a score: active, disabled, mixed,
divergent, malformed, linked outside a root, unaddressable, and the per-copy
states. `linked` is deliberately distinct from `malformed`: a refused symlink
is not a corrupt document.

## Files

```
index.html          the shell, landmarks, and the inline brand mark
preferences.js      first-paint theme and text-size resolution
fonts.css           local @font-face declarations
styles.css          tokens, components, responsive rules, motion
data.js             scopes, sample documents, findings, registry, recovery
core.js             state, formatting, icons, state marks, the ruler
views.js            the shell, overview, catalogue, document room, context
views2.js           quality, profiles, install, recovery, settings, states
overlays.js         palette, create, sync, diff, help, about, plan, purge
app.js              event handling, actions, focus, persistence
assets/fonts/       Instrument Sans, Newsreader, JetBrains Mono; OFL licences
.shots/             reference captures from the review pass
DESIGN.md           the design contract and measured contrast
```

## Limits

- No real backend, filesystem, registry, index, or authentication. The prototype
  is honest about that in the UI.
- The inventory, registry, quality findings, and recovery records are synthetic.
- This pass did not include human usability sessions or a screen-reader audit.
  Contrast is measured in `DESIGN.md`; the reviewed captures are in `.shots/`.
- The prototype is a design artifact. It is not the shipped Skills Manager and
  does not claim to be.

## Credits

The concept, copy, and interface are new. The direction was informed by
index-first documentation, editorial product interfaces, and the `/design`,
`ui-craft`, `ui-ux-craft`, `design-taste-frontend`, and `unslop-ui` guidance. The
inspo archive was used for reference analysis, not for copied layouts or assets.

Fonts are under the SIL Open Font License 1.1. The licence files ship beside the
WOFF2 files in `assets/fonts/`.
