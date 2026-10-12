"""4.7 — the action dialogs state what the product will actually do.

The sync dialog shipped a literal ``N`` in the sentence that reports the cost
of a sync: *"syncing to N agents ≈ 373.9k total across targets"*. The sentence
was written before the target count existed, the hole was never filled, and the
result still reads like a measurement. That is the defect this suite exists to
keep from returning, and it is why every figure the dialog shows is derived
once in ``computed`` rather than three times in the template.

Two rules, and both directions of each:

1. **One source per fact.** ``doSync`` must post ``syncPickedTargets`` — the
   same array the dialog states in ``syncOutcomeSentence``. A separately
   derived list is how a confirm starts naming one thing and doing another
   (the 2.3 lesson: a palette row that ran a different command than the one it
   drew). Asserting only that "the template calls the helper" would pass on a
   dialog that computed its own count inline, which is the original defect, so
   the template is asserted to carry NO inline derivation of ``picked`` at all.
2. **No placeholder tokens in shipped copy.** A literal ``N`` standing in for a
   number is not a measurement, and neither is ``issue(s)``.

The ``computed`` block is LOADED in a Node VM rather than sliced by marker.
Marker-slicing cannot tell an object-literal method from a top-level one, and
this branch has three recorded instances of exactly that defect shipping (2.1's
four getters appended after the closing brace, ``batchStaleTargets`` read as a
property off a method, ``detailObservation`` called as a function) — every one
of which passed ``node --check`` and every name-grep test in the suite.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _options_blocks():
    """Load the real options object in Node and return the named blocks.

    Slicing ``computed: {`` ... ``watch: {`` contains the getters whether or
    not they are inside the object, so it passes on a broken tree. This does
    not: it asks the object what it has.
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")
    # Slice the LITERAL app.js hands to createApp, not the call's argument
    # list: `createApp(appOptions)` passes an identifier, so matching parens
    # from the call yields the four letters `appOptions`.
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
    # The literal references module-level names (the registered component, the
    # markdown renderer, the formatters) whose NAMES are an implementation
    # detail we are not testing. Resolve every free identifier to a stub rather
    # than enumerating them: a hand-written stub list fails loudly the next
    # time app.js imports something new, which is a test failure about this
    # file rather than about the product. The globals the probe itself uses are
    # excluded, or `Object.keys` would come back from the proxy.
    prelude = (
        "const __own = { Object: Object, JSON: JSON, console: console };\n"
        "let __captured = null;\n"
        "const __scope = new Proxy(__own, {\n"
        "  has: (t, k) => !(k in t),\n"
        "  get: (t, k) => (k in t ? t[k] : function () {}),\n"
        "  // The `with` intercepts EVERY free name, including the one we would\n"
        "  // assign to, so the value is captured by a set trap rather than\n"
        "  // written to a bare binding the scope has already swallowed.\n"
        "  set: (t, k, v) => { __captured = v; return true; },\n"
        "});\n"
        "with (__scope) { __opts = " + literal + "; }\n"
        "const __opts = __captured;\n"
    )
    script = prelude + (
        "const out = {};\n"
        "for (const name of ['computed', 'methods', 'watch', 'data']) {\n"
        "  out[name] = Object.keys(__opts[name] || {});\n"
        "}\n"
        "out.__counts = {}\n"
        "for (const name of ['computed', 'methods']) {\n"
        "  const o = __opts[name] || {};\n"
        "  let n = 0;\n"
        "  for (const k of Object.keys(o)) {"
        " if (typeof o[k] === 'function') { n++; } }\n"
        "  out.__counts[name] = n;\n"
        "}\n"
        "console.log(JSON.stringify(out));\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "opts.js"
        p.write_text(script, encoding="utf-8")
        res = subprocess.run([node, str(p)], capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise AssertionError("loading app.js options failed:\n" + res.stderr[-2000:])
    return json.loads(res.stdout.strip().splitlines()[-1])


def _modal(name):
    """The markup of exactly one dialog, by tag depth.

    A regex to the next `</div>` walks straight out of the dialog and into the
    following ones, so "no inline styles in the validate dialog" would have been
    answered by every OTHER dialog's markup too. Counting `<div` against `</div>`
    from the opening overlay tag finds the tag that actually closes it.
    """
    m = re.search(r'<div[^>]*data-modal="%s"[^>]*>' % name, HTML)
    if not m:
        raise AssertionError(f"the {name} dialog must still exist")
    i = m.end()
    depth = 1
    token = re.compile(r"<div\b|</div>")
    while depth > 0:
        t = token.search(HTML, i)
        if not t:
            raise AssertionError(f"the {name} dialog is not closed")
        depth += 1 if t.group(0) != "</div>" else -1
        i = t.end()
    return HTML[m.end():i]


class ActionDialogFactsAreComputed(unittest.TestCase):
    """The helpers exist, live in `computed`, and are not duplicated on top."""

    @classmethod
    def setUpClass(cls):
        cls.blocks = _options_blocks()

    def test_every_sync_fact_is_in_computed(self):
        for name in ("syncPickedTargets", "syncPickedCount", "syncPickedLabels",
                     "syncProjectedTokens", "syncOutcomeSentence"):
            self.assertIn(name, self.blocks["computed"],
                          f"{name} must be a computed; a template reading a "
                          f"function's property is the 4.3b batchStaleTargets "
                          f"defect (`.length` is arity, so it rendered '0')")

    def test_no_sync_fact_leaked_to_the_top_level_of_the_options(self):
        # The half that matched 2.1's shipped defect: "present in computed" was
        # true of four getters appended *after* the closing brace, which Vue
        # never reads. Presence alone was the wrong assertion.
        for name in ("syncPickedTargets", "syncPickedCount", "syncPickedLabels",
                     "syncProjectedTokens", "syncOutcomeSentence"):
            self.assertNotIn(name, self.blocks.get("methods", []) + self.blocks.get("watch", []),
                             f"{name} appears outside computed")

    def test_do_sync_posts_the_very_list_the_dialog_states(self):
        m = re.search(r"async doSync\(\)\s*\{(.*?)\n    \}", APP, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("this.syncPickedTargets", body)
        self.assertNotIn("Object.keys(m.picked)", body,
                         "doSync must not re-derive the target list; a second "
                         "derivation is how a confirm names one scope and "
                         "sends another")

    def test_the_template_carries_no_inline_derivation_of_the_target_list(self):
        m = re.search(r'data-modal="sync"(.*?)\n  </div>', HTML, re.S)
        self.assertIsNotNone(m, "the sync dialog must still be in the markup")
        body = m.group(1)
        self.assertNotIn("Object.keys(modals.sync.picked)", body,
                         "the dialog computes its own counts inline; that is "
                         "how the placeholder N shipped")

    def test_outcome_sentence_names_the_real_count_and_its_plural(self):
        # A computed is referenced WITHOUT parentheses in a template. Asserting
        # `syncOutcomeSentence()` here would pin the method spelling that the
        # 4.3b defect shipped, and fail on the correct fix.
        self.assertIn("{{ syncOutcomeSentence }}", HTML)
        # One number, from the helper, in both singular and plural — never a
        # "(s)" and never a literal.
        self.assertIn('n === 1 ? " scope" : " scopes"', APP)


class NoPlaceholderInShippedCopy(unittest.TestCase):
    """A literal standing in for a value is not a measurement."""

    def test_the_sync_dialog_no_longer_says_n_agents(self):
        self.assertNotRegex(
            _modal("sync"), r"syncing to N\b",
            "the shipped sentence read 'syncing to N agents' — a hole in a "
            "template that was never filled")

    def test_no_action_dialog_ships_a_parenthetical_plural(self):
        for name in ("remove", "purge", "validate", "sync"):
            with self.subTest(dialog=name):
                self.assertNotRegex(
                    _modal(name), r"\b(issue|skill|scope|copy|agent)s?\)?\(s\)",
                    "'issue(s)' is the placeholder plural; the count is known")

    def test_purge_names_what_it_deletes_and_says_the_cost(self):
        body = _modal("purge")
        # 4.7c moved the plural out of the template into `purgeScopeSentence`,
        # so that the dialog and the toast cannot disagree about the grammar.
        # The INTENT of this test is unchanged -- the count reads as a word,
        # never as `skill(s)` -- but the mechanism it named is gone. The
        # ternary itself is asserted against the getter that now owns it, in
        # tests/test_redesign_purge_scope.py at 0 / 1 / many.
        self.assertIn("purgeScopeSentence", body)
        self.assertNotIn("(s)", body)
        # "This cannot be undone" was the whole warning and it names nothing.
        self.assertIn("Nothing here can be restored", body)

    def test_validate_states_which_name_was_validated(self):
        # "Skill is valid." says nothing about what was checked; a reader with
        # two dialogs open could not tell which name the verdict belonged to.
        self.assertIn("modals.validate.name", _modal("validate"))


class TheDialogsSpeakTheSharedVocabulary(unittest.TestCase):
    """31 inline `style` attributes became shared classes (1.5's `.choice`)."""

    def test_no_inline_style_attributes_in_the_action_dialogs(self):
        for name in ("remove", "purge", "validate", "sync"):
            with self.subTest(dialog=name):
                body = _modal(name)
                found = re.findall(r'\sstyle="', body)
                self.assertEqual(found, [],
                                 "inline styles make this dialog a different "
                                 "product from every other one")

    def test_remove_uses_the_choice_primitive_with_a_destructive_marker(self):
        body = _modal("remove")
        self.assertIn('class="choice choice-block"', body)
        self.assertIn('data-destructive="true"', body)

    def test_the_destructive_option_paints_only_while_it_is_selected(self):
        # A permanently-red dot beside an unselected option reads as "already
        # broken" — the 4.2d complaint about `problem` in a new place.
        rules = CSS[CSS.index("/* 4.7 ACTION DIALOGS"):]
        rules = rules[:rules.index(".template-list")]
        self.assertIn('.choice[data-destructive="true"] input:checked + .choice-box', rules)
        self.assertNotIn('.choice[data-destructive="true"] .choice-box { background:',
                         rules.replace('input:checked + .choice-box { background:', ''))

    def test_the_sync_row_keeps_a_native_checkbox_not_a_16px_mark(self):
        # `.choice-box` is 16px. Beside a full-width label that would be the
        # smallest target on the line, and RULES #13 has a floor for that.
        self.assertIn(".sync-target .choice-check", CSS)
        self.assertRegex(CSS, r"\.sync-target \.choice-check \{[^}]*accent-color")

    def test_the_count_column_may_not_clip_its_own_figure(self):
        # Found by LOOKING at the 1280 capture, which showed `19 skills · 4…`.
        # Measured 4px short at 1280, 768 and 390 alike.
        #
        # `flex: none` did not fix it, and the reason is worth stating: `.tag`
        # inherits `text-overflow: ellipsis`, which only applies alongside
        # `overflow: hidden`, and a flex item's `min-width: auto` resolves to
        # its content size ONLY while its overflow is visible. With the
        # overflow hidden it resolves to 0, so the column could shrink below
        # its own text whatever `flex` said. `min-width: max-content` states
        # it directly, and the label beside it is where the space comes from.
        self.assertRegex(CSS, r"\.sync-target \.tag \{[^}]*min-width:\s*max-content")
        self.assertRegex(CSS, r"\.sync-target \.tag \{[^}]*flex:\s*0 0 auto")

    def test_no_dead_issue_rule_remains(self):
        # 1.5's class: a rule that nothing selects reads as coverage.
        body = _modal("validate")
        self.assertNotIn('class="issue"', body)
        block = CSS[CSS.index("/* 4.7 ACTION DIALOGS"):]
        block = block[:block.index(".template-list")]
        self.assertNotIn(".issue {", block)
        # ...and the replacement names every part it styles.
        self.assertIn(".validate-issue .badge", block)
        self.assertIn(".validate-issue .issue-key", block)


if __name__ == "__main__":
    unittest.main()