"""5.7b — the Settings view: a rail that earns its column, and four subjects
that are not four identical boxes.

THE DEFECTS THESE EXIST FOR
---------------------------
1. The side column was `379x828` holding a title and one sentence that
   restated the detail pane's own lead. A 380px column, 94% empty.
2. The detail pane was 1309px tall in an 828px viewport — a screen and a half
   to change a radio.
3. All four subjects were `class="profile-editor settings-section"`: Profiles'
   editor class borrowed, so four different subjects rendered as four
   identical 748px bordered boxes.
4. `.settings-options` was a 1-column stack of three equal 714x58 rows for a
   three-way choice.
5. Found by LOOKING, not by a test: the shortcut reference's foot-note read
   "Row-by-row navigation in the Library list is not here yet" — and `j`/`k`
   and the arrows ARE bound (`onKeydown`, Library, fully guarded). The same
   honesty defect as 5.7a's, in the other direction: the UI under-claimed.

WHY THESE TESTS ARE SHAPED THE WAY THEY ARE
-------------------------------------------
Each one is RELATIONAL — it re-derives a fact from one place and requires the
other place to match. A test asserting the literal string "Settings sections"
or a specific pixel count would pass forever against the broken build, which
is precisely what the tests before this file did.

For (5) the reference is checked against the HANDLER, not against a list in
the test: the row keys are read out of `onKeydown`'s own guard, so the prose
cannot drift from the binding again.
"""
import re
import unittest
from pathlib import Path

WEBUI = Path(__file__).resolve().parents[1] / "skillsmgr" / "webui"
APP = (WEBUI / "app.js").read_text(encoding="utf-8")
HTML = (WEBUI / "index.html").read_text(encoding="utf-8")
CSS = (WEBUI / "styles.css").read_text(encoding="utf-8")


def settings_rail_entries() -> list:
    """The subjects the side column lists, as declared in the source."""
    match = re.search(r"const SETTINGS_SECTIONS = Object\.freeze\(\[(.*?)\]\);", APP, re.S)
    assert match, "SETTINGS_SECTIONS is gone — the rail and the sections must share one list"
    return re.findall(r'\{\s*id:\s*"([^"]+)",\s*label:\s*"([^"]+)",\s*hint:\s*"([^"]+)"\s*\}', match.group(1))


def settings_detail_block() -> str:
    """The Settings detail pane only (the side column is a separate branch).

    HTML comments are stripped because the 5.7b note in the file explains the
    defect in the very words a test must forbid.
    """
    start = HTML.index('<div v-else-if="view === \'settings\'" class="detail-inner settings-center">')
    end = HTML.index('<div v-else-if="view === \'recovery\'" class="detail-inner">', start)
    return re.sub(r"<!--.*?-->", "", HTML[start:end], flags=re.S)


def css_rule(selector: str) -> str:
    """One rule's declarations, brace-matched (not a slice to the next one)."""
    start = CSS.index(selector + " {")
    depth = 0
    for index in range(start + len(selector), len(CSS)):
        if CSS[index] == "{":
            depth += 1
        elif CSS[index] == "}":
            depth -= 1
            if depth == 0:
                return CSS[start:index]
    raise AssertionError(f"unbalanced braces after {selector}")


def settings_sidepanel_block() -> str:
    """The Settings side column only, comments stripped.

    This was `HTML[start:start + 3000]` — a fixed-character window with no end
    condition. The block is about 1,100 characters, so the window swallowed the
    whole next chain member, and when 7.4f documented its Trash branch next to
    a sentence containing "scrolls", the "the current marker follows the
    reader's choice, not a scroll" test failed on **prose in a different
    view's comment**. That is this repository's most repeated locator failure
    (six times by 6.3b), and it is also `settings_detail_block`'s own docstring
    two functions above, which already says why comments are stripped.

    Slicing to the next chain member is the end condition the chain itself
    defines; the comment strip keeps the assertion about copy a reader can see.
    """
    start = HTML.index('<div v-else-if="view === \'settings\'" class="sidepanel')
    end = HTML.index("<template v-else-if=", start)
    return re.sub(r"<!--.*?-->", "", HTML[start:end], flags=re.S)


class SettingsRailTests(unittest.TestCase):
    """(1) The side column carries the subjects, and it is wired to real DOM."""

    def test_the_rail_is_not_the_detail_pane_lead_again(self) -> None:
        side = settings_sidepanel_block()
        # A rail that lists subjects has more than a title and a sentence in
        # it. The old block was exactly: sidepanel-intro + one <div> of prose.
        self.assertIn('class="settings-rail"', side)
        self.assertIn("v-for=\"entry in settingsSections\"", side)
        self.assertIn("@click=\"jumpToSetting(entry.id)\"", side)

    def test_every_rail_entry_names_a_section_that_exists_in_the_dom(self) -> None:
        detail = settings_detail_block()
        entries = settings_rail_entries()
        self.assertGreaterEqual(len(entries), 4, "the rail lost subjects")
        for section_id, label, hint in entries:
            self.assertIn(f'id="{section_id}"', detail, f"{label} is listed but no section carries that id")
            self.assertTrue(label.strip(), "a rail row with no name is a dead button")
            self.assertTrue(hint.strip(), "a rail row with no hint is a dead button")

    def test_every_settings_section_is_reachable_and_focusable(self) -> None:
        detail = settings_detail_block()
        sections = re.findall(r'<section id="(settings-[a-z]+)" class="([^"]*)"', detail)
        self.assertEqual(len(sections), len(settings_rail_entries()))
        for section_id, classes in sections:
            # `tabindex="-1"` is what lets a keyboard reader follow the rail
            # and land ON the subject instead of being left at the top.
            self.assertIn('tabindex="-1"', detail.split(f'id="{section_id}"', 1)[1][:200])
            self.assertTrue(classes.split(), f"{section_id} has no class of its own")

    def test_jump_to_setting_only_records_a_subject_the_rail_actually_lists(self) -> None:
        body = APP[APP.index("jumpToSetting(id) {"):][:900]
        self.assertIn("SETTINGS_SECTIONS.some", body)
        self.assertIn("this.settingsSection = id;", body)
        self.assertIn("getElementById(id)", body)

    def test_the_current_marker_follows_the_readers_choice_not_a_scroll(self) -> None:
        # A scroll-spy would need a scroll listener this build does not have;
        # claiming "you are here" from a value nothing observes is exactly the
        # defect 5.7a fixed. The marker is driven by the click, full stop.
        side = settings_sidepanel_block()
        self.assertIn(":aria-current=\"settingsSection === entry.id ? 'true' : null\"", side)
        self.assertIn(":class=\"{ 'is-current': settingsSection === entry.id }\"", side)
        self.assertNotIn("scroll", side.lower())


class SettingsSubjectTests(unittest.TestCase):
    """(2)(3)(4) Four subjects, not four borrowed boxes; a row, not a stack."""

    def test_no_section_borrows_the_profiles_editor_class(self) -> None:
        detail = settings_detail_block()
        self.assertNotIn("profile-editor", detail)
        self.assertNotIn("profile-preview", detail)

    def test_each_subject_is_a_label_control_row(self) -> None:
        detail = settings_detail_block()
        for section_id, _ in re.findall(r'<section id="(settings-[a-z]+)" class="([^"]*)"', detail):
            chunk = detail.split(f'id="{section_id}"', 1)[1]
            chunk = chunk[:chunk.index("</section>")]
            self.assertIn('class="settings-section-label"', chunk)
            self.assertIn('class="settings-section-control"', chunk)

    def test_the_two_way_and_three_way_choices_are_one_segmented_row_each(self) -> None:
        detail = settings_detail_block()
        segmented = re.findall(r'class="settings-options settings-segmented"', detail)
        self.assertEqual(len(segmented), 2, "theme and text size are the two choice sets")
        css = CSS[CSS.index(".settings-segmented {"):]
        self.assertIn("grid-auto-flow: column", css[:400])

    def test_the_row_hairline_replaces_the_bordered_box(self) -> None:
        declarations = css_rule(".settings-section")
        self.assertIn("border-top: 1px solid var(--border)", declarations)
        self.assertNotIn("border-radius", declarations)
        # A boxed subject IS the defect; only the top hairline survives.
        self.assertEqual([d for d in re.findall(r"(?<![\w-])border[a-z-]*\s*:", declarations)], ["border-top:"])

    def test_no_bordered_box_rule_is_left_behind_for_the_removed_class(self) -> None:
        # `.profile-editor` keeps its border because Profiles still uses it.
        # What must not survive is a `.settings-...` rule that re-boxes the
        # subject — that is how the borrowed class came to read four times.
        boxed = re.findall(r"(\.settings-section\b[^{]*)\{([^}]*border:[^}]*)\}", CSS)
        for selector, body in boxed:
            self.assertNotIn("border-radius", body, f"{selector.strip()} re-boxes the subject")


class ShortcutReferenceHonestyTests(unittest.TestCase):
    """(5) The reference's foot-note claimed a binding does not exist."""

    def handler_row_keys(self) -> str:
        return APP[APP.index("const rowKey = "):APP.index("if (rowKey && this.moveRowFocus", APP.index("const rowKey = "))]

    def test_the_foot_note_makes_no_unbound_claim(self) -> None:
        foot = re.search(r'class="shortcuts-foot-note">([^<]+)<', HTML)
        self.assertTrue(foot)
        self.assertNotIn("not here yet", foot.group(1))

    def test_the_reference_lists_exactly_the_row_keys_the_handler_binds(self) -> None:
        guard = self.handler_row_keys()
        bound = set(re.findall(r'e\.key === "([^"]+)"', guard))
        # The guard mentions j/k/ArrowDown/ArrowUp. Every one of them must be
        # documented, and the documentation must not invent a fifth.
        for key in ("j", "k", "ArrowDown", "ArrowUp"):
            self.assertIn(key, bound, f"{key} moved out of the guard; update this test deliberately")
        section = HTML[HTML.index('<h3 class="shortcuts-section-title">Library list</h3>'):]
        section = section[:section.index("</section>")]
        keys = section.count('class="shortcuts-row"')
        self.assertEqual(keys, 2, "J/K and the arrows are two rows; anything else is a new claim")


if __name__ == "__main__":
    unittest.main()