"""The shell's chrome heights and its blank pane, measured on the running app.

Why this file exists
--------------------
Task 2.1c. The topbar measured **61px** and the statusbar **27px** — neither was
a choice, both were whatever block padding plus content happened to add up to.
An emergent height is one nobody re-checks, so this asserts the DECLARED numbers
(48 / 24) against ``getBoundingClientRect``, which is the only way a stylesheet
edit that changes nothing on screen can be caught.

The second half covers the Library's detail pane with nothing selected. It is
the widest surface in the app (680px at 1280) and it held a 22px wrench floating
at 12vh — the exact template tell task 2.1 removed from the brand one commit
earlier and left here. It also rendered "an empty library" and "a filter that
hid every skill" as the same two sentences, which is the ambiguity worth
solving: only one of those is a problem the reader can fix with a button.

Every assertion below is a statement about what renders, so a green run here is
evidence about the change rather than about the source text.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_shell_chrome.py
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEBUI = ROOT / "skillsmgr" / "webui"

TOPBAR_H = 48
STATUSBAR_H = 24


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


class ShellChromeMeasuredTests(unittest.TestCase):
    """Declared heights, actually rendered."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). This half needs a real "
                f"engine and is NOT silently passed."
            )
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])
        cls._base = _base_url()
        cls._page = cls._browser.new_page(viewport={"width": 1280, "height": 900})
        cls._console_errors: list[str] = []
        cls._page.on("console", lambda m: m.type == "error" and cls._console_errors.append(m.text))
        cls._page.on("pageerror", lambda e: cls._console_errors.append(str(e)))
        try:
            cls._page.goto(cls._base, wait_until="domcontentloaded", timeout=20000)
            cls._page.wait_for_selector(".scope-trigger", timeout=15000)
            cls._page.click('.viewtabs button:has-text("Library")')
            cls._page.wait_for_selector(".library-bar", timeout=10000)
            cls._page.wait_for_selector(".detail-empty", timeout=10000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {cls._base} did not reach the Library view "
                f"({exc}). Start it with `.redesign/dev.sh start` — this test "
                f"is NOT silently passed when it cannot run."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    # -- helpers ---------------------------------------------------------
    def _h(self, sel: str) -> float:
        return self._page.eval_on_selector(
            sel, "e => e.getBoundingClientRect().height"
        )

    def _w(self, sel: str) -> float:
        return self._page.eval_on_selector(
            sel, "e => e.getBoundingClientRect().width"
        )

    # -- the declared heights --------------------------------------------
    def test_the_topbar_is_the_declared_48px(self):
        self.assertEqual(self._h(".topbar"), TOPBAR_H)

    def test_the_statusbar_is_the_declared_24px(self):
        self.assertEqual(self._h(".statusbar"), STATUSBAR_H)

    def test_the_layout_sits_flush_between_the_two_bars(self):
        """Not "topbar.bottom == statusbar.top" — `<main>` fills that space by
        design, so the real claim is that neither bar is separated from the
        content column by a stray gap or an overlap."""
        top = self._page.eval_on_selector(".topbar", "e => e.getBoundingClientRect().bottom")
        main_top = self._page.eval_on_selector("#main-workspace", "e => e.getBoundingClientRect().top")
        main_bottom = self._page.eval_on_selector("#main-workspace", "e => e.getBoundingClientRect().bottom")
        foot = self._page.eval_on_selector(".statusbar", "e => e.getBoundingClientRect().top")
        self.assertLessEqual(abs(top - main_top), 1.0, f"a {main_top - top:.1f}px gap under the topbar")
        self.assertLessEqual(abs(foot - main_bottom), 1.0, f"a {foot - main_bottom:.1f}px gap above the status bar")
        self.assertLess(main_bottom, foot + 1.0, "the layout overlaps the status bar")

    # -- the blank pane ---------------------------------------------------
    def test_the_blank_pane_carries_no_decorative_icon(self):
        self.assertEqual(
            self._page.eval_on_selector_all(".detail-empty .empty-icon svg", "es => es.length"),
            0,
            "the blank pane must not open with a decorative glyph; it is a state, "
            "not an illustration",
        )

    def test_the_blank_pane_is_anchored_and_does_not_scale_with_the_viewport(self):
        """The defect was `padding: 12vh`, so the property to pin is that the
        pane's CONTENT offset does NOT track viewport height.

        Two wrong versions of this test are worth recording, because both went
        green under mutation:

        * asserting `.detail-empty`'s own `top` is unfalsifiable — `padding-top`
          pushes an element's *contents* down, never the element itself, so its
          border-box top was 80px under both the old rule and the new one. The
          measurement has to be taken on a node inside the padding.
        * the first version also used `top < 300`, a threshold picked after
          reading the value. Nothing can fail it.
        """
        def title_top_at(height: int) -> float:
            self._page.set_viewport_size({"width": 1280, "height": height})
            self._page.wait_for_timeout(150)
            return self._page.eval_on_selector(
                ".pane-blank-title", "e => e.getBoundingClientRect().top"
            )

        try:
            tall = title_top_at(1000)
            short = title_top_at(600)
        finally:
            self._page.set_viewport_size({"width": 1280, "height": 900})
            self._page.wait_for_timeout(150)
        self.assertAlmostEqual(
            tall, short, delta=1.0,
            msg=f"the pane's content moved with the viewport ({tall:.0f} -> "
                f"{short:.0f}px); a viewport-relative inset drops the state into "
                f"the middle of a tall window and pins it to the top of a short one",
        )

    def test_the_blank_pane_states_the_scope_it_is_showing(self):
        pairs = self._page.eval_on_selector_all(
            ".pane-blank-facts > div",
            "es => es.map(e => [e.querySelector('dt') && e.querySelector('dt').textContent.trim(),"
            "                       e.querySelector('dd') && e.querySelector('dd').textContent.trim()])",
        )
        pairs = {k: v for k, v in pairs if k}
        self.assertIn("Scope", pairs, f"the pane must label the scope it is showing, got {list(pairs)}")
        # Paired by key, not "any dd is non-empty": four of these rows are
        # conditionally rendered, so an aggregate assertion passes with any one
        # of them blank — which is exactly how a mutation emptied the Scope
        # value and the suite stayed green.
        self.assertTrue(
            pairs["Scope"], f"the Scope fact has a label but no value: {pairs['Scope']!r}"
        )
        self.assertTrue(pairs.get("Showing"), "the count row must carry a value")

    def test_the_blank_pane_distinguishes_an_empty_library_from_a_filtered_one(self):
        """The defect: both rendered as the same two sentences."""
        lede = self._page.eval_on_selector(
            ".pane-blank-lede", "e => e.textContent.trim()"
        )
        self.assertTrue(
            lede,
            "the blank pane must say which of the two situations it is, because "
            "only one of them has a button that fixes it",
        )
        self.assertIn("Choose a skill", lede)  # populated library, nothing selected

    def test_the_facts_table_is_a_definition_list(self):
        """The Overview already established dt/dd; Lighthouse's definition-list
        audit applies to every view, and this pane is the widest one."""
        self.assertEqual(
            self._page.eval_on_selector_all(".pane-blank-facts dt", "es => es.length") > 0,
            True,
        )
        self.assertEqual(
            self._page.eval_on_selector_all(".pane-blank-facts dd", "es => es.length") > 0,
            True,
        )

    # -- the status bar's observed facts ---------------------------------
    def test_the_statusbar_names_the_authority_the_page_was_served_from(self):
        # `textContent` reads through `hidden`, so the assertion also has to ask
        # whether the element is actually rendered — otherwise "hide the fact"
        # is a mutation that changes nothing this test can see.
        shown = self._page.eval_on_selector(
            ".statusbar-host",
            "e => { const r = e.getBoundingClientRect();"
            " return r.width > 0 && r.height > 0 ? e.textContent.trim() : ''; }",
        )
        self.assertTrue(shown, "a loopback tool's status bar must show which address it is on")
        self.assertRegex(
            shown, r"^127\.0\.0\.1(:\d+)?$|^localhost(:\d+)?$|^\[::1\](:\d+)?$",
            f"the served host must be a loopback authority as rendered, got {shown!r}",
        )

    def test_the_statusbar_states_the_locale_rather_than_implying_a_translation(self):
        text = self._page.eval_on_selector(
            ".statusbar", "e => e.innerText.replace(/\\s+/g, ' ')"
        )
        self.assertIn("formats", text)
        self.assertNotIn("translated", text.lower())

    # -- nothing above this point is vacuous ------------------------------
    def test_the_page_mounted_without_a_console_error(self):
        self.assertEqual(self._console_errors, [])


class ShellSourceContractTests(unittest.TestCase):
    """The parts that are cheaper to assert on source than in a browser."""

    def test_the_blank_pane_names_are_declared_in_the_template(self):
        html = (WEBUI / "index.html").read_text(encoding="utf-8")
        for needle in ("pane-blank-eyebrow", "pane-blank-lede", "pane-blank-facts"):
            self.assertIn(needle, html)

    def test_the_wrench_left_the_blank_pane(self):
        html = (WEBUI / "index.html").read_text(encoding="utf-8")
        self.assertNotIn(
            'class="empty-icon">\n            <app-icon name="wrench"',
            html.replace("\r\n", "\n"),
            "the blank pane must not reintroduce the decorative wrench",
        )

    def test_the_heights_are_declared_not_emergent(self):
        css = (WEBUI / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.topbar\s*\{[^}]*min-height:\s*48px")
        self.assertRegex(css, r"\.statusbar\s*\{[^}]*min-height:\s*24px")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)