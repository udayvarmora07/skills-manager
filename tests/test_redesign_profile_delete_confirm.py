"""5.3c — deleting a profile asks first, and the dialog is really a dialog.

The defect, measured before anything changed: `deleteProfile(name)` fired on a
single click with no confirmation, and its toast was the constant string
`"Profile deleted."` — the same shape 4.2b removed from the Library's rows. Four
typed fields are the only record of what a profile contained and there is no
profile trash, so this is the destructive half of 4.7b's principle: reversible
gets an Undo toast, destructive gets a confirm.

**The second defect was mine, and it is the reason this file exists as a
structure test rather than a behaviour test.** I first wrote the overlay's
attribute as `data-modal="delete-profile"` while the state key was
`deleteProfile`. `modalElement()` builds its selector from the KEY:

    document.querySelector('[data-modal="' + activeModal + '"] .modal')

so the mismatch produced a dialog that was **fully visible and completely
inert** — no focus trap, no Escape, focus still on `<body>`, and zero console
errors. Nothing in the app failed loudly, and every other modal in this file
has always matched; a test asserting "the dialog exists" would have been green
throughout. So the modal key and its `data-modal` attribute are asserted to be
the same string, for every modal, derived rather than enumerated.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")


def _options():
    """Load the real options object in a Node VM and return its blocks."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")
    decl = APP.index("const appOptions = {")
    open_brace = APP.index("{", decl)
    depth, i = 0, open_brace
    while True:
        if APP[i] == "{":
            depth += 1
        elif APP[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    literal = APP[open_brace:i + 1]
    script = (
        # `data()` reads localStorage. The 4.7 suite never called `data()` —
        # it wanted the block NAMES — so it needed no DOM stub; this one has
        # to read the modal map out of it, and the failure mode is a
        # TypeError from deep inside the options object rather than anything
        # about the contract under test.
        "const __own = { Object: Object, JSON: JSON, console: console,\n"
        "  localStorage: { getItem: () => null, setItem: () => {} } };\n"
        # The proxy's `has` returns true for every name it does not own, so a
        # name listed ONLY in the `const` is still swallowed by the `with` and
        # resolves to a bare stub function — which is why `getItem` was not a
        # function. It has to be in the passthrough set.
        "const localStorage = __own.localStorage;\n"
        "let __captured = null;\n"
        "const __scope = new Proxy(__own, {\n"
        "  has: (t, k) => !(k in t),\n"
        "  get: (t, k) => (k in t ? t[k] : function () {}),\n"
        "  set: (t, k, v) => { __captured = v; return true; },\n"
        "});\n"
        "with (__scope) { __opts = " + literal + "; }\n"
        "const __opts = __captured;\n"
        "console.log(JSON.stringify({"
        " data: Object.keys(((__opts.data ? __opts.data() : {}).modals) || {}),"
        " methods: Object.keys(__opts.methods || {}),"
        " computed: Object.keys(__opts.computed || {}) }));\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "opts.js"
        p.write_text(script, encoding="utf-8")
        res = subprocess.run([node, str(p)], capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise AssertionError("loading app.js failed:\n" + res.stderr[-1500:])
    return json.loads(res.stdout.strip().splitlines()[-1])


class DeletingAProfileAsksFirst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opts = _options()

    def test_the_state_key_exists(self):
        self.assertIn("deleteProfile", self.opts["data"],
                      "the confirm needs its own modal state")

    def test_the_handler_that_asks_replaced_the_one_that_deleted(self):
        methods = self.opts["methods"]
        self.assertIn("confirmDeleteProfile", methods)
        self.assertIn("doDeleteProfile", methods)
        # The old one deleted on a single click. Its ABSENCE is the fix, so
        # assert it rather than only asserting the new names exist.
        self.assertNotIn("deleteProfile", methods,
                         "a method literally named `deleteProfile` is the "
                         "single-click path this task removes")

    def test_the_delete_button_asks_rather_than_deletes(self):
        """M2: wiring the row's Delete straight to `doDeleteProfile` passed
        every other test in this file. The names of the new methods existing,
        and the old one being gone, say nothing about WHICH one the button
        reaches — and the button is the only path a reader can take."""
        buttons = [b for b in re.findall(r"<button[^>]*>", HTML)
                   if "confirmDeleteProfile" in b or "doDeleteProfile" in b]
        self.assertEqual(len(buttons), 2,
                         "one row Delete and one dialog confirm: %r" % buttons)
        # The ROW's delete is `.btn-danger-ghost` inside the master list; the
        # dialog's is `.btn-danger` in the footer. Selecting on "name" matched
        # the dialog button too, because its aria-label also interpolates the
        # profile name.
        row_button = [b for b in buttons if "btn-danger-ghost" in b]
        self.assertEqual(len(row_button), 1,
                         "exactly one row button: %r" % row_button)
        self.assertIn("@click=\"confirmDeleteProfile(name)\"", row_button[0],
                      "the row's Delete must ASK. Wiring it to the deleting "
                      "handler is the defect this task removes, and it passed "
                      "every other assertion in this file.")

    def test_only_the_confirming_verb_calls_the_deleting_handler(self):
        # Enumerated from the handlers the markup actually binds, so adding a
        # second call site is a decision rather than a silent duplication.
        sites = re.findall(r'@click="doDeleteProfile"', HTML)
        self.assertEqual(len(sites), 1,
                         "exactly one control may delete: %r" % sites)
        block = re.search(r'<div v-if="modals\.deleteProfile".*?\n  </div>',
                          HTML, re.S).group(0)
        self.assertIn('@click="doDeleteProfile"', block,
                      "the only deleting call site is inside the confirm")

    def test_nothing_in_the_markup_calls_the_removed_method(self):
        # Match the CALLEE, not the substring: `\bdeleteProfile\b` also
        # matches inside `closeModal('deleteProfile')`, which is how the
        # cancel button correctly dismisses the dialog. The first version of
        # this assertion failed on three sites that were all doing the right
        # thing.
        name = "deleteProfile"
        hits = re.findall(r'@click="([a-zA-Z_$][\w$]*)\(', HTML)
        self.assertNotIn(name, hits,
                         "markup still calls the removed method directly")
        callees = {c for c in hits if c != "closeModal"}
        self.assertNotIn(name, callees)

    def test_the_requester_binds_the_name_and_says_nothing_is_recoverable(self):
        m = re.search(r'confirmDeleteProfile\(name\)\s*\{(.*?)\n    \},', APP, re.S)
        self.assertIsNotNone(m)
        self.assertIn("modals.deleteProfile = { name }", m.group(1))

    def test_the_deleter_clears_the_editor_and_the_preview(self):
        # 5.3a's own contract: deleting the profile being edited leaves the
        # editor, and deleting the previewed one clears the detail pane. If
        # either were dropped the pane would keep naming a profile that is
        # gone, which is the "invented claim" RULES #12 forbids.
        m = re.search(r"async doDeleteProfile\(\)\s*\{(.*?)\n    \},", APP, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("cancelProfileEdit()", body)
        self.assertIn("this.profilePreview = null", body)

    def test_the_toast_names_the_profile_and_says_it_is_not_recoverable(self):
        m = re.search(r"async doDeleteProfile\(\)\s*\{(.*?)\n    \},", APP, re.S)
        body = m.group(1)
        self.assertIn("'Profile \"' + name + '\" deleted.", body)
        self.assertIn("not in the trash", body)
        self.assertNotIn('this.toast("Profile deleted.")', body,
                         "the constant string names nothing and says nothing "
                         "about where the profile went")


class TheDialogIsActuallyADialog(unittest.TestCase):
    """The defect a "does the dialog exist" assertion would have missed."""

    def test_every_modal_key_and_its_data_modal_attribute_are_the_same_string(self):
        # `modalElement()` derives the selector from the KEY, so a mismatch
        # renders an overlay that is visible and entirely inert: no focus
        # trap, no Escape, focus on <body>, no error anywhere. Derived, not
        # enumerated, so a future modal cannot reintroduce it by omission.
        # Slice the `modals` OBJECT LITERAL only. Matching `: null,` anywhere
        # in app.js also picks up unrelated single-key maps (the first version
        # of this assertion demanded a `data-modal="error"` overlay that has
        # never existed) — which is the same mistake as 4.7's `methods` slice
        # in a different place.
        start = APP.index("      modals: {")
        depth, i = 0, APP.index("{", start)
        open_brace = i
        while True:
            if APP[i] == "{":
                depth += 1
            elif APP[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = APP[open_brace:i + 1]
        keys = re.findall(r"([a-zA-Z][a-zA-Z0-9]*): null", block)
        self.assertGreater(len(keys), 10, "the modal map was not parsed: %r" % keys)
        self.assertIn("deleteProfile", keys)
        for key in keys:
            with self.subTest(modal=key):
                self.assertRegex(
                    HTML,
                    r'data-modal="%s"' % re.escape(key),
                    "`modalElement()` looks up `[data-modal=\"%s\"]` from the "
                    "KEY; a different attribute makes the dialog inert" % key)

    def test_the_overlay_uses_the_existing_modal_vocabulary(self):
        # RULES #5 bans inline script, so `confirm()` is not available; and
        # 4.7b's row is explicit: do not add a second way of asking.
        block = re.search(
            r'<div v-if="modals\.deleteProfile".*?\n  </div>', HTML, re.S)
        self.assertIsNotNone(block, "the overlay must exist")
        markup = block.group(0)
        self.assertIn('role="dialog"', markup)
        self.assertIn('aria-modal="true"', markup)
        self.assertIn('aria-labelledby="delete-profile-modal-title"', markup)
        self.assertIn("@mousedown.self=", markup, "the scrim must dismiss")
        self.assertNotRegex(markup, r"\bconfirm\(",
                            "inline confirm() is banned by RULES #5")
        self.assertIn("tabindex=\"-1\"", markup)

    def test_it_names_what_is_lost_and_what_is_not(self):
        block = re.search(
            r'<div v-if="modals\.deleteProfile".*?\n  </div>', HTML, re.S).group(0)
        # "No skill is changed on disk" separates deleting a DESIRED SET from
        # deleting skills, which is the distinction a reader most needs here.
        self.assertIn("No skill is changed on disk", block)
        self.assertIn("Nothing is written to the trash", block)
        self.assertIn("only record", block)
        # It was "the four fields BELOW", written for the editor's context.
        # This dialog has no fields and nothing below the sentence, so the
        # word pointed a reader at a form that is not on screen — RULES #12's
        # "states only observed facts" applied to the pointer, not the claim.
        self.assertNotIn("fields below", block)
        self.assertIn("fields in the editor", block)

    def test_both_verbs_are_present_and_only_one_is_destructive(self):
        block = re.search(
            r'<div v-if="modals\.deleteProfile".*?\n  </div>', HTML, re.S).group(0)
        foot = re.search(r'<div class="modal-foot">(.*?)</div>', block, re.S).group(1)
        self.assertIn("Cancel", foot)
        self.assertIn("btn-danger", foot)
        self.assertEqual(foot.count("btn-danger"), 1,
                         "Cancel must not be painted as the destructive verb")


if __name__ == "__main__":
    unittest.main()