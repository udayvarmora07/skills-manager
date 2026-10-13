"""5.7a — the keyboard-shortcut reference must not claim a view the key fails on.

THE DEFECT THIS EXISTS FOR
--------------------------
The help dialog filed `/` — "Focus skill search" — under a section headed
**"Anywhere"**. `onKeydown` gates that key on `searchAppliesHere`, which was
`["skills", "trash", "quality", "install"]`: four views of nine. On Overview,
Profiles, Workspaces, Recovery and Settings the keypress deliberately does
nothing. The handler's own comment said exactly that ("swallowing `/` there
would be a keypress that visibly does nothing"), so the BEHAVIOUR was
deliberate and the DOCUMENTATION contradicted it — RULES #12, the honesty
principle: the UI states only observed facts.

THE FIX
-------
`SEARCH_VIEWS` is the single list. `searchAppliesHere` reads it (so the
guard is unchanged in meaning) and the dialog renders `searchShortcutScope`
from the same list. Two hosts, one definition.

WHY THESE TESTS ARE SHAPED THE WAY THEY ARE
------------------------------------------
A test that asserts the dialog contains the string "Library, Install,
Quality and Trash" passes forever if somebody adds a sixth view to
SEARCH_VIEWS and forgets this one — which is the exact drift that caused
the defect. So the assertions below are RELATIONAL: they re-derive the
guard from the source and require the prose to match it. A test that pins
the literal sentence would have passed against the broken build too.
"""
import json
import re
import unittest
from pathlib import Path

WEBUI = Path(__file__).resolve().parents[1] / "skillsmgr" / "webui"
APP = (WEBUI / "app.js").read_text(encoding="utf-8")
HTML = (WEBUI / "index.html").read_text(encoding="utf-8")


def search_view_block() -> str:
    """The SEARCH_VIEWS literal, as declared in the source."""
    match = re.search(r"const SEARCH_VIEWS = Object\.freeze\(\[(.*?)\]\);", APP, re.S)
    assert match, "SEARCH_VIEWS is gone — the guard and the reference must share one list"
    return match.group(1)


def declared_search_views() -> list:
    return re.findall(r'\{\s*id:\s*"([^"]+)",\s*label:\s*"([^"]+)"\s*\}', search_view_block())


def every_view() -> list:
    """The view ids the shell can actually switch to."""
    ids = set(re.findall(r"switchView\('([^']+)'\)", HTML))
    ids |= set(re.findall(r"args:\s*\[\"([a-z]+)\"\],\s*focusDestination", APP))
    return sorted(ids)


def help_section_titles() -> list:
    body = HTML[HTML.index('data-modal="help"'):]
    body = body[:body.index("</div>\n  </div>")] if "</div>\n  </div>" in body else body
    return re.findall(r'class="shortcuts-section-title">([^<]+)<', body)


class TestShortcutReferenceIsHonest(unittest.TestCase):
    """The reference describes the guard; it does not describe a wish."""

    def test_search_guard_is_not_an_independent_literal(self):
        """`searchAppliesHere` must read SEARCH_VIEW_IDS, not its own array.

        The defect needed two lists. If the guard goes back to a private
        literal, this test fails before the prose can drift again.
        """
        body = re.search(r"searchAppliesHere\(\)\s*\{(.*?)\n    \},", APP, re.S)
        self.assertIsNotNone(body, "searchAppliesHere() not found")
        self.assertIn("SEARCH_VIEW_IDS", body.group(1))
        self.assertNotIn('["skills"', body.group(1))

    def test_the_reference_row_is_not_filed_under_anywhere(self):
        """`/` must not sit in the section that claims to work everywhere."""
        help_html = HTML[HTML.index('data-modal="help"'):]
        anywhere_start = help_html.index('shortcuts-section-title">Anywhere<')
        next_section = help_html.index("shortcuts-section-title", anywhere_start + 10)
        anywhere = help_html[anywhere_start:next_section]
        self.assertNotIn(
            '<span class="kbd">/</span>', anywhere,
            "`/` is still listed under 'Anywhere' — it is bound on %d of %d views"
            % (len(declared_search_views()), len(every_view())),
        )

    def test_the_other_three_rows_really_are_global(self):
        """The rows left under 'Anywhere' must be the ones that guard on nothing.

        Moving `/` out is only honest if what stayed is still true. `Ctrl K`,
        `?` and `Esc` are gated on `typing`/`activeModal` only — never on the
        view — so they keep the section. If a future change narrows one of
        them to a view, this fails.
        """
        help_html = HTML[HTML.index('data-modal="help"'):]
        anywhere_start = help_html.index('shortcuts-section-title">Anywhere<')
        next_section = help_html.index("shortcuts-section-title", anywhere_start + 10)
        anywhere = help_html[anywhere_start:next_section]
        for key in ("Ctrl", "?", "Esc"):
            self.assertIn(key, anywhere, "%s left 'Anywhere' unexpectedly" % key)
        for view_id, _label in declared_search_views():
            self.assertNotIn("searchAppliesHere", anywhere)

    def test_the_prose_names_every_view_the_guard_admits(self):
        """Each declared view's LABEL must appear in the `/` row."""
        help_html = HTML[HTML.index('data-modal="help"'):]
        row = re.search(r'<span class="kbd">/</span></dt>\s*<dd>(.*?)</dd>', help_html, re.S)
        self.assertIsNotNone(row, "the `/` row is gone")
        self.assertIn("searchShortcutScope", row.group(1),
                      "the `/` row must render the derived scope, not a literal sentence")

    def test_the_scope_sentence_is_derived_and_properly_joined(self):
        """Run the real computed against the real list — in a Node VM.

        A computed that is never rendered throws on the page and nothing
        fails here (5.5's `qualityCategoryLabel`, exactly this bug). Running
        the actual expression catches the whole class.
        """
        import shutil
        import subprocess
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required to evaluate the real computed")
        declared = json.dumps(
            [{"id": i, "label": l} for i, l in declared_search_views()])
        script = f"""
const SEARCH_VIEWS = {declared};
const searchShortcutScope = () => {{
  const labels = SEARCH_VIEWS.map((view) => view.label);
  if (labels.length < 2) return labels.join("");
  return `${{labels.slice(0, -1).join(", ")}} and ${{labels[labels.length - 1]}}`;
}};
console.log(JSON.stringify({{
  sentence: searchShortcutScope(),
  expected: labelsExpect(),
}}));
""".replace("labelsExpect()", json.dumps(
            " and ".join([", ".join([l for _i, l in declared_search_views()][:-1]),
                          [l for _i, l in declared_search_views()][-1]])))
        out = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(data["sentence"], data["expected"])
        self.assertIn(" and ", data["sentence"], "a bare comma list reads as a menu, not a sentence")
        self.assertNotIn(", and ", data["sentence"], "Oxford comma would not match the derivation")

    def test_search_views_are_a_minority_of_the_shell(self):
        """Guards THIS defect from being quietly undone by widening the guard.

        If someone made `/` work everywhere by editing the guard, the prose
        would follow and every other test here would pass. This one states
        the product decision plainly: `/` is scoped, not global.
        """
        self.assertLess(
            len(declared_search_views()), len(every_view()),
            "`/` now claims every view — confirm that is intended before widening it",
        )

    def test_every_search_view_has_a_label(self):
        """A view with an empty label would render ", , and ." in the prose."""
        for view_id, label in declared_search_views():
            self.assertTrue(label.strip(), "view %r has no label" % view_id)


if __name__ == "__main__":
    unittest.main()