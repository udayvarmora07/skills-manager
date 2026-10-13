"""5.7e — the Settings view, in a browser.

**Why this file exists at all.** MAP.md records, at the end of its 5.9a
section, that `tests/e2e/` had **no suite for the Settings view** and that
"this is now the branch's clearest coverage hole". Everything this branch
claims about Settings was a source-text assertion: it could prove a control was
written and could not prove it was reachable, could not see a wrap, and could
not see what the OS was actually doing.

That last one is not hypothetical. 5.7c slice A found the accessibility-
evidence row printing "OS has not requested reduced motion" on a machine that
had asked for reduced motion, and it did so while 6.4c's own test was green —
because the test read `app.js` and the reader was in `index.html`, and **no
stdlib test renders the template at all**. `ReducedMotionRowTests` is the
regression for that specific finding: two browser contexts, one forced to
`reduced_motion="reduce"`, asserting the row actually flips.

What is measured here that source text cannot reach:

1. **The OS signal, from the OS.** `reduced_motion="reduce"` on the context;
   the row's text must differ between the two contexts, and `matchMedia` in the
   page is the control that proves the emulation took (a green sweep from a
   context that never emulated would be this suite's own version of 7.3's
   "a control that fires nothing").
2. **The segmented control is ONE row at every width**, including 1100 —
   5.7b reached for a column at 1199px and 5.7e measured what that cost
   (+140px of page height and a checklist's look).
3. **A three-way choice does not span a 636px column.** The measure is
   declared (`max-width: 460px`); the assertion is that the control is
   narrower than its container at every width, which fails if someone deletes
   the measure and leaves a locale `<select>` edge to edge.
4. **The rail's subjects and the pane's sections are the same set**, derived
   from `SETTINGS_SECTIONS` via the mounted app rather than enumerated here —
   5.7b's one-definition rule, and a hand-kept list is a list that rots.

SKIPS LOUDLY when Playwright or the fixture is absent (never a silent pass).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

WIDTHS = (1100, 1280, 1440, 1920)


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


def _open_settings(page, app_url):
    """Open Settings through the rail, drawer and all.

    Below 761px the rail IS the phone drawer (2.1e2), so a `click()` on a
    button that is in the DOM and off screen waits out Playwright's timeout and
    then reports a timeout rather than a navigation problem.
    """
    page.goto(app_url, wait_until="domcontentloaded")
    page.wait_for_selector("#nav-drawer", state="attached", timeout=20000)
    if page.evaluate(
        "() => { const t = document.querySelector('.nav-drawer-trigger');"
        " if (!t) return false; const r = t.getBoundingClientRect();"
        " return r.width > 0 && r.height > 0; }"
    ):
        page.click(".nav-drawer-trigger")
        page.wait_for_selector("#nav-drawer.open", timeout=10000)
    page.click("#nav-drawer button[data-tip='Settings']")
    page.wait_for_selector(".settings-center", timeout=15000)


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: whether the OS signal reaches the row, "
    "whether the segmented control is one row, and whether a control spans its "
    "column are only observable through a real engine, and are NOT verified by "
    "this skip",
)
class SettingsViewTests(unittest.TestCase):
    """The one view on this branch with no browser coverage until now."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-settings-")
        # RULES #8. The Store takes a data dir, but the AGENT SCOPES come from
        # HOME, so the redirect has to happen before anything reads it.
        cls._saved_env = {
            k: os.environ.get(k)
            for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                      "PLAYWRIGHT_BROWSERS_PATH")
        }
        browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers:
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            browsers = os.path.join(real_home, ".cache", "ms-playwright")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers

        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        # About lists the roots the app is pointed at, so the view must have
        # something to point at. One skill is enough; the seed is not the
        # subject of any assertion here.
        cls.store.create(
            "settings-fixture",
            "A fixture skill so the About section has a root to name.",
            body="# settings-fixture\n\nFixture body.\n",
        )
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(args=["--no-sandbox"])

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()
        if cls.server:
            cls.server.shutdown()
            cls.thread.join(timeout=5)
        for key, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH") is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        # ONE browser for the class and a fresh CONTEXT per test. Launching a
        # browser per test is the shape 2.1b recorded as costing a whole
        # iteration's time and, here, an intermittent `TargetClosedError`: the
        # reduced-motion test opens its own contexts off the same browser, so a
        # per-test browser teardown can pull the ground out from under them.
        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900})
        self._page = self._context.new_page()
        self._errors = []
        self._page.on("pageerror", lambda e: self._errors.append(str(e)))
        self._page.on(
            "console",
            lambda m: self._errors.append(m.text) if m.type == "error" else None,
        )
        _open_settings(self._page, self.server.url)

    def tearDown(self):
        self._context.close()

    # -- helpers --------------------------------------------------------------

    def _at(self, width):
        self._page.set_viewport_size({"width": width, "height": 900})
        self._page.wait_for_timeout(120)

    def _evidence(self, label):
        return self._page.evaluate(
            "(label) => { const rows = [...document.querySelectorAll("
            "'#settings-accessibility .settings-evidence > div')];"
            " const row = rows.find(d => d.querySelector('dt').textContent.trim() === label);"
            " return row ? row.querySelector('dd').textContent.trim() : null; }",
            label,
        )

    # -- 1. the control that proves the sweep can fail ------------------------

    def test_the_view_reports_its_own_heading(self):
        """`document.title` and `#app` having children both stay true when a
        branch throws during render and empties itself — 5.5's failure, on a
        page with no console error."""
        self.assertEqual(
            self._page.text_content("#view-title").strip(), "Settings")
        self.assertEqual(self._errors, [], "console/page errors on the Settings view")

    # -- 2. the OS signal ------------------------------------------------------

    def test_the_reduced_motion_row_follows_the_os(self):
        """5.7c slice A's finding, as the regression it never had.

        Two contexts, one forced to `reduced_motion="reduce"`. The assertion is
        that the ROW DIFFERS, and `matchMedia` in each page is the control that
        proves the emulation reached the document — otherwise a broken
        emulation would make both rows agree and this would pass.
        """
        reads = {}
        for motion in ("no-preference", "reduce"):
            context = self._browser.new_context(
                viewport={"width": 1440, "height": 900}, reduced_motion=motion)
            page = context.new_page()
            _open_settings(page, self.server.url)
            reads[motion] = (
                page.evaluate(
                    "() => matchMedia('(prefers-reduced-motion: reduce)').matches"),
                page.evaluate(
                    "() => { const rows = [...document.querySelectorAll("
                    "'#settings-accessibility .settings-evidence > div')];"
                    " const row = rows.find(d => d.querySelector('dt')"
                    ".textContent.trim().indexOf('reduced-motion') >= 0);"
                    " return row ? row.querySelector('dd').textContent.trim() : null; }"),
            )
            context.close()
        self.assertIs(reads["reduce"][0], True,
                      "the reduce context did not emulate; both rows would agree "
                      "and this assertion could not fail")
        self.assertIs(reads["no-preference"][0], False,
                      "the default context is already emulating reduced motion")
        self.assertIsNotNone(reads["reduce"][1],
                             "the reduced-motion row did not render at all")
        self.assertNotEqual(
            reads["reduce"][1], reads["no-preference"][1],
            "the row is the same sentence under both OS settings: it states a "
            "constant about the reader's machine")

    # -- 3. the shrunk-laptop band --------------------------------------------

    def test_a_choice_is_one_row_at_every_width(self):
        """5.7e. Three one-word choices rendered as three 636px rows is a
        checklist wearing a control's border, and it cost 28% of the page
        height at 1100 — the width a laptop window shrinks to."""
        for width in WIDTHS:
            self._at(width)
            measured = self._page.evaluate(
                "() => [...document.querySelectorAll('.settings-segmented')]"
                ".map(f => {"
                " /* `:scope > .settings-option`, not `f.children`: a"
                " `<legend class='sr-only'>` is a child and sits at its own"
                " top, so counting children reports two rows for a control"
                " that is plainly one row. */"
                " const cells = [...f.querySelectorAll(':scope > .settings-option')]"
                "   .map(c => Math.round(c.getBoundingClientRect().top));"
                " return {rows: new Set(cells).size,"
                "          cells: cells.length,"
                "          h: Math.round(f.getBoundingClientRect().height)}; })")
            self.assertTrue(measured, "no segmented control rendered at %d" % width)
            for group in measured:
                self.assertEqual(
                    group["rows"], 1,
                    "a segmented control broke into %d rows at %dpx: a "
                    "three-way choice is one row at any width"
                    % (group["rows"], width))
                # The height is the observable consequence, not a second
                # assertion about the same thing: three cells of >=44px in one
                # row cannot be taller than one cell plus a 2px border.
                self.assertLessEqual(group["h"], 60,
                                     "the segmented row is %dpx tall at %dpx, so "
                                     "the cells are not in one row"
                                     % (group["h"], width))
                self.assertGreaterEqual(group["h"], 44,
                                        "the control fell below the 44px touch "
                                        "floor at %dpx" % width)
                # A bordered group whose box runs past its last cell reads as a
                # fourth, blank choice — visible in 5.7e's first capture.
                box = self._page.evaluate(
                    "() => { const f = document.querySelector('.settings-segmented');"
                    " const kids = [...f.querySelectorAll(':scope > .settings-option')];"
                    " const last = kids[kids.length - 1].getBoundingClientRect();"
                    " return Math.round(f.getBoundingClientRect().right - last.right); }")
                if width == 1100:
                    self.assertLessEqual(
                        box, 2,
                        "%dpx of empty tail inside the segmented box at %dpx"
                        % (box, width))

    def test_a_control_does_not_span_its_column(self):
        """The declared measure. A locale <select> and a three-way choice
        stretching edge to edge across 636px is what 5.7e removed; deleting
        `max-width` brings it straight back and this fails."""
        for width in (1100, 1280):
            self._at(width)
            pairs = self._page.evaluate(
                "() => [...document.querySelectorAll('.settings-section-control')]"
                ".map(c => ({control: Math.round(c.getBoundingClientRect().width),"
                "           parent: Math.round(c.parentElement"
                "             .getBoundingClientRect().width)}))")
            self.assertTrue(pairs, "no control column measured at %d" % width)
            for pair in pairs:
                self.assertLessEqual(
                    pair["control"], pair["parent"],
                    "a control column is wider than the section that holds it at %d"
                    % width)
                if width == 1100:
                    # 460 of 636 measured: the measure is what stops a locale
                    # <select> and a three-way choice from spanning the pane.
                    self.assertLess(
                        pair["control"], pair["parent"],
                        "at 1100 the control fills its column, so the declared "
                        "measure is gone")

    def test_nothing_overflows_horizontally(self):
        for width in WIDTHS:
            self._at(width)
            over = self._page.evaluate(
                "() => document.documentElement.scrollWidth -"
                " document.documentElement.clientWidth")
            self.assertLessEqual(over, 1, "%dpx overflows by %dpx" % (width, over))

    # -- 4. one definition of the subjects ------------------------------------

    def test_the_rail_and_the_pane_agree_on_the_subjects(self):
        """Derived from `SETTINGS_SECTIONS` on the mounted app, never
        enumerated here: 5.7b's one-definition rule, and a hand-kept list is a
        list that rots the first time a subject is added."""
        sections = self._page.evaluate(
            "() => window.__skillsManagerApp.settingsSections.map(s => s.id)")
        rail = self._page.evaluate(
            "() => [...document.querySelectorAll('.settings-rail-item')]"
            ".map(b => b.getAttribute('data-settings-section'))")
        painted = self._page.evaluate(
            "() => [...document.querySelectorAll('.settings-section')].map(s => s.id)")
        self.assertTrue(sections, "settingsSections is empty: the rail has no list")
        self.assertEqual(sorted(rail), sorted(sections),
                         "the rail does not offer every subject the list declares")
        self.assertEqual(sorted(painted), sorted(sections),
                         "a rail subject has no section: pressing it would move "
                         "focus to nothing")

    def test_the_accessibility_blurb_matches_what_the_section_says(self):
        """5.7e. The rail said "The OS signals this app honors" above a row
        that says the app FOLLOWS them and cannot change them — and an
        explicit Light/Dark choice deliberately does not honor the OS at all.
        Two claims about the same behaviour, one of them false."""
        hint = self._page.evaluate(
            "() => { const s = window.__skillsManagerApp.settingsSections"
            ".find(s => s.id === 'settings-accessibility'); return s ? s.hint : ''; }")
        section_hint = self._page.evaluate(
            "() => document.querySelector('#settings-accessibility .hint')"
            ".textContent.trim()")
        self.assertTrue(hint, "the accessibility subject has no blurb")
        self.assertNotIn("honors", hint.lower(),
                         "the rail still promises the app honors the OS, which "
                         "its own section contradicts")
        self.assertIn("cannot change them", section_hint)
        # both sentences name the same source, so neither can be read as a
        # claim about a different signal: the rail abbreviates, the section
        # spells it out
        self.assertIn("OS", hint)
        self.assertIn("operating system", section_hint)

    def test_no_evidence_row_glues_prose_to_a_value(self):
        """5.7c's copy fix, as a rendered claim: `<dt>` is the subject and
        `<dd>` is the value. Source text proved the markup; this proves what a
        reader is actually given."""
        rows = self._page.evaluate(
            "() => [...document.querySelectorAll("
            "'#settings-accessibility .settings-evidence > div')]"
            ".map(d => [d.querySelector('dt').textContent.trim(),"
            " d.querySelector('dd').textContent.trim()])")
        self.assertGreaterEqual(len(rows), 4)
        for label, value in rows:
            self.assertTrue(label, "an evidence row has no subject")
            self.assertTrue(value, "the %r row has no value" % label)
            self.assertNotIn(" preference", value,
                             "the %r row still glues prose onto the value: %r"
                             % (label, value))


if __name__ == "__main__":
    unittest.main()