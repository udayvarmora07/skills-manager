# INSPIRATION — 12 principles to apply (each with evidence)

1. **Keyboard-first power layer** (Linear, GitHub): single-key list verbs, `?` shortcut
   overlay, `g+<key>` view prefixes, `t`-style fuzzy finder. Our palette exists —
   extend with `?` overlay + a few safe single-keys (with focus-context guards).
2. **Selection ≠ action** (Raycast Action Panel): keep row selection; move secondary
   verbs (validate/export/trash/sync...) into the Ctrl+K panel to de-clutter rows
   and detail headers.
3. **Undo over confirm** (Linear): toasts already have Undo for trash — extend the
   pattern to enable/disable/sync where the backend makes it cheap.
4. **Teaching empty states** (Supabase, Notion): every empty state names the ONE next
   action (+ `/` hint where search applies); first-run guidance beyond Overview.
5. **Meters, not numbers** (Vercel): budget/largest/validation signals as bars with
   threshold marks everywhere counts appear (rail, rows, quality) — already our
   language; extend consistently.
6. **Pinned + recent shortcuts** (Stripe Home): Overview gets a recency-aware "back to
   work" strip (exists as Recently touched — sharpen it) instead of generic guidance.
7. **Reader-first document** (Notion): 68ch (done), generous prose rhythm, H2/H3
   outline mini-nav for long SKILL.md bodies, sticky detail header that never covers
   focus (WCAG 2.4.11).
8. **Grouped settings, destructive isolated** (Cal.com, Stripe): settings by concern
   with per-section save states; rebuild/resync/purge behind confirm + dry-run
   (mostly true today — audit and tighten).
9. **Progressive disclosure defaults** (Vercel, Supabase): zero-config first screen;
   advanced (tag filters, batch, evals, provenance) one disclosure away, never removed.
10. **Density with air** (Raycast, Linear): keep 56px rows; earn spaciousness in page
    headers and section gaps, not by shrinking touch targets (24px WCAG floor, 44px
    mobile kept).
11. **Motion with purpose** (WCAG 2.3.3 + reduced-motion): same-document view
    transitions for list→detail only, gated on no-preference; skeletons over spinners;
    filter keystroke→paint budgeted <150ms (INP headroom).
12. **Honest instrument voice** (ours, reinforced by Stripe's stated support policy):
    state support + measurement method inline (chars/4 vs tiktoken, files-on-disk vs
    model usage); never a score, never inferred provenance. Non-negotiable keeper.
