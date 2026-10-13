"""5.9b — the four INVENTORY dialogs join 4.7's shared vocabulary.

`history`, `templates`/`newtemplate`, `import` and `validate` were the last
surfaces still describing layout with inline `style` attributes. Two of the
defects below were *claims* rather than layout, and neither was falsifiable
from the source: the Snapshots block hung off the `<select>`'s v-model rather
than off the name the data below it was fetched for, and two REST vocabularies
were painted raw where every other surface names them.

The structural assertions load the real `app.js` options object in a Node VM
rather than slicing between markers: a marker slice returns the same region
whether or not the code it names is *inside* the object literal, which is how
2.1 shipped four getters that Vue never read and a test passed on it.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "skillsmgr" / "webui" / "app.js"
HTML = ROOT / "skillsmgr" / "webui" / "index.html"
CSS = ROOT / "skillsmgr" / "webui" / "styles.css"

APP_SRC = APP.read_text(encoding="utf-8")
HTML_SRC = HTML.read_text(encoding="utf-8")
CSS_SRC = CSS.read_text(encoding="utf-8")

# The four dialogs this row owns, and the line range each occupies in index.html.
DIALOG_KEYS = ("history", "templates", "newtemplate", "import", "validate")


def _dialog_markup(key):
    """Return one `data-modal` block from index.html, by `<div>` nesting.

    The first version counted `{`/`}`, which a Vue interpolation unbalances on
    its own: `{{ x }}` walks the depth 1->2->1->0 and the slice ended at the
    first interpolation in the dialog.  Count the tags the element is made of.
    """
    start = HTML_SRC.index('data-modal="%s"' % key)
    open_at = HTML_SRC.rindex("<div", 0, start)
    depth = 0
    for m in re.finditer(r"<div\b|</div>", HTML_SRC[open_at:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            end = open_at + m.end()
            return HTML_SRC[open_at:end]
    raise AssertionError("unbalanced markup for dialog %r" % key)


_HARNESS = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}),
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const meth = sandbox.app.methods, comp = sandbox.app.computed;
// The sandbox the browser would give these two: they read the two frozen
// tables at module scope, which `vm` puts on the context's global, so the
// table they consult is the one the file declares.
const label = meth[process.argv[1]];
const out = {
  computed_names: Object.keys(comp),
  has: Object.prototype.hasOwnProperty.call(meth, process.argv[1]),
  known: label.call({}, process.argv[2]),
  unknown: label.call({}, process.argv[3]),
};
console.log(JSON.stringify(out));
'''


def _options_object(label_fn, known, unknown):
    proc = subprocess.run(
        ["node", "-e", _HARNESS, label_fn, known, unknown],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise AssertionError("node harness failed:\n" + proc.stderr[-2000:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _run_method(source, body, extra=None):
    """Evaluate one app.js method against a literal state object."""
    driver = r"""
const state = JSON.parse(process.argv[3]);
const method = new Function("state", process.argv[2] + "\n" + process.argv[4]);
console.log(JSON.stringify(method(state)));
"""
    proc = subprocess.run(
        ["node", "-e", driver, source, body, json.dumps(extra or {})],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError("method failed: %s" % proc.stderr[-1500:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestInventoryDialogsHaveNoInlineLayout(unittest.TestCase):
    """The row's literal subject: these four still described layout inline."""

    def test_no_dialog_carries_an_inline_style_attribute(self):
        # 4.7 removed 31 of them from remove/sync. These four are what is left.
        offenders = {}
        for key in DIALOG_KEYS:
            hits = re.findall(r'style="[^"]*"', _dialog_markup(key))
            if hits:
                offenders[key] = hits
        self.assertEqual(
            offenders, {},
            "inline layout is back in a dialog: %r" % offenders,
        )

    def test_every_replacement_class_is_actually_declared(self):
        # A selector that does not exist is invisible to every gate here —
        # 5.1c's recorded finding. Renaming a class without adding the rule
        # would leave the dialog unstyled and this file green.
        used = set()
        for key in DIALOG_KEYS:
            for attr in re.findall(r'class="([^"]*)"', _dialog_markup(key)):
                # `class="choice-list import-options"` is TWO classes; keeping
                # the attribute whole made a multi-class attribute read as a
                # class name nothing matches.
                used.update(attr.split())
        wanted = {
            "history-bar", "field-select", "history-action", "history-snapshots",
            "modal-subhead", "modal-subhead-of", "empty-note", "dropzone-lead",
            "dropzone-hint", "import-picked", "import-picked-name",
            "import-picked-size", "import-options", "choice", "choice-box",
            "choice-text", "choice-note", "form-grid-single",
        }
        missing = sorted(c for c in wanted if c not in used)
        self.assertEqual(missing, [], "class used but never put in the markup")
        undeclared = sorted(
            c for c in wanted
            if not re.search(r"\.%s\b" % re.escape(c), CSS_SRC)
        )
        self.assertEqual(undeclared, [], "class in the markup with no CSS rule")


class TestHistoryClaimsOnlyWhatWasLoaded(unittest.TestCase):
    """The defect: picking a skill said "No snapshots for this skill" above a
    table still listing every skill, because the block hung off the select's
    v-model and not off the name the data was fetched for."""

    markup = _dialog_markup("history")

    def test_the_snapshots_block_is_not_bound_to_the_unapplied_selection(self):
        self.assertNotIn(
            'v-if="modals.history.name"', self.markup,
            "the Snapshots block is bound to the <select>, not to what was loaded",
        )
        self.assertIn('v-if="modals.history.loaded"', self.markup)

    def test_rollback_uses_the_loaded_name_not_the_selection(self):
        # rollbackSnapshot(name, s) is a POST. Sending the unapplied selection
        # is how a rollback could act on a different skill than the one shown.
        self.assertNotIn("rollbackSnapshot(modals.history.name", self.markup)
        self.assertIn("rollbackSnapshot(modals.history.loaded", self.markup)

    def test_loaded_is_initialised_and_only_assigned_after_the_fetches_settle(self):
        self.assertRegex(
            APP_SRC,
            r'modals\.history = \{ name: "", loaded: "",',
            "the field the template reads must exist on open, or it is undefined "
            "and the block never appears at all",
        )
        load = APP_SRC.index("async loadHistory()")
        body = APP_SRC[load:APP_SRC.index("\n    },", load)]
        self.assertIn("m.loaded = asked;", body)
        # ...and it must be set AFTER the snapshot fetch, not before it.
        self.assertLess(
            body.index("m.snapshots = snapshotResult.snapshots || [];"),
            body.index("m.loaded = asked;"),
            "loaded is claimed before the data it describes has arrived",
        )

    def test_the_snapshots_heading_names_the_skill_it_is_scoped_to(self):
        self.assertIn("modal-subhead-of", self.markup)
        self.assertRegex(self.markup, r'modal-subhead-of">of \{\{ modals\.history\.loaded \}')


class TestWireVocabulariesAreNamed(unittest.TestCase):
    """`issue.level` and `history.action` are REST values. Printing them raw
    is 5.4c's badge defect and 5.5's ten category headings, once more."""

    def test_no_dialog_paints_a_raw_wire_value_where_a_word_belongs(self):
        validate = _dialog_markup("validate")
        self.assertNotIn(
            ">{{ issue.level }}<", validate,
            "the issue level is painted raw in its badge",
        )
        history = _dialog_markup("history")
        self.assertNotIn(">{{ r.action }}<", history, "the history action is painted raw")

    def test_the_wire_value_is_kept_not_deleted(self):
        # 5.4c's trade: dropping the slug would leave the label as the only
        # record of which status this was.
        self.assertIn(':data-status="issue.level"', _dialog_markup("validate"))
        self.assertIn(':data-status="r.action"', _dialog_markup("history"))

    def test_both_tables_exist_and_are_frozen(self):
        for name in ("HISTORY_ACTIONS", "VALIDATE_LEVELS"):
            self.assertRegex(
                APP_SRC, r"const %s = Object\.freeze\(\{" % name,
                "%s must be one frozen table, not an inline ternary" % name,
            )

    def test_the_tables_cover_every_action_the_store_can_write(self):
        """Derived from source, not from one seed: a run that never produced a
        `restore` must still render the word."""
        written = set(re.findall(
            r'_commit_history\([^,]+,\s*"([a-z-]+)"|_history\([^,]+,\s*"([a-z-]+)"',
            (ROOT / "skillsmgr" / "store.py").read_text(encoding="utf-8"),
        ))
        pairs = {a or b for a, b in written}
        pairs.discard("")
        block = APP_SRC[APP_SRC.index("const HISTORY_ACTIONS"):APP_SRC.index("const VALIDATE_LEVELS")]
        missing = sorted(a for a in pairs if '"%s"' % a not in block)
        self.assertEqual(
            missing, [],
            "the store writes an action the History table cannot name: %r" % missing,
        )

    def test_an_unknown_value_falls_back_to_the_raw_string(self):
        # RULES #12: never invent a word for a state we have not observed.
        for fn_name, body in (
            ("historyActionLabel", "return HISTORY_ACTIONS[action] || String(action);"),
            ("validateLevelLabel", "return VALIDATE_LEVELS[level] || String(level);"),
        ):
            self.assertIn(fn_name, APP_SRC)
            self.assertIn(
                "String(%s)" % ("action" if "history" in fn_name else "level"),
                body,
                "%s must fall back to the raw value" % fn_name,
            )


class TestLabelsAreMethodsNotComputeds(unittest.TestCase):
    """5.5's trap, verbatim: Vue UNWRAPS a computed before the template sees it,
    so a computed that the template CALLS throws during render and the section
    it labels renders nothing — with every stdlib gate green."""

    def setUp(self):
        self.hist = _options_object("historyActionLabel", "trash", "teleport")
        self.level = _options_object("validateLevelLabel", "error", "catastrophe")

    def test_both_label_functions_are_methods(self):
        for options, name in ((self.hist, "historyActionLabel"),
                              (self.level, "validateLevelLabel")):
            self.assertTrue(options["has"], "%s is not a method" % name)
            self.assertNotIn(
                name, options["computed_names"],
                "%s is in computed: — a template calling it throws during render" % name,
            )

    def test_the_template_actually_calls_them(self):
        history = _dialog_markup("history")
        self.assertIn("historyActionLabel(r.action)", history)
        self.assertIn("validateLevelLabel(issue.level)", _dialog_markup("validate"))

    def test_a_known_action_and_level_render_words(self):
        self.assertEqual(self.hist["known"], "Trashed")
        self.assertEqual(self.level["known"], "Error")

    def test_an_unknown_value_falls_back_to_the_raw_string(self):
        # RULES #12: never invent a word for a state we have not observed.
        # Deleting the fallback would make an unobserved action read as blank.
        self.assertEqual(self.hist["unknown"], "teleport")
        self.assertEqual(self.level["unknown"], "catastrophe")


class TestImportDialogContract(unittest.TestCase):
    """The Import dialog was the only one in the product with no close glyph,
    and its chosen filename was a <label> pointing at no control."""

    markup = _dialog_markup("import")

    def test_it_has_a_close_glyph_like_every_other_dialog(self):
        self.assertIn('aria-label="Close"', self.markup)
        self.assertIn("closeModal('import')", self.markup)

    def test_the_chosen_file_is_not_a_label_pointing_at_nothing(self):
        # A <label> with no `for` and nothing wrapped announces a filename as a
        # field name to a screen reader.
        self.assertNotRegex(
            self.markup, r'<label[^>]*>\s*\{\{ modals\.import\.file\.name',
            "the chosen filename is announced as a field label",
        )
        self.assertIn('class="import-picked-name"', self.markup)

    def test_each_flag_states_its_consequence(self):
        """4.7's rule for a dialog option: say what it costs, beside the verb.
        A hidden option cannot state anything, so both are unconditional."""
        self.assertNotIn('v-if="modals.import.file"', self.markup)
        notes = re.findall(r'<span class="choice-note">(.*?)</span>', self.markup, re.S)
        self.assertEqual(len(notes), 2, "both import flags must carry a consequence")
        # Counting the elements was the first version of this test and it went
        # GREEN on a mutation that emptied one of the sentences: the class
        # survived, the claim did not. Assert the words, not the hook.
        for note in notes:
            words = re.sub(r"<[^>]+>", "", note).split()
            self.assertGreaterEqual(
                len(words), 6,
                "a consequence that renders as %d words tells the reader nothing: %r"
                % (len(words), " ".join(words)),
            )

    def test_the_file_input_is_reachable_by_keyboard(self):
        # `display: none` is what this had. The dropzone is a button, so the
        # input itself needs no focus of its own — but it must not be removed
        # from the tree in a way that breaks the ref-based click.
        self.assertRegex(self.markup, r'class="sr-only"')
        self.assertNotIn('class="sr-only" tabindex="-1"', self.markup)


if __name__ == "__main__":
    unittest.main()