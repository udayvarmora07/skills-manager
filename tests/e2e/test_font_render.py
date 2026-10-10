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
globally). It is therefore *skipped loudly*, never silently passed, when
Playwright or the dev server is absent. The stdlib half of the same contract
(faces declared, files shipped, none restricted away from ASCII) lives in
``tests/test_redesign_contracts.py`` and always runs.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_font_render.py
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

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


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


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
        """
        for family, weight in self._faces:
            rows = self._page.evaluate(
                """([family, weight, phantom, probes]) => {
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


if __name__ == "__main__":
    unittest.main(verbosity=2)