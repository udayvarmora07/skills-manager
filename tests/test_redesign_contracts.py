"""Contracts for the Warm Instrument redesign (2026-10-08).

These pin behaviour that the redesign introduced or changed, and they were
written against the pre-change sources first so that a green run means
something. Three groups:

* the **observed state vocabulary**, which gained a state;
* the **context-budget meter**, which is new markup plus new arithmetic;
* the **design contract**, which is a file and a stylesheet that must agree.

Where a rule can be exercised, it is exercised against the real source in a
Node VM rather than pattern-matched. A test that reads a string proves the
string is present; a test that runs ``observedStateFor`` proves the rule.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "skillsmgr" / "webui"
DOMAIN_JS = WEBUI / "domain.js"
APP_JS = WEBUI / "app.js"
INDEX_HTML = WEBUI / "index.html"
CSS = WEBUI / "styles.css"
DESIGN_MD = ROOT / "DESIGN.md"
FONTS = WEBUI / "static" / "fonts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slice(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _domain_script(body: str) -> dict:
    """Run ``body`` against the real domain.js in a Node VM and parse stdout."""
    script = f"""
const fs = require('fs'), vm = require('vm');
const sandbox = {{ window: {{}}, document: {{}} }};
vm.runInNewContext(fs.readFileSync({str(DOMAIN_JS)!r}, 'utf8'), sandbox);
const D = sandbox.window.SkillManagerDomain;
{body}
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"node harness failed:\n{result.stderr}")
    return json.loads(result.stdout)


class ObservedStateVocabularyTests(unittest.TestCase):
    """A refused symlink is not a malformed document.

    The backend already carries the precise reason in ``decode_error``; the UI
    collapsed every reason into the word "Malformed". On this machine that
    mislabelled 301 of 1,962 instances and pointed the reader at the wrong
    remedy — repairing frontmatter, when the actual fix is to stop linking or
    to copy the tree in.
    """

    LINK = {
        "name": "linked-skill",
        "malformed": True,
        "decode_error": "path escapes managed root: /home/u/.agents/skills/linked-skill",
    }
    TRULY_MALFORMED = {"name": "broken", "malformed": True, "decode_error": "undecodable byte at 0x41"}
    FINE = {"name": "fine"}

    def test_a_link_escape_is_named_as_a_link_not_as_malformed(self):
        out = _domain_script(f"""
console.log(JSON.stringify({{
  state: D.observedStateFor({json.dumps(self.LINK)}),
  keys: D.observedStateKeys({json.dumps(self.LINK)}),
  labels: D.OBSERVED_STATE_LABELS,
}}));
""")
        self.assertEqual(out["state"], "linked")
        self.assertEqual(out["keys"], ["linked"])
        self.assertEqual(out["labels"]["linked"], "Linked outside root")

    def test_a_genuinely_malformed_document_still_says_malformed(self):
        # The distinction must not swallow the state it replaced.
        out = _domain_script(f"""
console.log(JSON.stringify({{
  state: D.observedStateFor({json.dumps(self.TRULY_MALFORMED)}),
  keys: D.observedStateKeys({json.dumps(self.TRULY_MALFORMED)}),
}}));
""")
        self.assertEqual(out["state"], "malformed")
        self.assertEqual(out["keys"], ["malformed"])

    def test_a_link_escape_is_still_an_unreadable_document(self):
        # Every existing count and predicate keys off `malformedDocument`, so
        # that must stay true. This is a finer reading of one observation, not
        # a new observation that the old counters would miss.
        out = _domain_script(f"""
const o = D.observeRecord({json.dumps(self.LINK)});
console.log(JSON.stringify({{ malformed: o.malformedDocument, link: o.linkEscape }}));
""")
        self.assertTrue(out["malformed"])
        self.assertTrue(out["link"])

    def test_a_clean_record_is_still_active(self):
        out = _domain_script(f"""
console.log(JSON.stringify({{
  state: D.observedStateFor({json.dumps(self.FINE)}),
  keys: D.observedStateKeys({json.dumps(self.FINE)}),
}}));
""")
        self.assertEqual(out["state"], "active")
        self.assertEqual(out["keys"], ["active"])

    def test_every_state_the_seam_can_return_has_a_label(self):
        # A key with no label renders as a bare identifier in the UI.
        states = {"active", "disabled", "invalid", "malformed", "linked",
                  "unaddressable", "divergent"}
        labels = _domain_script("console.log(JSON.stringify(D.OBSERVED_STATE_LABELS));")
        self.assertEqual(set(labels), states)
        for key in states:
            self.assertTrue(labels.get(key), f"{key} has no label")


class ContextBudgetMeterTests(unittest.TestCase):
    """The meter is the most consequential thing this tool observes.

    Three scope roots on this machine each hold more skill text than an entire
    1M context window. Nothing errors, every file is valid, and the agent works
    from half its own rules — so the meter leads the Overview.
    """

    def _app(self, scope_tokens, window_tokens):
        # Computeds reference each other through `this`, so the harness needs a
        # context whose own properties resolve the computeds rather than a flat
        # data object — otherwise `overBudgetScopeCount` cannot see
        # `scopeBudgetRows` and the test would be exercising a harness bug.
        script = f"""
const fs = require('fs'), vm = require('vm');
const domainSandbox = {{ window: {{}}, document: {{}} }};
vm.runInNewContext(fs.readFileSync({str(DOMAIN_JS)!r}, 'utf8'), domainSandbox);
const sandbox = {{
  window: {{SkillManagerDomain: domainSandbox.window.SkillManagerDomain}},
  Vue: {{createApp(app){{sandbox.app = app; return {{mount(){{}}}};}}, nextTick(){{}}}},
  localStorage: {{getItem(){{return null;}}, setItem(){{}}}},
  document: {{addEventListener(){{}}, removeEventListener(){{}}, documentElement:{{dataset:{{}}}},
             querySelectorAll(){{return[];}}, querySelector(){{return null;}}}},
  setTimeout, clearTimeout,
}};
vm.runInNewContext(fs.readFileSync({str(APP_JS)!r}, 'utf8'), sandbox);
const c = sandbox.app.computed;
const data = {{
  scopes: {json.dumps(scope_tokens)}.map((t, i) => ({{ id: 's' + i, label: 'Scope ' + i, tokens: t, count: 1 }})),
  budget: {{ window_tokens: {window_tokens} }},
}};
const ctx = Object.assign({{}}, data);
for (const name of ['scopeBudgetRows', 'overBudgetScopeCount', 'budgetAxisMax', 'scopeThresholdPos']) {{
  Object.defineProperty(ctx, name, {{ get: () => c[name].call(ctx) }});
}}
const rows = ctx.scopeBudgetRows;
console.log(JSON.stringify({{
  rows: rows.map(r => ({{ id: r.id, pct: r.pct, rounded: r.pctRounded, over: r.over }})),
  over: ctx.overBudgetScopeCount,
  axis: ctx.budgetAxisMax,
  threshold: ctx.scopeThresholdPos,
}}));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(f"node harness failed:\n{result.stderr}")
        return json.loads(result.stdout)

    def test_a_root_over_one_window_is_reported_as_over(self):
        out = self._app([1_210_856, 1_189_659, 1_110_822, 406_580], 1_000_000)
        self.assertEqual([r["over"] for r in out["rows"]][:3], [True, True, True])
        self.assertFalse(out["rows"][3]["over"])
        self.assertEqual(out["over"], 3)

    def test_rows_are_ordered_largest_first(self):
        out = self._app([10, 900_000, 400_000], 1_000_000)
        self.assertEqual([r["pct"] for r in out["rows"]], sorted(
            (r["pct"] for r in out["rows"]), reverse=True))

    def test_the_axis_runs_past_one_hundred_percent(self):
        # On a 0-100% axis, 111% and 121% both clamp to a full bar and the
        # chart hides the one thing it exists to show.
        out = self._app([1_210_856, 1_189_659], 1_000_000)
        self.assertGreaterEqual(out["axis"], 125)
        self.assertGreater(out["axis"], 121.0)
        # The 100% mark therefore sits inside the track, not at its end.
        self.assertLess(float(out["threshold"].rstrip("%")), 100.0)

    def test_an_empty_window_does_not_divide_by_zero(self):
        out = self._app([500_000], 0)
        self.assertEqual(out["rows"][0]["pct"], 0)
        self.assertFalse(out["rows"][0]["over"])

    def test_the_hero_is_the_first_block_of_the_overview(self):
        html = _read(INDEX_HTML)
        shell = _slice(html, 'v-if="view === \'overview\'"', "</section>\n\n          <section class=\"attention-queue\"")
        self.assertIn('class="budget-hero"', shell)
        self.assertIn("scopeBudgetRows", shell)
        # It must not claim to know anything the API did not report.
        self.assertNotIn("winner", shell.lower())

    def test_meter_colour_is_scoped_to_the_fill_not_the_label(self):
        # Regression: the percentage label and the bar share a class name, and
        # an unscoped background rule painted the figure on a block of colour.
        css = _read(CSS)
        self.assertRegex(css, r"\.scope-meter-fill\.pct-bad\s*\{\s*background:\s*var\(--err\)")
        # An unscoped background rule is the regression: it paints the figure.
        self.assertNotRegex(css, r"^\.pct-bad\s*\{[^}]*background", re.M)


class DesignContractTests(unittest.TestCase):
    """DESIGN.md is the contract; the stylesheet and the package are its proof."""

    def test_the_contract_file_exists_and_carries_tokens_and_rationale(self):
        doc = _read(DESIGN_MD)
        self.assertTrue(doc.startswith("---\n"), "DESIGN.md must open with token front matter")
        self.assertIn("colors:", doc)
        self.assertIn("typography:", doc)
        self.assertIn("## Don't change", doc)

    def test_no_runtime_font_cdn_anywhere_in_the_frontend(self):
        for path in (CSS, INDEX_HTML, APP_JS, DOMAIN_JS):
            text = _read(path)
            self.assertNotIn("fonts.googleapis.com", text, f"{path.name} fetches a font CDN")
            self.assertNotIn("fonts.gstatic.com", text, f"{path.name} fetches a font CDN")

    def test_the_typeface_is_vendored_not_declared_only(self):
        # "Declared but never shipped" is a scanner finding for good reason:
        # the CSS names a face the page never loads, so everyone sees the
        # fallback. Assert the bytes exist, not just the @font-face.
        #
        # This no longer names a family. It derives the contract from the
        # shipped face stylesheet, so swapping the typeface is a data edit and
        # a future change cannot quietly stop shipping the faces the page uses.
        self.assertTrue(FONTS.is_dir(), "static/fonts/ is missing")
        sheets = sorted(FONTS.glob("*.css"))
        self.assertTrue(sheets, "static/fonts/ has no face stylesheet to derive from")
        declared = [s for sh in sheets
                    for s in re.findall(r"url\(([^)]+)\)", sh.read_text(encoding="utf-8"))]
        self.assertGreaterEqual(len(declared), 4, declared)
        for src in declared:
            src = src.strip().strip("'\"")
            self.assertNotIn("http", src, f"{src} is a remote reference")
            self.assertTrue((FONTS / src).is_file(), f"{src} does not exist beside {sheets[0].name}")
            self.assertGreater((FONTS / src).stat().st_size, 1000, f"{src} looks empty")
        # Every shipped face is declared. An orphan woff2 is dead weight that
        # still reads as "the font is vendored" to whoever greps for it.
        declared_names = {p.strip().strip("'\"") for p in declared}
        for face in FONTS.glob("*.woff2"):
            self.assertIn(face.name, declared_names,
                          f"{face.name} is vendored but nothing loads it")

    def test_the_vendored_faces_are_not_restricted_away_from_ascii(self):
        """The first vendoring pass shipped faces that covered no ASCII.

        Six @font-face rules were declared and 176 KB of woff2 sat in the
        package, but every one of them carried only the `latin-ext`
        unicode-range. No English character in this interface matched any
        declared face, so the browser never fetched one, never reported an
        error, and every visitor silently got the fallback — while the file
        existed and every "is the font vendored" check passed.

        This is the same failure as "declared but never shipped", one level
        down: the bytes are present, the declaration is present, and the page
        still renders in the wrong typeface. Assert the glyph coverage.

        Checked *per face* rather than once per file: the original bug lived
        in six rules and one stray `latin-ext` on any one of them is the same
        defect. A face with no unicode-range at all is accepted and is the
        safer default here — the browser still falls back per-glyph for
        characters the face lacks, which is what a skill body needs.
        """
        for sheet in sorted(FONTS.glob("*.css")):
            css = sheet.read_text(encoding="utf-8")
            for block in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
                face = re.search(r"font-family:\s*([^;]+);", block)
                label = face.group(1).strip() if face else "?"
                unicode_range = re.search(r"unicode-range:\s*([^;]+);", block)
                if unicode_range:
                    self.assertIn(
                        "U+0000-00FF", unicode_range.group(1),
                        f"{sheet.name}: {label} is restricted by unicode-range to "
                        f"{unicode_range.group(1).strip()} — basic Latin would "
                        f"silently render in the fallback")

    def test_the_woff2_files_are_real_woff2_containers(self):
        """A `.woff2` extension is a claim; `wOF2` is the proof.

        Cheap, stdlib, and it catches the whole class of "the bytes are not a
        font" (a truncated download, an HTML error page saved under the name,
        a placeholder). The heavier question — does the face actually carry the
        glyphs — is answered in a real browser by
        ``tests/e2e/test_font_render.py``.
        """
        for face in sorted(FONTS.glob("*.woff2")):
            head = face.read_bytes()[:4]
            self.assertEqual(head, b"wOF2", f"{face.name} is not a WOFF2 container")

    def test_a_licence_file_ships_beside_the_faces(self):
        # Vendored type is still someone's licensed work. The file records
        # which licence and who holds it; nothing here interprets the licence,
        # it just refuses to ship third-party bytes without one.
        licences = [p.name for p in FONTS.iterdir() if "LICEN" in p.name.upper()]
        self.assertTrue(licences, "static/fonts/ ships woff2 with no licence file")

    def test_the_stylesheet_imports_the_vendored_faces(self):
        imports = re.findall(r'@import\s+url\("([^"]+)"\)', _read(CSS))
        sheets = {p.name for p in FONTS.glob("*.css")}
        font_imports = [i for i in imports if i.startswith("static/fonts/")]
        self.assertTrue(font_imports, "styles.css imports no vendored face stylesheet")
        for imp in font_imports:
            self.assertIn(imp.rsplit("/", 1)[-1], sheets,
                          f"styles.css imports {imp}, which is not in static/fonts/")

    def test_the_palette_is_not_a_named_default(self):
        # Two clusters this tool's own reference list names explicitly: cream
        # ground with terracotta (the prototype's palette) and near-black with
        # one vermilion accent. Neither may come back.
        for selector in ('[data-theme="light"], [data-theme="system"] {',
                         '[data-theme="dark"] {'):
            block = _slice(_read(CSS), selector, "\n}\n")
            for banned, why in (
                ("#faf7f1", "the prototype's parchment ground"),
                ("#9e4415", "the prototype's copper accent"),
                ("#d97757", "the catalog's terracotta"),
                ("#16130e", "the prototype's near-black ground"),
                ("#e08a4e", "the prototype's vermilion"),
            ):
                self.assertNotIn(banned, block.lower(),
                                 f"{why} is back in {selector}")

    def test_no_easing_curve_overshoots(self):
        # A y control point above 1.0 is the bounce/elastic tell; it makes a
        # dense tool feel unsteady and reads dated.
        #
        # The y points are index 1 and index 3 in cubic-bezier(x1, y1, x2, y2).
        # This first checked indices 1 and 2, which are y1 and *x2* — so it read
        # `0.2, 0.9, 0.3, 1.15` (the exact curve it was written to catch) as
        # clean, and passed vacuously against the tree that had it. The
        # red-first run is what surfaced it.
        css = _read(CSS)
        checked = 0
        for curve in re.findall(r"cubic-bezier\(([^)]*)\)", css):
            parts = [p.strip() for p in curve.split(",")]
            if len(parts) != 4:
                continue
            checked += 1
            for index, name in ((1, "y1"), (3, "y2")):
                self.assertLessEqual(
                    float(parts[index]), 1.0,
                    f"{name} overshoots: cubic-bezier({curve})")
        self.assertGreater(checked, 0, "no cubic-bezier found — the check is vacuous")

    def test_the_gate_that_enforces_the_palette_exists_and_passes(self):
        script = ROOT / "check_design_tokens.py"
        self.assertTrue(script.exists(), "the design gate is missing")
        result = subprocess.run(["python3", str(script)], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()