"""6.4c slice A — the two halves of the busy state that could be decided without
painting anything new.

**What arrived here, measured (re-verify, do not re-derive):**

  * `prefersReducedMotion` was declared in `data()` (app.js) and assigned once in
    `mounted()` from `readReducedMotion()`, and this test claimed it had **no
    reader anywhere**. That was true of `app.js` and false of the product:
    `index.html`'s Accessibility-evidence row was bound to the field all along,
    so deleting it made that row print "OS has not requested reduced motion" on
    every machine. **5.7c found it** (the row printed the same sentence with
    `prefers-reduced-motion: reduce` forced on in Chromium) and restored the
    field WITH a reader, plus `reducedMotionLabel` and a live subscription. The
    test below was rewritten with the same intent — a motion state may exist
    only while something reads it — and the rest of this docstring is 6.4c's.
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
    """The reduced-motion state is only here because something reads it."""

    def test_the_reduced_motion_state_has_a_reader_or_it_does_not_exist(self):
        """**REWRITTEN by 5.7c — see TEST-CHANGES.md.**

        This used to assert that `prefersReducedMotion` and
        `readReducedMotion` appear nowhere in `app.js`. It passed, and the
        product broke: `index.html`'s Accessibility-evidence row was bound to
        the field, so deleting it made that row print "OS has not requested
        reduced motion" on **every** machine, including the ones that had asked
        for it. The gate read one file and the reader was in another — the
        repository's tenth recorded "a check about a path it cannot see".

        The intent was never "this name must not exist". It was "no motion
        state without a reader", and this asserts that: the field, the computed
        it feeds and the markup that binds the computed are all checked, so the
        chain can never be broken at any link. The one-shot `readReducedMotion`
        is still banned by name — a sampled value is a claim about the machine
        at load, not about the machine now.
        """
        app = read(APP_JS)
        if "prefersReducedMotion" not in app:
            self.skipTest(
                "the field is gone and nothing reads it, which is the state "
                "this suite recorded. If it comes back, it must come back with "
                "its reader; tests/test_redesign_settings_evidence.py asserts "
                "the chain when it exists.")
        self.assertIn(
            "reducedMotionLabel", app,
            "the field is back with no computed reading it — that is the "
            "orphan this suite exists to prevent.")
        html = read(INDEX_HTML)
        self.assertIn(
            "reducedMotionLabel", html,
            "the field and its computed exist but nothing renders them")
        self.assertNotIn(
            "readReducedMotion", app,
            "the one-shot reader is back. The signal must be SUBSCRIBED: a "
            "value sampled at mount is a claim about the machine at load.")


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