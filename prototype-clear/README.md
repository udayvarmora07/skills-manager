# Clear — Skills Manager design prototype

A from-scratch, **frontend-only** prototype of the two main pages: **Home** and
**Skills**. It shares no code, tokens or markup with `skillsmgr/webui/` or the
earlier `prototype-*` folders. All data is made-up demo data held in memory:
nothing reads or writes skill files, and there is no backend.

## Open it

Open `index.html` directly in a browser, or serve this folder on loopback:

```bash
python3 -m http.server 8731 --bind 127.0.0.1   # then visit http://127.0.0.1:8731/
```

No build step, no dependencies, no network requests. Fonts are vendored in `fonts/`.

## The idea: plain language for anyone

The current UI speaks the engineer's vocabulary (scopes, instances, divergent,
malformed, unaddressable). Clear says the same true things in words anyone can follow:

| Engineering term | What Clear says |
|---|---|
| scope | agent (Claude Code, Codex, Cursor…) |
| global store | Your library |
| instance | copy |
| divergent | Copies differ |
| malformed / unaddressable | Can't be read, plus the reason in one sentence |
| disabled | Turned off |
| tokens vs context window | Size (Small / Medium / Large, about N words) and "reading space used" |

Every problem is written as **what happened → why it matters → one button to fix it**.

## Page 1: Home ("Your skills at a glance")

1. One sentence that answers "is everything OK?" (e.g. *20 skills across 6 agents, 5 need a quick look*).
2. One large search box as the main action.
3. A dismissible "New here?" explainer with three steps.
4. Three health cards (**Working / Needs a look / Turned off**). Each one opens the Skills page with that filter applied.
5. **What needs your attention**: the 4 most important items, with "Show more" for the rest.
6. **Your agents**: skill count, on/off split, and a bar showing how much reading space the skills use.
7. **Recent changes** and **Quick actions**.

## Page 2: Skills

- Large search box, three filter chips and an agent picker. That is the whole toolbar.
- One row per skill: name, purpose, which agents use it (letter tiles), status in words, and size.
- Clicking a row opens a panel that starts with a coloured **explanation box** saying what's wrong and offering the one fix. Below it are three tabs:
  - **Where it lives**: every copy, an on/off switch per agent, and a copy-path button.
  - **Read it**: the instructions, rendered and escaped.
  - **History**.
- Actions: **Make all copies match**, **Add to another agent**, **Turn off / on**, **Move to trash**. Every change shows a toast with **Undo**, so nothing needs an "are you sure?" dialog except the two steps that copy files.
- On phones the sidebar becomes a bottom tab bar, and the detail panel becomes its own screen with an "All skills" back button.

Keyboard: `/` focuses search, `↑`/`↓` move between rows, `←`/`→` switch tabs, `Esc` closes the panel or a dialog. Dialogs keep keyboard focus inside them and return it to where you were when they close.

## Visual direction (from the Inspo MCP study)

`recommend` measured 24 comparable sites: 83% use a light background and 71%
use a grotesk sans-serif. I took a position *with* that norm (calm and familiar
suits non-expert users) and borrowed from three references:

- **Biome** (`biomejs-dev`): a single confident blue as the only accent → `#0b5bd3` (5.9:1 on white).
- **Deno** (`deno-com`): cool neutrals (`#f8f9fc`, `#475269`), 8/12/16px radii, pill buttons, tight bold headings.
- **Glide** (`glideapps-com`): one big input as the focal point of the page, lots of quiet space.

Type: **Figtree** (friendly, very legible) for the interface and **JetBrains
Mono** only for folder paths. Status is never shown by colour alone: there is
always an icon and a word. Light and dark themes are both included, and
reduced-motion is respected.

## Files

| File | Purpose |
|---|---|
| `index.html` | App shell: sidebar, mobile tab bar, toast region |
| `styles.css` | Tokens, components, responsive and dark rules |
| `data.js` | Demo agents, skills, activity |
| `app.js` | Hash router, the two pages, detail panel, dialogs, toasts, keyboard |
| `fonts/` | Figtree and JetBrains Mono variable woff2 files (SIL OFL) |
| `screenshots/` | Captures at 1440px and 390px, light and dark |

## Not in this prototype (next)

Get new skills (registry install), Trash & backups, Settings, the create/edit
flow, and the fix-a-broken-file flow. These appear in the sidebar under
"Coming next", and their buttons show a "next prototype" toast.
