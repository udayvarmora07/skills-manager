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
    """5.7a rewrite — was `assertEqual(titles, ["Anywhere", "Command palette",
    "Inside a dialog"])`.

    THE INTENT was "the reference is grouped by context": a reader needs to
    know WHERE a key applies before trusting it. Pinning the exact title list
    asserted a weaker thing — the three strings — and would have failed on
    the addition of a fourth, correct section. 5.7a added one.

    What follows asserts the intent, and adds two things the literal could
    not: every row belongs to a named section (an orphan row is a shortcut
    with no stated scope, which is the defect 5.7a fixed), and every section
    carries at least one row (an empty heading is a promise with nothing
    behind it). TEST-CHANGES.md carries the full old -> new row.
    """
    def _sections(self):
        html = _read(HTML_PATH)
        block = html.split('class="modal-body shortcuts-reference"', 1)[1]
        return re.findall(
            r'class="shortcuts-section-title">([^<]+)<(.*?)</section>', block, re.S)

    def test_the_reference_is_grouped_by_context(self):
        sections = self._sections()
        self.assertGreaterEqual(len(sections), 3)
        titles = [title for title, _body in sections]
        self.assertEqual(len(titles), len(set(titles)), "duplicate section headings: %r" % titles)
        for title, body in sections:
            self.assertTrue(title.strip(), "a section has no title")
            self.assertIn("shortcuts-row", body,
                          "section %r is a heading with no rows" % title)

    def test_no_shortcut_row_is_outside_a_named_section(self):
        """The defect 5.7a fixed: a row that claims a scope it cannot have.

        `/` sat under "Anywhere" on four of nine views. Asserting that every
        row is inside a section makes "which scope does this row claim?"
        answerable for every row, including any added later.
        """
        html = _read(HTML_PATH)
        block = html.split('class="modal-body shortcuts-reference"', 1)[1]
        block = block.split("</div>\n      <div class=\"modal-foot\"", 1)[0]
        total_rows = len(re.findall(r'class="shortcuts-row"', block))
        sectioned_rows = sum(
            len(re.findall(r'class="shortcuts-row"', body)) for _t, body in self._sections())
        self.assertEqual(total_rows, sectioned_rows,
                         "%d row(s) sit outside any section and claim no scope"
                         % (total_rows - sectioned_rows))

    def test_anywhere_holds_only_keys_that_are_not_view_scoped(self):
        """Moving `/` out of "Anywhere" is only honest if what stayed is global.

        `Ctrl K`, `?` and `Esc` are gated on `typing`/`activeModal` alone —
        never on `this.view`. If a future change narrows one of them to a
        view, the heading has become a false claim again and this fails.
        """
        anywhere = dict(self._sections()).get("Anywhere")
        self.assertIsNotNone(anywhere, "the 'Anywhere' section is gone")
        for key in ("Ctrl", "?", "Esc"):
            self.assertIn(key, anywhere, "%s left 'Anywhere' unexpectedly" % key)
        self.assertNotIn('>/<', anywhere.replace(" ", ""),
                         "`/` is filed under 'Anywhere' again")

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


_APP_VM = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {api(){}, formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){}, renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){}, groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}}},
  Vue: {createApp(app){sandbox.app = app; return {mount(){}};}, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return[];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const computed = sandbox.app.computed;
function contextFor(query) {
  const context = {view:'overview', selectedName:null, selected:null, selectedDisabled:false, commandPaletteQuery:query};
  Object.defineProperty(context, 'commandPaletteCommands', {get(){return computed.commandPaletteCommands.call(context);}});
  Object.defineProperty(context, 'filteredCommandPaletteCommands', {get(){return computed.filteredCommandPaletteCommands.call(context);}});
  /* Vue resolves `this.<computed>` through the instance proxy; a bare object
     would hand the watcher `undefined` and the probe would then be testing
     its own mistake rather than the product. */
  Object.defineProperty(context, 'bestCommandPaletteIndex', {get(){return computed.bestCommandPaletteIndex.call(context);}});
  return context;
}
const QUERY = %s;
const ctx = contextFor(QUERY);
/* Drive the REAL watcher, not the computed: the product path is
 * `watch.commandPaletteQuery` writing `commandPaletteActiveIndex`, and a probe
 * that assigns the index itself proves nothing about it. */
const watcher = sandbox.app.watch.commandPaletteQuery;
watcher.call(ctx, QUERY);
const drawn = computed.filteredCommandPaletteCommands.call(ctx).map(item => item.id);
const best = computed.bestCommandPaletteIndex.call(ctx);
const active = computed.commandPaletteActiveCommand.call(ctx);
/* 5.2d: two Install rows for one destination. The property, not the absence
   of one id — a tree that grew a DIFFERENT duplicate would satisfy the latter.
   `action|args` is what `runCommand` dispatches on, so two rows with the same
   key are two rows the reader cannot tell apart by what they do. */
const allRows = computed.commandPaletteCommands.call(contextFor('zzz-no-such-command'));
const seenAction = {};
const dupes = [];
for (const r of allRows) {
  const key = r.action + '|' + JSON.stringify(r.args || []);
  if (Object.prototype.hasOwnProperty.call(seenAction, key)) dupes.push([seenAction[key], r.id, key]);
  else seenAction[key] = r.id;
}
const allIds = allRows.map(r => r.id);
console.log(JSON.stringify({
  drawn: drawn,
  best: best,
  active: active ? active.id : null,
  installDrawn: computed.filteredCommandPaletteCommands.call(contextFor('install')).map(item => item.id),
  runnerDrawn: computed.filteredCommandPaletteCommands.call(contextFor('bunx')).map(item => item.id),
  emptyBest: computed.bestCommandPaletteIndex.call(contextFor('')),
  dupes: dupes,
  duplicateIds: allIds.filter((id, i) => allIds.indexOf(id) !== i),
  rowCount: allRows.length,
}));
"""



def _rank_module() -> str:
    """`commandMatchRank` lifted verbatim out of app.js.

    Same reason as `_palette_module`: app.js's top level dereferences `window`,
    so Node cannot import it. The block is lifted, not copied, and
    `test_the_executed_module_is_the_one_in_app_js` above is the reason a stale
    copy would be noticed.
    """
    source = _read(JS_PATH)
    start = source.index("const COMMAND_MATCH_LABEL_EXACT")
    end = source.index("\n}", source.index("return elsewhere.includes(needle)", start)) + 2
    return source[start:end]


class ActiveRowFollowsTheTypedName(unittest.TestCase):
    """Enter must run the command whose LABEL the reader typed.

    Why this file exists (found by the CI browser harness, not by a test)
    ---------------------------------------------------------------------
    ``browser_harness.py`` drives the palette with a real keypress: type
    "library", press Enter, assert the Library heading took focus. It failed in
    **all eight scenarios** — every viewport, plus the synthetic empty and
    unavailable-root inventories — with

        Library command did not focus the visible Library destination

    The cause is not flaky timing. 2.2 groups results and ``COMMAND_GROUP_ORDER``
    puts Transfer before Navigation, so the query "library" draws

        Transfer      Export archive      (title: "Export the current skill library")
        Navigation    Library
        Navigation    Focus search

    and Enter ran whatever the active index pointed at, which was 0 — the
    download. In the sandbox that answered HTTP 400 and toasted; in a populated
    library it answered 200 and silently downloaded an archive instead of
    navigating. Either way the reader asked for a destination and got a file.

    The group order is a recorded 2.2 decision with a test of its own
    (``tests/test_webui_contracts.py`` asserts Transfer before Navigation for
    "install"), so it is **not** reversed here. What changes is which row is
    active: the best *label* match, wherever it is drawn. Group order, drawn
    order, Home/End and ArrowDown are untouched.
    """

    @staticmethod
    def _probe(query):
        """Run the real app.js in a Node VM and ask it what Enter would run.

        A separate runner from `_node_evaluate` because that one evaluates an
        EXPRESSION; this program needs its own top level to build the sandbox.
        """
        program = _APP_VM % json.dumps(query)
        proc = subprocess.run(
            ["node", "-e", program], capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr.strip() or "node failed")
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_typing_a_destination_name_activates_that_destination(self):
        # RED FIRST: against the pre-fix source this returned
        # {"active": "export-archive"} — the download, not the destination.
        self.assertEqual(self._probe("library")["active"], "nav-library")

    def test_the_drawn_order_is_unchanged_by_this_fix(self):
        # The 2.2 decision under test is the GROUP order, and it must survive:
        # a fix that quietly reversed it would have invalidated the recorded
        # reasoning behind tests/test_webui_contracts.py without anyone reading
        # that test.
        result = self._probe("library")
        self.assertEqual(result["drawn"], ["export-archive", "nav-library", "focus-search"])
        # `installDrawn` was `["install-workflow", "nav-install"]` until 5.2d
        # deleted the second Install row. That it was drawn in THAT order was
        # 2.2's Transfer-before-Navigation rule working correctly on a row that
        # should not have existed, so the order assertion goes with the row.
        # The property that keeps it deleted is the next test, not this line.
        self.assertEqual(result["installDrawn"], ["nav-install"])

    def test_no_two_palette_rows_do_the_same_thing(self):
        """5.2d's rule: one destination is one row.

        `install-workflow` survived 5.2b — which deleted the dialog it used to
        name — as a second palette row whose action was a one-line alias of
        `nav-install`'s. Two rows that land on the same page offer a choice the
        reader cannot act on, and because 2.2 ranks Transfer before Navigation
        the copy naming a surface the product no longer has was drawn ABOVE
        the one naming the real destination, so Enter on "install" highlighted
        it.

        """
        # Asserting the absence of the string `install-workflow` would pass on
        # a tree that had grown a DIFFERENT duplicate, so this drives the real
        # computed in the Node VM above and compares `(action, args)` across
        # every row — the property, which is what the fix actually was.
        result = self._probe("")
        self.assertEqual(result["dupes"], [],
                         "two palette rows run the same action with the same "
                         "arguments — one destination, one row (5.2d)")
        self.assertEqual(result["duplicateIds"], [],
                         "a palette row id appears twice")
        # 0 is the number that can fail here: deleting every row satisfies
        # "no duplicates" and would prove nothing at all.
        self.assertGreater(result["rowCount"], 20,
                           "the palette list was empty — nothing was compared")

    def test_the_runner_keywords_the_deleted_row_carried_still_reach_install(self):
        """The other half, and the one that makes the collapse honest.

        `install-workflow`'s keywords were `install npx pnpm bunx registry`.
        Deleting the row without moving them would make "bunx" — the word a
        reader who wants the installer half actually types — match nothing,
        which turns a tidied palette into a less reachable one. The words moved
        to `nav-install`; this drives the filter with one of them.
        """
        for term in ("npx", "bunx", "pnpm", "runner"):
            with self.subTest(term=term):
                drawn = self._probe(term)["drawn"]
                self.assertIn("nav-install", drawn,
                              f"{term!r} no longer reaches the Install view "
                              f"(5.2d dropped the runner keywords): {drawn}")

    def test_an_empty_query_activates_the_first_row(self):
        # No query means no name was typed, so row 0 is the whole answer.
        self.assertEqual(self._probe("library")["emptyBest"], 0)

    def test_an_unmatched_query_matches_nothing_and_stays_at_the_first_row(self):
        result = self._probe("zzzz-no-such-command")
        self.assertEqual(result["drawn"], [])
        self.assertEqual(result["best"], 0)
        self.assertIsNone(result["active"])

    def test_every_name_match_tier_is_reachable(self):
        """The four tiers are the model, so they are tested directly.

        The end-to-end probe cannot separate them: the real command set has no
        two commands in one group where one label is a prefix of the other, so
        "exact" and "prefix" look identical from the outside and a mutation that
        disabled exact-label matching stayed green. This test drives
        `commandMatchRank` itself, lifted out of app.js, with commands chosen to
        land in each tier.
        """
        program = _rank_module() + r"""
const commands = [
  {id:'exact',    label:'Library',        title:'Open Library', category:'Navigation', keywords:'skills browse'},
  {id:'prefix',   label:'Library search', title:'Open Library search', category:'Navigation', keywords:''},
  {id:'inside',   label:'Open Library',   title:'Open Library', category:'Tools', keywords:''},
  {id:'prose',    label:'Export archive', title:'Export the current skill library', category:'Transfer', keywords:''},
  {id:'absent',   label:'Doctor',         title:'Inspect health', category:'Tools', keywords:''},
];
console.log(JSON.stringify(commands.map(c => [c.id, commandMatchRank(c, 'library')])));
"""
        proc = subprocess.run(["node", "-e", program], capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr.strip() or "node failed")
        ranks = dict(json.loads(proc.stdout.strip().splitlines()[-1]))
        self.assertEqual(ranks["exact"], 1, "an exact label match must rank best")
        self.assertEqual(ranks["prefix"], 2)
        self.assertEqual(ranks["inside"], 3, "a label that merely contains the query still beats prose")
        self.assertEqual(ranks["prose"], 4, "a title sentence that mentions it is the weakest match")
        self.assertEqual(ranks["absent"], 0, "no mention anywhere is not a match")
