"""The vendored typeface must actually render — in a browser, not in a string.

Why this file exists at all
--------------------------
This repository has claimed "the font is vendored" more than once and caught the
real defect only by rendering. The first pass declared six ``@font-face`` rules
carrying only a ``latin-ext`` unicode-range: 176 KB of woff2 sat in the package,
every "is the font vendored" check passed, and not one English character in the
interface matched any declared face — so the browser fetched nothing, reported no
error, and every visitor silently got the fallback. Reading a stylesheet cannot
catch that. Measuring a rendered probe can.

So this is deliberately not a unittest. It needs a real font engine, which means
Playwright, which lives in the project venv (RULES #9 forbids installing one
globally). The stdlib half of the same contract (faces declared, files shipped,
none restricted away from ASCII) lives in ``tests/test_redesign_contracts.py``
and always runs.

How this file is collected — read this before trusting a green run
----------------------------------------------------------------
**`unittest discover -s tests` does not reach this directory.** There is no
``__init__.py``, so discovery never recurses into it. That is deliberate: the CI
unit job must not launch a browser. The consequence, stated plainly because it
was previously claimed away, is that **these tests are not skipped when
Playwright is absent — they are never collected at all**, and emit no skip line,
no skip count and no exit-code signal. A green `discover` run is *silent* about
this file.

Run it explicitly (see ``tests/e2e/README.md``). When Playwright or the dev
server is missing, the explicit run reports ``skipped``, which is a green
result: **a skip here means the evidence was NOT produced**, not that the
contract holds.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_font_render.py
"""

from __future__ import annotations

import os
import sys
import re
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _live_server  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "skillsmgr" / "webui" / "static" / "fonts"
FACE_CSS = FONTS / "geist.css"
CSS = ROOT / "skillsmgr" / "webui" / "styles.css"

#: Probe strings spanning the ASCII the interface actually renders: prose,
#: figures, and a path. A face with partial coverage passes a single letter; a
#: face with none fails all of these.
PROBES = (
    "Hamburgefonstiv 0123456789",
    "The quick brown fox jumps over the lazy dog",
    "/home/user/.claude/skills/my-skill/SKILL.md",
    "Malformed, Unaddressable, Divergent",
)

#: A family that cannot exist. The browser resolves it to its default face, so
#: measuring against it answers "did the vendored face actually get used".
PHANTOM = "SkillsMgrPhantomFaceThatDoesNotExist"


def _declared_faces() -> list[tuple[str, int]]:
    """``(family, weight)`` for every ``@font-face`` the stylesheet declares.

    Weights matter, and reading only the family names hid that. ``@font-face``
    declares *pairs*: a family is not loaded, it is loaded at a weight. An
    earlier version of this file probed only the default weight, so a face
    restricted at 500 or 600 — the whole class of defect this test exists to
    catch — measured as a healthy page. Measured, not assumed: with
    ``unicode-range: U+0100-02AF` injected on the Medium face, the 400 and 600
    probes stayed distinct from the phantom and only weight **500** collapsed
    onto it, while ``document.fonts.check()`` cheerfully returned ``True`` at
    all three. Every declared pair is probed at its own weight now.
    """
    css = FACE_CSS.read_text(encoding="utf-8")
    out: list[tuple[str, int]] = []
    for block in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
        family = re.search(r"font-family:\s*([^;]+);", block)
        weight = re.search(r"font-weight:\s*([^;]+);", block)
        if not family:
            continue
        name = family.group(1).strip().strip("'\"")
        try:
            value = int((weight.group(1).strip() if weight else "400"))
        except ValueError:
            value = 400
        pair = (name, value)
        if pair not in out:
            out.append(pair)
    return out


def _declared_families() -> list[str]:
    """Family names the shipped face stylesheet declares, in order."""
    out: list[str] = []
    for name, _ in _declared_faces():
        if name not in out:
            out.append(name)
    return out


#: The frontend sources whose *text* the user actually sees. The sprite is SVG
#: ``<path>`` geometry and carries no glyphs, so it is deliberately absent from
#: this list — a claim that the sprite needed font coverage would be a fiction.
TEXT_SOURCES = ("index.html", "styles.css", "app.js", "domain.js", "preferences.js")

#: A Private Use Area codepoint. No font — vendored or system — carries a glyph
#: for one, so it is the reference for "this browser painted nothing real".
NOTDEF = ""


def shipped_glyphs() -> list[str]:
    """Every non-ASCII codepoint the shipped frontend can put on screen.

    Derived from the sources rather than listed here, because a hand-kept list
    is a claim about the past: it cannot notice the glyph someone added
    yesterday, and it silently keeps passing after that glyph ships broken. This
    is the whole point of the row that produced it — a test that reads the
    ``@font-face`` block proves a file exists, not that a glyph painted, and a
    test that reads a hardcoded inventory proves the inventory was correct when
    it was written.
    """
    found: set[str] = set()
    for name in TEXT_SOURCES:
        path = ROOT / "skillsmgr" / "webui" / name
        if not path.exists():
            continue
        for ch in path.read_text(encoding="utf-8"):
            if ord(ch) > 127 and ch != NOTDEF:
                found.add(ch)
    return sorted(found)


def _base_url() -> str:
    # 6.2f: one helper owns the base URL for every suite that needs a running
    # web UI, so a sweep launched without `.redesign/dev.sh start` brings up its
    # own isolated server instead of reporting ERR_CONNECTION_REFUSED as if the
    # tree were broken. See tests/e2e/_live_server.py for the order.
    return _live_server.live_server().url


class FontRendersInABrowserTests(unittest.TestCase):
    """The face is loaded, and it changes the pixels."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). The stdlib half of this "
                f"contract runs in tests/test_redesign_contracts.py; this half "
                f"needs a real font engine and is NOT silently passed.")
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])
        cls._families = _declared_families()
        cls._faces = _declared_faces()
        cls._base = _base_url()

        # Measured against the *real* page, served by the real stdlib server
        # over the loopback origin the app always uses. Anything less faithful
        # is how the original bug got through: a stylesheet in a synthetic
        # document resolves relative URLs quite differently from the page that
        # actually ships.
        page = cls._browser.new_page()
        try:
            page.goto(cls._base, wait_until="networkidle", timeout=20000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {cls._base} is not reachable ({exc}). Start "
                f"it with `.redesign/dev.sh start` — this test is NOT silently "
                f"passed when it cannot run.")
        cls._console_errors: list[str] = []
        page.on("console", lambda m: m.type == "error" and cls._console_errors.append(m.text))
        page.on("pageerror", lambda e: cls._console_errors.append(str(e)))
        cls._page = page
        page.wait_for_function("() => document.fonts.ready.then(() => true)")
        page.evaluate("() => document.fonts.ready")

    @classmethod
    def tearDownClass(cls) -> None:
        page = getattr(cls, "_page", None)
        if page is not None:
            page.close()
        browser = getattr(cls, "_browser", None)
        if browser is not None:
            browser.close()
        cm = getattr(cls, "_pw_cm", None)
        if cm is not None:
            cm.stop()

    def test_every_declared_face_loads_with_no_console_error(self):
        """``document.fonts.check()``, asked per weight.

        Kept even though the width probe below is the stronger check, because
        it answers a different question: not "does this face render" but "did
        the browser consider it available at all". It is *not* sufficient on its
        own and is not relied on as such — with a ``unicode-range`` injected on
        one face, ``check()`` returned ``True`` at every weight while the Medium
        probe measured exactly like the phantom. Asking per weight is still
        right: a family-level answer cannot distinguish a loaded face from a
        sibling face in the same family standing in for it.
        """
        for family, weight in self._faces:
            loaded = self._page.evaluate(
                "q => document.fonts.check(q)",
                f'{weight} 16px "{family}"')
            self.assertTrue(
                loaded,
                f"{family} {weight} is declared but the browser reports it as "
                f"not loaded — the page is rendering the fallback")
        self.assertEqual(self._console_errors, [],
                         "the page logged a console error while the faces loaded")

    def test_every_declared_face_changes_the_rendered_width(self):
        """A probe in each declared face must not measure like the phantom.

        This is the direct descendant of the 2026-10-08 measurement: a probe in
        "IBM Plex Sans" measured 310px — identical to a probe in a face that
        does not exist — where a correctly built page measured 339px. Equality
        with the phantom *is* the bug, so that is exactly what is asserted.

        Every ``(family, weight)`` pair is probed at **its own** weight, which is
        the half that was missing. A ``unicode-range`` injected on the Medium
        face leaves 400 and 600 rendering correctly and takes only 500 down to
        the fallback, so a single-weight probe reports a healthy page over a
        font that is half missing. Mutation-proved: that exact injection was
        green here before the weights were read from the stylesheet.

        **The probe now forces the load it is measuring.** `document.fonts.ready`
        resolves when the loading *already in progress* is finished; a face
        nobody has asked for is never requested, so it never loads, and a
        synchronous measure of it reads the fallback. That made this test fail
        on ``Geist Mono 600`` — a face the page genuinely never requests at that
        weight — and report a broken font file. The distinction matters: "this
        face is requested" and "this face is real" are two questions, and only
        the second is this test's subject. Asking the browser for the exact
        face first keeps the failure it is looking for (a face that will not
        load at all still measures like the phantom) and drops the one that was
        never a defect.
        """
        for family, weight in self._faces:
            rows = self._page.evaluate(
                """async ([family, weight, phantom, probes]) => {
                    const spec = weight + ' 64px "' + family + '"';
                    if (document.fonts && document.fonts.load) {
                        try { await document.fonts.load(spec); } catch (e) {}
                        await document.fonts.ready;
                    }
                    const mk = (f) => {
                        const el = document.createElement('span');
                        el.style.cssText = 'position:absolute;top:-9999px;left:0;' +
                            'visibility:hidden;white-space:pre;font-size:64px;' +
                            'font-weight:' + weight + ';' +
                            'font-family:' + JSON.stringify(f);
                        document.body.appendChild(el);
                        return el;
                    };
                    const a = mk(family), b = mk(phantom);
                    const out = probes.map(p => {
                        a.textContent = p; b.textContent = p;
                        return [a.getBoundingClientRect().width,
                                b.getBoundingClientRect().width];
                    });
                    a.remove(); b.remove();
                    return out;
                }""",
                [family, weight, PHANTOM, list(PROBES)])
            for probe, (vendored, phantom) in zip(PROBES, rows):
                self.assertGreater(
                    vendored, 0,
                    f"{family} {weight} measured zero width for {probe!r}")
                self.assertNotEqual(
                    vendored, phantom,
                    f"{family} {weight} renders {probe!r} at exactly the phantom "
                    f"width ({vendored}px) — the browser is using the fallback, "
                    f"not the vendored face")

    def test_the_live_page_never_asks_for_a_weight_nobody_ships(self):
        """The rendered page requests only weights the stylesheet declares.

        The stdlib half (``test_redesign_contracts``) reads the cascade. This
        reads the *pixels' own answer* — every element on every open view, with
        inherited weights resolved by walking up — because the two catch
        different things. The cascade half catches a rule that is wrong on
        paper; this catches a weight that arrives through inheritance, a
        shorthand, or a view the reader opened, none of which the other can see.

        What it is for is the defect 7.3a measured: fourteen rules asked for
        640/650/700/750 and the package ships 400/500/600 only. Nothing broke.
        The browser **synthesised** the missing weights by smearing the nearest
        face, and `document.fonts.check()` returned ``True`` for every one of
        them — the check that sounds like it would have caught it is the check
        that cannot, because "can this face render 700?" is answered yes by
        synthesising. The giveaway was the advance width: 600, 650, 700 and 750
        all measured exactly 533.609px. One face, four weights, zero difference.

        So this asserts the honest direction — nothing on screen asks for a
        weight that does not exist — rather than "every face is rendered", which
        was 7.3a's open question and which the measurement answered *yes* (all
        six declared faces are genuinely reached, 400 included, so nothing here
        is dead weight and nothing needed to be deleted).
        """
        declared_by_family: dict[str, set[int]] = {}
        for family, weight in self._faces:
            declared_by_family.setdefault(family, set()).add(weight)

        resolved = self._page.evaluate(
            """() => {
                const out = {};
                const strip = (s) => s.replace(/^['"]|['"]$/g, '');
                const views = Array.from(document.querySelectorAll('[data-nav]'))
                    .map(e => e.getAttribute('data-nav'));
                const walk = () => {
                    const root = document.getElementById('app') || document.body;
                    for (const el of root.querySelectorAll('*')) {
                        const fam = strip(getComputedStyle(el).fontFamily
                                              .split(',')[0].trim());
                        let p = el, weight = null;
                        while (p) {
                            const w = getComputedStyle(p).fontWeight;
                            if (w && w !== '400') { weight = w; break; }
                            p = p.parentElement;
                        }
                        const key = fam + ' ' + (weight || '400');
                        out[key] = (out[key] || 0) + 1;
                    }
                };
                walk();
                for (const v of views) {
                    try { if (window.switchView) window.switchView(v); } catch (e) {}
                    walk();
                }
                return out;
            }""")

        ours = {k: n for k, n in resolved.items()
                if k.rsplit(" ", 1)[0] in declared_by_family}
        self.assertTrue(ours, "the page resolved no element into a vendored face")

        offenders = [
            f"{k} (x{n})" for k, n in sorted(ours.items())
            if int(k.rsplit(" ", 1)[1]) not in declared_by_family[k.rsplit(" ", 1)[0]]
        ]
        self.assertEqual(
            offenders, [],
            "the live page requests weight(s) no @font-face declares, so these "
            "elements render in synthesised (smeared) type: " + ", ".join(offenders))

        # The control. An app that set weight: 400 on everything satisfies the
        # assertion above while having no type hierarchy at all — which is the
        # shape a "fix" that deletes every weight would take. Require the page
        # to actually use more than one, and to use the heaviest face it ships.
        weights = {int(k.rsplit(" ", 1)[1]) for k in ours}
        self.assertGreaterEqual(
            len(weights), 3,
            f"the page only ever asks for {sorted(weights)} — the assertion "
            f"above would pass on a page with no type hierarchy")
        for family, weights_ in declared_by_family.items():
            if any(k.startswith(family + " ") for k in ours):
                self.assertIn(
                    max(weights_), weights,
                    f"{family} ships a {max(weights_)} face that nothing on "
                    f"screen ever asks for")

    def test_the_two_vendored_families_are_visually_distinct(self):
        """Sans and Mono must not be the same face under two names.

        A mono token that silently resolves to the sans face is the same class
        of silent failure: the identifiers, hashes and figures this tool
        compares across machines stop lining up.
        """
        if len(self._families) < 2:
            self.skipTest("only one family is vendored")
        widths = self._page.evaluate(
            """([a, b, probe]) => {
                const mk = (f) => {
                    const el = document.createElement('span');
                    el.style.cssText = 'position:absolute;top:-9999px;left:0;' +
                        'visibility:hidden;white-space:pre;font-size:64px;' +
                        'font-family:' + JSON.stringify(f);
                    document.body.appendChild(el);
                    el.textContent = probe;
                    return el.getBoundingClientRect().width;
                };
                return [mk(a), mk(b)];
            }""",
            [self._families[0], self._families[1], PROBES[0]])
        self.assertNotEqual(
            widths[0], widths[1],
            f"{self._families[0]} and {self._families[1]} measure identically — "
            f"one of them is not really loading")

    def test_the_live_computed_style_resolves_to_the_vendored_families(self):
        """What the browser *resolved*, not what the stylesheet claimed.

        Every other check here reads a declaration. This one reads
        ``getComputedStyle`` on the live document, so a token that lost its
        vendored face somewhere between ``:root`` and the element is still
        caught.

        The body resolves to ``--font`` (sans) by design, and a mono element
        resolves to ``--mono``; both must name the vendored family rather than
        falling through to the next entry in the stack.
        """
        tokens = dict(re.findall(r"(--(?:font|mono)):\s*([^;]+);",
                                 CSS.read_text(encoding="utf-8")))
        leads = {tok: value.split(",")[0].strip().strip("'\"")
                 for tok, value in tokens.items()}

        body = self._page.evaluate("() => getComputedStyle(document.body).fontFamily")
        self.assertIn(leads["--font"], body,
                      f"the live body resolves to {body!r}, which does not "
                      f"include the vendored {leads['--font']!r}")

        # Ask the document for the mono token rather than hunting for a hard-
        # coded element class: any element carrying `font-family: var(--mono)`
        # resolves through the same declaration, and asking for the token
        # itself tests the contract rather than today's markup.
        mono_token = self._page.evaluate(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--mono')")
        self.assertIn(leads["--mono"], mono_token,
                      f"--mono resolves to {mono_token!r}, which does not lead "
                      f"with the vendored {leads['--mono']!r}")

    def test_the_stylesheet_token_names_a_family_that_is_really_shipped(self):
        """`--font`/`--mono` must lead with a face that has a shipped @font-face.

        A token pointing at a family with no @font-face renders in the fallback
        just as silently as a face restricted away from ASCII, and the shipped
        bytes are then dead weight.
        """
        css = CSS.read_text(encoding="utf-8")
        tokens = dict(re.findall(r"(--(?:font|sans|mono)):\s*([^;]+);", css))
        declared = set(self._families)
        for token in ("--font", "--sans", "--mono"):
            self.assertIn(token, tokens, f"{token} is not defined in :root")
            lead = tokens[token].split(",")[0].strip().strip("'\"")
            self.assertIn(
                lead, declared,
                f"{token} leads with {lead!r}, which no shipped @font-face "
                f"declares — the page renders in the fallback")


class ShippedGlyphsRenderTests(unittest.TestCase):
    """Every character the interface can display must actually paint.

    The gap this closes
    -------------------
    The probes above are English prose. Every one of them is ASCII, and ASCII is
    the part of a font nobody has ever had to think about. This repository ships
    **21 distinct non-ASCII codepoints** — an em dash (144 uses), a middot, an
    ellipsis, arrows, a checkmark — and not one of them was asserted to render
    anywhere. `document.fonts.check()` returns ``True`` for a codepoint the face
    does not carry, and every other probe in this file asked about ASCII, so a
    shipped `✓` that painted as a tofu box would have passed the whole suite.

    Why pixels and not widths
    -------------------------
    The obvious method — measure the advance width and compare against a family
    that does not exist — does not work, and measured twice on this tree it is
    worth recording why. In ``"Geist Mono"`` the advance width is a constant for
    *every* codepoint including ``.notdef``, because a monospaced face gives an
    absent glyph the same cell as a present one: the width probe could not tell
    a tofu box from a letter. And across faces the widths collide by
    coincidence — `–`, `§` and `↑` all measured 31.8px in one pass. So this
    rasterises to a canvas and compares an ink signature, which distinguishes
    "drew something shaped like a checkmark" from "drew the same rectangle
    nothing draws", which is the actual question.
    """

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). Coverage of the shipped "
                f"glyphs needs a real font engine and is NOT silently passed.")
        cls._glyphs = shipped_glyphs()
        cls._families = _declared_families()
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])
        cls._page = cls._browser.new_page()
        try:
            cls._page.goto(_base_url(), wait_until="networkidle", timeout=20000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {_base_url()} is not reachable ({exc}). "
                f"Start it with `.redesign/dev.sh start`.")
        cls._page.wait_for_function("() => document.fonts.ready.then(() => true)")

        # One round trip for the whole inventory: per-glyph `evaluate` calls over
        # ~21 codepoints cost more than the assertions they feed.
        css = CSS.read_text(encoding="utf-8")
        tokens = dict(re.findall(r"(--(?:font|mono)):\s*([^;]+);", css))
        cls._stacks = {k: v.strip() for k, v in tokens.items()}
        # The honest baseline: the shipped stack with ONLY the vendored families
        # removed. Comparing against bare `sans-serif` instead — the obvious
        # shortcut — measures a different face from the one the token actually
        # falls back to (`system-ui` wins before the generic is reached), so it
        # reports "vendored" for a glyph that came from the system. Mutation-
        # proved: with `unicode-range` banning U+2014 on Geist Sans 400, the em
        # dash demonstrably fell out of the vendored face, and a `sans-serif`
        # baseline still disagreed with it, so the test passed over the exact
        # defect it exists to catch.
        cls._without = {
            tok: ", ".join(
                part for part in
                (p.strip() for p in stack.split(","))
                if not any(fam.strip("'\" ") in part for fam in cls._families)
            )
            for tok, stack in cls._stacks.items()
        }
        cls._rendered = cls._page.evaluate(
            """([glyphs, stacks, without]) => {
                const cv = document.createElement('canvas');
                cv.width = 96; cv.height = 96;
                const g = cv.getContext('2d', {willReadFrequently: true});
                const sig = (ch, stack) => {
                    g.clearRect(0, 0, 96, 96);
                    g.fillStyle = '#000'; g.textBaseline = 'top';
                    g.font = '64px ' + stack;
                    g.fillText(ch, 4, 4);
                    const d = g.getImageData(0, 0, 96, 96).data;
                    let ink = 0, h = 2166136261 >>> 0;
                    for (let i = 3; i < d.length; i += 4) {
                        if (d[i] > 8) { ink++;
                            h = (h ^ d[i]) >>> 0; h = Math.imul(h, 16777619) >>> 0; }
                    }
                    return {ink: ink, hash: h >>> 0};
                };
                const NOTDEF = '\\uE000';
                return glyphs.map(ch => ({
                    ch: ch,
                    sans: sig(ch, stacks['--font']),
                    mono: sig(ch, stacks['--mono']),
                    notdefSans: sig(NOTDEF, stacks['--font']),
                    notdefMono: sig(NOTDEF, stacks['--mono']),
                    // The same glyph in the same stack with the vendored
                    // families stripped: identical output means the vendored
                    // face had nothing to say and a system face drew it.
                    sansNoVendored: sig(ch, without['--font']),
                }));
            }""",
            [cls._glyphs, cls._stacks, cls._without])

    @classmethod
    def tearDownClass(cls) -> None:
        page = getattr(cls, "_page", None)
        if page is not None:
            page.close()
        browser = getattr(cls, "_browser", None)
        if browser is not None:
            browser.close()
        cm = getattr(cls, "_pw_cm", None)
        if cm is not None:
            cm.stop()

    def test_the_inventory_is_not_empty(self):
        """Guards the assertion below against silently testing nothing.

        If the sources ever moved out of ``TEXT_SOURCES`` this file would report
        a clean bill of health for a set of glyphs it never looked at. The list
        is derived, so this is the only thing standing between a refactor and a
        vacuous pass.
        """
        self.assertGreaterEqual(
            len(self._glyphs), 15,
            f"only {len(self._glyphs)} non-ASCII codepoints were found in "
            f"{TEXT_SOURCES}; the inventory is derived, so this usually means "
            f"the sources moved rather than that the UI lost its punctuation")

    def test_every_shipped_glyph_paints_something_other_than_notdef(self):
        """The contract: no character the UI can display renders as tofu.

        Compared in BOTH shipped stacks. A glyph absent from Geist Sans but
        present in Geist Mono is still a defect in the prose column — the em
        dash is the most-used non-ASCII character in this codebase, at 144
        uses, and it renders in the running column on every screen.
        """
        for row in self._rendered:
            ch = row["ch"]
            with self.subTest(glyph=ch, codepoint=f"U+{ord(ch):04X}"):
                for token, key, notdef in (
                    ("--font", "sans", "notdefSans"),
                    ("--mono", "mono", "notdefMono"),
                ):
                    painted = row[key]
                    blank = row[notdef]
                    self.assertGreater(
                        painted["ink"], 0,
                        f"{ch!r} painted no ink at all in {token} — the "
                        f"browser has no glyph and no fallback for it")
                    self.assertNotEqual(
                        painted["hash"], blank["hash"],
                        f"{ch!r} paints the .notdef box in {token} (identical to "
                        f"a Private Use codepoint) — the user sees a blank "
                        f"rectangle where {ch!r} should be")

    def test_prose_glyphs_come_from_the_vendored_face_not_the_system(self):
        """Characters in running text must be the face the design chose.

        ``.notdef`` only catches a glyph nobody has. The quieter failure is a
        glyph the *system* happens to carry, rendering in a face nobody chose:
        the em dash and the middot would silently be the host's font at the
        host's weight, mixed into vendored text, and it would look fine on the
        machine that built it.

        This is deliberately a **narrow** assertion over an explicit set, not a
        blanket "every glyph must be vendored" rule. Measured on this tree, five
        of the twenty-one shipped codepoints — ``↻ ⌘ ▸ ▾ ✓`` — are genuinely
        absent from Geist Sans and resolve to a system face, and the vendoring
        note in ``geist.css`` says per-glyph fallback is intended for skill
        bodies. Those five are UI furniture (a disclosure triangle, a refresh
        glyph) rather than prose, and changing them is a design decision, not a
        test failure. So the rule covers the characters that carry meaning in
        sentences, and the measured fallback set is asserted as a known, named
        quantity below so it cannot grow unnoticed.
        """
        prose = set("—–·…’“”§©−")
        for row in self._rendered:
            ch = row["ch"]
            if ch not in prose:
                continue
            with self.subTest(glyph=ch, codepoint=f"U+{ord(ch):04X}"):
                self.assertNotEqual(
                    row["sans"]["hash"], row["sansNoVendored"]["hash"],
                    f"{ch!r} renders identically with and without the vendored "
                    f"face — it is coming from the system font, so the vendored "
                    f"typeface is not what the reader is looking at")

    def test_the_set_of_glyphs_the_vendored_face_lacks_is_known_and_small(self):
        """Pin the measured fallback set, so it cannot grow in silence.

        Not a design assertion — a tripwire. If someone adds a glyph that the
        vendored face does not carry, this fails and the decision becomes
        explicit: vendor it, accept the fallback in writing, or draw it as SVG
        from the sprite the interface already ships.
        """
        known = set("↻⌘▸▾✓")
        unvendored = {
            row["ch"] for row in self._rendered
            if row["sans"]["hash"] == row["sansNoVendored"]["hash"]
        }
        self.assertEqual(
            unvendored, known,
            f"the set of shipped glyphs the vendored face does not carry "
            f"changed: was {''.join(sorted(known))}, now "
            f"{''.join(sorted(unvendored))}. A new entry means a character is "
            f"rendering in the system font — accept it deliberately and update "
            f"this set, or draw it from the vendored sprite instead.")


if __name__ == "__main__":
    unittest.main(verbosity=2)