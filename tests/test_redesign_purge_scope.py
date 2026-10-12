"""4.7c -- the purge confirm states what the action covers, not only what it shows.

The backlog row for this task asserted that ``/api/trash/purge`` is unscoped:
that it deletes every scope's trash while the dialog can only see the global
list. **That premise is wrong, and the suite pins the observation rather than
the assumption.** On the sandbox a skill removed from ``commandcode`` is parked
at ``~/.commandcode/trash/commandcode__<name>-<ts>``; ``Store.purge_trash()``
walks one directory -- the global ``<data>/skills-manager/trash`` -- so the POST
returned exactly the three names ``GET /api/trash`` had listed and the scope
copy survived on disk. The dialog's list was complete all along.

A complete list is not the same as an honest dialog. Nothing in the trash view
said *which* trash it was listing, so a reader who removed a skill from an
agent scope, watched it leave the Library, and opened the trash view was told
the trash was empty. Three rules, and both directions of each:

1. **The claim is in the copy.** The dialog and the trash view both render
   ``purgeScopeNote``. A dialog that dropped the note would still pass every
   behavioural test in the repo, which is how the row survived the gate.
2. **The claim is derived, never typed.** ``agentScopeLabels`` reads ``kind ===
   "agent"`` off ``/api/scopes`` instead of hardcoding the scope list, so a
   scope that was not detected is not advertised and a scope that is detected
   cannot go unnamed. A copy change alone cannot satisfy this: it is asserted
   against the loaded getter, in Node, against a stub ``this``.
3. **No ungrammatical placeholder survives.** The toast read
   ``"Purged 3 skill(s) from trash."`` -- the last ``(s)`` in the four action
   dialogs, and it never named the scope either.

The computed block is LOADED in a Node VM rather than sliced by marker, for the
reason recorded in ``test_redesign_action_dialogs``: marker-slicing cannot tell
an object-literal method from a top-level one and has passed on a broken tree
three times in this repo.
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
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _app_options_literal() -> str:
    """Return the object literal ``app.js`` hands to ``createApp``."""
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
    return APP[open_brace:i + 1]


def _eval_getters(exprs: dict, *, scopes, trash, fns=("agentScopeLabels", "purgeScopeSentence", "purgeScopeNote")):
    """Call the named computed getters against a stub ``this`` and return them.

    The getters are called for real. A test that only greps the source cannot
    tell a getter that reads ``this.scopes`` from one that hardcodes the scope
    names, and the whole point of rule 2 is that the two are different.
    """
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")
    literal = _app_options_literal()
    prelude = (
        "const __own = { Object: Object, JSON: JSON, console: console };\n"
        "let __captured = null;\n"
        "const __scope = new Proxy(__own, {\n"
        "  has: (t, k) => !(k in t),\n"
        "  get: (t, k) => (k in t ? t[k] : function () {}),\n"
        "  set: (t, k, v) => { __captured = v; return true; },\n"
        "});\n"
        "with (__scope) { __opts = " + literal + "; }\n"
        "const __opts = __captured;\n"
    )
    calls = "".join(
        "  out[%s] = stub[%s];\n" % (json.dumps(k), json.dumps(k)) for k in fns
    )
    script = prelude + (
        "const stub = {\n"
        "  scopes: " + json.dumps(scopes) + ",\n"
        "  trashSkills: " + json.dumps(trash) + ",\n"
        "  formatNumber: (v) => String(v),\n"
        "};\n"
        # Vue installs computed getters on the instance, so a getter may read
        # another one as `this.x`. The stub must do the same, or the only getter
        # this suite can exercise is the one with no dependencies -- which is
        # exactly the getter whose honesty is not in question.
        "for (const k of " + json.dumps(list(fns)) + ") {\n"
        "  Object.defineProperty(stub, k, { get() { return __opts.computed[k].call(stub); } });\n"
        "}\n"
        "const out = {};\n" + calls + "console.log(JSON.stringify(out));\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "opts.js"
        p.write_text(script, encoding="utf-8")
        res = subprocess.run([node, str(p)], capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise AssertionError("loading app.js options failed:\n" + res.stderr[-2000:])
    return json.loads(res.stdout.strip().splitlines()[-1])


def _purge_dialog() -> str:
    start = HTML.index('data-modal="purge"')
    return HTML[start:HTML.index("</div>\n  </div>", start)]


class PurgeScopeNoteTest(unittest.TestCase):
    def test_note_names_the_scopes_observed_from_the_api(self):
        scopes = [
            {"id": "global", "label": "Global", "kind": "global"},
            {"id": "claude-code", "label": "Claude Code", "kind": "agent"},
            {"id": "codex", "label": "Codex", "kind": "agent"},
        ]
        got = _eval_getters({}, scopes=scopes, trash=[])
        self.assertEqual(got["agentScopeLabels"], ["Claude Code", "Codex"])
        self.assertIn("Claude Code, Codex", got["purgeScopeNote"])

    def test_note_invents_no_scope_when_none_is_detected(self):
        """A scope that is not installed must not be advertised.

        The parenthetical is the risk: a hardcoded list would name Codex on a
        machine that has never run Codex, which is RULES #12 -- the UI states
        only observed facts.
        """
        scopes = [{"id": "global", "label": "Global", "kind": "global"}]
        got = _eval_getters({}, scopes=scopes, trash=[])
        self.assertEqual(got["agentScopeLabels"], [])
        self.assertNotIn("(", got["purgeScopeNote"])

    def test_note_is_two_grammatical_sentences_and_names_no_number(self):
        scopes = [{"id": "claude-code", "label": "Claude Code", "kind": "agent"}]
        got = _eval_getters({}, scopes=scopes, trash=[{"name": "a"}])
        note = got["purgeScopeNote"]
        self.assertTrue(note.endswith("."), note)
        self.assertNotIn("(s)", note)
        self.assertNotIn("N ", note)
        # Two sentences: the boundary claim and the consequence.
        self.assertEqual(len([s for s in note.split(". ") if s.strip()]), 2, note)

    def test_sentence_agrees_with_the_list_it_describes(self):
        """0 / 1 / many. ``skill(s)`` was the defect; 0 has its own grammar."""
        for n, expected in (
            (0, "Permanently delete 0 trashed skills from the global trash?"),
            (1, "Permanently delete 1 trashed skill from the global trash?"),
            (3, "Permanently delete 3 trashed skills from the global trash?"),
        ):
            got = _eval_getters({}, scopes=[], trash=[{"name": str(i)} for i in range(n)])
            self.assertEqual(got["purgeScopeSentence"], expected, "n=%d" % n)
            self.assertNotIn("(s)", got["purgeScopeSentence"])


class PurgeDialogCopyTest(unittest.TestCase):
    def test_dialog_renders_the_computed_sentence_and_note(self):
        dlg = _purge_dialog()
        self.assertIn("{{ purgeScopeSentence }}", dlg)
        self.assertIn("{{ purgeScopeNote }}", dlg)
        # The count must not be re-derived inside a TEXT node: two sources for
        # one fact is the 2.3 defect (a row that ran a different command than
        # the one it drew). `v-if="trashSkills.length"` is a visibility
        # condition, not a derivation, and an assertion that forbade the
        # substring outright would fail on correct code.
        for m in re.finditer(r"\{\{(.*?)\}\}", dlg, re.S):
            self.assertNotIn("trashSkills.length", m.group(1), m.group(0))

    def test_dialog_titles_itself_by_scope(self):
        dlg = _purge_dialog()
        self.assertIn("Empty the global trash", dlg)
        self.assertIn("global trash", dlg)
        self.assertNotIn("Empty trash permanently", dlg)

    def test_trash_view_names_the_trash_it_lists(self):
        self.assertIn("Global trash", HTML)
        self.assertIn("purgeScopeNote", HTML)
        self.assertIn("scope-note-inline", HTML)
        # The one surface that was already honest stays honest.
        self.assertIn("Global trash is empty", HTML)

    def test_no_scope_note_icon(self):
        """An alert glyph here would make a factual boundary read as an error."""
        dlg = _purge_dialog()
        self.assertNotIn("<app-icon", dlg)

    def test_toast_is_grammatical_and_names_the_scope(self):
        start = APP.index("async purgeTrash()")
        body = APP[start:APP.index("\n    },", start)]
        # Comments are stripped first. 4.7d lost a locator to exactly this: the
        # new comment quotes the old string verbatim, so an assertion that does
        # not strip them fails on a tree where the string is gone.
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.S)
        self.assertNotIn("(s)", code)
        self.assertIn("global trash", code)
        self.assertIn("res.purged", code)


class ScopeNoteStyleTest(unittest.TestCase):
    def test_scope_note_is_styled_in_the_dialog_block(self):
        self.assertRegex(CSS, r"\.scope-note\s*\{[^}]*border-left")
        self.assertRegex(CSS, r"\.scope-note-inline\s*\{")

    def test_scope_note_colour_is_a_token_not_a_literal(self):
        rule = CSS[CSS.index(".scope-note {"):CSS.index("}", CSS.index(".scope-note {"))]
        self.assertIn("var(--text-muted)", rule)
        self.assertNotRegex(rule, r"#[0-9a-fA-F]{3,8}\b")


if __name__ == "__main__":
    unittest.main()