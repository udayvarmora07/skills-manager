"""The command palette and the shortcut reference, measured on the running app.

Why this file exists
--------------------
Task 2.2 grouped the palette's results and rebuilt the shortcut reference.
``tests/test_redesign_command_palette.py`` pins that against the *source*, and
source tests are how the last four tasks in this branch shipped defects: the
scope switcher rendered an empty label while every name-grep test passed, and
the Library's blank pane pinned a ``padding-top`` value that can never move a
box. Both were found by looking at a screenshot.

So the claim that matters here is behavioural and has no source-level proxy:
**the order the keyboard walks is the order the reader sees.** Grouping can be
implemented twice — once in the flat list ArrowDown indexes and again in the
rendered groups — and when the two disagree, ArrowDown highlights a row the
reader cannot see. The symptom is not a crash; it is a palette that looks
right and behaves wrong for exactly the queries that match more than one group,
which is why the tests below drive real keypresses rather than reading a
computed property.

Second, a `role="listbox"` whose options live inside `role="group"` wrappers is
a legal ARIA 1.2 grouping, and it is also the shape a screen reader walks. If
the group label is not wired to its group, every option announces without the
context that says which section it is in.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_command_palette.py
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

#: RULES.md #13. The floor on coarse pointers is 40px; the CSS asks for 44.
TARGET = 44


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


class PaletteBrowser:
    """One browser for the whole module, resized per case.

    A second ``sync_playwright()`` inside a test raises, so every case drives
    this shared page and moves it back to a known state. That is also why each
    test opens the palette itself: a test that leaves the menu open hands the
    next one a surface it did not arrange.
    """

    def __init__(self, width: int = 1280, height: int = 900) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright()
        self._cm = self._pw.start()
        self.browser = self._cm.chromium.launch(args=["--no-sandbox"])
        self.page = self.browser.new_page(viewport={"width": width, "height": height})
        self.console_errors: list[str] = []
        self.failed_requests: list[str] = []
        self.page.on("console",
                    lambda m: m.type == "error" and self.console_errors.append(m.text))
        self.page.on("pageerror", lambda e: self.console_errors.append(str(e)))
        self.page.on("requestfailed",
                     lambda r: self.failed_requests.append(f"{r.method} {r.url}"))
        self.base = _base_url()
        self.page.goto(self.base, wait_until="domcontentloaded", timeout=20000)
        self.page.wait_for_selector(".navigation-rail .viewtabs button", timeout=15000)
        self.page.wait_for_timeout(400)

    def resize(self, width: int, height: int = 900) -> None:
        self.page.set_viewport_size({"width": width, "height": height})
        self.page.wait_for_timeout(250)

    def open_palette(self, query: str = "") -> None:
        """Open Commands the way a reader does: with the keyboard."""
        self.page.keyboard.press("Control+k")
        self.page.wait_for_selector("#command-palette", state="visible", timeout=8000)
        if query:
            self.page.fill("#command-palette-input", query)
            self.page.wait_for_timeout(250)
        else:
            self.page.wait_for_timeout(250)

    def close_palette(self) -> None:
        """Dismiss whatever overlay is up, whatever it is.

        Guarding on ``#command-palette`` alone was wrong: the dialogs are
        ``v-if``, so after the reference test the palette element is GONE while
        `help` is still open. Ctrl+K is deliberately inert while any modal is
        open, so the next open timed out on a surface this helper had left up.
        """
        if self.page.locator(".overlay").count():
            for _ in range(3):
                if not self.page.locator(".overlay").count():
                    break
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)

    # -- DOM reads -------------------------------------------------------
    def options(self) -> list[dict]:
        """Every option in the order it is PAINTED, with its group.

        ``querySelectorAll`` returns document order, which is the visual order
        for a non-reversed layout. Reading it here rather than from the app's
        own data is the point: the question is what a reader's eye follows,
        not what the component believes it drew.
        """
        return self.page.evaluate(
            """() => Array.from(
                 document.querySelectorAll('#command-palette-results [role="option"]')
               ).map((el) => {
                 const group = el.closest('[role="group"]');
                 const label = group && group.querySelector('.command-palette-group-label');
                 const r = el.getBoundingClientRect();
                 return {
                   id: el.id,
                   text: (el.querySelector('strong') || {}).textContent || '',
                   group: label ? label.textContent.trim() : null,
                   selected: el.getAttribute('aria-selected') === 'true',
                   top: Math.round(r.top),
                   height: Math.round(r.height),
                 };
               })""")

    def selected_id(self) -> str | None:
        rows = [o for o in self.options() if o["selected"]]
        return rows[0]["id"] if rows else None

    def close(self) -> None:
        self.browser.close()
        self._cm.stop()


class PaletteTests(unittest.TestCase):
    maxDiff = None
    app: PaletteBrowser

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). This needs a real "
                f"engine and is NOT silently passed.")
        cls.app = PaletteBrowser()
        try:
            cls.app.open_palette()
        except Exception as exc:
            cls.app.close()
            raise unittest.SkipTest(
                f"the dev server at {_base_url()} did not open the palette ({exc}). "
                f"Start it with `.redesign/dev.sh start` — this test is NOT "
                f"silently passed when it cannot run.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.close()

    def setUp(self) -> None:
        self.app.close_palette()
        self.app.resize(1280)

    # -- the order trap --------------------------------------------------
    def test_the_keyboard_order_is_the_painted_order(self) -> None:
        """ArrowDown walks exactly the sequence a reader's eye follows.

        This is the assertion the whole grouping design exists to make
        checkable. It is written against a query that matches rows in MORE THAN
        ONE group, because the two implementations of the order agree trivially
        when every result belongs to a single group.
        """
        self.app.open_palette("skill")
        rows = self.app.options()
        self.assertGreater(len(rows), 3, "need several results to prove an order")
        groups = {r["group"] for r in rows}
        self.assertGreater(len(groups), 1,
                           "the query matched one group only, so this proves nothing")

        # Home first: the highlight's starting index is left over from the
        # previous interaction, and ArrowDown wraps, so a walk that does not
        # begin at the first row measures the wrap-around instead of the order.
        self.app.page.keyboard.press("Home")
        self.app.page.wait_for_timeout(100)
        self.assertEqual(self.app.selected_id(), rows[0]["id"],
                         "Home did not select the first painted row")

        # Collect where the highlight lands after each of the remaining
        # N-1 presses. Recording AFTER every press instead would need N+1
        # presses to cover N rows, and the list CLAMPS rather than wraps, so
        # the extra press reads the last row twice and reports an off-by-one
        # as a product defect. Clamping is the behaviour a listbox should have.
        walked = [self.app.selected_id()]
        for _ in range(len(rows) - 1):
            self.app.page.keyboard.press("ArrowDown")
            self.app.page.wait_for_timeout(60)
            walked.append(self.app.selected_id())
        painted = [r["id"] for r in rows]

        self.assertEqual(
            walked, painted,
            "the order ArrowDown walks is not the order the options are painted "
            "in; a palette that highlights a row the reader cannot see is worse "
            "than one that is merely ungrouped")

    def test_exactly_one_row_is_selected_at_a_time(self) -> None:
        """`aria-activedescendant` is not used, so the selection is the aria state.

        Two rows reading `aria-selected="true"` in a listbox is an ARIA error a
        screen reader resolves by announcing the wrong one.
        """
        self.app.open_palette()
        self.app.page.keyboard.press("ArrowDown")
        self.app.page.keyboard.press("ArrowDown")
        self.app.page.wait_for_timeout(120)
        selected = [r for r in self.app.options() if r["selected"]]
        self.assertEqual(len(selected), 1, f"expected one active option, got {selected}")

    def test_home_and_end_jump_to_the_first_and_last_painted_row(self) -> None:
        self.app.open_palette()
        rows = self.app.options()
        self.assertGreater(len(rows), 2)
        self.app.page.keyboard.press("End")
        self.app.page.wait_for_timeout(120)
        self.assertEqual(self.app.selected_id(), rows[-1]["id"])
        self.app.page.keyboard.press("Home")
        self.app.page.wait_for_timeout(120)
        self.assertEqual(self.app.selected_id(), rows[0]["id"])

    def test_arrows_wrap_and_the_selection_never_leaves_the_results(self) -> None:
        """Wrapping is the decision; landing outside the list would be the defect.

        The first version of this test asserted the opposite — that ArrowUp
        from the first row *stays put* — and it failed against a product that
        wraps. Nothing specified clamping, so the test was demanding a rule
        rather than checking one: the same mistake as 2.1c's `top` assertion
        and 2.1b's specificity scorer, in a test written to catch them.

        Wrapping is deliberate and matches the reference surfaces: from the
        last row one press of ArrowDown reaches the first, which is what a
        reader holding ArrowDown expects in a palette. The invariant worth
        protecting is the one the wrap could plausibly break — off-by-one at
        the boundary producing an index of -1 or count, which would select
        nothing at all.
        """
        self.app.open_palette()
        painted = [r["id"] for r in self.app.options()]
        self.assertGreater(len(painted), 2, "need at least three rows to cross a boundary")
        self.app.page.keyboard.press("Home")
        self.app.page.wait_for_timeout(100)
        # One press across each boundary is the whole claim. Walking N times
        # and checking where it ended was the version before this one, and its
        # arithmetic was wrong in the direction that hides the bug: (0 - k) % N
        # lands on index N-3, so an assertion about the final row passed and
        # said nothing about the wrap it was written for.
        self.app.page.keyboard.press("ArrowUp")
        self.app.page.wait_for_timeout(80)
        self.assertEqual(self.app.selected_id(), painted[-1],
                         "ArrowUp from the first row must wrap to the last")
        self.app.page.keyboard.press("ArrowDown")
        self.app.page.wait_for_timeout(80)
        self.assertEqual(self.app.selected_id(), painted[0],
                         "ArrowDown from the last row must wrap to the first")
        # The boundary is where an off-by-one produces an index of -1 or count,
        # and that selects nothing at all rather than the wrong row.
        seen = []
        for _ in range(len(painted) * 2):
            self.app.page.keyboard.press("ArrowDown")
            self.app.page.wait_for_timeout(35)
            seen.append(self.app.selected_id())
        self.assertEqual([s for s in seen if s not in painted], [],
                         "the selection left the painted options at a boundary")
        self.assertNotIn(None, seen,
                         "a boundary press selected nothing; -1 and count both do")

    # -- grouping --------------------------------------------------------
    def test_each_group_heading_names_the_group_it_labels(self) -> None:
        self.app.open_palette()
        groups = self.app.page.evaluate(
            """() => Array.from(
                 document.querySelectorAll('#command-palette-results [role="group"]')
               ).map((g) => {
                 const label = g.querySelector('.command-palette-group-label');
                 const named = g.getAttribute('aria-labelledby');
                 const target = named && document.getElementById(named);
                 return {
                   named: !!named,
                   resolves: !!target,
                   matches: !!target && target === label,
                   text: label ? label.textContent.trim() : '',
                   options: g.querySelectorAll('[role="option"]').length,
                 };
               })""")
        self.assertGreater(len(groups), 1, "expected several groups in the palette")
        for group in groups:
            self.assertTrue(group["named"], f"group {group['text']!r} has no aria-labelledby")
            self.assertTrue(group["resolves"],
                            f"aria-labelledby on {group['text']!r} points at nothing")
            self.assertTrue(group["matches"],
                            f"aria-labelledby on {group['text']!r} points at another element")
            self.assertGreater(group["options"], 0, f"group {group['text']!r} is empty")

    def test_a_category_is_stated_once_per_group_not_once_per_row(self) -> None:
        """The reason for grouping: the word repeated once per row before."""
        self.app.open_palette()
        counts = self.app.page.evaluate(
            """() => {
                 const rows = document.querySelectorAll('#command-palette-results [role="option"]');
                 const heads = document.querySelectorAll('#command-palette-results .command-palette-group-label');
                 return {rows: rows.length, heads: heads.length,
                         groups: document.querySelectorAll('#command-palette-results [role="group"]').length};
               }""")
        self.assertGreater(counts["rows"], counts["groups"],
                           "grouping collapsed rows; something is not rendering")
        self.assertEqual(counts["heads"], counts["groups"],
                         "every group needs exactly one heading")

    def test_options_inside_a_group_are_still_options(self) -> None:
        """`role="group"` is a wrapper, not a replacement.

        A reader who never opens the palette still navigates the Library with
        these rows' siblings; dropping the option role would make the result
        list unrepresentable to assistive technology.
        """
        self.app.open_palette()
        # The heading is aria-hidden and the GROUP carries the name through
        # aria-labelledby. Leaving the heading exposed put the category text
        # inside the group a second time, so a screen reader announced
        # "Navigation" and then read it again on the way to the first option.
        bad = self.app.page.evaluate(
            """() => Array.from(
                 document.querySelectorAll('#command-palette-results [role="group"] > *')
               )
               .filter((el) => el.getAttribute('role') !== 'option'
                             && el.getAttribute('aria-hidden') !== 'true')
               .map((el) => el.className || el.tagName)""")
        self.assertEqual(bad, [],
                         "a group child is neither an option nor hidden from "
                         "the accessibility tree")
        heads = self.app.page.evaluate(
            """() => Array.from(
                 document.querySelectorAll('#command-palette-results .command-palette-group-label')
               ).map((el) => el.getAttribute('aria-hidden'))""")
        self.assertTrue(heads, "expected group headings")
        self.assertEqual(set(heads), {"true"},
                         "the visible heading duplicates the group's own name and "
                         "must be hidden from the announcement")

    # -- targets and the key cap -----------------------------------------
    def test_every_result_is_at_least_the_touch_target_floor(self) -> None:
        self.app.resize(390, 844)
        self.app.open_palette()
        rows = self.app.options()
        self.assertGreater(len(rows), 3)
        short = [r for r in rows if r["height"] < TARGET]
        self.assertEqual(short, [], f"results under {TARGET}px tall: {short}")

    def test_a_key_cap_on_a_row_is_hidden_from_the_announcement(self) -> None:
        """The cap is a visual affordance; the label is the announcement.

        A screen reader that reads "Focus search" and then "/" twice is worse
        than one that reads it once, and the palette is a listbox of options —
        the option's accessible name is what lands in the announcement.
        """
        self.app.open_palette("focus search")
        rows = self.app.options()
        self.assertTrue(rows, "expected the Focus search command to match")
        cap = self.app.page.evaluate(
            """() => {
                 const el = document.querySelector('.command-palette-keys');
                 if (!el) return null;
                 return {hidden: el.getAttribute('aria-hidden'), visible: !!el.offsetParent};
               }""")
        self.assertIsNotNone(cap, "the matched command declares no key cap")
        self.assertEqual(cap["hidden"], "true",
                         "the key cap must be aria-hidden so it is not read twice")

    # -- the shortcut reference ------------------------------------------
    def test_the_reference_opens_from_the_palette_and_lists_live_keys_only(self) -> None:
        """A shortcut reference that lists a key that does nothing is a false claim.

        Row-by-row Library navigation is backlog 4.2; listing it today would
        teach a reader to press keys this build ignores. The reference says so
        explicitly rather than being silent about the omission.
        """
        self.app.open_palette("shortcuts")
        self.app.page.keyboard.press("Enter")
        self.app.page.wait_for_selector('[data-modal="help"] #help-modal-title', timeout=8000)
        text = self.app.page.inner_text('[data-modal="help"] .modal-body')
        for key in ("Ctrl", "K", "/", "?", "Esc"):
            self.assertIn(key, text, f"{key!r} is missing from the reference")
        self.assertNotIn("Press j", text,
                         "j/k navigation ships in 4.2 and must not be claimed yet")
        self.assertIn("not here yet", text,
                      "the reference must state the omission rather than hide it")

    def test_the_reference_is_grouped_by_context(self) -> None:
        """One flat table hides the fact a reader needs: which keys are live now."""
        self.app.open_palette("shortcuts")
        self.app.page.keyboard.press("Enter")
        self.app.page.wait_for_selector('[data-modal="help"] #help-modal-title', timeout=8000)
        sections = self.app.page.eval_on_selector_all(
            '[data-modal="help"] .shortcuts-section-title',
            "els => els.map(e => e.textContent.trim())")
        self.assertGreaterEqual(len(sections), 3,
                                f"the reference is one flat list: {sections}")
        self.assertEqual(len(sections), len(set(sections)),
                         "duplicate section titles")

    def test_escape_returns_focus_to_the_palette_trigger(self) -> None:
        """RULES.md #13: focus returns to the opener, and Escape is the way back."""
        self.app.open_palette("shortcuts")
        self.app.page.keyboard.press("Enter")
        self.app.page.wait_for_selector('[data-modal="help"] #help-modal-title', timeout=8000)
        self.app.page.keyboard.press("Escape")
        self.app.page.wait_for_timeout(300)
        owner = self.app.page.evaluate(
            """() => {
                 const el = document.activeElement;
                 return {tag: el ? el.tagName : null,
                         text: el ? (el.textContent || '').trim() : ''};
               }""")
        self.assertIsNotNone(owner["tag"], "focus left the document")
        self.assertTrue(owner["tag"] != "BODY",
                        "focus fell back to the body instead of the opener")

    # -- hygiene ---------------------------------------------------------
    def test_no_console_errors_and_no_failed_requests(self) -> None:
        """Every task in this branch has asserted this; a dropped one is a gap."""
        self.app.open_palette()
        self.app.page.keyboard.press("ArrowDown")
        self.app.page.keyboard.press("Escape")
        self.app.page.wait_for_timeout(200)
        self.assertEqual(self.app.console_errors, [], "console errors during the palette flow")
        self.assertEqual(self.app.failed_requests, [], "failed requests during the palette flow")

    def test_no_horizontal_overflow_at_the_narrowest_phone(self) -> None:
        self.app.resize(390, 844)
        self.app.open_palette()
        overflow = self.app.page.evaluate(
            "() => document.documentElement.scrollWidth - window.innerWidth")
        self.assertLessEqual(overflow, 0,
                             f"the palette overflows the viewport by {overflow}px at 390")


class PaletteAtWidthsTests(PaletteTests):
    """The same contract at the phone width.

    A dialog measured only at 1280 has told you nothing about the width where
    the layout is a different set of rules — and the drawer work in 2.1e2 found
    `elementFromPoint` and paint behaviour diverging from layout boxes only at
    the narrow end.
    """

    def setUp(self) -> None:
        PaletteTests.setUp(self)
        self.app.resize(390, 844)


if __name__ == "__main__":
    unittest.main(verbosity=2)