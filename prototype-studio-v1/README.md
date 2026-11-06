# Skills Manager · frontend concept 01

A standalone, offline prototype. Open `index.html` directly in a browser. All records are illustrative sample data; controls change the prototype state only and never touch real skill files.

## Design direction

The root `DESIGN.md` is the source for color, type, status, and interaction rules. This is a fresh information architecture rather than a copy of the current interface. The one external UX reference is [Carbon's data table guidance](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines): a compact toolbar, readable rows, and progressive detail. The [Component Gallery](https://component.gallery/) was consulted to compare common navigation and disclosure patterns, not as a separate visual style.

## Shot list

1. Workspace shell — make location, scope, search, and the next action visible.
2. Overview — show observed health, context budget, and concrete issues.
3. Library — filter by scope and state; select an exact skill without losing the list.
4. Detail — read document, compare physical copies, inspect evidence.
5. Quality — triage independent hygiene signals without a fabricated score.

## Prototype interactions

Navigate with the sidebar or bottom bar; search skills; filter by state; switch scopes; select a record; switch detail tabs; open the create dialog with validation; use the command menu with `/` or Ctrl/Cmd+K; toggle sample empty/loading/error states from the “Demo states” menu. The layout adapts at 1080px and 760px. All data is local and reset on refresh.

## Open decisions

- The prototype uses a document-first Library and an overview that starts with work requiring attention. This is a reversible navigation choice.
- The prototype keeps the repo's light palette. Dark mode can be explored in a later version using the existing dark token rationale.
- No live backend connection is included in concept 01; sample data is explicitly labelled.
- Laptop sizing is calibrated for 100% browser zoom above a 1200px CSS viewport: larger type and controls, smaller outer gutters, and shorter overview panels. At 125% zoom on a 1366px screen, the viewport falls below that breakpoint and retains the original sizing path.
