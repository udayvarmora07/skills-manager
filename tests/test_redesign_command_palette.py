"""Command palette and shortcut-reference contracts (redesign task 2.2).

Why this file exists
--------------------
Task 2.2 had two halves and one of them was a defect found by reading, not by a
test.

**Product.** DESIGN-V2 §A names Raycast's *grouped* results as the reference for
the command palette. The palette was a flat list that printed the category on
every row — the word "Navigation" appeared 8 times, "Tools" 7 — so it read as a
column rather than as groups, and a reader scanning for "where does this group
end" had nothing to find. The shortcut reference was worse: a two-column
``<dl>`` of bare ``<kbd>`` elements, which is a legend, not a reference, and
which listed ``/`` and ``?`` beside palette keys without saying that ``/`` and
``?`` only work when no dialog is open.

**Also fixed here.** Task 2.1d recorded two findings against ``.menu`` and named
this task as the owner: it was ``min-width: 200px`` with no maximum, so it was
the narrowest surface in the app while carrying its longest labels, and three
of those labels wrapped onto two lines.

**The trap this file is written around.** Grouping can be implemented twice —
once in the flat list the keyboard walks and again in the rendering — and the
two orders then disagree. ArrowDown would highlight a row the reader cannot see.
So the tests below assert that there is exactly ONE ordering in the source and
that the grouping is presentation over it, not a second sort.

Each test was written to be able to FAIL; the mutation proof is recorded in
.redesign/TEST-CHANGES.md.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "skillsmgr" / "webui"
CSS_PATH = WEBUI / "styles.css"
HTML_PATH = WEBUI / "index.html"
JS_PATH = WEBUI / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), css, flags=re.S)


def _declarations(css: str, selector: str) -> dict[str, str]:
    """Merged declarations of every rule whose prelude is exactly ``selector``.

    Merged, not "the first block": a rule may legitimately be declared twice
    (a media query plus the base cascade), and returning only the first is how a
    test ends up asserting against a block that does not carry the property it
    claims to pin. This is the same bug task 2.1d hit in the motion tests.
    """
    body = _strip_comments(css)
    out: dict[str, str] = {}
    for match in re.finditer(r"(?:^|[};])\s*" + re.escape(selector) + r"\s*\{", body):
        depth, i = 1, match.end()
        while i < len(body) and depth:
            depth += 1 if body[i] == "{" else (-1 if body[i] == "}" else 0)
            i += 1
        for decl in body[match.end():i - 1].split(";"):
            if ":" in decl:
                key, _, value = decl.partition(":")
                out[key.strip()] = value.strip()
    return out


def _node_evaluate(script: str) -> object:
    """Run ``script`` with the app's palette helpers in scope, in real Node.

    The ordering is a pure function of module-level constants, so it is
    testable without a browser. A test that only greps the source cannot fail on
    a wrong sort; this one executes it.
    """
    program = "\n".join([
        _PALETTE_MODULE,
        f"console.log(JSON.stringify(({script})));",
    ])
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.strip() or "node failed")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _palette_module() -> str:
    """The palette's ordering helpers, lifted verbatim out of app.js.

    Lifted rather than imported: app.js is one 3000-line file whose top level
    dereferences ``window``, so a Node import cannot run. Copying the block is
    what makes this executable, and the two tests below assert the copy still
    matches the file it claims to come from.
    """
    source = _read(JS_PATH)
    start = source.index("const COMMAND_GROUP_ORDER")
    end = source.index('return String(a || "").localeCompare(String(b || ""));', start)
    end = source.index("\n}", end) + 2
    return source[start:end]


_PALETTE_MODULE = _palette_module()


class PaletteOrdering(unittest.TestCase):
    """There must be exactly one ordering, and the keyboard walks it."""

    def test_the_executed_module_is_the_one_in_app_js(self):
        # If app.js is edited and this copy is not, every ordering assertion
        # below would be measuring a program no user ever runs.
        self.assertIn("const COMMAND_GROUP_ORDER", _read(JS_PATH))
        self.assertEqual(_palette_module(), _PALETTE_MODULE)

    def test_declared_groups_rank_in_the_declared_order(self):
        result = _node_evaluate(
            '["Navigation","Selected skill","Tools","Transfer","Skill actions"]'
            ".slice().sort(compareCommandGroups)"
        )
        self.assertEqual(
            result, ["Selected skill", "Skill actions", "Transfer", "Tools", "Navigation"]
        )

    def test_an_undeclared_group_ranks_after_every_declared_one(self):
        result = _node_evaluate(
            '["Something new","Navigation"].slice().sort(compareCommandGroups)'
        )
        self.assertEqual(result, ["Navigation", "Something new"])

    def test_two_undeclared_groups_are_ordered_deterministically(self):
        # Alphabetical, not hash order: a hash collision would be stable but
        # unreadable, and the headings are the reader's only map of the list.
        result = _node_evaluate(
            '["Zebra","Alpha","Middle"].slice().sort(compareCommandGroups)' 
        )
        self.assertEqual(result, ["Alpha", "Middle", "Zebra"])

    def test_the_grouped_computed_does_not_re_sort(self):
        """Grouping is presentation. A second sort here is the bug 2.2 avoids."""
        source = _read(JS_PATH)
        start = source.index("commandPaletteGroups()")
        end = source.index("commandPaletteActiveCommand()", start)
        block = source[start:end]
        self.assertNotIn(".sort(", block)
        self.assertIn("filteredCommandPaletteCommands", block)

    def test_the_flat_list_carries_the_single_sort(self):
        source = _read(JS_PATH)
        start = source.index("filteredCommandPaletteCommands()")
        end = source.index("commandPaletteGroups()", start)
        block = source[start:end]
        self.assertEqual(block.count(".sort("), 1)
        self.assertIn("compareCommandGroups", block)


class PaletteMarkup(unittest.TestCase):
    def test_results_are_a_listbox_of_groups_of_options(self):
        html = _read(HTML_PATH)
        self.assertIn('role="listbox" aria-label="Available commands"', html)
        self.assertIn('class="command-palette-group" role="group"', html)
        self.assertIn('role="option"', html)

    def test_every_group_heading_is_labelled_for_the_group_it_names(self):
        # A heading nobody can associate with its rows is decoration. The
        # `role="group"` is only worth having if `aria-labelledby` binds it.
        html = _read(HTML_PATH)
        self.assertIn(":aria-labelledby=\"group.id + '-label'\"", html)
        self.assertIn(":id=\"group.id + '-label'\"", html)

    def test_the_flat_index_is_the_selection_and_the_group_is_not(self):
        # `aria-activedescendant` walks the flat list, so the row that claims
        # `aria-selected` must be the row at that flat index — not the position
        # within its own group, which is the mistake that grouping invites.
        html = _read(HTML_PATH)
        self.assertIn(
            ':aria-selected="filteredCommandPaletteCommands.indexOf(command) === commandPaletteActiveIndex"',
            html,
        )

    def test_a_key_cap_on_a_result_is_hidden_from_the_announcement(self):
        # The row already announces its label; a bare "/" glyph read after it
        # states the same fact twice.
        html = _read(HTML_PATH)
        self.assertIn('class="command-palette-keys" aria-hidden="true"', html)

    def test_the_footer_uses_the_kbd_primitive_and_not_a_bare_kbd_element(self):
        html = _read(HTML_PATH)
        self.assertIn('<div class="modal-foot command-palette-help">', html)
        footer = html.split('class="modal-foot command-palette-help"', 1)[1].split("</div>", 1)[0]
        self.assertIn('class="kbd"', footer)
        # A bare <kbd> was the old rule's target; it rendered a different cap
        # from the primitive and was the reason `.kbd` had no reader.
        self.assertNotIn("<kbd>", footer)


class ShortcutReference(unittest.TestCase):
    def test_the_reference_is_grouped_by_context(self):
        html = _read(HTML_PATH)
        titles = re.findall(r'class="shortcuts-section-title">([^<]+)<', html)
        self.assertGreaterEqual(len(titles), 3)
        self.assertEqual(titles, ["Anywhere", "Command palette", "Inside a dialog"])

    def test_every_shortcut_key_cap_is_the_kbd_primitive(self):
        html = _read(HTML_PATH)
        block = html.split('class="modal-body shortcuts-reference"', 1)[1].split("</div>\n      <div class=\"modal-foot\"", 1)[0]
        self.assertNotIn("<kbd>", block)
        self.assertIn('class="kbd"', block)

    def test_the_reference_lists_only_shortcuts_that_work(self):
        """j/k ship in 4.2. Listing them before then is a false claim.

        RULES.md 12: the UI states only observed facts. A shortcut reference
        that lists a key the build does not handle is worse than one that
        omits it, because it is trusted.
        """
        source = _read(JS_PATH)
        html = _read(HTML_PATH)
        block = html.split('class="modal-body shortcuts-reference"', 1)[1]
        for key, handler in (("j", '"j"'), ("k", '"k"')):
            if handler not in source:
                self.assertNotIn(
                    f'>{key}</span>', block,
                    f"the reference advertises '{key}' but app.js has no handler for it",
                )

    def test_the_row_grid_collapses_on_a_narrow_viewport(self):
        # 320px is in the supported range (DESIGN-V2 §J). A fixed two-column
        # dt/dd at 96px + 1fr leaves the description with nothing.
        decls = _declarations(_read(CSS_PATH), ".shortcuts-row")
        self.assertIn("grid-template-columns", decls)


class MenuWidth(unittest.TestCase):
    """The 2.1d findings this task inherited."""

    def test_the_menu_has_a_minimum_that_fits_its_longest_label(self):
        decls = _declarations(_read(CSS_PATH), ".menu")
        self.assertIn("min-width", decls)
        self.assertGreater(int(decls["min-width"].removesuffix("px")), 200)

    def test_the_menu_is_bounded_at_both_ends(self):
        # Right-anchored, so it grows leftward; unbounded it is the narrowest
        # surface in the app, which is how it shipped.
        decls = _declarations(_read(CSS_PATH), ".menu")
        self.assertIn("max-width", decls)
        self.assertIn("100vw", decls["max-width"])

    def test_a_menu_item_never_wraps_onto_two_lines(self):
        decls = _declarations(_read(CSS_PATH), ".menu button")
        self.assertEqual(decls.get("white-space"), "nowrap")


if __name__ == "__main__":
    unittest.main()