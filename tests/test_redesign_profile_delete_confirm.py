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


# Runs the WHOLE of app.js in a VM, so the module's own top level resolves its
# own module-scope names. These stubs are the minimum a first-load browser
# provides; everything else app.js needs at load time is its own.
#
# 5.9c — this harness used to slice the `appOptions` LITERAL out of app.js and
# evaluate it inside `with (new Proxy(...))` whose `has` trap returns true for
# every name it does not own. A module-scope `const` is invisible to such a
# slice, so `SETTINGS_SECTIONS` resolved to the stub `function (){}`,
# `SETTINGS_SECTIONS[0]` was `undefined`, and `data()` — 5.7b's
# `settingsSection: SETTINGS_SECTIONS[0].id` — threw before a single assertion
# in this file ran. The suite had been RED on 3.11/3.12/3.13 since 5.9a and
# reported it as a stack trace about a Settings list, because the slice could
# not see the constant it was asking about.
#
# 7.1 diagnosed and fixed this exact class in `test_redesign_profile_editor.py`
# with the whole-file harness below; this file was simply never given it. A
# slice can be missing a closing scope; a whole file cannot.
_APP_HARNESS = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}),
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){},
    observeRecord(){}, observedStateFor(){}, observedStateKeys(){},
    observedSeverity(){}, apiText: async () => ({}), apiBlob: async () => ({})
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}, h(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {
    addEventListener(){}, documentElement:{dataset:{}, setAttribute(){}},
    querySelectorAll(){return [];}, querySelector(){return null;},
    createElement(){return {setAttribute(){}, style:{}};},
    body:{appendChild(){}}
  },
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
// `sandbox.app` IS the options object - it is what was handed to createApp.
const __opts = sandbox.app;
const __data = __opts.data();
'''


def _options():
    """Load the real options object in Node and report where each name lives.

    Marker-slicing cannot tell an object-literal method from a top-level one,
    which is the whole defect class in this file's docstring.
    """
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")
    script = _APP_HARNESS + (
        "console.log(JSON.stringify({\n"
        "  data: Object.keys(__data),\n"
        "  modals: Object.keys(__data.modals || {}),\n"
        "  methods: Object.keys(__opts.methods || {}),\n"
        "  computed: Object.keys(__opts.computed || {})\n"
        "}));\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "opts.js"
        p.write_text(script, encoding="utf-8")
        res = subprocess.run(
            [node, str(p)], capture_output=True, text=True, timeout=60, cwd=str(ROOT)
        )
    if res.returncode != 0:
        raise AssertionError("loading app.js options failed:\n" + res.stderr[-2000:])
    opts = json.loads(res.stdout.strip().splitlines()[-1])
    # `data()` must actually have RUN. A harness that catches the TypeError and
    # reports `{}` would turn every `assertIn(...)` above into a green assertion
    # about a `data()` that threw — the exact failure this harness had. The
    # modal map is the load-bearing part: it is the only place `data()` proves
    # it ran to completion rather than half way.
    if not opts["modals"]:
        raise AssertionError(
            "data() produced an empty modal map, so the harness is reporting "
            "about a data() that threw rather than one that ran"
        )
    return opts


class DeletingAProfileAsksFirst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opts = _options()

    def test_the_state_key_exists(self):
        # The old harness labelled the MODAL MAP as "data" (it returned
        # `Object.keys(data().modals)`), so this assertion is about the modal
        # map's keys — `deleteProfile` is the name inside `modals`, not a
        # top-level piece of state. Asserted against the map that actually
        # holds it, so a reader is not misled by the key the harness prints.
        self.assertIn("deleteProfile", self.opts["modals"],
                      "the confirm needs its own modal state")
        self.assertNotIn("deleteProfile", self.opts["data"],
                         "the confirm's state lives in the modal map; a "
                         "top-level copy would be a second source of truth")

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