# Skills Manager: final prototype

A complete, frontend-only prototype that combines the four chosen design
directions into one app. All data is made-up demo data held in memory: nothing
reads or writes skill files, there is no backend, and no network request is made.

## Open it

Open `index.html` in a browser, or serve this folder on loopback:

```bash
python3 -m http.server 8734 --bind 127.0.0.1   # then visit http://127.0.0.1:8734/
```

## What each concept became

| Screen | From concept | What you can do |
|---|---|---|
| **Home** (`#/home`) | 1. Agent rooms | See every AI tool as a card: health, its skills, reading space used. "Needs a look" shows the top 3 problems with **Fix it**, plus most-shared skills and recent changes. Click an agent to see only its skills. |
| **Skills** (`#/skills`) | 3. Skill shelf | Skills **grouped by category** (Engineering, Design, Data & Ops, Writing, Git, Security) as cards with status badges. Search, filter (All / Needs care / Turned off), and filter by agent. |
| **Sync map** (`#/map`) | 2. Sync map | Your library in the middle, lines to each agent: green in sync, dashed orange out of date, broken red can't be read. Click an agent to see why, **Peek** at the exact changes, choose skills and **Update** them. |
| **Inbox** (`#/inbox`) | 4. Inbox zero | One problem at a time with a before/after comparison and one clear fix. **Skip for now**, jump to any item, progress bar, and an "All done" screen. Keys: `Enter` fixes, `S` skips. |
| **Skill page** (`#/skill/<name>`) | 7. Notebook | Read the skill as a clean document, with all skills listed by category on the left. Margin notes show problems, a highlighter for lines missing from an older copy, on/off per agent, length, history and folders. **Edit** gives a Write/Preview editor with formatting buttons and lets you choose which agents receive the change. |

## How it behaves

- **Every change can be undone** from the message that appears.
- **Unsaved edits are protected.** Leaving the page asks first, with "Keep editing" as the default choice. `Ctrl/Cmd+S` saves.
- **Everything stays in sync across screens.** Fixing something on one screen updates the badge, cards, map lines and inbox everywhere.
- **Problems explain themselves in plain words:** what happened, why it matters, and what the button will do.
- **Keyboard:** `/` focuses search, and dialogs keep focus inside them and support `Esc`. On phones the map becomes a list and the skill page puts the problem note right under the description.

## Design system

- **Surface:** warm paper `#f7f5f0`, white cards, ink-black `#1b1d22` for main actions, terracotta `#b8492a` used sparingly (inbox badge, emphasis).
- **Status:** always icon + word + colour. Green = working, orange = copies differ, red = can't be read, grey = turned off.
- **Type:** Plus Jakarta Sans for the interface, Newsreader serif for headings and skill documents, Geist Mono for folder paths. All are SIL OFL fonts stored in `fonts/`, so it works offline.

## Not included yet

Dark theme, creating a new skill, trash/backup screens, and real file access.
Screenshots of every screen are in `screenshots/`.
