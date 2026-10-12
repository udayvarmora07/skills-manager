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


def _request_helper_body():
    m = re.search(r"async toggleSkillState\([^)]*\)\s*\{(.*?)\n    \},", APP, re.S)
    assert m, "toggleSkillState must still exist"
    return m.group(1)


def _toggle_outcome():
    """Run the REAL `toggleOutcome` against the shipped app.js.

    A Python re-implementation of the sentence would pass while the shipped one
    keeps the defect — the same reason `test_redesign_document_typography`
    renders through Node instead of parsing the output itself.
    """
    import json
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")

    start = APP.index("const TOGGLE_PAST = {")
    end = APP.index("\n}\n", APP.index("function toggleOutcome(")) + 3
    source = APP[start:end]
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(source + """
const cases = [
  [{ name: "jumbo-kernel-notes", scope_label: "Claude Code" }, "disable"],
  [{ name: "jumbo-kernel-notes", scope_label: "Claude Code" }, "enable"],
  [{ name: "bare", scope: "opencode" }, "disable"],
  [{ name: "nothing", scope_label: "", scope: "global" }, "enable"],
  [{ name: "third-verb", scope_label: "Cursor" }, "archive"],
  [{}, "disable"],
];
console.log(JSON.stringify(cases.map(([r, a]) => toggleOutcome(r, a))));
""")
        path = fh.name
    try:
        out = subprocess.run([node, path], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, f"toggleOutcome threw: {out.stderr[-600:]}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


class EnableDisableIsNotARepeatedDecision(unittest.TestCase):
    def test_the_handler_guards_on_busy_before_it_posts(self):
        body = _toggle_body()
        self.assertIn("if (this.busy) return;", body,
                      "a second press during an in-flight request is a reader "
                      "who was not sure the first landed, not a second decision")
        # Assert the ORDER against whatever performs the request, not the
        # literal `await api(`: 4.7b moved the POST into a shared helper so the
        # toast's Undo and the button send the same request, which is exactly
        # the sort of change that silently invalidates a test pinned to the
        # old call site. Naming the helper keeps the claim — guard first — and
        # lets the request move again without the test lying about it.
        self.assertLess(body.index("if (this.busy) return;"),
                        body.index("await this.toggleSkillState("),
                        "the guard is after the request; it cannot stop the "
                        "duplicate it exists to stop")

    def test_busy_is_set_before_the_first_await(self):
        # `busy = true` must be synchronous, or the guard reads `false` on the
        # second dispatch because the coroutine has not reached it yet. This is
        # the reason the guard is not merely "check busy at the end".
        body = _toggle_body()
        self.assertLess(body.index("this.busy = true"),
                        body.index("await this.toggleSkillState("))

    def test_the_button_and_its_undo_send_one_request_through_one_helper(self):
        """The drift this prevents, stated so it can fail.

        4.7 shipped a literal `N` in a sentence that measured it because the
        fact had two sources. If Undo grew its own POST, the reader's Undo and
        the reader's click would be two code paths to the same effect and they
        would drift the same way.

        Asserted BOTH ways: exactly one place in the file builds the toggle
        URL, and `toggleSelected` reaches the request through the helper.
        """
        # Scoped to the toggle's DISTINGUISHING segment, the interpolated verb.
        # The bare `/api/skills/<name>` prefix is used six times across the
        # product (read, raw read, create, toggle, delete, update) and pinning
        # its count would assert something false about the whole app. `"/" +
        # action +` is what makes a URL the TOGGLE and nothing else, so this
        # counts the request whose duplication is the actual risk.
        self.assertEqual(
            len(re.findall(r'"/api/skills/" \+ encodeURIComponent\([^)]*\) \+ "/" \+ action', APP)), 1,
            "the toggle request must be built in exactly one place; a second is "
            "a second copy of it, free to drift from the first")
        self.assertIn("await this.toggleSkillState(", _toggle_body())
        self.assertIn('await api("/api/skills/"', _request_helper_body(),
                      "the shared helper is where the request actually goes")


class DisablingIsReversibleSoItGetsUndoRatherThanAQuestion(unittest.TestCase):
    """4.7b's actual design decision, asserted so it cannot be lost.

    The row asked whether disabling warrants a confirmation, and the answer is
    no: it is reversible with one click on the same button, so a modal taxes
    every reader for a mistake they can already fix. What the product does owe
    is that the reader can see what happened and put it back **without finding
    the row again** — which is the toast's Undo.

    The reason this is a test and not a comment: 2.3 shipped that Undo — the
    third `toast()` argument, the `toast-undo` button in the markup, an
    8-second `TOAST_UNDO_MS` window built for it and `undoToast` to run it —
    and measured, **no caller in the product had ever passed it**. The affordance
    shipped and was unreachable. A decision that was never exercised is a
    decision nothing keeps.
    """

    def _toast_call(self):
        m = re.search(r"this\.toast\(toggleOutcome\(.*?\n\s*:\s*null\);", _toggle_body(), re.S)
        self.assertIsNotNone(m, "the toast call must still pass the undo argument")
        return m.group(0)

    def test_the_disable_path_passes_an_undo(self):
        call = self._toast_call()
        self.assertIn('action === "disable"', call)
        self.assertIn("() => this.toggleSkillState(name, sc, \"enable\")", call,
                      "the Undo must send the inverse action through the same "
                      "helper the button does, or the two drift")

    def test_the_undo_is_the_reverse_of_what_was_performed(self):
        # Not `action === "enable"` (undo a disable = enable) asserted by
        # reading the same line: the inverse is what a reader pressing Undo
        # expects, and a hard-coded verb would still read correctly if the
        # guard above it were removed.
        call = self._toast_call()
        self.assertIn('? () => this.toggleSkillState(name, sc, "enable")', call)

    def test_enabling_gets_no_undo(self):
        """Re-enabling IS the restore. Offering "Undo" on it would offer the
        action the reader just took, and would consume the 8-second window to
        get them back to where they started."""
        self.assertIn('action === "disable"\n', _toggle_body().replace("\\n", "\n"))

    def test_the_undo_survives_longer_than_a_plain_toast(self):
        """The 8s window exists because of this call and only this call. If a
        disable toast expires on the 4s `TOAST_MS`, the Undo is a button with
        a 4-second life — long enough to be seen, short enough to miss."""
        self.assertIn("const TOAST_UNDO_MS = 8000;", APP)
        self.assertRegex(APP, r"const life = undo \? TOAST_UNDO_MS : TOAST_MS;")

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
    """Both tenses, and the scope by its observed NAME.

    The sentence used to be `action + "d in " + sc`, which (a) built a past
    tense by concatenation — correct for exactly two English words — and
    (b) printed the wire slug, so the toast read `disabled in claude-code.`
    beside a Library row whose chip said `Claude Code`. Every other surface in
    the app names the scope from the same `scope_label` the record carries.
    """

    def test_the_sentence_names_the_verb_it_performed_in_both_tenses(self):
        got = _toggle_outcome()
        self.assertEqual(got[0], 'Skill "jumbo-kernel-notes" Disabled in Claude Code.')
        self.assertEqual(got[1], 'Skill "jumbo-kernel-notes" Enabled in Claude Code.')

    def test_the_sentence_never_prints_a_wire_slug_when_a_label_was_observed(self):
        got = _toggle_outcome()
        # Case 2 has ONLY a slug (no scope_label). RULES #12: fall back to the
        # observed id rather than invent a name — but never uppercase a slug
        # into a fake label, which is what `" + action.charAt(0).toUpperCase()`
        # style reformatting of `claude-code` would produce.
        self.assertEqual(got[2], 'Skill "bare" Disabled in opencode.')
        self.assertEqual(got[3], 'Skill "nothing" Enabled in global.')

    def test_an_unknown_verb_does_not_become_a_malformed_word(self):
        """`action + "d"` is the bug in miniature: a third verb silently
        becomes `archived` or `archivedd`. An unmapped verb states what it
        did instead of guessing a tense."""
        got = _toggle_outcome()
        self.assertEqual(got[4], 'Skill "third-verb" archive in Cursor.')
        self.assertNotIn("archived", got[4])
        self.assertNotIn("archivedd", got[4])

    def test_a_record_with_neither_scope_field_does_not_print_undefined(self):
        got = _toggle_outcome()
        self.assertEqual(got[5], 'Skill "" Disabled in .')

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