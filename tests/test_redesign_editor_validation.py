"""4.5c — the editor validates one rule, in one place, and the pane and the
form do not use two words for one field.

Two claims, and the second is the one that looked like work and turned out to
be a measurement.

**One validator.** `saveSkill` and the blur handler used to be two independent
statements of "this field is required", and after 4.5c they are one
(`skillFieldError`) read by both. The reason to care is not tidiness: two copies
of a rule is how a form comes to accept on blur what it rejects on submit, and
the only assertion that catches that is one that asks BOTH paths the same
question. So the seam is driven twice per case and compared.

**The name's format is the server's rule, said earlier.** The catalog validates
`^[a-z0-9]+(-[a-z0-9]+)*$` over 1-64 characters; the field's own hint has stated
that in prose since before this branch, and nothing checked it — so the reader
met the rule as a 400 and a toast. Saying it on blur is the same observed fact,
earlier. It is stated here as a copy of a server rule on purpose: if the server
ever changes it, `skillFieldError` is the one place that has to change with it,
and the comment in app.js says so.

**An error the reader cannot act on is a guard that trains them to dismiss
errors.** In edit mode the name input is `:readonly`, so no message is produced
there — 4.5 slice A's lesson, applied to a field rather than to a dialog.

The label half is smaller than the backlog row implied and is recorded as
measured: the form legitimately describes MORE than the pane (it is the writer;
the pane shows what was written), so the invariant is not "the same list" but
"the same literal for every field that appears in both". `Allowed tools
(comma-separated)` did not satisfy that — the parenthetical was a format hint
wearing a label's clothes, and it is the only field in this form whose label
carried its format. Every other one uses a placeholder or a `.hint`.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")

# Every name the catalog will refuse, with the reason. Written out as literals
# rather than derived from the regex, so a rule that quietly stops matching one
# of its own cases fails instead of agreeing with itself.
BAD_NAMES = [
    "My Skill",          # space
    "Upper_Case",        # underscore
    "trailing-",         # trailing hyphen
    "-leading",          # leading hyphen
    "double--hyphen",    # consecutive hyphens
    ".hidden",           # leading dot
    "a" * 65,            # over the 64-character limit
]
GOOD_NAME = "release-checklist"

# The words the name hint uses to state the rule. Anchored to the hint as
# shipped (asserted below), so this list cannot rot into a check against
# nothing: if the hint is reworded, the anchoring assertion fails first.
RULE_WORDS = ("lowercase", "letters", "digits", "hyphens")

BODY = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}), apiText: async () => '', apiBlob: async () => new Uint8Array(),
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(s){return s;}, parseFrontmatter(){return {};}, formatCompat(){return '';},
    formatTools(){return '';}, groupLogicalSkills(){return [];},
    deriveLogicalSkillIdentity(){return {identities:[]};}, observedIdentity(){return {};},
    observeRecord(){return {};}, observedStateFor(){return 'active';},
    observedStateKeys(){return ['active'];}, observedSeverity(){return 'ok';},
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const M = sandbox.app.methods;

/* The validator reads `this.modals`, so the context is the modal itself — and
 * it must ALSO carry its siblings. `validateSkillField` calls
 * `this.skillFieldError`, and binding only the method under test made Node
 * throw `this.skillFieldError is not a function`. That is this repo's recorded
 * shape (2.1's four getters, 4.3b's `batchStaleTargets`): a method calling
 * another method is fine in Vue, where `this` is the component, and undefined
 * in a context built by hand. The REAL methods are bound, never a
 * re-implementation, or the test would agree with a stub. */
const ctx = (mode, form, touched) => ({
  modals: { skill: { mode, form, errors: {}, touched: touched || {} } },
  skillFieldError: M.skillFieldError,
  toast(){}, closeModal(){}, loadScopes: async () => {}, loadSkills: async () => {},
  loadTrash: async () => {}, loadDetail(){}, busy: false, query: '',
  /* `saveSkill` focuses the first invalid field inside `$nextTick`. Stubbing it
     as a no-op means this suite does NOT verify that focus move — it verifies
     the error set both paths produce, which is the claim this task makes. Said
     here rather than left as an unstated gap in a suite that looks complete. */
  $nextTick(){}, document: { querySelector(){ return null; } },
});

/* Ask BOTH paths. `saveSkill` returns early on an error set (after focusing),
 * so `await` it and read `errors` — the early return is part of its contract
 * and a test that only asked the validator would never see it. */
async function submit(form, mode) {
  const c = ctx(mode, form, { name: true, description: true });
  await M.saveSkill.call(c);
  return Object.assign({}, c.modals.skill.errors);
}

(async () => {
  const out = {};
  const cases = __CASES__;
  for (const c of cases) {
    /* `touched` separates "tabbed past" from "filled and emptied", and it is
     * why the two paths may legitimately differ on an untouched empty field:
     * Save must report it, a blur must not. */
    const ctxv = ctx(c.mode, { name: c.name, description: c.description }, c.touched);
    const onBlur = M.skillFieldError.call(ctxv, c.field);
    /* Drive the real blur handler, not the validator it calls. */
    M.validateSkillField.call(ctxv, c.field);
    const blurred = ctxv.modals.skill.errors[c.field] || '';
    const onSubmit = (await submit({ name: c.name, description: c.description }, c.mode))[c.field] || '';
    out[c.label] = { blur: blurred, submit: onSubmit, direct: onBlur };
  }
  /* A field with no error must be REMOVED, not left behind as "". */
  const keep = ctx('create', { name: 'ok-name', description: 'Typed something.' });
  M.validateSkillField.call(keep, 'name');
  keep.modals.skill.errors.description = 'stale';
  M.validateSkillField.call(keep, 'name');
  out.clearsOnlyItsOwnField = JSON.stringify(keep.modals.skill.errors);
  console.log(JSON.stringify(out));
})();
'''


def _run() -> dict:
    cases = [
        {"label": "valid", "field": "name", "mode": "create",
         "name": GOOD_NAME, "description": "Does a thing."},
        {"label": "empty", "field": "name", "mode": "create",
         "name": "   ", "description": "Does a thing."},
        {"label": "uppercase", "field": "name", "mode": "create",
         "name": "My Skill", "description": "Does a thing."},
        {"label": "underscore", "field": "name", "mode": "create",
         "name": "snake_case", "description": "Does a thing."},
        {"label": "trailing", "field": "name", "mode": "create",
         "name": "trailing-", "description": "Does a thing."},
        {"label": "touched_empty", "field": "name", "mode": "create", "touched": {"name": True},
         "name": "", "description": "Does a thing."},
        {"label": "readonly_edit", "field": "name", "mode": "edit", "touched": {"name": True},
         "name": "My Skill", "description": "Does a thing."},
        {"label": "desc_empty", "field": "description", "mode": "create",
         "name": GOOD_NAME, "description": ""},
        {"label": "both_empty", "field": "description", "mode": "create",
         "name": "", "description": ""},
    ]
    # Every name the catalog refuses, driven through the SAME path as the named
    # cases above. Written out as literals rather than derived from the regex:
    # a case list generated from the rule under test agrees with it by
    # construction and can never fail.
    for i, bad in enumerate(BAD_NAMES):
        cases.append({"label": "bad%02d" % i, "field": "name", "mode": "create",
                      "name": bad, "description": "Does a thing."})
    script = BODY.replace("__CASES__", json.dumps(cases))
    result = subprocess.run(["node", "-e", script], capture_output=True,
                            text=True, cwd=str(ROOT))
    if result.returncode != 0:
        raise AssertionError("node harness failed:\n" + result.stderr)
    return json.loads(result.stdout)


class OneValidatorTwoPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _run()

    def test_the_harness_actually_executed(self):
        """A suite that cannot execute looks identical to a suite that passes.
        `saveSkill` returning early on an error set is the whole contract here,
        so the output must actually carry error strings."""
        self.assertTrue(self.out, "the node harness returned nothing")
        self.assertTrue(
            any(v["submit"] for v in self.out.values() if isinstance(v, dict)),
            "no case produced a submit-time error, so nothing was asserted",
        )

    def test_blur_never_says_anything_save_would_not(self):
        """The claim the extraction exists to make true, and it is deliberately
        one-directional. Pressing Save must report an empty required field even
        when the reader never typed in it; a BLUR must not, or tabbing through a
        form you have not started scolds you for it - which is what the first
        version of this did, and what the e2e caught.

        So: `blur == submit`, or `blur == ""`. The weak version of this test -
        asserting the two are simply equal - would have forced the scolding
        back in to make it pass."""
        for label, case in self.out.items():
            if not isinstance(case, dict) or "blur" not in case:
                continue
            with self.subTest(case=label):
                if case["blur"] == "":
                    continue
                self.assertEqual(
                    case["submit"], case["blur"],
                    f"{label}: blur said something saveSkill would not, so the "
                    "form warns about a field it will then accept",
                )

    def test_a_field_the_reader_typed_into_and_emptied_is_reported_on_both(self):
        case = self.out["touched_empty"]
        self.assertNotEqual("", case["blur"],
                            "a field that was typed into and emptied must be "
                            "reported when the reader leaves it")
        self.assertEqual(case["submit"], case["blur"])

    def test_a_name_the_catalog_would_refuse_is_refused_before_the_request(self):
        """One case per name the server refuses, on BOTH paths. The point is not
        that a message exists — it is that the reader meets the rule before a
        400 and a toast, in the same words on both paths."""
        for i, bad in enumerate(BAD_NAMES):
            with self.subTest(name=bad[:20]):
                case = self.out["bad%02d" % i]
                self.assertNotEqual("", case["submit"],
                                    f"{bad!r} was accepted by saveSkill")
                self.assertNotEqual("", case["blur"],
                                    f"{bad!r} was accepted on blur")
                self.assertEqual(case["submit"], case["blur"])

    def test_a_valid_name_says_nothing_on_either_path(self):
        self.assertEqual("", self.out["valid"]["blur"])
        self.assertEqual("", self.out["valid"]["submit"])

    def test_a_readonly_field_never_produces_an_error_the_reader_cannot_act_on(self):
        """Edit mode renders the name input `:readonly`. A message there would
        be a scolding for something the reader cannot change."""
        self.assertEqual("", self.out["readonly_edit"]["submit"])
        self.assertEqual("", self.out["readonly_edit"]["blur"])

    def test_an_empty_field_still_says_it_on_submit(self):
        """Blur validation must not have weakened submit validation — that is the
        direction nobody tests."""
        self.assertNotEqual("", self.out["empty"]["submit"])
        self.assertNotEqual("", self.out["desc_empty"]["submit"])
        self.assertNotEqual("", self.out["both_empty"]["submit"])

    def test_blurring_one_field_leaves_another_alone(self):
        import json as _json
        self.assertEqual({"description": "stale"},
                         _json.loads(self.out["clearsOnlyItsOwnField"]),
                         "validateSkillField rebuilt the whole error object "
                         "instead of removing its own key")


class TemplateWiring(unittest.TestCase):
    def test_both_required_fields_blur_into_the_shared_validator(self):
        for field in ("name", "description"):
            with self.subTest(field=field):
                self.assertIn("@blur=\"validateSkillField('%s')\"" % field, HTML)

    def test_saveSkill_reads_the_same_validator(self):
        app = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
        save = app[app.index("async saveSkill()"):]
        save = save[:save.index("\n    openAdd(")]
        self.assertIn("skillFieldError", save,
                      "saveSkill must read the shared validator, not restate "
                      "the rule; two copies drift and nothing notices")


class LabelVocabulary(unittest.TestCase):
    """The measured half of 4.5c, kept because it is easy to regress."""

    def _labels(self):
        return set(re.findall(r'<label for="f-[a-z]+">([^<]+)</label>', HTML))

    def _detail_dts(self):
        block = HTML[HTML.index('class="meta detail-facts"'):]
        block = block[:block.index("</dl>")]
        return set(re.findall(r"<dt>([^<]+)</dt>", block))

    def test_the_two_vocabularies_are_measured_before_they_are_asserted(self):
        """If the locator stops finding either list the intersection is empty
        and the assertion below passes vacuously."""
        self.assertGreaterEqual(len(self._labels()), 8, "editor labels not found")
        self.assertGreaterEqual(len(self._detail_dts()), 4, "detail-facts <dt>s not found")

    def test_a_field_named_in_both_places_is_named_identically(self):
        shared = self._labels() & self._detail_dts()
        self.assertTrue(shared, "no field is named in both places, which means "
                                "the locators are wrong rather than the product")
        # Nothing may be in the pane but spelled differently in the form.
        for label in self._labels():
            for dt in self._detail_dts():
                if label != dt and label.split(" (")[0] == dt.split(" (")[0]:
                    self.fail(f"the form says {label!r} where the pane says {dt!r} "
                              "- two names for one field")

    def test_no_editor_label_carries_its_own_format_hint(self):
        """`Allowed tools (comma-separated)` was the only label in this form that
        described its format, and it made the field's name differ from the
        detail pane's `<dt>` for no reason. Every other field here uses a
        placeholder or a `.hint`."""
        for label in self._labels():
            self.assertNotIn("(", label,
                             f"label {label!r} carries a format hint; it belongs "
                             "in a .hint or a placeholder so the field keeps "
                             "the name the detail pane gives it")

    def test_the_removed_name_is_still_stated_somewhere(self):
        """The parenthetical was not deleted, it was moved."""
        field = HTML[HTML.index('<label for="f-tools">'):]
        field = field[:field.index("</div>")]
        self.assertIn("Comma-separated", field)

    def test_no_error_restsates_a_rule_the_hint_already_states(self):
        """Found by reading a capture, not by any assertion: the first format
        message said "Lowercase letters, digits and single hyphens only — it
        becomes the folder name" directly under a hint saying "Lowercase
        letters, digits, hyphens. Becomes the folder name." Two statements of
        one rule, in different words, on adjacent lines, in the same dialog.

        A hint is always visible under this field, so it is the rule's home and
        a message under it only has to deliver the verdict. The words checked
        are the rule's own vocabulary, and the first assertion anchors that
        list to the hint as shipped — so rewording the hint fails loudly here
        instead of leaving the check comparing against nothing."""
        import re as _re
        hint = _re.search(r'id="f-name-hint"[^>]*>([^<]+)<', HTML)
        self.assertIsNotNone(hint, "the name hint is gone; re-measure this test")
        hint_text = hint.group(1).lower()
        for word in RULE_WORDS:
            self.assertIn(word, hint_text,
                          f"the hint no longer says {word!r}; re-measure which "
                          "words state the rule before trusting the check below")

        app = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
        message = _re.search(r'return "(Not a valid name\.[^"]*)";', app)
        self.assertIsNotNone(message, "the format message moved; re-measure this test")
        self.assertEqual(
            [], [w for w in RULE_WORDS if w in message.group(1).lower()],
            "the error and the hint both explain the rule, in different words, "
            "on adjacent lines. The hint is always visible; the message should "
            "carry the verdict only.",
        )


if __name__ == "__main__":
    unittest.main()