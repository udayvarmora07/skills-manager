"""7.4c — the Trash view has a door.

The defect this file exists for is not a styling problem and no amount of
looking at it would find it. The Trash view shipped with a sidepanel list
(`v-else-if="view === 'trash'"`), a detail pane with per-item facts, Restore
and Purge, an entry in `SEARCH_VIEWS` — so the search field rendered a
"Search trash…" placeholder and the `?` reference told the reader the field
filtered Trash — and **not one control anywhere opened it**. There were
exactly eight `switchView(...)` controls in the markup and none named `trash`.

Nothing on this branch could see it:

* the branch renders correctly, so there is no console error;
* `VIEWS` in `tests/e2e/test_visual_sweep.py` and `test_width_gate.py` are
  the same eight views *without* trash, so every capture and every width
  assertion on this branch was honest and simply never went there;
* `check_inventory.py` reads views FROM the markup, so it counted the Trash
  view as existing — which it did. It is not the same question as "can a
  reader open it".

So the invariant is stated here as the derived form that would have failed:
**a view the markup renders must be reachable from a control in the markup**.
Every set below is derived from source, never enumerated, so the next view
added is added to the wrong side of this assertion by being absent — which is
how `tests/test_webui_contracts.py` already does its focus-heading check.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def rendered_views() -> set:
    """Every view id the markup renders a branch for.

    Both `v-if` and `v-else-if` are matched; the distinction does not matter
    for reachability and only invites a second code path to get wrong.
    """
    return set(re.findall(r'v(?:-else)?-?if="view === \'([a-z]+)\'"', HTML))


def markup_reachable_views() -> set:
    """Every view id a CONTROL IN THE MARKUP opens.

    Two declarations count, and only because both are real affordances:
    `data-nav-view="x"` (the attribute 7.4c added so a test can read markup
    rather than count occurrences of a substring) and `switchView('x')` (the
    existing rail and drawer buttons).
    """
    ids = set(re.findall(r'data-nav-view="([a-z]+)"', HTML))
    ids |= set(re.findall(r"switchView\('([a-z]+)'\)", HTML))
    return ids


def palette_reachable_views() -> set:
    ids = set(re.findall(r'args:\s*\["([a-z]+)"\]\s*,\s*focusDestination', APP))
    ids |= set(re.findall(r'switchView\("([a-z]+)"\)', APP))
    return ids


def search_view_ids() -> list:
    match = re.search(r"const SEARCH_VIEWS = Object\.freeze\(\[(.*?)\]\);", APP, re.S)
    assert match, "SEARCH_VIEWS is gone — the guard and the reference must share one list"
    return re.findall(r'\{\s*id:\s*"([^"]+)"\s*,', match.group(1))


def _recovery_center_block() -> str:
    start = HTML.index('class="detail-inner recovery-center"')
    # To the next sibling branch of the same chain. The pane is a flat run of
    # `<div v-else-if="view === ...">` siblings, so the next one ends it.
    rest = HTML[start + 10:]
    end = rest.index('<div v-else-if="view === ')
    return HTML[start:start + 10 + end]


def _trash_pane_block() -> str:
    start = HTML.index('<div v-else-if="view === \'trash\'" class="detail-inner">')
    return HTML[start:start + 3000]


class TestEveryRenderedViewHasADoor(unittest.TestCase):
    """The assertion that would have failed before 7.4c."""

    def test_no_view_is_rendered_without_a_control_that_opens_it(self):
        unreachable = sorted(rendered_views() - markup_reachable_views())
        self.assertEqual(
            unreachable, [],
            "these views render markup but no control in the markup opens them: "
            f"{unreachable}. A view nobody can reach is not a feature; it is "
            "dead markup that every capture gate reports as covered.",
        )

    def test_the_rendered_set_is_not_empty_and_covers_the_trash_view(self):
        """The control: a regex that matches nothing passes the test above."""
        rendered = rendered_views()
        self.assertGreaterEqual(len(rendered), 9,
                                f"only {sorted(rendered)} parsed as rendered views — "
                                "the extraction is broken, not the product")
        self.assertIn("trash", rendered)

    def test_the_recovery_section_is_inside_the_rendered_set(self):
        """Guards `_recovery_center_block`'s slice against silently widening.

        If the locator stopped finding the pane it would raise, not pass — but
        a locator that matched the WRONG `<div v-else-if=` would return a block
        that satisfies every assertion below and describes something else.
        """
        block = _recovery_center_block()
        self.assertIn("recovery-trash-title", block)
        self.assertNotIn("settings-center", block)


class TestTheDoorItself(unittest.TestCase):
    """Where the door is, and what it says."""

    def test_the_trash_door_lives_on_the_section_that_owns_the_subject(self):
        """0.1's recorded decision, kept and made checkable.

        `trash` is not a rail destination: a ninth icon in the 56px column
        would push the scope picker and the context meter out of reach, and it
        would be the only Operations item that is a *sub*-destination of the
        one above it. So the door is a link-shaped control inside Recovery's
        "Global trash" section, and this asserts the placement so a later run
        cannot quietly promote it into the nav without making that a decision.
        """
        block = _recovery_center_block()
        self.assertIn('data-nav-view="trash"', block,
                      "the Trash door must sit in Recovery's Global trash section")
        self.assertIn('@click="switchView(\'trash\')"', block)
        rail = HTML[HTML.index('<nav class="viewtabs"'):]
        rail = rail[:rail.index("</nav>")]
        self.assertNotIn('data-nav-view="trash"', rail,
                         "trash must not be promoted into the nav rail without the "
                         "rail-capacity decision being made explicitly")

    def test_the_door_is_a_button_with_a_type_and_a_text_label(self):
        """A door with no accessible name is a control, not a door."""
        block = _recovery_center_block()
        door = re.search(r'<button[^>]*data-nav-view="trash"[^>]*>(.*?)</button>', block, re.S)
        self.assertIsNotNone(door, "the trash door must be a <button>")
        attrs = door.group(0)
        self.assertIn('type="button"', attrs)
        label = re.sub(r"<[^>]+>", "", door.group(1)).strip()
        self.assertTrue(label, "the trash door must carry a text label")

    def test_the_door_has_a_way_back(self):
        """Entering a view must not be a one-way trip."""
        pane = _trash_pane_block()
        self.assertIn('data-nav-view="recovery"', pane)
        self.assertIn('@click="switchView(\'recovery\')"', pane)

    def test_the_trash_pane_names_its_view_instead_of_being_the_fallback(self):
        """Was `v-else`: the chain's unconditional last member.

        An unconditional fallback renders "Global trash" — a claim about a
        specific directory — for any view id no branch above it names. Naming
        the branch is what makes the view a view.
        """
        self.assertIn('<div v-else-if="view === \'trash\'" class="detail-inner">', HTML)
        pane = _trash_pane_block()
        self.assertNotIn("v-else-if=\"view === 'trash'\" class=\"detail-inner\">\n        <div v-else",
                         pane)


class TestTheSearchFieldStopsPromisingAnUnreachableView(unittest.TestCase):
    """The copy defect that made the missing door hard to spot.

    `SEARCH_VIEWS` is read by the guard, the search field's placeholder AND
    the `?` reference, so all three advertised Trash filtering — and the `?`
    dialog told the reader so in as many words — while nothing opened the
    view. That is why the string "trash" appeared all over the product and a
    grep for it looked like evidence the view existed.
    """

    def test_every_view_the_search_field_names_is_reachable(self):
        reachable = markup_reachable_views()
        orphans = [v for v in search_view_ids() if v not in reachable]
        self.assertEqual(orphans, [],
                         f"the search field advertises {orphans}, which no control opens")

    def test_the_trash_placeholder_and_its_label_exist_and_the_view_is_openable(self):
        self.assertIn('view === \'trash\' ? \'Search trash', HTML)
        self.assertIn("trash", search_view_ids())
        self.assertIn("trash", markup_reachable_views())


class TestThePaletteNoLongerHidesTheMissingDoor(unittest.TestCase):
    """Why this survived review, recorded as a check.

    `nav-recovery` carried the keyword `trash`, so typing "trash" in the
    palette did *something* — it opened Recovery. The string was present and
    the destination was not, which is what makes "grep says it's there" a
    useless signal for reachability.
    """

    def _row(self, row_id: str) -> str:
        match = re.search(r'\{ id: "%s".*?\},' % row_id, APP, re.S)
        self.assertIsNotNone(match, f"palette row {row_id} not found")
        return match.group(0)

    def test_the_recovery_row_no_longer_claims_the_trash_keyword(self):
        row = self._row("nav-recovery")
        keywords = re.search(r'keywords: "([^"]*)"', row).group(1).split()
        self.assertNotIn("trash", keywords,
                         "Recovery carrying 'trash' is what made the missing door "
                         "read as present")

    def test_there_is_a_palette_row_that_opens_the_trash_view(self):
        row = self._row("nav-trash")
        self.assertIn('args: ["trash"]', row)
        self.assertIn('category: "Navigation"', row)
        self.assertIn("focusDestination: true", row)

    def test_no_palette_row_opens_a_view_the_markup_does_not_render(self):
        """The mirror of the door invariant, on the other surface."""
        phantom = sorted(palette_reachable_views() - rendered_views())
        self.assertEqual(phantom, [],
                         f"palette rows navigate to views the markup never renders: {phantom}")


class TestTheDoorIsStyled(unittest.TestCase):
    """A control that exists but is invisible is still a missing door."""

    def test_the_door_and_its_group_have_rules(self):
        self.assertIn(".recovery-trash-door", CSS)
        self.assertIn(".recovery-section-tools", CSS)

    def test_the_section_label_row_group_is_not_spread_across_three_children(self):
        """`.section-label-row` is `justify-content: space-between`.

        A third child would have been distributed to a third of the row, so
        the door drifted away from the heading it belongs to. The right-hand
        side is one inline group instead — and the group has to be declared, or
        it is an inline element with two flex children doing nothing.
        """
        self.assertRegex(CSS, r"\.recovery-section-tools\s*\{[^}]*display:\s*inline-flex")

    def test_the_door_is_a_link_shaped_control_not_a_third_button(self):
        """It navigates; it does not act on the section it sits in."""
        block = _recovery_center_block()
        door = re.search(r'<button class="([^"]*recovery-trash-door[^"]*)"', block)
        self.assertIsNotNone(door)
        classes = door.group(1).split()
        self.assertFalse([c for c in classes if c.startswith("btn")],
                         "the door must not paint as a primary/secondary button")
        self.assertIn("text-button", classes)


if __name__ == "__main__":
    unittest.main()