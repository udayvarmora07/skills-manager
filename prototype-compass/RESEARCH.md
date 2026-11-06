# Compass — research record

Prototype two for Skills Manager. This file records **what was studied and which
decision each finding produced**, so every part of the design can be traced to
evidence. Where a decision is my own judgement, it says so.

## 1. Sources used

| Source | What it is | How it was used |
|---|---|---|
| **Inspo MCP** (`inspomcp.dev`) | Archive of real shipped sites: captures, palettes, fonts, structure | `recommend`, 2× `search_screens`, `compare` ×2, `find_components`, `get_design_system` ×3, hero captures studied at 1440px |
| **open-mobbin** (`~/open-mobbin`) | Local reverse-engineered dossier of Mobbin | Pattern taxonomy with real capture counts (`datasets/patterns.csv`), Mobbin's own design skills (`reference/mobbin-skills`) |
| **Free web guidance**, via a research agent that fetched each page | NN/g, IBM Carbon, GitHub Primer, GOV.UK, WCAG 2.2, Digital.gov, GitHub Docs, Google Docs help | Rules for dashboards, lists, states, status, wording, onboarding, accessibility, diffs |

Mobbin Pro and the Mobbin MCP were **not** available, so no Mobbin screenshots were
viewed. The open-mobbin material provided Mobbin's taxonomy and method, not its images.

## 2. What Inspo showed

| Reference | What I took | Where it shows up |
|---|---|---|
| **Calendly** (`calendly-com`) | Its real CSS tokens: midnight ink `#0b3558`, slate `#476788`, ground `#f0f3f8`, borders `#e7edf6`/`#d8dce0`, primary `#004eba`, 10px button radius, and diff colours (add `#0eb4641a`, remove `#c80a641f`). Workflow cards written as plain sentences. | The whole palette. The Compare view's added/removed lines. The "what happened → what to do" wording of every problem. |
| **Linear** (`linear-app`) | The product UI in its hero: a sidebar of plain nouns, a detail page as document + properties rail, and "02 / 145" previous/next stepping | Skill detail as a full page with a right-hand facts rail and "3 of 20" stepping |
| **Buildkite** (`buildkite-com`) | Rows of steps shown as small chips with a status icon each, and a grid of test cells with ticks | The **Agents grid** view: skills × agents, one status icon per cell |
| **Capacities** (`capacities-io`) | Soft colour-coded type chips on a calm light canvas | Agent identity chips (colour + initials + name) |
| **Biome / Deno / Glide** (first study) | One confident blue; cool neutrals; one focal input | Single primary colour; search placed directly under the title |
| `recommend` evidence | 24 comparable sites: 83% light background, 71% grotesk sans | Light by default (dark mode included); Plus Jakarta Sans as a free stand-in for Calendly's geometric face |

## 3. What open-mobbin showed

**Mobbin's capture counts say real products spend their screens on states.**
Across web screens, the most-captured patterns after "Add & Create" (4,116) are
Acknowledgement & Success (3,280), Settings (3,161), Edit (2,936), **Loading
(2,567)**, Select (2,173), **Empty State (2,126)**, Search (1,809), **Error (1,592)**
and **Confirmation (1,576)**. The most common UI elements are Button, Text Field,
Dialog, **Banner**, Card, Icon, Popover, **Badge**, Tab and Chip. The most common web
flows include **Filtering & Sorting** (1,962), **Switching View** (942) and
**Turning On/Off** (921).

→ Prototype one showed almost none of these states. Compass has a **state
switcher** that shows each one: first run, loading, scan error, no results, all
fixed, and success. Filtering, sorting, switching view and on/off are all present.

**Mobbin's `redesign-screen` skill (`taste.md`) supplied the build rules:**
- Add nothing a problem doesn't need.
- A new element copies its nearest sibling.
- One thing leads per screen.
- The same job always looks the same.
- Change the least that answers the problem.

→ That is why Compass has no quick-actions grid, no decorative illustrations, and
one primary button per screen.

## 4. What the free guidance showed, and the decision it produced

| Finding (source) | Decision in Compass |
|---|---|
| A dashboard serves one task and needs minimal interaction (NN/g, dashboards) | Overview answers one question: *"Do my skills need attention?"* |
| Bullet charts beat gauges for "value vs target"; sort bars by value (NN/g) | "Reading space" is a bar with a marked limit per agent, sorted largest first. No gauges. |
| At most two levels of progressive disclosure (NN/g) | Overview → skill page. Folder paths and the raw file sit behind one disclosure. |
| Roll several statuses up to the highest-attention one; use about 5–6 statuses; never colour alone; shape before label (Carbon) | Five statuses, each with a unique icon shape + word + colour. The page banner shows the most serious one. |
| Red = error, orange = serious warning, green = success, grey = off (Carbon) | Can't be read = red. Copies differ = orange. Working = green. Turned off = grey. |
| One item per row; right-align numbers; tabular numerals; 64px rows when two lines (Primer, Carbon) | Two-line 64px rows. Size right-aligned in tabular numerals. |
| Search sits under the title; the toolbar has at most five global actions (Carbon) | Search under the title, then filters, sort and view switch. |
| Row checkboxes + a tri-state header + a batch bar that replaces the toolbar; Cancel exits (Carbon) | Exactly that, with *Turn on / Turn off / Move to trash / Cancel*. |
| Empty states have different jobs: first use, no results, error (Carbon, Primer, NN/g) | Three separate empty states, each with one primary action and no dead ends. |
| 2–10s: skeleton; scans: a progress bar (NN/g) | The scan shows a progress bar naming each agent folder, with skeletons beneath matching the real layout. |
| Undo over confirm; confirm only serious irreversible actions, with outcome-labelled buttons, not defaulting to the destructive one (NN/g) | Turn on/off and trash use **Undo**. Overwriting files asks first, with buttons like *"Update 1 copy"* / *"Keep as is"*, and focus starts on the safe one. |
| Inline notifications sit beside their item and persist; toasts suit system messages (Carbon) | A skill's problem is an inline banner on its page, while action results are toasts. |
| Never put essential information in a tooltip; offer a "What does this mean?" disclosure (NN/g, Primer) | Jargon (skill, agent, copy, reading space) uses keyboard-reachable *term* buttons that open a short explanation. Nothing essential lives only there. |
| Pull help over push help; onboarding is optional and attached to the empty state (NN/g, Carbon) | First-run guidance appears in the empty state. On Overview, "How this works" is a closed disclosure. |
| Rich (rendered) diff by default, source as a toggle; frame changes by who and when; restore is explicit (GitHub Docs, Google Docs) | **Compare copies**: pick two copies, see added/removed lines in rendered text, with a "Show file text" toggle. *Use newer version* is explicit and backed up. |
| `role="status"` for results and success, `role="alert"` only for errors; 24px minimum targets; 3:1 for control boundaries (WCAG 2.2 4.1.3, 2.5.8, 1.4.11) | Result counts and toasts use a polite status region; the scan error uses alert. All targets ≥ 32px; boundaries are checked in `check-contrast.py`. |

## 5. My own judgement (no source)

- **Full page vs side panel** for the skill detail. The research found no evidence
  either way. I chose a full page (as Linear's capture shows) because Compare needs the width.
- **"Needs attention first"** as the default sort.
- **Three summary numbers** on Overview. NN/g gives no count.
