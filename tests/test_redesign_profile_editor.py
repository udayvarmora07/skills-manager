"""5.3a — the Profiles view could create and delete, and had no edit path.

The DESIGN-V2 §G.3 screen is "create/edit/delete profile dialogs"; the view had
the first and the last. Clicking a saved profile called ``previewProfile`` and
the only thing the form could do was POST, which the backend upserts by name
(``catalog.save_profile``). So editing is a pure frontend path — and it was
absent, which is the awkward kind of gap: nothing was broken, something simply
could not be done.

That absence hid a worse failure. Because the name field was never populated
from a stored profile, an editor that *did* exist and left the name editable
would POST a SECOND profile and leave the original untouched, while the page
said "Profile saved." So the lock is not decoration: ``saveProfile`` refuses a
renamed edit where the request is built, because a disabled field is a
convention and a refused request is the product.

Two rules here, and both are asserted in both directions:

1. **The new members live inside the options object.** 2.1 shipped four
   getters appended *after* the closing brace of ``computed`` — valid
   JavaScript, an option Vue never reads, and every name-grep test green. So
   presence in the block is only half the claim; absence from the top level is
   the half that matches that defect, and it is asserted too.
2. **The heading, the verb and the toast come from one source.** Three inline
   ternaries in the template can drift apart; the 2.3 lesson is a surface
   saying one thing and doing another.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _app_options():
    """Load the real options object in Node and report where each name lives.

    Marker-slicing cannot tell an object-literal method from a top-level one,
    which is the whole defect class in this file's docstring.
    """
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")
    decl = APP.index("const appOptions = {")
    open_brace = APP.index("{", decl)
    depth = 0
    i = open_brace
    while True:
        if APP[i] == "{":
            depth += 1
        elif APP[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    literal = APP[open_brace:i + 1]
    names = [
        "data", "computed", "methods",
        "profileFormTitle", "profileSaveLabel", "profileSaveOutcome",
        "editProfile", "cancelProfileEdit", "profileEditing",
    ]
    prelude = (
        "const __own = { Object: Object, JSON: JSON, console: console,\n"
        # data() reads the stored theme through localStorage; a stub that
        # answers null is the same answer a first-run browser gives.
        "  localStorage: { getItem: function () { return null; }, setItem: function () {} } };\n"
        "let __captured = null;\n"
        "const __scope = new Proxy(__own, {\n"
        "  has: (t, k) => !(k in t),\n"
        "  get: (t, k) => (k in t ? t[k] : function () {}),\n"
        "  set: (t, k, v) => { __captured = v; return true; },\n"
        "});\n"
        "with (__scope) { __opts = " + literal + "; }\n"
        # `data` is a FUNCTION, so it has to be called to see its keys — and it
        # must be called after the `with` block, because inside it the name
        # `__opts` is still intercepted by the proxy's getter and resolves to a
        # stub rather than to the object.
        "const __opts = __captured;\n"
    )
    script = prelude + (
        # data() is CALLED outside the `with`, so its free names need real
        # globals rather than proxy interception. `localStorage` answers null —
        # the same answer a first-run browser gives.
        "globalThis.localStorage = { getItem: function () { return null; }, setItem: function () {} };\n"
        "if (typeof globalThis.window === 'undefined') globalThis.window = globalThis;\n"
        "const __data = __opts.data();\n"
        "const where = {};\n"
        "for (const name of " + json.dumps(names) + ") {\n"
        "  const spots = [];\n"
        "  if (Object.prototype.hasOwnProperty.call(__data, name)) spots.push('data');\n"
        "  for (const block of ['data', 'computed', 'methods', 'watch']) {\n"
        "    if (__opts[block] && Object.prototype.hasOwnProperty.call(__opts[block], name)) {\n"
        "      spots.push(block);\n"
        "    }\n"
        "  }\n"
        "  if (Object.prototype.hasOwnProperty.call(__opts, name)) spots.push('TOP-LEVEL');\n"
        "  where[name] = spots;\n"
        "}\n"
        "const call = (name, self) => __opts.computed[name].call(self);\n"
        "const results = {};\n"
        "for (const editing of [null, 'release-ready']) {\n"
        "  const self = { profileEditing: editing, profileForm: { name: '  spaced  ' } };\n"
        "  results[String(editing)] = [\n"
        "    call('profileFormTitle', self),\n"
        "    call('profileSaveLabel', self),\n"
        "    call('profileSaveOutcome', self),\n"
        "  ];\n"
        "}\n"
        "console.log(JSON.stringify({ where, results }));\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "opts.js"
        p.write_text(script, encoding="utf-8")
        res = subprocess.run([node, str(p)], capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise AssertionError("loading app.js options failed:\n" + res.stderr[-2000:])
    return json.loads(res.stdout.strip().splitlines()[-1])


_OPTIONS = None


def options():
    global _OPTIONS
    if _OPTIONS is None:
        _OPTIONS = _app_options()
    return _OPTIONS


class ProfileEditorPlacement(unittest.TestCase):
    def test_state_and_getters_live_in_the_options_object(self):
        where = options()["where"]
        self.assertEqual(where["profileEditing"], ["data"])
        for name in ("profileFormTitle", "profileSaveLabel", "profileSaveOutcome"):
            self.assertEqual(where[name], ["computed"], name)
        for name in ("editProfile", "cancelProfileEdit"):
            self.assertEqual(where[name], ["methods"], name)

    def test_nothing_leaked_to_the_top_level_of_the_options_object(self):
        """2.1's defect, in both halves. Appending after the closing brace is
        valid JS and an option Vue never reads; every name-grep stays green."""
        for name, spots in options()["where"].items():
            if name in ("data", "computed", "methods"):
                continue  # the block names themselves, not members this task added
            self.assertNotIn("TOP-LEVEL", spots, f"{name} is outside the options object")

    def test_the_three_copy_strings_follow_profileEditing(self):
        results = options()["results"]
        # The name is trimmed in the toast, because the form's v-model is
        # `.trim` too — printing the raw field would put leading spaces inside
        # quotes the reader believes are the profile's identity.
        self.assertEqual(results["null"], ["New profile", "Save profile", "Profile spaced saved."])
        self.assertEqual(
            results["release-ready"],
            ["Edit release-ready", "Save changes", "Profile release-ready updated."],
        )


class ProfileEditorMarkup(unittest.TestCase):
    def test_the_name_field_is_locked_while_an_edit_is_in_flight(self):
        row = [line for line in HTML.splitlines() if 'id="profile-name"' in line]
        self.assertEqual(len(row), 1, "expected exactly one profile name field")
        self.assertIn(':disabled="busy || !!profileEditing"', row[0])

    def test_the_stored_profile_says_what_saving_over_it_will_do(self):
        self.assertIn("saves over this profile", HTML)
        self.assertIn("Saving here writes over", HTML)

    def test_each_saved_profile_offers_preview_edit_and_delete(self):
        """5.3b: the row template MOVED from a bordered card in the detail pane
        to the master list in the sidepanel. The intent — every saved profile
        offers all three controls, and the one being edited says so — is
        unchanged; only the region it is looked for in has moved."""
        start = HTML.index('class="profile-master-row"')
        end = HTML.index("</div>\n      </div>", start)
        block = HTML[start:end]
        self.assertIn('@click="previewProfile(name)"', block)
        self.assertIn('@click="editProfile(name)"', block)
        self.assertIn('@click="deleteProfile(name)"', block)
        self.assertIn(':aria-pressed="profileEditing === name', block)

    def test_the_detail_pane_is_not_a_second_copy_of_the_master_list(self):
        """The shape defect 5.3b fixed: the same names, with the same three
        buttons, rendered once in the sidepanel and once in a bordered card in
        the detail pane. Asserted as ABSENCE from the detail branch, because
        "every row offers its three controls" (above) is satisfied by a list
        rendered anywhere."""
        start = HTML.index('v-else-if="view === \'profiles\'" class="detail-inner"')
        end = HTML.index('v-else-if="view === \'recovery\'"', start)
        detail = HTML[start:end]
        self.assertNotIn("v-for=\"(profile, name) in catalog.profiles\"", detail)
        self.assertNotIn("Saved profiles", detail)
        # ...and the pane the row mark points at is the one that exists.
        self.assertIn('id="profile-detail"', detail)

    def test_a_selection_marks_the_row_and_the_pane_from_one_function(self):
        """The mark and the preview were two independent answers to "which
        profile is showing". Both now read `profileCurrent`, so they cannot
        disagree; a mutation that hard-codes `true` into one of them fails."""
        start = HTML.index('class="profile-master-row"')
        block = HTML[start:HTML.index("</div>\n      </div>", start)]
        self.assertIn(':aria-pressed="profileCurrent(name) ? \'true\' : \'false\'"', block)
        self.assertIn("'is-current': profileCurrent(name)", block)
        self.assertIn(":aria-controls=\"profileCurrent(name) ? 'profile-detail' : undefined\"", block)
        src = APP[APP.index("profileCurrent(name) {"):]
        src = src[:src.index("\n    },")]
        self.assertIn("this.profileEditing", src)
        self.assertIn("this.profilePreview", src)

    def test_an_instances_list_is_not_auto_placed_beside_a_member_name(self):
        """The observed copies of one member share the grid with the member's
        own name and colour, so auto-placement made a path read as a second
        member. The copies take a row of their own."""
        self.assertIn('class="profile-member-copies"', HTML)
        self.assertIn(".profile-member-copies { grid-column: 1 / -1;", CSS)
        # ...and the control, not the assertion, is what makes it so.
        self.assertNotRegex(
            HTML, r'<li v-for="member in profilePreview\.members"[^>]*>(?:(?!profile-member-copies).)*?<code v-for')

    def test_the_form_has_a_way_out_that_does_not_save(self):
        self.assertIn('@click="cancelProfileEdit"', HTML)
        self.assertIn(">Cancel</button>", HTML)

    def test_a_profile_with_no_observed_instance_says_why_there_is_no_plan(self):
        """The button is gated on profileObservedCount, so an all-missing
        profile showed no action and no reason — the reader cannot tell a
        bounded tool declining from a control that failed to render."""
        self.assertIn('v-if="!profileObservedCount"', HTML)
        self.assertIn("class=\"hint profile-no-targets\"", HTML)


class ProfileEditorGuard(unittest.TestCase):
    def test_saving_refuses_an_edit_whose_name_was_changed(self):
        start = APP.index("async saveProfile()")
        body = APP[start:APP.index("async previewProfile(", start)]
        self.assertIn("if (editing && form.name.trim() !== editing)", body)
        self.assertIn("return;", body)
        # The refusal must come BEFORE the request, not after it.
        self.assertLess(body.index("!== editing"), body.index('await api("/api/catalog/profiles"'))

    def test_delete_of_the_profile_being_edited_leaves_the_editor(self):
        start = APP.index("async deleteProfile(name)")
        body = APP[start:APP.index("/* ---------------------------------------------------------- helpers */", start)]
        self.assertIn("if (this.profileEditing === name) this.cancelProfileEdit();", body)

    def test_the_toast_is_derived_not_a_literal_pair(self):
        start = APP.index("async saveProfile()")
        body = APP[start:APP.index("async previewProfile(", start)]
        self.assertIn("this.toast(this.profileSaveOutcome)", body)
        self.assertNotIn('this.toast("Profile saved.")', body)

    def test_edit_profile_loads_arrays_back_into_the_comma_separated_fields(self):
        start = APP.index("editProfile(name) {")
        body = APP[start:APP.index("cancelProfileEdit() {", start)]
        self.assertIn('(profile.skills || []).join(", ")', body)
        self.assertIn('(profile.targets || []).join(", ")', body)
        self.assertIn("this.profileEditing = name;", body)

    def test_the_editing_row_is_marked_by_a_rule_not_a_tint(self):
        """Two renderings of one profile on screen at once is the thing to
        avoid; a background behind the name puts a second copy of it there.
        5.3b: the selector is the master row's, which is where the row lives."""
        self.assertIn(".profile-master-row.is-editing", CSS)
        self.assertIn("box-shadow: inset 2px 0 0 var(--accent)", CSS)
        block = CSS[CSS.index(".profile-master-row.is-current"):CSS.index(".profile-master-select")]
        self.assertNotIn("background:", block)
        self.assertIn(".profile-editor-actions", CSS)
        # The weaker claim must not paint as the stronger one.
        self.assertIn(".profile-master-row.is-current { box-shadow: inset 2px 0 0 var(--border-strong); }", CSS)


if __name__ == "__main__":
    unittest.main()