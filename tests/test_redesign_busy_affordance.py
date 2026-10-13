"""6.4c slice A — the two halves of the busy state that could be decided without
painting anything new.

**What arrived here, measured (re-verify, do not re-derive):**

  * `prefersReducedMotion` was declared in `data()` (app.js) and assigned once in
    `mounted()` from `readReducedMotion()`, and had **no reader anywhere** in
    `skillsmgr/` or `tests/`. `readReducedMotion()` existed only to feed it. That
    is this repository's recurring "declared and never read" class, and it was
    the ninth instance. **Deleted**, with
    `test_the_reduced_motion_token_cannot_come_back_green_looking` so it cannot
    be re-added silently.
  * `.btn.is-busy` existed as exactly ONE rule in the cascade (styles.css) with
    **zero** users in any markup, so its only `animation: spin` never played.
    Under `prefers-reduced-motion: reduce` it would have frozen on the first
    frame rather than stopped — which is why the freeze was measured and
    declared correct instead of "fixed" in 6.4.

**The decision, and what is deliberately NOT here.** 6.4c asked whether a
visible progress affordance is owed. **It is**, and it is split into 6.4c2
rather than guessed at here: `busy` is ONE global flag read by 32 controls, so
32 individual spinners would be the wrong shape — and shipping a spinner
without looking at it is how a product ends up with 32 moving targets. What
ships in this slice is the half that needs no new paint and can be asserted
exactly: **`#app` carries `aria-busy`**, so assistive tech is told the truth
while a request is in flight. `test_the_busy_rule_is_still_unused` is the
tripwire that tells the next task when the spinner finally has users.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "skillsmgr", "webui", "app.js")
INDEX_HTML = os.path.join(ROOT, "skillsmgr", "webui", "index.html")
STYLES_CSS = os.path.join(ROOT, "skillsmgr", "webui", "styles.css")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class BusyStateToken(unittest.TestCase):
    """The dead reduced-motion token is gone and stays gone."""

    def test_the_reduced_motion_token_cannot_come_back_green_looking(self):
        """`prefersReducedMotion` and the method that fed it.

        Asserted by name rather than by count, so re-adding the field fails this
        test even if a reader appears to justify it. If a future feature really
        needs the preference, the honest change is to give it a reader in the
        same commit — not to let the declaration back in on its own.
        """
        app = read(APP_JS)
        for name in ("prefersReducedMotion", "readReducedMotion"):
            self.assertNotIn(
                name, app,
                "%s is declared again with no reader. Add the reader in the "
                "same commit, or this token is a third green-looking "
                "declaration." % name)


class BusyIsPerceivable(unittest.TestCase):
    """RULES #13: a state that is only painted is not perceivable."""

    def test_the_app_root_carries_the_busy_state(self):
        """`busy` is one global fact, so the root announces it.

        32 controls read `:disabled="busy"`; the state lives in one place, and
        `:aria-busy` on the root is the one attribute that reports it to
        assistive tech without 32 duplicate announcements.
        """
        html = read(INDEX_HTML)
        root = re.search(r'<div id="app"[^>]*>', html)
        self.assertIsNotNone(root, 'the app root <div id="app"> is gone')
        self.assertIn(
            ":aria-busy=", root.group(0),
            "the app root does not carry aria-busy, so an action in flight is "
            "announced as an idle one: %r" % root.group(0))

    def test_aria_busy_is_bound_to_the_busy_flag_and_nothing_else(self):
        """A binding to anything but `busy` would report a fact that is not the
        one 32 controls are showing, which is worse than reporting nothing."""
        root = re.search(r'<div id="app"[^>]*>', read(INDEX_HTML)).group(0)
        binding = re.search(r':aria-busy="([^"]*)"', root).group(1)
        self.assertIn("busy", binding)
        # The two states, both named. A binding that could only ever be "true"
        # would leave an idle app claiming to be busy.
        self.assertIn("'true'", binding)
        self.assertIn("'false'", binding)


class BusySpinnerTripwire(unittest.TestCase):
    """The spinner has no users yet, and that is a recorded state, not a fact
    to be discovered later."""

    def test_the_busy_rule_is_still_unused(self):
        """`.btn.is-busy` exists and nothing applies it.

        This is a **tripwire, not an endorsement**. When 6.4c2 gives the spinner
        its users, this test fails and says so — which is the point: a dead rule
        that looks finished is the failure this repository keeps recording, and
        the cheapest defence is a test that notices the day it stops being dead.
        """
        css = read(STYLES_CSS)
        self.assertIn(".btn.is-busy", css,
                      "the spinner rule is gone; 6.4c2 has landed, so update "
                      "this tripwire and the backlog row together")
        for name in ("index.html", "app.js"):
            source = read(os.path.join(ROOT, "skillsmgr", "webui", name))
            self.assertNotIn(
                "is-busy", source,
                "%s now applies .btn.is-busy. The visible affordance has "
                "landed: delete this tripwire and tick 6.4c2 with what it does."
                % name)


if __name__ == "__main__":
    unittest.main()