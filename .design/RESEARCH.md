# RESEARCH (2026-10-15; researcher subagent; web = data, public pages only)

## Benchmarks (dense-local-dev-tool lens)
1. **Linear** (app + linear.app/docs): keyboard-first triage (`C/O/L/A/U/M`, `?` overlay,
   Cmd+K), list→detail split, optimistic updates + undo toast over confirms.
2. **Raycast** (manual.raycast.com): density without clutter; Action Panel (⌘K)
   separates selection from action; predictable ordering; grouped docs nav.
3. **Supabase** (dashboard + docs): table browser w/ inline filters, SQL fallback,
   teaching empty states, scoped read-only modes, feature-group settings toggles.
4. **GitHub** (docs: shortcuts + palette): `?` dialog, `t` finder, `g+<key>` prefixes,
   palette removing memorization burden; diff `i`/`a` toggles, blame inline.
5. **Stripe Dashboard** (docs): Home-as-overview w/ pinnable widgets, Shortcuts
   (pinned + recent), dense filterable tables + saved filters + export, settings split
   Personal/Account/Product, stated browser support (last-20-Chrome/4-Safari).
6. **Vercel dashboard** (docs): overview + usage meters (bars + threshold warnings),
   zero-config defaults with progressive disclosure.
7. **Cal.com settings** (docs): grouped-by-concern settings, per-setting save states,
   destructive actions isolated behind confirm + dry-run.
8. **Notion** (reader): ~65ch measure, outline nav, skeletons, `/`-hint empty states.
Shots: /tmp/opencode/bench-shots/{linear_app_method,www_raycast_com,supabase_com_dashboard}.png

## Official standards (URLs + dates)
- **WCAG 2.2** Recommendation 2023-10-05 (w3.org/WAI/standards-guidelines/wcag/new-in-22/;
  TR/WCAG22 cross-check). New AA relevant: **2.4.11 Focus Not Obscured** (sticky
  modal head/foot must not cover focus — OUR modal-head/foot are sticky!),
  **2.5.7 Dragging** (single-pointer alternative; we have no drag — compliant by absence),
  **2.5.8 Target Size minimum 24px** (we exceed on mobile/44, desktop 32-34 — OK),
  3.2.6 Consistent Help, 3.3.7 Redundant Entry. 2.4.7 Focus Visible
  (w3.org/WAI/WCAG22/Understanding/focus-visible.html, upd. 2026-09-06). 1.4.3 contrast
  4.5:1 / 3:1 large (same site, contrast-minimum.html, upd. 2026-09-06; WCAG21 TR
  cross-check). 1.4.11 non-text 3:1 (inside focus-visible doc). 2.3.3 motion AAA→adopt
  as best practice (animation-from-interactions.html, upd. 2025-09-16; MDN cross-link).
  4.1.2 Name/Role/Value (name-role-value.html, upd. 2026-07-12).
- **Core Web Vitals**: LCP ≤2.5s, INP ≤200ms, CLS ≤0.1, p75 (developers.google.com/search/
  docs/appearance/core-web-vitals upd. 2025-12-10; web.dev/articles/vitals upd.
  2024-10-31 — agree). Local reading: first-paint list/reader, badge layout shift,
  filter keystroke→paint <150ms headroom.
- **Vue 3**: latest stable **3.5.44** (~2026-10-13; github.com/vuejs/core/releases +
  npmjs.com/package/vue agree); 3.6.x is RC only. We pin vendored 3.5.13 — patch-only
  bump is low-risk BUT package tests pin the Vue hash (test_package_data + hash comment
  in suite); bump = update vendored file + hash pins together, verify offline. Candidate
  for Phase 4 perf/hygiene item, not required for design.
- **Modern CSS in current Chrome (local 154 verified)**: `:has()` Widely available
  (MDN mod. 2026-08-11; caniuse css-has 95.91%, Chrome 105+); avoid `body:has()` perf
  trap. Size container queries baseline Feb 2023, Chrome 106+ (web.dev/baseline;
  caniuse 95.89%) — style queries NOT yet, stick to size. Same-document View
  Transitions Chrome 111+/Safari 18+/FF 144+ (caniuse 92.9%; MDN mod. 2026-09-28) —
  usable as progressive enhancement gated on `prefers-reduced-motion: no-preference`;
  cross-document navigation API is MPA-only, irrelevant.
