# Skills Manager — Library prototype

Open `index.html` in a browser, or serve the repository root and visit `/prototype-ui/`.

This is a standalone, frontend-only design prototype. All skill names, paths, counts, states, and document text are illustrative demo data. Actions in this prototype change only in-memory state and never read or write skill files.

## Screen plan

| Area | Purpose | Action and state | Small-screen behavior |
| --- | --- | --- | --- |
| Header | Identity, search, primary action | Search by name/description; create demo skill; theme toggle | Search remains visible; secondary actions compact |
| Rail | Navigate work areas and filter by agent scope | Library and Overview views; scope selection; context budget | Scope filter moves into a labelled select |
| Library list | Scan logical skills and their observed state | Search, status filter, select a skill; true empty state | Full-width list screen |
| Document | Inspect the selected skill and its exact copies | Overview, instances, source, and content tabs; copy path; sample validation feedback | Separate screen with Back button |
| New skill dialog | Try creation flow | Name and description validation, submit success, Escape/cancel | Full-width sheet |

Visual direction follows `DESIGN.md`: cool paper surfaces, ruled separation, IBM Plex Sans/Mono, teal interaction ink, and labelled status colours. Carbon’s patterns and data-table guidance informed search/filter placement and row density; the project design remains the authority.
