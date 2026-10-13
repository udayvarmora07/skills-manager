# Frontend Comprehensive Testing Report — Skills Manager Web UI

**Date:** 2026-09-05
**Target:** Local Web UI (`skillsmgr/webui/` + `skillsmgr/webapp.py`)
**Mode:** Beginner to advanced, real-user E2E + harnesses
**Rule:** Report-first, no repo fixes applied

## Summary

Full layered sweep completed: static baselines, Node JS unit harness, API edge harness, Playwright + Chromium real-browser E2E (beginner, advanced, responsive, keyboard, theme, a11y, XSS, race).

**Totals:**

- Static: `py_compile` OK, `node --check` OK, 47 unittest OK
- `smoke_store.py` PASS, `smoke_web.py` PASS
- Beginner E2E: 12/12 PASS, zero console errors
- Advanced E2E: 34/35 PASS (1 fail = expected 400 logging only)
- Extra suite: 23/24 PASS (1 fail = 2 axe serious findings)
- Responsive overflow 0 px at 1280 / 900 / 640 / 400
- XSS probe inert, dark theme OK, keyboard OK

## Environment

- Backend: stdlib `ThreadingHTTPServer` on `127.0.0.1`, ephemeral port
- Frontend: Vue 3.5.13 vendored, no build step
- Browser: Playwright Chromium 151, headless
- Hermetic: temp `SKILLS_MANAGER_DATA`, temp HOME, `localStorage skillsmgr-scope=global`
- Python 3.12.3, Node v22.22.3
- OS: Linux

## Verified Working

- CRUD create / edit / view / list
- Validation banners (valid + invalid)
- Disable / enable toggle
- Remove to trash, Undo toast, restore, purge with confirm
- Trash tab, search trash placeholder
- Live search with debounce (~220 ms)
- Filters All / Active / Disabled
- Doctor, Stats, History, Templates, New Template
- Export download round-trip, archive import, folder upload
- Sync modal, Install command builder (npx/pnpm/yarn/bunx, uvx rejected)
- Scope switcher, topbar, detail metadata, statusbar, toasts
- Markdown: headings, lists, code fences, inline code, bold, italic, links, quotes, single `<table>`
- Responsive stacking, compact topbar, dark theme, `/` focus, Esc close, Tab order
- `prefers-reduced-motion` media query present
- Zero app `pageerror` across all suites (`ERRORS:[]`)

## Confirmed Bugs

### P1-1 Double-trash DELETE returns 200 twice

**Severity:** P1 data integrity

**Repro:**

```python
DELETE /api/skills/<name>  # 200 trashed
DELETE /api/skills/<name>  # 200 again, should be 404
```

**Observed:**

Second delete returns 200, creates ghost trash dir, duplicate history entry, `GET` still lists skill.

**Root:**

`store.py` `remove()` guard:

```python
if row is None and not skill_dir.is_dir():
```

Trashed row remains with `status='trashed'`, so guard passes after directory moved.

**Evidence:** `api-edge.py` 37 pass / 1 fail.

### P1-2 `formatCompat(array)` renders `0 a`

**Severity:** P1 wrong render, currently latent

**File:** `skillsmgr/webui/app.js:144`

```javascript
function formatCompat(v) {
  if (!v) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") return Object.entries(v).map(([k, val]) => `${k} ${val}`).join(", ");
  return String(v);
}
```

```javascript
formatCompat(["a"]) // "0 a" — wrong
formatTools(["a"])  // "a" — correct
```

Latent because frontmatter serializes lists to flow string and DB drops column, but reachable if API ever returns array.

### P2-1 Invalid `dt` nesting in Path block

**Severity:** P2 a11y serious (`axe dlitem`, 2 nodes)

**File:** `skillsmgr/webui/index.html:249`

Second metadata block is `<div class="meta">` containing `<div><dt>Path`, so `dt` parent chain is `div`, not `dl`.

**Fix:** change Path wrapper to `dl` or replace `dt/dd` with `div/span`.

### P2-2 Chip count contrast fails AA

**Severity:** P2 a11y serious (`axe color-contrast`, 3 nodes)

**Selector:** `.chip:nth-child(1) > .chip-count`

Cause: `var(--text-muted)` at 11 px with `opacity: 0.8` on surface.

**Evidence:**

```text
AXE-ALL:[["color-contrast","serious",3],["dlitem","serious",2]]
ERRORS:[]
```

### P2-3 Import hint advertises `.zip`, backend rejects it

**Severity:** P2 UX / contract mismatch

UI `index.html:617`:

```text
.tar.gz, .tar, .zip
```

Backend `webapp.py:723` allows only `.tar.gz/.tgz/.tar` → 400.

**Fix:** remove `.zip` from hint or add zip support.

### P2-4 CRLF markdown heading fails in pure function

**Severity:** P2 latent

`renderMarkdown` splits on `\n` only, so `# T\r` misses heading regex and renders as paragraph.

Masked live because Python `read_text` universal newlines normalize on file round-trip. Live `C1-crlf-heading h1=1` passes, Node harness `md-crlf` fails.

### P2-5 Oversize POST resets connection

**Severity:** P2 UX

`PUT /api/import` >25 MB (`MAX_BODY_BYTES`) rejects correctly but client sees `BrokenPipe` / connection reset instead of clean JSON error.

### P2-6 Detail compat fields silently empty if raw fetch fails

**Severity:** P2 UX

DB schema has no `compatibility` / `allowed_tools` columns. `Store.get/list` never return them. Detail view masks this by re-fetching `/raw` and merging via `parseFrontmatter`. If raw fetch fails, fields show `—` with no warning.

## False Positives

- Duplicate-create 400 in console is browser auto-log of failed `fetch`, app toast handles correctly. Not an app bug.
- `smoke_web.py` not HOME-hermetic for `doctor?scope=all` because scopes resolve via `Path.home`. Assert shape, not emptiness.

## Test Evidence

Session harnesses:

- `js-harness.js` — 60 pass / 2 fail (`md-crlf`, `compat-arr`)
- `api-edge.py` — 37 pass / 1 fail (double-trash)
- `e2e-beginner.py` — 12/12 PASS
- `e2e-advanced-pw.py` — 34/35
- `e2e-extra-pw.py` — 23/24 + axe audit + reduced-motion
- `a11y/node_modules/axe-core/axe.min.js` — axe injector
- Screenshots: `shot-width-*.png`, `shot-dark.png`, `shot-xss.png`, `shot-adv-*.png`, `e2e-export.tar.gz`

## Selectors / Gotchas Learned

- Theme button has no emoji, use `aria-label="Toggle theme"`
- Scope `All` chip vs `.filters All` chip are distinct
- `.detail h1` matches title + body h1, use `.detail-head h1`
- `.detail .meta` matches `dl` + `div`, scope to `dl.meta`
- Template submit label is `Create template`
- `PLAYWRIGHT_BROWSERS_PATH` must point at real home when HOME redirected
- `smoke_web.py` leaks real `~/.agents/skills` into doctor scope-all

## Next

Awaiting user pick of fixes. No repo code changed in this testing pass.
