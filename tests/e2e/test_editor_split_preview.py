"""The editor's preview and the Source tab must render one document, not two.

4.5b. Before this task the editor called the same `renderMarkdown` as the
Source tab and still looked nothing like it: `.markdown-preview` carried three
declarations (border, padding, a 14px size) and none of the ~25 rules that give
`.body` its heading ladder, list rhythm, blockquote, code and tables. One
function, two outputs - and every existing assertion was green, because nothing
in the suite ever had the two documents on screen together.

So the assertions here are comparisons, not expectations:

  * at 1280 the two panes are side by side and occupy the SAME box height;
  * at 390 they stack and the dialog does not overflow horizontally;
  * and the centrepiece - for a set of document elements, the computed style in
    the live editor preview equals the computed style in the live Source tab.

That last one is the point of the task. It fails on the tree this commit started
from, and it cannot be satisfied by adding a rule that looks right.
"""

import os
import shutil
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

# The document elements whose rendered style must agree between the two hosts.
# Chosen because each one had its own rule in `.body` and nothing in the preview:
# a heading (the ladder), body text (leading), a list item, a quote, inline code
# and a table cell. `p` and `li` are what a reader notices first; `h2` and
# `blockquote` are where the old gap was loudest.
STYLED_ELEMENTS = ("h2", "p", "li", "blockquote", "code", "td")

# A JS array literal, built by hand. Interpolating the Python TUPLE above gave
# `('h2', 'p', ...)`, which JavaScript reads as a comma EXPRESSION: the loop ran
# exactly once, with the last element. The probe still returned a well-formed
# `{}` instead of raising, so a suite that skipped five sixths of its own
# comparison reported a clean failure for the wrong reason.
_STYLE_ARRAY = "[" + ", ".join('"%s"' % tag for tag in STYLED_ELEMENTS) + "]"


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


RICH_BODY = """# Preview parity

## A second-level heading

A paragraph with `inline code` and enough words to have a measurable leading
value rather than a nominal one.

- First item
- Second item

> A quotation, which `.body` styled and the preview did not.

| Column | Meaning |
| --- | --- |
| Scope | Where the copy lives |
"""


def _styles_probe():
    """Read the computed style of each element type inside a host container.

    Returns `{tag: {prop: value}}`. Returns an empty dict when the container has
    no such element, so a caller can distinguish "styled differently" from
    "the element is not there".
    """
    return """(host) => {
      const out = {};
      const root = document.querySelector(host);
      if (!root) return out;
      for (const tag of %s) {
        const el = root.querySelector(tag);
        if (!el) continue;
        const cs = getComputedStyle(el);
        out[tag] = {
          fontSize: cs.fontSize,
          fontFamily: cs.fontFamily,
          fontWeight: cs.fontWeight,
          lineHeight: cs.lineHeight,
          marginTop: cs.marginTop,
          marginBottom: cs.marginBottom,
          color: cs.color,
          backgroundColor: cs.backgroundColor,
          borderLeftWidth: cs.borderLeftWidth,
        };
      }
      return out;
    }""" % (_STYLE_ARRAY,)


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this compares computed styles between two "
    "live renders of the same document, and is NOT verified by this skip",
)
class EditorSplitPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-splitpreview-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not the data dir.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        cls.store.create(
            "parity-probe",
            "A fixture whose body exercises every element the two hosts style.",
            body=RICH_BODY,
        )
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        for key, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_function(
            "() => document.getElementById('app').children.length > 0", timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # ------------------------------------------------------------- helpers

    def _resize(self, width, height=900):
        self._page.set_viewport_size({"width": width, "height": height})
        self._page.wait_for_timeout(120)

    def _select_fixture(self, name="parity-probe"):
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.click(f'.skilllist > li[data-skill-key]:has-text("{name}")')
        self._page.wait_for_timeout(300)
        selected = self._page.evaluate(
            "() => (window.__skillsManagerApp.selectedName || '')")
        if selected != name:
            self._page.evaluate(
                """(n) => { const a = window.__skillsManagerApp;
                   const rec = (a.skills || []).find(s => s.name === n);
                   if (rec) a.selectSkill(rec); }""",
                name,
            )
            self._page.wait_for_timeout(300)

    def _boxes(self):
        return self._page.evaluate(
            """() => {
              const ta = document.querySelector('[data-modal="skill"] #f-body');
              const pv = document.querySelector('[data-modal="skill"] .markdown-preview');
              const box = (e) => { if (!e) return null;
                const r = e.getBoundingClientRect();
                return {x: r.left, y: r.top, w: r.width, h: r.height,
                        right: r.right, bottom: r.bottom}; };
              return {ta: box(ta), pv: box(pv)};
            }"""
        )

    def _open_edit(self):
        self._select_fixture()
        with self._page.expect_response(lambda r: "/raw" in r.url, timeout=10000):
            self._page.evaluate("() => window.__skillsManagerApp.openEdit()")
        self._page.wait_for_selector('[data-modal="skill"] #f-body', timeout=10000)
        self._page.wait_for_timeout(400)

    # --------------------------------------------------------------- tests

    def test_the_two_panes_sit_side_by_side_and_share_one_box_height(self):
        """`shared scroll height` has to mean the same box, not two constants
        that happened to be typed the same. If the panes can differ, the reader
        comparing them compares two different heights and reads the difference
        as a difference in the document."""
        self._open_edit()
        self._resize(1280)
        b = self._boxes()
        self.assertIsNotNone(b["ta"] and b["pv"], "a pane is missing")
        self.assertGreaterEqual(
            b["pv"]["x"] - b["ta"]["right"], -1,
            "at 1280 the preview must sit BESIDE the textarea, not under it: "
            f"textarea right={b['ta']['right']} preview left={b['pv']['x']}",
        )
        self.assertAlmostEqual(
            b["ta"]["h"], b["pv"]["h"], delta=1,
            msg=f"the panes are not one shared height: {b['ta']['h']} vs {b['pv']['h']}",
        )
        self.assertGreater(b["pv"]["w"], 200, "the preview column collapsed")

    def test_the_panes_stack_on_a_phone_and_nothing_overflows(self):
        self._open_edit()
        self._resize(390, 844)
        b = self._boxes()
        self.assertGreaterEqual(
            b["pv"]["y"] - b["ta"]["bottom"], -1,
            "below 900px the preview must stack UNDER the textarea",
        )
        overflow = self._page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertLessEqual(overflow, 0,
                             f"the stacked split pushed the document {overflow}px sideways")

    def test_the_textarea_is_never_squeezed_smaller_than_the_preview(self):
        """The defect the screenshot matrix found, at both stacked widths.

        `.form-field` is a flex column and the textarea was shrinking to
        whatever height was left over - measured 219px against a 402px preview
        at 768, so the field the reader types in was the smaller of the two
        fields they are comparing. A screenshot of a dialog whose panes have
        different heights looks like a design choice; only the measurement says
        otherwise, which is why 4.2d's and 4.2e's defects were also measured.
        """
        self._open_edit()
        self._page.fill('[data-modal="skill"] #f-body', RICH_BODY)
        self._page.wait_for_timeout(200)
        for width in (390, 768):
            with self.subTest(width=width):
                self._resize(width, 900 if width == 768 else 844)
                b = self._boxes()
                self.assertGreaterEqual(
                    b["ta"]["h"], 240,
                    f"at {width}px the textarea is {b['ta']['h']}px tall - it is "
                    "being squeezed by the flex column, not given a height",
                )

    def test_a_long_document_scrolls_inside_the_panes_not_out_of_the_dialog(self):
        """The reason the height is declared on the container. A 400-line body
        must not push Save out of reach."""
        self._open_edit()
        self._resize(1280)
        self._page.fill('[data-modal="skill"] #f-body', "\n\n".join(
            f"## Section {n}\n\nParagraph number {n}, long enough to occupy a line "
            f"or two of the pane at this width and height." for n in range(200)))
        self._page.wait_for_timeout(250)
        scrolls = self._page.evaluate(
            """() => {
              const ta = document.querySelector('[data-modal="skill"] #f-body');
              const pv = document.querySelector('[data-modal="skill"] .markdown-preview');
              return {ta: ta.scrollHeight - ta.clientHeight,
                      pv: pv.scrollHeight - pv.clientHeight,
                      saveVisible: (() => {
                        const b = document.querySelector('[data-modal="skill"] .modal-foot .btn-primary');
                        if (!b) return false;
                        b.scrollIntoView({block: 'nearest'});
                        const r = b.getBoundingClientRect();
                        const hit = document.elementFromPoint(r.left + r.width / 2,
                                                             r.top + r.height / 2);
                        return !!(hit && b.contains(hit));
                      })()};
            }"""
        )
        self.assertGreater(scrolls["ta"], 0, "the textarea does not scroll in place")
        self.assertGreater(scrolls["pv"], 0, "the preview does not scroll in place")
        self.assertTrue(scrolls["saveVisible"],
                        "a long body pushed Save out of the dialog")

    def test_the_preview_and_the_source_tab_render_the_same_document(self):
        """The centrepiece, and the one that fails on the tree this task
        started from. Same `renderMarkdown`, same input, two hosts - and the
        computed style of every element type must agree, property by property.

        Reading the Source tab first and the editor second means both numbers
        come from a live render; nothing here asserts what the CSS 'says'.
        """
        self._select_fixture()
        self._page.click('#detail-tab-source')
        self._page.wait_for_selector('.detail-panel[aria-labelledby="detail-tab-source"] .body h2',
                                     timeout=10000)
        self._page.wait_for_timeout(200)
        source = self._page.evaluate(_styles_probe(), ".detail-panel .body")
        self.assertTrue(source, "the Source tab rendered no measurable elements")

        self._open_edit()
        self._resize(1280)
        self._page.wait_for_timeout(300)
        preview = self._page.evaluate(_styles_probe(), '[data-modal="skill"] .markdown-preview')
        self.assertTrue(preview, "the editor preview rendered no measurable elements")

        for tag in STYLED_ELEMENTS:
            with self.subTest(element=tag):
                self.assertIn(tag, preview,
                              f"the preview rendered no <{tag}> to compare")
                self.assertIn(tag, source,
                              f"the Source tab rendered no <{tag}> to compare")
                differing = [p for p in source[tag]
                             if source[tag][p] != preview[tag].get(p)]
                self.assertEqual(
                    [], differing,
                    f"<{tag}> renders differently in the editor preview and the "
                    "Source tab: " + ", ".join(
                        f"{p} {preview[tag].get(p)!r} != {source[tag][p]!r}"
                        for p in differing),
                )

    def test_the_preview_renders_the_typed_markdown_live(self):
        self._open_edit()
        self._resize(1280)
        self._page.fill('[data-modal="skill"] #f-body', RICH_BODY)
        self._page.wait_for_timeout(300)
        tags = self._page.evaluate(
            """() => {
              const pv = document.querySelector('[data-modal="skill"] .markdown-preview');
              if (!pv) return [];
              return ['h1','h2','p','ul > li','blockquote','table td']
                .filter(s => pv.querySelector(s));
            }"""
        )
        self.assertEqual(
            ["h1", "h2", "p", "ul > li", "blockquote", "table td"], tags,
            "the preview is not showing the document being typed; this is a "
            "preview that renders something else",
        )

    def test_the_preview_is_a_named_keyboard_reachable_region(self):
        """It scrolls, so it must be reachable: a scrollable pane with no name
        and no tab stop is invisible to a keyboard reader, and `aria-label` on a
        plain div is announced by nothing."""
        self._open_edit()
        attrs = self._page.evaluate(
            """() => { const pv = document.querySelector('[data-modal="skill"] .markdown-preview');
                return pv ? {role: pv.getAttribute('role'),
                             name: pv.getAttribute('aria-label'),
                             tabIndex: pv.tabIndex} : null; }"""
        )
        self.assertIsNotNone(attrs)
        self.assertEqual("region", attrs["role"])
        self.assertEqual("Markdown preview", attrs["name"])
        self.assertEqual(0, attrs["tabIndex"])
        self._page.evaluate(
            """() => document.querySelector('[data-modal="skill"] .markdown-preview').focus()"""
        )
        self.assertTrue(
            self._page.evaluate(
                """() => document.activeElement ===
                          document.querySelector('[data-modal="skill"] .markdown-preview')"""),
            "the preview could not take focus, so it cannot be scrolled by keyboard")


if __name__ == "__main__":
    unittest.main()