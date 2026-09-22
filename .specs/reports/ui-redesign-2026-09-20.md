# UI redesign implementation note — 2026-09-20

## Scope

Frontend-only redesign of the existing local Vue UI. No REST endpoint, Store
method, SQLite schema, runtime dependency, or build step changed.

| Before | After | Why |
|---|---|---|
| One 340px sidebar mixed navigation, scopes, budget, filters, and rows | Sibling navigation rail, list pane, and detail pane | Preserves orientation and gives rows usable width |
| Name and badges competed in one flex row | Name/description region plus wrapping `.row-badges` | Long skill names remain readable and cannot collapse to zero |
| Detail metadata appeared before documentation as a dense block | Native `Skill details` disclosure follows summary/instances; documentation is the work surface | Keeps useful instructions early while retaining exact metadata/path actions |
| Light mode used a warm cream blanket and dark mode was brown | Cool neutral canvas/rail/content tokens with authored copper dark theme | Better contrast and calmer developer-tool identity |
| Mobile stacked sidebar capped at 42vh | Full-height list/detail flow with explicit back state; profiles/workspaces/trash remain reachable | Prevents one-row mobile lists and empty-canvas waste |
| Import drop target used a visually oversized icon | Bordered ~160px dropzone with 40px icon and file copy | Clear target without dominating the modal |

## Verification boundary

Automated checks validate syntax, selectors, viewport overflow, and primary
interactions. Visual judgment of spacing, hierarchy, and copy remains a human
review item; screenshots should be read as rendered evidence, not participant
usability research.
