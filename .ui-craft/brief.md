# Skills Manager UI brief

Date: 2026-09-20

Skills Manager is a local developer tool for choosing, inspecting, and moving
skill documents. Its visual job is to make scope, selection, and documentation
legible at a glance without turning filesystem details into the primary story.

## Direction

- Calm, precise tool workspace with a copper action color.
- Light canvas `#f5f6f8`, cool rail `#f0f2f5`, white work surface; authored dark
  canvas/rail/content surfaces for low-light use.
- System UI typography and `ui-monospace` only; no network fonts or assets.
- 4/8/12/16/24/32 spacing rhythm; 6px fields, 8px buttons, 10px panels,
  16px dialogs.
- Desktop is a navigation rail, skill list pane, and left-aligned document pane.
  Tablet keeps the list and document side by side; phones use list → detail with
  an explicit Back to Library action.

## Interaction contract

Scope and filter controls are progressively disclosed where space is tight.
Rows keep the name and description primary; badges wrap below in their own
region. Technical metadata lives under the native Skill details disclosure.
Actions retain their existing Vue methods and REST seams. Dialogs preserve
focus trapping, restore focus to their opener, use sticky headers/footers, and
respect reduced motion.

## Review dials

CRAFT9 · MOTION2 · DENSITY7 · VARIANCE4
