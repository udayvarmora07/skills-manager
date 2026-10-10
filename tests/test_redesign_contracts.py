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


class IconSpriteTests(unittest.TestCase):
    """The vendored Lucide subset: declaration, licence, and resolution.

    Every other check in this repository reads a *declaration*. The one time a
    real defect lived here, every declaration read green while the page rendered
    something else — the vendored typeface that shipped six ``latin-ext`` faces
    and no ASCII glyphs. So this class deliberately pins three different things
    a declaration alone would miss:

    1. every ``<app-icon name=…>`` in the template resolves to a symbol;
    2. every symbol is reachable and used, so the subset stays a subset;
    3. the sprite carries its ISC licence and loads nothing remote.

    Whether the strokes actually *paint* needs a font-and-paint engine, so it
    lives in ``tests/e2e/``; the stdlib half here runs on every ordinary test
    run and must never be the only thing that could have caught it.
    """

    ICONS = WEBUI / "static" / "icons"
    SPRITE = ICONS / "lucide-sprite.svg"
    LICENCE = ICONS / "Lucide-ISC-LICENSE.txt"

    @classmethod
    def setUpClass(cls) -> None:
        cls.html = _read(INDEX_HTML)
        cls.sprite = _read(cls.SPRITE)
        cls.app = _read(APP_JS)
        cls.css = _read(CSS)
        cls.declared = set(re.findall(r'<symbol\s+id="i-([a-z0-9-]+)"', cls.sprite))
        cls.used = set(re.findall(r'<app-icon\s+name="([a-z0-9-]+)"', cls.html))

    def test_sprite_and_licence_ship(self):
        self.assertTrue(self.SPRITE.is_file(), f"missing {self.SPRITE}")
        self.assertTrue(self.LICENCE.is_file(), f"missing {self.LICENCE}")
        self.assertIn("ISC License", _read(self.LICENCE))

    def test_the_sprite_declares_at_least_one_symbol(self):
        # An empty sprite renders every icon as an empty box and reports nothing.
        self.assertGreaterEqual(len(self.declared), 20)

    def test_every_icon_used_resolves_to_a_symbol(self):
        # The "declared but never shipped" failure, one level down: an
        # <app-icon> naming a symbol the sprite does not define renders blank.
        missing = sorted(self.used - self.declared)
        self.assertEqual(missing, [], f"icons used but not in the sprite: {missing}")

    def test_every_declared_symbol_is_used(self):
        # The sprite is a *subset*. An unused symbol means the subset stopped
        # being curated, which is how a 2 000-icon sprite becomes a 200 KB page.
        unused = sorted(self.declared - self.used)
        self.assertEqual(unused, [], f"symbols declared but never used: {unused}")

    def test_the_sprite_loads_nothing_remote(self):
        # The SVG namespace is spelled http://… by definition and is not a
        # fetch; only a reference the browser would resolve over the network
        # is a defect, because this app must work offline.
        remote = [r for r in re.findall(r'(?:href|src)\s*=\s*"([^"]*)"', self.sprite)
                  if not r.startswith("#")]
        remote += re.findall(r"url\(\s*['\"]?(https?://[^'\")]*)", self.sprite)
        self.assertEqual(remote, [], f"sprite loads a remote resource: {remote}")

    def test_the_sprite_is_inlined_so_icons_work_offline(self):
        # A sprite fetched over the network is a second round trip and a second
        # failure mode; the whole reason for inlining it is offline operation.
        self.assertIn('class="icon-sprite"', self.html)
        self.assertLess(
            self.html.index('class="icon-sprite"'),
            self.html.index('<app-icon'),
            "the sprite must precede its first use so it renders on first paint",
        )

    def test_no_icon_is_self_closed_in_the_markup(self):
        # HTML has no self-closing syntax for an unknown element. `<app-icon/>`
        # opens an element and swallows the rest of its parent — which silently
        # ate the `v-else` sibling of the theme toggle and left Vue failing to
        # compile the whole template. Nothing in a DOM dump shows this; the
        # template simply renders nothing. Every icon pairs its tags explicitly.
        self.assertNotRegex(
            self.html, r"<app-icon\b[^>]*?/>",
            "self-closed <app-icon/> in HTML markup; write </app-icon>",
        )
        opened = len(re.findall(r"<app-icon\b", self.html))
        closed = len(re.findall(r"</app-icon>", self.html))
        self.assertEqual(opened, closed, f"{opened} <app-icon> opened, {closed} closed")

    def test_no_inline_icon_geometry_remains_in_the_template(self):
        # One icon, one source. A stray hand-drawn <path> beside the sprite is
        # how the set drifts back to 40 unrelated shapes.
        #
        # Exactly one exception, and it is not an ICON: the product wordmark.
        # Lucide ships no wordmark, so a stacked-layers mark belongs to this
        # product; putting it in static/icons/lucide-sprite.svg would file a
        # project-authored glyph under someone else's ISC licence. The
        # exception is a class, not a blank cheque — the wordmark must be the
        # only inline geometry, must appear once, and must be stroked (no
        # filled path, which is what would let it stand in for an icon).
        body = _slice(self.html, "<body>", "</body>")
        leftovers = [m for m in re.finditer(r"<svg\b[^>]*>(.*?)</svg>", body, re.S)
                     if "<symbol" not in m.group(1) and "<use" not in m.group(1)
                     and 'class="brand-glyph"' not in m.group(0)]
        self.assertEqual(
            [m.group(0)[:80] for m in leftovers], [],
            "inline SVG geometry outside the sprite; use <app-icon name=…>",
        )

    def test_the_wordmark_is_the_only_inline_svg_and_it_is_stroked(self):
        body = _slice(self.html, "<body>", "</body>")
        marks = re.findall(r'<svg class="brand-glyph".*?</svg>', body, re.S)
        self.assertEqual(len(marks), 1, f"expected one wordmark, found {len(marks)}")
        mark = marks[0]
        self.assertNotIn('fill="currentColor"', mark,
                         "a filled wordmark can stand in for an icon; keep it stroked")
        self.assertIn('stroke="currentColor"', mark)
        # A wordmark with no geometry is an empty box: the shape IS the mark.
        self.assertGreaterEqual(len(re.findall(r"<path\b", mark)), 2,
                                "the wordmark needs its stacked layers")

    def test_the_component_is_registered_and_validates_its_names(self):
        # A misspelled name must be loud. Rendering nothing is the failure this
        # seam exists to prevent, so the component reads the sprite's own id
        # list and marks anything it cannot resolve.
        self.assertIn("components: { AppIcon }", self.app)
        # Not `.component("app-icon", AppIcon)` on the `createApp` return value:
        # every Node harness in tests/ stubs that as `{ mount() {} }`, so a
        # chained call throws before a single one of them can run.
        self.assertNotIn('.component("app-icon"', self.app)
        self.assertIn('querySelectorAll(".icon-sprite symbol")', self.app)
        self.assertIn("data-missing-icon", self.app)

    def test_icons_are_hidden_from_assistive_tech_by_default(self):
        # Decorative by default: the sprite is aria-hidden, and the component
        # stamps aria-hidden on every rendered instance.
        self.assertIn('class="icon-sprite" aria-hidden="true"', self.html)
        self.assertIn('"aria-hidden": "true"', self.app)

    def test_the_sprite_is_hidden_and_a_missing_icon_is_visible(self):
        self.assertRegex(self.css, r"\.icon-sprite\s*\{\s*display:\s*none")
        self.assertRegex(self.css, r"\.app-icon\[data-missing-icon\]")

    def test_packaging_ships_the_icon_directory(self):
        pyproject = _read(ROOT / "pyproject.toml")
        self.assertIn('"webui/static/icons/*"', pyproject,
                      "a build that drops the sprite ships a UI with blank icons")

    def test_the_package_data_gate_verifies_the_sprite(self):
        source = _read(ROOT / "check_package_data.py")
        self.assertIn("verify_icon_sprite", source)


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


class DesignScaleContractTests(unittest.TestCase):
    """The v2 scale contract (DESIGN.md, task 1.3).

    Every assertion here corresponds to a defect that shipped: the space scale
    declared two names for one step, the doc/stylesheet comparison compared
    nothing, and a third palette existed that no gate could reach. Each is
    asserted against the shipped stylesheet rather than against this file.
    """

    def _root(self) -> dict:
        css = _read(CSS)
        body = css[css.index(":root {"):]
        depth, out, i = 0, "", 0
        while i < len(body):
            ch = body[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", out))
            if depth >= 1:
                out += ch
            i += 1
        self.fail("unterminated :root block")

    def test_the_space_scale_is_a_real_sequence(self):
        """`--s7` and `--s9` were both 32px, so "the ninth step" was a lie.

        Nothing noticed, because no check read the scale. Assert the whole
        step set, not just that the tokens exist.
        """
        root = self._root()
        want = {"--s1": "4px", "--s2": "8px", "--s3": "12px", "--s4": "16px",
                "--s5": "20px", "--s6": "24px", "--s7": "32px", "--s9": "48px"}
        got = {k: v.strip() for k, v in root.items() if k in want}
        self.assertEqual(got, want, f"space scale drifted: {got}")
        self.assertNotEqual(root["--s9"].strip(), root["--s7"].strip(),
                            "--s9 and --s7 are the same step again")

    def test_the_radius_steps_ascend_and_the_relationship_is_the_contract(self):
        root = self._root()
        ctl = float(root["--r-ctl"].removesuffix("px"))
        panel = float(root["--r-panel"].removesuffix("px"))
        dialog = float(root["--radius"].removesuffix("px"))
        self.assertLess(ctl, panel, "a panel must be squarer than a control")
        self.assertLess(panel, dialog, "a dialog must be squarer than a panel")

    def test_the_type_scale_is_six_declared_steps(self):
        root = self._root()
        for step in ("--t-meta", "--t-table", "--t-ui", "--t-prose",
                     "--t-page", "--t-empty"):
            self.assertIn(step, root, f"{step} is missing from the token layer")

    def test_motion_is_inside_the_band_and_does_not_overshoot(self):
        root = self._root()
        ms = int(re.match(r"(\d+)ms", root["--dur"].strip()).group(1))
        self.assertGreaterEqual(ms, 100)
        self.assertLessEqual(ms, 160, "motion outside 100-160ms reads dated")
        for curve in re.findall(r"cubic-bezier\(([^)]*)\)", _read(CSS)):
            parts = [p.strip() for p in curve.split(",")]
            if len(parts) == 4:
                self.assertLessEqual(float(parts[1]), 1.0, f"y1 overshoots: {curve}")
                self.assertLessEqual(float(parts[3]), 1.0, f"y2 overshoots: {curve}")

    def test_there_is_no_third_palette_behind_the_two_themes(self):
        """`preferences.js` resolves `system` to an explicit theme *before*
        styles.css loads, so a prefers-color-scheme palette can only fire in a
        window that does not exist. One did, with an orange accent and surfaces
        from before the palette was ever measured — and every test measured the
        two explicit blocks, so every test passed.
        """
        css = _read(CSS)
        self.assertNotRegex(
            css, r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{[^@]*?\[data-theme",
            "a media-query palette shadows the two measured themes")
        self.assertNotIn("#e7a06f", css,
                         "the stale system-dark accent is back")

    def test_the_document_and_the_stylesheet_are_actually_compared(self):
        """The v1 check looked tokens up without the `--` prefix, got None for
        every one, and skipped all nine comparisons behind an `if css_hex`
        guard: a drift check that had never compared anything. Assert the
        lookup itself, which is where that bug lived.
        """
        source = _read(ROOT / "check_design_tokens.py")
        self.assertIn('tokens.get(f"--{css_name}")', source,
                      "the doc/stylesheet comparison is looking up an unprefixed name again")
        self.assertNotIn("if css_hex and doc_hex != css_hex", source,
                         "the vacuous comparison guard is back")


if __name__ == "__main__":
    unittest.main()

class TypeScaleIsConsumedTests(unittest.TestCase):
    """The scale must be the thing the UI reads, not a table beside it.

    `check_design_tokens.py` owns the exhaustive form of this (every declared
    size in the stylesheet, every step, the exceptions). It runs in the `docs`
    CI job. This is the same contract in the `unit` job, so a regression is
    caught by the suite a contributor actually runs — and, unlike the previous
    floor check, it resolves the tokens rather than scanning for literals that
    may no longer be there.
    """

    STEPS = ("--t-meta", "--t-table", "--t-ui", "--t-prose", "--t-page", "--t-empty")

    def _css(self) -> str:
        return _read(CSS)

    def test_the_six_steps_are_rem_sizes_in_ascending_order(self):
        root = re.search(r":root \{(.*?)\n\}", self._css(), re.S).group(1)
        sizes = []
        for step in self.STEPS:
            m = re.search(re.escape(step) + r":\s*([0-9.]+)rem", root)
            self.assertIsNotNone(m, f"{step} is not a rem size; `font-size:` cannot consume it")
            sizes.append(float(m.group(1)))
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(len(set(sizes)), len(sizes), "two steps share one size")

    def test_no_rule_declares_an_off_scale_font_size(self):
        """The cascade may only name a step, or one of the named exceptions."""
        css = re.sub(r"/\*.*?\*/", "", self._css(), flags=re.S)
        allowed = {
            "1.125rem": 'html[data-text-size="large"]',  # rescales html itself
            "0": "the two narrow-breakpoint glyph rules",
        }
        for value in re.findall(r"font-size:\s*([^;{}]+)", css):
            value = value.strip()
            if value.startswith("var("):
                self.assertIn(value, {f"var({s})" for s in self.STEPS},
                              f"{value} is not one of the six steps")
            elif value not in allowed:
                self.fail(f"off-scale font-size {value!r}; use a step or add a reason")

    def test_every_declared_step_is_read_by_at_least_one_rule(self):
        css = self._css()
        used = set(re.findall(r"font-size:\s*var\((--t-[a-z]+)\)", css))
        for step in self.STEPS:
            self.assertIn(step, used, f"{step} is declared and read by nothing")
