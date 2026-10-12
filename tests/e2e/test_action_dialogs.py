"""4.7 e2e — the action dialogs say what they will do, and then do it.

The shipped defect the stdlib suite pins is a source-level one. This file
exists because the things a source assertion cannot see are exactly what made
these four dialogs feel like a different product:

* A dialog's stated count and the array it POSTS must be the SAME number. A
  dialog that derives its own count inline can print one figure and send
  another, and no amount of reading that source reveals it — only two states,
  compared, with one target unpicked between them.
* The destructive option must be distinguishable WITHOUT colour. Measured on
  the rendered box, not the class attribute.
* Nothing may overflow at 390. 4.3b shipped an overflow that a capture found
  and no test did; that gap is closed here at all three widths.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this reads rendered text and geometry, "
    "which need a real DOM and are NOT verified by this skip",
)
class ActionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-actions-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8, and the trap 4.2 slice A recorded: the agent SCOPES come
        # from HOME, not from the data dir, so redirecting only the store walks
        # the maintainer's real ~/.codex and silently reports their skills.
        # Pin the browser cache BEFORE redirecting HOME — moving HOME also
        # moves Playwright's cache, which surfaces as an unrelated
        # "Sync API inside the asyncio loop" error.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        for name in ("api-contract-handbook", "release-notes-courier"):
            cls.store.create(name, f"Fixture {name}.",
                             body=f"# {name}\n\nFixture body with enough words to measure.\n")
        # The sync dialog lists only WRITABLE scopes other than the source, and
        # with an empty HOME there are none: `openSync` produced zero targets
        # and every count assertion below was vacuously satisfiable. The
        # fixture has to create them, which is the same reason 4.2 slice A's
        # fixture names its skills after the letters under test.
        for agent in ("codex", "cursor"):
            root = os.path.join(home, ".%s" % agent, "skills")
            os.makedirs(root, exist_ok=True)
            skill_dir = os.path.join(root, "agent-side-note")
            os.makedirs(skill_dir, exist_ok=True)
            with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write("---\nname: agent-side-note\n"
                         "description: Present only in one agent scope.\n---\n\n"
                         "# agent-side-note\n\nA copy that exists in exactly one "
                         "agent scope, so the sync dialog has something to offer.\n")
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
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        # 4.4's entry records that the FIRST row does not open the detail pane,
        # so nothing here may assume index 0 works.
        self._page.evaluate(
            "() => { const rows = [...document.querySelectorAll("
            "'.skilllist > li[data-skill-key]')];"
            " const t = rows[Math.min(1, rows.length - 1)]; if (t) t.click(); }")
        self._page.wait_for_timeout(900)
        self.assertTrue(self._page.evaluate("() => !!window.__skillsManagerApp.selected"),
                        "the fixture must reach a selected skill; without one "
                        "every dialog assertion below would be vacuous")

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # ------------------------------------------------------------------ sync

    def _open_sync(self):
        self._page.evaluate("() => window.__skillsManagerApp.openSync()")
        self._page.wait_for_selector('[data-modal="sync"]', timeout=8000)
        self._page.wait_for_timeout(300)

    def _sync_text(self):
        return self._page.evaluate(
            "() => document.querySelector('[data-modal=\"sync\"] .modal-body')"
            ".textContent.replace(/\\s+/g, ' ').trim()")

    def test_the_sync_dialog_paints_no_placeholder_letter(self):
        # The shipped defect, asserted against the RENDERED text. A source
        # check for one exact phrase would miss the same placeholder written
        # any other way; this cannot.
        self._open_sync()
        text = self._sync_text()
        self.assertNotIn("syncing to N", text)
        self.assertNotRegex(text, r"\bto N agents?\b")
        # And the sentence the dialog does print must carry a real count.
        self.assertRegex(text, r"Writes 1 copy to \d+ scopes?\.")

    def test_the_stated_count_is_the_count_that_would_be_posted(self):
        # The 2.3 lesson: a confirm that names one thing and does another.
        # Unpick one target and BOTH the sentence and the posted array move
        # together; a dialog computing its own count would print a stale figure.
        self._open_sync()
        before = self._page.evaluate(
            "() => ({ shown: window.__skillsManagerApp.syncOutcomeSentence,"
            " ids: window.__skillsManagerApp.syncPickedTargets.slice() })")
        self.assertTrue(before["ids"], "the fixture offers no writable target; "
                                       "the count assertions below would be vacuous")
        self._page.evaluate(
            "() => { const a = window.__skillsManagerApp;"
            " a.modals.sync.picked[a.syncPickedTargets[0]] = false; }")
        self._page.wait_for_timeout(250)
        after = self._page.evaluate(
            "() => ({ shown: window.__skillsManagerApp.syncOutcomeSentence,"
            " ids: window.__skillsManagerApp.syncPickedTargets.slice() })")
        self.assertEqual(len(after["ids"]), len(before["ids"]) - 1)
        self.assertIn(str(len(after["ids"])), after["shown"])
        self.assertNotEqual(after["shown"], before["shown"])

    def test_the_projection_is_labelled_as_a_multiplier_not_a_prediction(self):
        # The tool has no resolver. A bare "≈ 373.9k total across targets"
        # reads as what an agent will load, which would be an invented claim
        # (RULES #12).
        self._open_sync()
        text = self._sync_text()
        self.assertIn("not a prediction", text)
        self.assertIn("does not resolve", text)

    # ---------------------------------------------------------------- remove

    def _open_remove(self):
        self._page.evaluate(
            "() => { const a = window.__skillsManagerApp;"
            " a.confirmRemove(a.selected || a.skills[0]); }")
        self._page.wait_for_selector('[data-modal="remove"]', timeout=8000)
        self._page.wait_for_timeout(300)

    def test_the_remove_dialog_names_the_scope_it_will_act_on(self):
        # BUG-5 bound the dialog to the record it was opened for, but the
        # rendered dialog named only the skill, so the scope the request would
        # carry was invisible to the reader.
        self._open_remove()
        scope = self._page.evaluate(
            "() => window.__skillsManagerApp.modals.remove.scope")
        self.assertTrue(scope, "confirmRemove must bind a scope; without one "
                               "this assertion has nothing to look for")
        text = self._page.evaluate(
            "() => document.querySelector('[data-modal=\"remove\"]').textContent")
        self.assertIn(scope, text)

    def test_the_two_options_say_which_one_is_reversible(self):
        # A red label is not a label. Each option states its own consequence.
        self._open_remove()
        text = self._page.evaluate(
            "() => document.querySelector('[data-modal=\"remove\"]').textContent")
        self.assertIn("Reversible", text)
        self.assertIn("no restore path", text)

    def test_the_destructive_option_paints_only_once_it_is_selected(self):
        # Measured on the rendered box, not the class attribute: an unselected
        # red dot reads as "already broken", which is 4.2d's complaint about
        # `problem` in a new place.
        self._open_remove()
        before = self._page.evaluate(
            "() => getComputedStyle(document.querySelector("
            "'.choice[data-destructive=\"true\"] .choice-box')).backgroundColor")
        self._page.evaluate(
            "() => document.querySelector("
            "'.choice[data-destructive=\"true\"] input').click()")
        self._page.wait_for_timeout(250)
        after = self._page.evaluate(
            "() => ({ bg: getComputedStyle(document.querySelector("
            "'.choice[data-destructive=\"true\"] .choice-box')).backgroundColor,"
            " mode: window.__skillsManagerApp.modals.remove.mode })")
        self.assertEqual(after["mode"], "purge")
        self.assertNotEqual(before, after["bg"])

    def test_no_measurement_in_the_dialog_is_clipped(self):
        # Found by looking at the 1280 capture: `19 skills · 4…`. Measured 4px
        # short at 1280, 768 AND 390.
        #
        # **The first version of this test could not fail, and the reason is
        # the recorded 2.1e lesson.** It compared `scrollWidth` to
        # `clientWidth`; against the genuinely clipped tree both read EQUAL,
        # because `.tag` sets `overflow: hidden` and clipping is a PAINT
        # operation that layout boxes do not report. `scrollWidth` on an
        # `overflow: hidden` element is its own box, not its content's.
        #
        # A `Range` over the text was tried first and is WRONG: the client
        # rects of the text are measured in the text's own coordinate space
        # and are unaffected by the box being squeezed, so a clipped row
        # reported `gap: +74` — the exact inverse of the truth. The correct
        # signal is `scrollWidth - clientWidth`, which for an
        # `overflow: hidden` element is the width the content wanted and was
        # not given.
        #
        # **The fixture's own tag is only 75px wide and never clips**, which is
        # why this assertion was green against a mutated tree on two attempts:
        # the columns in this fixture are one digit + one token figure, so
        # there is nothing for `flex: none` to cut. The assertion is only
        # meaningful where a COUNT is long enough to be clipped, so it puts the
        # widest value the row can carry into the tag itself and measures THAT.
        # A fixture whose numbers are too small to break is a fixture that
        # cannot fail — the same thing 4.2 slice A recorded about naming its
        # skills after the letters under test.
        self._open_sync()
        for width in (1280, 768, 390):
            with self.subTest(width=width):
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(250)
                # Drive a value long enough to break, rather than hoping the
                # fixture's own happens to be. See the docstring above.
                self._page.evaluate(
                    """() => {
                         const t = document.querySelector('.sync-target .tag');
                         t.textContent = '1,234,567 skills · 1.23M';
                       }""")
                self._page.wait_for_timeout(150)
                rows = self._page.evaluate(
                    """() => [...document.querySelectorAll('.sync-target .tag')].map(t => {
                         // `scrollWidth` here is the CONTENT's width, because
                         // `.tag` sets `overflow: hidden` — for an
                         // `overflow: hidden` box the scrollable area IS the
                         // content, and `clientWidth` is what it was given.
                         // Their difference is the width the text wanted and
                         // did not get, which is precisely "how many pixels of
                         // this measurement are not on screen".
                         return {
                           text: t.textContent.trim(),
                           lost: t.scrollWidth - t.clientWidth,
                         };
                       })""")
                self.assertTrue(rows, "no target rows rendered at %dpx" % width)
                for row in rows:
                    self.assertLessEqual(
                        row["lost"], 0,
                        f"{row['text']!r} loses {row['lost']}px of itself at "
                        f"{width}px — a measurement may not lose its own digits")

    def test_the_radio_group_is_one_group(self):
        # Two radios with the same name in a DOM that other dialogs also touch
        # must not become two groups. Assert the DOM property, not the markup.
        self._open_remove()
        groups = self._page.evaluate(
            "() => { const rs = [...document.querySelectorAll("
            "'[data-modal=\"remove\"] input[type=radio]')];"
            " rs[0].checked = true;"
            " return { n: rs.length,"
            "  same: rs.every(r => r.name === rs[0].name),"
            "  only_one: rs.filter(r => r.checked).length }; }")
        self.assertEqual(groups["n"], 2)
        self.assertTrue(groups["same"], "the two options are one choice")
        self.assertEqual(groups["only_one"], 1, "selecting one deselects the other")

    # ---------------------------------------------------------------- overflow

    def test_no_action_dialog_overflows_at_any_width(self):
        # 4.3b shipped an overflow a capture found and no test did.
        for width in (390, 768, 1280):
            with self.subTest(width=width):
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(250)
                for name in ("sync", "remove"):
                    with self.subTest(dialog=name):
                        if name == "sync":
                            self._open_sync()
                        else:
                            self._open_remove()
                        over = self._page.evaluate(
                            "() => { const m = document.querySelector('.overlay .modal');"
                            " return m.scrollWidth - m.clientWidth; }")
                        self.assertLessEqual(over, 0,
                                             f"{name} overflows its modal at {width}px")
                        self._page.evaluate(
                            "(n) => window.__skillsManagerApp.closeModal(n)", name)
                        self._page.wait_for_timeout(200)
        self._page.set_viewport_size({"width": 1280, "height": 900})

    def test_no_console_errors_across_the_whole_suite(self):
        self.assertEqual(self._errors, [], f"console errors: {self._errors}")


if __name__ == "__main__":
    unittest.main()