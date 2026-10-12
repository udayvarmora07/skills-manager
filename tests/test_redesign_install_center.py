"""Contracts for the 5.1 Install center.

The nav destination `install` rendered NOTHING before this task: the rail had
an Install button, the topbar rendered a search field promising "Search
registry sources…", and every piece of behaviour (`install.registryOp`,
`runRegistry`, `install.lastResult`) already existed behind a dialog. These
assertions are about the VIEW and about the two claims it is allowed to make.

Each one is written to be able to fail. Where a test could be satisfied by
deleting the thing it checks, a control is asserted alongside it — see
`test_every_row_state_says_only_what_was_observed`.
"""

import re
import unittest
from pathlib import Path

WEBUI = Path(__file__).resolve().parents[1] / "skillsmgr" / "webui"
APP_JS = WEBUI / "app.js"
INDEX_HTML = WEBUI / "index.html"
STYLES_CSS = WEBUI / "styles.css"

APP = APP_JS.read_text(encoding="utf-8")
HTML = INDEX_HTML.read_text(encoding="utf-8")
CSS = STYLES_CSS.read_text(encoding="utf-8")


def _computed_body(name):
    """Return the source text of ONE computed/method getter.

    Scoped by name and brace-balanced rather than by slicing between markers:
    a marker slice returns the same text whether or not the getter is inside
    the options object at all, which is the defect class this repo has now hit
    seven times (2.1's four getters outside `computed: {}` passed their own
    placement test).
    """
    match = re.search(r"\n    " + re.escape(name) + r"\(", APP)
    assert match, "no top-level getter named " + name
    start = match.start()
    depth = 0
    for index in range(start, len(APP)):
        if APP[index] == "{":
            depth += 1
        elif APP[index] == "}":
            depth -= 1
            if depth == 0:
                return APP[start:index + 1]
    raise AssertionError("unbalanced braces for " + name)


def _install_block():
    start = HTML.index('<div v-else-if="view === \'install\'" class="install-shell"')
    end = HTML.index('<div v-else-if="view === \'skills\'" class="detail-inner">', start)
    return HTML[start:end]


class InstallViewContracts(unittest.TestCase):
    def test_the_install_navigation_target_renders_a_view(self):
        """The defect: a rail button that switched to a destination with no
        markup behind it. Asserted on the markup, not on the nav button — the
        button existed and was correct, and that is why nothing noticed."""
        self.assertIn('v-else-if="view === \'install\'" class="install-shell"', HTML)
        block = _install_block()
        self.assertIn('aria-labelledby="install-view-title"', block)
        self.assertIn('id="install-view-title"', block)

    def test_the_three_sources_are_exactly_the_ones_the_route_reads(self):
        """POST /api/install carries browse / curated / search / fetch.

        `fetch` is NOT a read — it creates a review and writes state — and
        5.2 owns the stepper it belongs to, so offering it on a page whose
        whole copy is "nothing here writes to disk" would make the page a
        liar. This assertion can fail by deletion.
        """
        ids = set(re.findall(r'\{ id: "(\w+)", label:', _computed_body("installSources")))
        self.assertEqual(ids, {"browse", "curated", "search"})

    def test_a_search_is_not_fired_below_the_routes_own_minimum(self):
        """registry.py:773 rejects a search query under 2 characters.

        The contract is stated in terms of the BACKEND's threshold, so if the
        route's bound moves the assertion fails rather than continuing to
        bless a control that fires a request certain to be rejected.
        """
        body = _computed_body("installCanRead")
        self.assertIn("installQueryLength >= 2", body)
        markup = _install_block()
        self.assertIn(':disabled="!installCanRead"', markup)
        # And the control is never disabled when the precondition IS met.
        self.assertNotIn(':disabled="true"', markup)

    def test_the_unmet_precondition_is_stated_rather_than_hidden(self):
        self.assertIn("installMissingReason", _install_block())
        self.assertIn("registry search rejects a query shorter than", _computed_body("installMissingReason"))

    def test_the_stale_banner_is_gated_on_the_backend_boolean(self):
        """`cache_state` has four values (registry.py:75) and only `stale`
        means the answer did not come from the registry. Deriving the banner
        from the string would let an unrecognised state read as fresh."""
        self.assertIn("meta.stale === true", _computed_body("installShowingStaleCache"))
        self.assertIn('v-if="installShowingStaleCache"', _install_block())
        self.assertIn("install-cache-banner", _install_block())

    def test_a_failed_read_states_the_registrys_own_message_and_does_not_summarise_it(self):
        """RULES #12: the UI states observed facts. A failed registry read is
        the whole content of this page, so the message must persist in the
        pane — the toast is gone in four seconds."""
        self.assertIn("install.error = e && e.message", APP)
        block = _install_block()
        self.assertIn("{{ install.error }}", block)
        self.assertIn("No conclusion is drawn from a read that failed.", block)

    def test_an_empty_answer_is_not_reported_as_a_failure(self):
        """`installRows.length === 0 && installMeta` — the empty branch needs a
        settled read behind it. Without `&& installMeta` the page would call
        "no rows" for a request it never made."""
        self.assertIn("installRows.length === 0 && installMeta", _install_block())

    def test_switching_source_retires_the_previous_answer(self):
        """A result from Curated left up while the reader reads Browse is the
        'stale sentence beside a correct bar' pair 3.3 shipped."""
        body = _computed_body("selectInstallSource")
        self.assertIn("this.install.lastResult = null", body)
        self.assertIn("this.install.error = null", body)
        self.assertIn("@click=\"selectInstallSource(s.id)\"", _install_block())

    def test_the_arrow_keys_move_selection_and_focus_together(self):
        """Roving tabindex only composes if the DOM focus follows the arrow."""
        body = _computed_body("onInstallTabKey")
        for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
            self.assertIn(key, body)
        self.assertIn("event.preventDefault()", body)
        self.assertIn(".focus()", body)
        # Only those four keys are consumed: a strip that swallowed Escape or
        # `/` would take a shortcut away from its owner.
        self.assertEqual(body.count("event.key ==="), 4)

    def test_rows_are_normalised_once_rather_than_by_optional_chains_in_the_markup(self):
        """`browse`/`curated` validate only that the response carries a list
        under `data` (registry.py:488), so every field INSIDE a row is the
        registry's. The template indexes normalised keys, never raw ones."""
        body = _computed_body("installRows")
        for field in ("key:", "name:", "source:", "installs:"):
            self.assertIn(field, body)
        block = _install_block()
        self.assertNotIn("row.registry_provenance", block)
        self.assertNotIn('row["id"]', block)
        # A row with neither a source nor a count says so, rather than
        # rendering an empty description line.
        self.assertIn("without a source or an install count", block)

    def test_every_row_state_says_only_what_was_observed(self):
        """The control: the trailing mark cannot claim a skill was installed,
        reviewed or fetched. 'Listed' is the strongest true word available on
        a page that has performed no write."""
        block = _install_block()
        self.assertIn(">Listed<", block)
        for forbidden in ("Installed", "Fetched", "Reviewed", "Updated"):
            self.assertNotIn(">" + forbidden + "<", block)

    def test_the_view_has_a_width_and_no_stray_shadow(self):
        """A full-width list under `.detail` reads as an unconstrained
        paragraph; and a registry catalogue is a readout, not a card."""
        self.assertIn(".install-shell {", CSS)
        block = CSS[CSS.index(".install-shell {"):CSS.index("/* -------------------------------------------------------------- statusbar */")]
        self.assertIn("max-width:", block)
        self.assertNotIn("box-shadow:", block)

    def test_nothing_on_the_view_sends_an_install(self):
        """The page's promise is in its first sentence. A control that broke it
        would make every other sentence on the page false."""
        block = _install_block()
        self.assertIn("Nothing on this page writes to disk", block)
        for forbidden in ("commitRegistryReview", "prepareSnapshotReview", "doInstall"):
            self.assertNotIn("@click=\"" + forbidden, block)
            self.assertNotIn('"fetch"', block.replace("Search", ""))


if __name__ == "__main__":
    unittest.main()