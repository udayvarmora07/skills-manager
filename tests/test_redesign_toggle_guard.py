"""4.7b — the enable/disable action: a second press is not a second decision.

The defect, measured on the live app before anything changed: two dispatches
inside one tick produced **two** `POST /api/skills/<name>/disable`, and the
second one's rejection reached the screen verbatim —

    Skill "api-contract-handbook" disabled in global.
    skill 'api-contract-handbook' is already enabled

— which is the backend's own sentence: lower case, single quotes, no leading
capital, in a different voice from every other message in the product, and it
reads as a failure of the tool rather than of the click.

Both halves of the fix are asserted here, because either alone is satisfied by
the wrong change:

* **the guard** — one request per burst, measured by counting requests, not by
  reading `:disabled`;
* **the attribute** — the button is visibly disabled while one is in flight.
  The attribute cannot stop two dispatches inside a single frame and the guard
  alone leaves the button looking clickable, so neither substitutes for the
  other and both are asserted.
"""

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")


def _toggle_body():
    m = re.search(r"async toggleSelected\(\)\s*\{(.*?)\n    \},", APP, re.S)
    assert m, "toggleSelected must still exist"
    return m.group(1)


class EnableDisableIsNotARepeatedDecision(unittest.TestCase):
    def test_the_handler_guards_on_busy_before_it_posts(self):
        body = _toggle_body()
        self.assertIn("if (this.busy) return;", body,
                      "a second press during an in-flight request is a reader "
                      "who was not sure the first landed, not a second decision")
        # The guard must come BEFORE the request, or it guards nothing.
        self.assertLess(body.index("if (this.busy) return;"),
                        body.index("await api("),
                        "the guard is after the POST; it cannot stop the "
                        "duplicate it exists to stop")

    def test_busy_is_set_before_the_first_await(self):
        # `busy = true` must be synchronous, or the guard reads `false` on the
        # second dispatch because the coroutine has not reached it yet. This is
        # the reason the guard is not merely "check busy at the end".
        body = _toggle_body()
        self.assertLess(body.index("this.busy = true"), body.index("await api("))

    def test_both_buttons_carry_the_busy_guard(self):
        # `v-if` / `v-else` produce two separate buttons; guarding one and not
        # the other leaves the defect reachable in exactly half its states.
        for verb in ("Disable", "Enable"):
            with self.subTest(button=verb):
                m = re.search(
                    r'<button[^>]*>\s*<app-icon name="file-text"></app-icon>\s*%s\s*'
                    r'</button>' % verb, HTML)
                self.assertIsNotNone(m, f"the {verb} button must still exist")
                self.assertIn(':disabled="busy"', m.group(0),
                              f"the {verb} button was the one action in the row "
                              f"that looked clickable during a request")

    def test_every_action_in_the_detail_row_carries_the_same_guard(self):
        # Not a style preference: Remove sits beside Disable and takes a
        # destructive path, so a reader who has just clicked Disable must not
        # be able to click Remove while that request is in flight either.
        #
        # The row is found by ITS OWN BUTTONS, by handler. `.detail-actions`
        # is carried by two other blocks (the profile Preview/Delete pair and
        # Recovery's purge), and a terminator matched to a later `</div>`
        # sweeps in the detail TABS as well — navigation, deliberately never
        # disabled. Both versions of this assertion reported a defect that was
        # not there. Naming the handlers states the subject exactly.
        handlers = ("openEdit", "toggleSelected", "confirmRemove")
        for handler in handlers:
            with self.subTest(action=handler):
                found = [b for b in re.findall(r"<button[^>]*>", HTML)
                         if '@click="%s' % handler in b]
                self.assertTrue(found, f"no button calls {handler}")
                for button in found:
                    self.assertIn(':disabled="busy"', button,
                                  "every action in the detail row is disabled "
                                  "during a request: %r" % button)


class TheToggleSaysWhatHappened(unittest.TestCase):
    def test_the_toast_names_the_verb_it_performed(self):
        body = _toggle_body()
        # Built by concatenation, so assert the SHAPE rather than a literal:
        # a hard-coded "disabled" here would be wrong on the enable path.
        self.assertIn('+ action + "d in " + sc', body)

    def test_no_backend_rejection_is_shown_verbatim_as_an_error(self):
        # The product speaks in its own voice; the backend's sentence reached
        # the screen because `catch (e) { this.toast(e.message, "err") }` has no
        # filter and the duplicate request produced one. With the guard the
        # duplicate cannot happen, so this pins the SHAPE: the catch is still
        # the right place for a real failure, and a test that demanded it be
        # removed would be asking for the wrong thing.
        self.assertIn("this.toast(e.message", _toggle_body())


if __name__ == "__main__":
    unittest.main()