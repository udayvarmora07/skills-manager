"""Contracts for the v2 app shell (backlog 2.1).

The shell is chrome, so almost none of it is worth a screenshot assertion. What
*is* worth pinning is the behaviour that a redraw silently drops: the scope
switcher is a listbox with a real keyboard contract, the availability dot is an
observed fact rather than an inference, and the wordmark is the product's own
mark rather than a stock tool icon.

These read the template and the Vue source as text. They are not a substitute
for driving the real thing -- `shots.py` renders the shell at six viewports in
both themes -- but they catch the regressions that survive a screenshot review
because the picture still looks right.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _between(text, start, end):
    head = text.index(start) + len(start)
    return text[head : text.index(end, head)]


class ScopeSwitcherMarkupTests(unittest.TestCase):
    """The rail shows one trigger; the scopes live in a popover listbox."""

    def setUp(self):
        self.picker = _between(HTML, '<div class="dropdown scopepicker"', "</aside>")

    def test_the_trigger_is_a_button_with_listbox_semantics(self):
        # A div with @click is unreachable by keyboard and announces nothing.
        self.assertIn('<button ref="scopeMenuTrigger"', self.picker)
        self.assertIn('aria-haspopup="listbox"', self.picker)
        self.assertIn('aria-controls="scope-menu"', self.picker)
        self.assertIn(':aria-expanded="scopeMenuOpen ? \'true\' : \'false\'"', self.picker)

    def test_the_popover_is_a_listbox_and_options_carry_selection_state(self):
        self.assertIn('role="listbox"', self.picker)
        self.assertIn('role="option"', self.picker)
        self.assertIn(':aria-selected="opt.id === activeScope ? \'true\' : \'false\'"', self.picker)

    def test_availability_is_shown_and_never_inferred(self):
        # `exists` is the observed fact from /api/scopes. An undiscovered root
        # is NOT an empty library, so the copy says "not detected" and the
        # option stays selectable -- collapsing the two is the honesty defect
        # rule 12 exists to prevent.
        self.assertIn("opt.exists ? 'dot-ok' : 'dot-missing'", self.picker)
        self.assertIn("Root not detected on this machine", self.picker)
        self.assertNotIn(":disabled", self.picker)

    def test_every_scope_reachable_in_the_old_flat_list_is_still_reachable(self):
        # The swap removed one button per scope. Nothing may quietly drop out.
        self.assertIn("v-for=\"opt in scopeOptions\"", self.picker)
        self.assertIn('id: "all"', APP)
        self.assertIn('label: "All scopes"', APP)


class ScopeSwitcherBehaviourTests(unittest.TestCase):
    """Keyboard, focus return, and the two popovers not fighting each other."""

    def test_escape_returns_focus_to_the_trigger(self):
        self.assertIn("closeScopeMenu(true)", APP)
        self.assertRegex(APP, r"if \(this\.scopeMenuOpen\) this\.closeScopeMenu\(true\);")
        self.assertIn("this.$nextTick(() => trigger && trigger.focus());", APP)

    def test_the_listbox_is_a_single_tab_stop_and_arrows_roam_it(self):
        # Tab must leave the listbox rather than walk 9 rows; arrows move within.
        self.assertRegex(APP, r'if \(e\.key === "Tab"\) \{[^}]*closeScopeMenu\(false\)')
        for key in ("ArrowDown", "ArrowUp", "Home", "End"):
            self.assertIn(f'e.key === "{key}"', APP)

    def test_opening_the_scope_list_closes_the_actions_menu(self):
        # Two popovers, one owner. Leaving both open stacks them at right:0.
        toggle = _between(APP, "toggleScopeMenu() {", "closeScopeMenu(restoreFocus = false)")
        self.assertIn("this.menuOpen = false;", toggle)

    def test_a_click_outside_dismisses_it(self):
        mousedown = _between(APP, "onDocMousedown(e) {", "menuDo(action)")
        self.assertIn("this.$refs.scopeMenuWrap && !this.$refs.scopeMenuWrap.contains(e.target)",
                      mousedown)
        self.assertIn("this.scopeMenuOpen = false;", mousedown)

    def test_choosing_a_scope_returns_focus_to_the_trigger(self):
        choose = _between(APP, "chooseScope(id) {", "onScopeMenuKeydown(e)")
        self.assertIn("this.activeScope = id;", choose)
        self.assertIn("this.closeScopeMenu(true);", choose)

    def test_state_starts_closed(self):
        self.assertRegex(APP, r"scopeMenuOpen: false,")

    def test_the_derived_values_live_in_computed_not_methods(self):
        # Found by rendering, not by reasoning: appended to `methods`, the four
        # pure getters were handed to the template as function objects and the
        # scope trigger rendered `function() { [native code] }` where the label
        # belongs. It is invisible to a syntax check and to every test that
        # only greps for a name, so the placement itself is pinned.
        computed = _between(APP, "  computed: {", "  watch: {")
        methods = _between(APP, "  methods: {", "}).mount(\"#app\")")
        for name in ("scopeOptions", "activeScopeOption", "activeScopeLabel",
                     "activeScopeAvailable"):
            self.assertRegex(computed, rf"(?m)^\s*{name}\(\) \{{")
            self.assertNotRegex(methods, rf"(?m)^\s*{name}\(\) \{{")
        # The imperative half belongs in methods, so this is not just "not the
        # other block" -- each half is asserted where it has to be.
        for name in ("toggleScopeMenu", "closeScopeMenu", "chooseScope",
                     "onScopeMenuKeydown", "scopeMenuItems"):
            self.assertRegex(methods, rf"(?m)^\s*{name}\(")

    def test_a_method_is_not_stored_as_a_value(self):
        # `allScopesCount` is a method; `count: this.allScopesCount` stores the
        # function object. Both this and the block placement above were the same
        # class of mistake and are worth a standing check on any new derived row.
        self.assertNotRegex(APP, r"count: this\.allScopesCount[,}\s]")
        self.assertRegex(APP, r"count: this\.allScopesCount\(\),")


class DeadShellCssTests(unittest.TestCase):
    """CSS the shell no longer renders is a lie about coverage (task 1.5)."""

    def test_the_retired_flat_scope_list_is_gone(self):
        self.assertNotIn(".scopebar", CSS)
        self.assertNotIn(".scope-link", CSS)
        self.assertNotIn('class="scope-link"', HTML)

    def test_the_new_selectors_are_declared_from_tokens_only(self):
        block = _between(CSS, "/* --- scope switcher (v2 shell)", "/* --- wordmark")
        sizes = re.findall(r"font-size:\s*([^;]+);", block)
        self.assertTrue(sizes)
        for value in sizes:
            self.assertTrue(
                re.fullmatch(r"var\(--t-[a-z-]+\)", value.strip()),
                f"scope-switcher font-size {value!r} is a literal, not a type step",
            )


class WordmarkTests(unittest.TestCase):
    def test_the_mark_is_geometric_and_stacked(self):
        mark = re.search(r'<svg class="brand-glyph".*?</svg>', HTML, re.S).group(0)
        self.assertGreaterEqual(len(re.findall(r"<path\b", mark)), 2)
        self.assertIn('viewBox="0 0 20 20"', mark)

    def test_the_name_is_the_package_name_in_mono(self):
        self.assertIn('<span class="brand-name">skills-manager</span>', HTML)
        block = _between(CSS, "/* --- wordmark", "\n\n")
        self.assertIn("font-family: var(--mono);", block)

    def test_the_retired_wrench_mark_is_not_still_referenced(self):
        # The Lucide `wrench` symbol legitimately stays in the sprite -- other
        # surfaces still use it. What must go is the *brand* pointing at a
        # stock tool icon, so the assertion is scoped to the brand button.
        brand = _between(HTML, '<button class="brand"', "</button>")
        self.assertNotIn("wrench", brand)
        self.assertNotIn("brand-mark", brand)


if __name__ == "__main__":
    unittest.main()