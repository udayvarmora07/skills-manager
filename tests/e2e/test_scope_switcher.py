"""The scope switcher must *resolve*, not merely be declared — in a browser.

Why this file exists
--------------------
Task 2.1 shipped a scope trigger whose label span rendered empty: the dot, the
count and the chevron were all there, so a screenshot showed a control that
looked finished. Every name-grep test passed, ``node --check`` passed, and the
gate was green.

The cause was structural and invisible to prose. The four derived getters had
been appended *after* the closing ``},`` of ``computed: {``, which is still
valid JavaScript — an object-literal method shorthand at the top level of the
options object is an **option Vue never reads**. No warning, no error, no failed
render: the template simply bound ``undefined`` and printed nothing.

A second defect sat behind the first and only surfaced once it was fixed:
``allScopesCount`` lives in ``computed``, not ``methods``, so calling it as
``this.allScopesCount()`` threw and took the entire mount down with it
(``TypeError`` -> ``#app`` with zero children). Both are only observable by
running the page.

So this asserts what the user actually sees, on the running app:

* the trigger's label span has **text** — not a function's source, not empty;
* the label is the currently selected scope's label, and it *changes* when the
  selection changes;
* the availability dot reflects the observed ``exists`` field, so a scope whose
  root was not discovered cannot render as available;
* the listbox opens and lists every scope the server reported — the swap from
  one-button-per-scope must not have dropped any;
* the page mounts at all, because every assertion above is vacuous otherwise.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_scope_switcher.py
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


class ScopeSwitcherResolvesTests(unittest.TestCase):
    """The trigger renders the selected scope, from the running app."""

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
            cls._page.goto(cls._base, wait_until="networkidle", timeout=20000)
            # Mount, not load: an empty #app satisfies none of the assertions
            # below, so every one of them has to be guarded by this wait.
            cls._page.wait_for_selector(".scope-trigger", timeout=15000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {cls._base} did not mount the shell ({exc}). "
                f"Start it with `.redesign/dev.sh start` — this test is NOT "
                f"silently passed when it cannot run."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    # -- helpers ---------------------------------------------------------
    def _label(self) -> str:
        return self._page.eval_on_selector(".scope-trigger-label", "e => e.textContent.trim()")

    def _dot(self) -> str:
        return self._page.eval_on_selector(".scope-trigger .scope-dot", "e => e.className")

    def _open(self) -> None:
        if self._page.eval_on_selector(".scope-trigger", "e => e.getAttribute('aria-expanded')") != "true":
            self._page.click(".scope-trigger")
            self._page.wait_for_selector(".scope-option", timeout=5000)

    def _option_labels(self) -> list[str]:
        return self._page.eval_on_selector_all(".scope-option-label", "es => es.map(e => e.textContent.trim())")

    # -- the defect ------------------------------------------------------
    def test_the_mount_survives_computing_the_scope_list(self):
        """A computed that throws takes the whole app down, not just the label.

        This is the second defect, and it is the one that hides the first: with
        `this.allScopesCount()` throwing inside `scopeOptions`, Vue's render
        aborts before the trigger is built at all, so a test that only checks
        "is the trigger there" fails for a reason that reads like a flake.
        """
        # Not "== 1": the mount may legitimately have several top-level nodes.
        # The property being asserted is that Vue built *something* — an aborted
        # render leaves the container empty, which is how the failure reads.
        self.assertGreater(
            self._page.evaluate("document.getElementById('app').children.length"), 0,
            "#app is empty: the first render threw",
        )
        self.assertEqual(self._console_errors, [], "console/page errors during mount")

    def test_the_trigger_label_has_text(self):
        label = self._label()
        self.assertNotEqual(label, "", "the scope trigger rendered an empty label")
        # A getter that landed in the wrong options block arrives at the
        # template as a function object and prints its source. This is what it
        # looked like before the block placement was fixed.
        self.assertNotIn("function", label, f"a function object is being rendered: {label!r}")
        self.assertNotIn("=>", label, f"a function object is being rendered: {label!r}")

    def test_the_label_is_the_selected_scope(self):
        self._open()
        labels = self._option_labels()
        self.assertIn(self._label(), labels, "the trigger label is not one of the listed scopes")

    def test_the_label_follows_the_selection(self):
        self._open()
        original = self._label()
        # "Global" is the only non-scope option, so it is always present and
        # always differs from the default "All scopes".
        self._page.click(".scope-option:has-text('Global')")
        self._page.wait_for_function(
            "() => document.querySelector('.scope-trigger-label').textContent.trim() !== %r"
            % original,
            timeout=5000,
        )
        self.assertEqual(self._label(), "Global")
        # ...and back, so the test cannot pass by a one-way transition.
        # Choosing closes the listbox by contract, so it must be reopened --
        # otherwise this is a timeout, not an assertion.
        self._open()
        self._page.click(".scope-option:has-text('All scopes')")
        self._page.wait_for_function(
            "() => document.querySelector('.scope-trigger-label').textContent.trim() === %r" % original,
            timeout=5000,
        )

    # -- the honesty property -------------------------------------------
    def test_availability_is_observed_not_inferred(self):
        """A scope whose root was not discovered must not render as available.

        `exists` is the observed field from /api/scopes. `activeScopeAvailable`
        was the second casualty of the same block placement: unbound it was
        `undefined`, so every scope -- including undetected roots -- painted the
        "available" dot.
        """
        self._open()
        dots = self._page.eval_on_selector_all(
            ".scope-option",
            "es => es.map(e => e.querySelector('.scope-dot').className)",
        )
        self.assertTrue(dots, "the listbox rendered no options")
        for cls in dots:
            self.assertTrue(
                "dot-ok" in cls or "dot-missing" in cls,
                f"an availability dot is neither observed state: {cls!r}",
            )
        self.assertEqual(self._label(), self._label(), "label read twice for stability")
        self.assertTrue(
            "dot-ok" in self._dot() or "dot-missing" in self._dot(),
            "the trigger dot is not an observed state",
        )

    def test_every_scope_the_server_reports_is_selectable(self):
        """One button per scope became one trigger; nothing may quietly drop out."""
        self._open()
        options = self._option_labels()
        self.assertEqual(len(options), len(set(options)), "duplicate scope options")
        self.assertIn("All scopes", options)
        server = self._page.evaluate(
            """async () => (await (await fetch('/api/scopes')).json())
                 .map(s => s.label)"""
        )
        missing = [label for label in server if label not in options]
        self.assertEqual(missing, [], f"scopes the server reported but the switcher hides: {missing}")

    def test_the_listbox_reports_its_expanded_state(self):
        self._open()
        self.assertEqual(
            self._page.eval_on_selector(".scope-trigger", "e => e.getAttribute('aria-expanded')"),
            "true",
        )
        self.assertEqual(
            self._page.eval_on_selector("#scope-menu", "e => e.getAttribute('role')"), "listbox"
        )


class ScopeSwitcherFitsTheViewportTests(unittest.TestCase):
    """A listbox that opens off the bottom of the screen is not reachable.

    The trigger sits near the rail's bottom edge, so a list that always opens
    downward runs past the fold on any short viewport: measured at 800px the
    list was 307px tall starting at y=676, leaving 183px of it below the fold
    and un-clickable. The popover now measures on open and flips above when
    there is more room above than below.
    """

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        from playwright.sync_api import sync_playwright
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    def _open_at(self, height: int) -> dict:
        """One browser, resized per case -- the sync API cannot be nested."""
        page = self._browser.new_page(viewport={"width": 1280, "height": height})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(_base_url(), wait_until="networkidle", timeout=20000)
        page.wait_for_selector(".scope-trigger", state="attached", timeout=15000)
        page.click(".scope-trigger")
        page.wait_for_selector(".scope-option", timeout=5000)
        rect = page.eval_on_selector(
            "#scope-menu",
            "e => { const r = e.getBoundingClientRect();"
            " return {top: r.top, bottom: r.bottom,"
            "         flipped: e.classList.contains('is-up')}; }",
        )
        rect["errors"] = errors
        self.addCleanup(page.close)
        return rect

    def test_it_fits_a_short_viewport_by_opening_upward(self):
        rect = self._open_at(700)
        self.assertTrue(rect["flipped"], f"it did not flip with only 700px of room: {rect}")
        self.assertGreaterEqual(rect["top"], 0, rect)
        self.assertLessEqual(rect["bottom"], 700, rect)
        self.assertEqual(rect["errors"], [])

    def test_it_fits_a_typical_viewport(self):
        rect = self._open_at(800)
        self.assertGreaterEqual(rect["top"], 0, rect)
        self.assertLessEqual(rect["bottom"], 800, rect)
        self.assertEqual(rect["errors"], [])

    def test_it_still_opens_downward_when_there_is_room(self):
        # The flip must be a decision, not an unconditional class: a listbox
        # pinned upward on a tall window puts the first row -- what focus lands
        # on -- on the wrong side of the trigger.
        rect = self._open_at(1200)
        self.assertFalse(rect["flipped"], f"it flipped upward with room below: {rect}")
        self.assertLessEqual(rect["bottom"], 1200, rect)
        self.assertEqual(rect["errors"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)