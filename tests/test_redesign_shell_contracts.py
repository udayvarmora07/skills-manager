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

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _between(text, start, end):
    head = text.index(start) + len(start)
    return text[head : text.index(end, head)]


# Loads the real app.js in a Node VM with the seams stubbed, and reports which
# block each option actually landed in. The two blocks are separate namespaces
# to Vue, so "the name is in the file" is not the question -- "the name is in
# the block Vue reads" is.
_OPTIONS_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {},
  Vue: {createApp(def) { sandbox.def = def; return {mount() {}}; },
         nextTick(fn) { if (fn) fn(); return Promise.resolve(); }},
  localStorage: {getItem() { return null; }, setItem() {}},
  document: {
    addEventListener() {}, removeEventListener() {},
    documentElement: {dataset: {}},
    querySelectorAll() { return []; }, querySelector() { return null; },
    getElementById() { return null; },
    createElement() { return {style: {}, setAttribute() {}, appendChild() {},
                              click() {}, remove() {}}; },
    contains() { return false; }, activeElement: null, body: {appendChild() {}},
  },
  fetch: async () => ({ok: true, status: 200,
    headers: {get: () => null}, json: async () => ({}),
    text: async () => '', blob: async () => ({})}),
  setTimeout, clearTimeout, console,
  URL: {createObjectURL() { return 'blob:x'; }, revokeObjectURL() {}},
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const def = sandbox.def;
console.log(JSON.stringify({
  computed: Object.keys(def.computed || {}),
  methods: Object.keys(def.methods || {}),
  topLevel: Object.keys(def).filter((k) => !['data', 'computed', 'methods',
                                          'watch', 'components'].includes(k)),
}));
"""


def _options_blocks():
    """Return the option names Vue actually reads, plus the top-level leftovers."""
    result = subprocess.run(
        ["node", "-e", _OPTIONS_HARNESS],
        capture_output=True, text=True, check=True, cwd=str(ROOT),
    )
    blocks = json.loads(result.stdout)
    return {k: set(v) for k, v in blocks.items()}


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
        """Structural, not a text slice -- and it has to be.

        Two rounds of this defect were invisible to a prose check. First the
        getters were appended to `methods`, so the template was handed function
        objects. Then they were moved *past* the closing `},` of `computed: {`,
        which is still valid JavaScript: an object-literal method shorthand at
        the top level of the options object becomes an option Vue ignores. The
        test that "pinned the placement" sliced the text between `computed: {`
        and `watch: {` -- a region that still contained the four getters, so it
        passed on the broken tree. This reads the real options object instead.
        """
        blocks = _options_blocks()
        for name in ("scopeOptions", "activeScopeOption", "activeScopeLabel",
                     "activeScopeAvailable"):
            self.assertIn(name, blocks["computed"],
                          f"{name} is not a computed property of the options object")
            self.assertNotIn(name, blocks["methods"],
                             f"{name} is reachable as a method, not a computed")
        # The imperative half belongs in methods, so this is not just "not the
        # other block" -- each half is asserted where it has to be.
        for name in ("toggleScopeMenu", "closeScopeMenu", "chooseScope",
                     "onScopeMenuKeydown", "scopeMenuItems"):
            self.assertIn(name, blocks["methods"], f"{name} must be a method")

    def test_the_scope_trigger_resolves_to_a_computed_not_a_top_level_option(self):
        """The exact failure: an option Vue does not read, so `this.x` is undefined.

        `computed`, `methods`, `data` and the component options are separate
        namespaces. A getter in the wrong one is not an error, not a warning, and
        not a syntax failure -- it is simply never called, so the template binds
        `undefined` and the label renders empty while every name-grep test is
        green. Asserting the name is absent from the *top level* is what closes
        it; asserting it is present in `computed` is only half the statement.
        """
        top_level = _options_blocks()["topLevel"]
        for name in ("scopeOptions", "activeScopeOption", "activeScopeLabel",
                     "activeScopeAvailable"):
            self.assertNotIn(name, top_level,
                             f"{name} is a top-level component option, which Vue "
                             f"never calls -- the template binds undefined")

    def test_a_computed_is_not_called_as_a_method(self):
        """`allScopesCount` is a computed, so `this.allScopesCount()` throws.

        The previous version of this test asserted the opposite, having read the
        getter's line without checking which block it lived in: it pinned a call
        to a computed, which blows up the first time the scope list is computed
        and takes the whole mount with it. The structural assertion is stronger
        than either spelling -- if it is a computed, every read of it in app.js
        must be a bare reference.
        """
        self.assertIn("allScopesCount", _options_blocks()["computed"])
        self.assertNotIn("allScopesCount", _options_blocks()["methods"])
        # Only *call sites*: the definition `allScopesCount() {` is correct for
        # a computed, so the pattern has to require a receiver.
        self.assertNotRegex(APP, r"\.allScopesCount\(")


class ScopeSwitcherPlacementTests(unittest.TestCase):
    """The listbox must be able to open upward, and must decide to."""

    def test_the_template_binds_the_flip_class(self):
        # A CSS rule nothing selects is the "declared but never used" class a
        # gate cannot see; the binding is the half that makes it live.
        self.assertIn("'is-up': scopeMenuFlip", HTML)
        self.assertIn(".scope-menu.is-up", CSS)

    def test_placement_is_measured_on_open_not_hard_coded(self):
        # A CSS-only flip (`:focus-within`, a media query at one height) passes
        # the check above and still runs off the fold at every other height.
        self.assertIn("positionScopeMenu()", APP)
        self.assertRegex(APP, r"positionScopeMenu\(\)\s*\{[^}]*getBoundingClientRect")
        self.assertRegex(APP, r"positionScopeMenu\(\)\s*\{[^}]*innerHeight")

    def test_the_flip_is_reset_when_the_menu_closes(self):
        # A remembered flip is a wrong answer to the next question: the window
        # may have been resized, and a list pinned the wrong way is worse than
        # one that is merely tall.
        close = _between(APP, "closeScopeMenu(restoreFocus = false) {", "chooseScope(id) {")
        self.assertIn("this.scopeMenuFlip = false;", close)

    def test_measurement_failure_leaves_the_default_placement(self):
        # The menu is rendered by `v-if`, so it may not exist on the first tick
        # on a slow mount. Returning early keeps the downward default rather
        # than flipping a menu that was never measured.
        #
        # This asserted the literal `if (!menu) return;` and broke when the guard
        # was *strengthened* to `if (!menu || !trigger) return;` — a pure
        # improvement that the sentence did not survive. What is actually being
        # protected is the early return that guards on the menu, so assert that:
        # scoped to the method, and indifferent to what else joined the condition.
        placement = _between(APP, "positionScopeMenu() {", "closeScopeMenu(restoreFocus = false) {")
        self.assertRegex(
            placement,
            r"if \(\s*![^\n;]*\bmenu\b[^\n;]*\)\s*return;",
            "positionScopeMenu must return early when the menu is absent",
        )


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


class TheClosedDrawerIsNotAHitTarget(unittest.TestCase):
    """A CLOSED drawer must be unreachable by pointer, not merely unseen.

    The defect, measured rather than argued: at a 390px viewport with
    `drawerOpen === false`, `document.elementFromPoint` over the Install view's
    own fetch control returned `aside#nav-drawer.navigation-rail`. The rail is
    `position: fixed` and `min(300px, 84vw)` wide, so for the 150ms after any
    resize down into the phone band it was eating clicks aimed at the content
    underneath it. `tests/e2e/test_fetch_flow.py` reported it as a failure in a
    module whose subject is a different view entirely — which is why it was
    recorded rather than written off as flake.

    **Why `visibility: hidden` was not enough, and this is the whole point.**
    2.1e2's rule is "a closed drawer must be `visibility: hidden`, not merely
    translated", and it is correct — but BOTH of those properties transition
    over `--dur`. So on the way out the rail is still `visible` AND still at
    `translateX(0)`: painted, laid out, and hit-testable for the length of the
    animation. Hiding from the eye is not the same claim as being out of reach.

    The assertion is deliberately about the CLOSED state rather than about
    `pointer-events` as a keyword: an implementation that dropped the
    transition, or hid the rail another way, would satisfy the product claim
    without ever writing this declaration.
    """

    def _drawer_rules(self):
        block = _between(CSS, "/* --- 2.1e2: the rail becomes the drawer",
                         "\n  .drawer-head {")
        self.assertIn(".navigation-rail.open", block,
                      "the drawer block was not located; every assertion over "
                      "it would pass vacuously")
        closed = block[: block.index(".navigation-rail.open")]
        return closed, block[block.index(".navigation-rail.open"):]

    def test_a_closed_drawer_declares_no_pointer_events(self):
        closed, _ = self._drawer_rules()
        self.assertIn("pointer-events: none;", closed,
                      "the closed drawer must not intercept clicks")

    def test_opening_it_gives_the_pointer_back(self):
        # The control that proves the first: `pointer-events: none` applied to
        # the OPEN drawer would satisfy it while stranding the navigation
        # behind an invisible sheet — which is precisely the defect 2.1e2
        # exists to prevent, restated.
        _, open_rule = self._drawer_rules()
        self.assertIn("pointer-events: auto;", open_rule,
                      "the open drawer must accept pointer events")

    def test_the_control_is_not_left_to_the_transition(self):
        # Removing the declaration entirely satisfies neither assertion above
        # but WOULD leave the drawer intercepting for --dur; this one is the
        # control that says the property has to be declared, not merely
        # intended. `visibility` and `transform` are both present and both
        # transition, which is the measurement that produced the bug.
        closed, _ = self._drawer_rules()
        self.assertRegex(closed, r"visibility:\s*hidden;",
                         "2.1e2's hidden-when-closed rule must survive")
        self.assertRegex(closed, r"transition:[^;]*visibility[^;]*;",
                         "the delayed hide is the reason pointer-events is "
                         "declared at all; if this goes, re-measure before "
                         "deleting the other one")


if __name__ == "__main__":
    unittest.main()