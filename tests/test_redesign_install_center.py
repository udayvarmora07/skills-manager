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


def _install_halves():
    """The view's workflows, split where the markup splits them.

    5.1b's whole point is that "does this page write to disk?" has two answers,
    so the contract has to ask about one half at a time. **5.2 added a third**,
    and this is exactly the helper's failure mode: it took the FIRST
    `<template v-else>` after the registry half and returned everything from
    there to the end of the block, so the fetch stepper silently joined the
    installer half and the runner-half count assertions saw both.

    **The halves are keyed on their MODE, not on the directive that opens
    them.** They were `v-if` / `v-else` / `v-else`, and with three branches
    Vue's compiler **silently dropped the middle one** — `mode === "runner"`
    rendered the FETCH half, with no error and no console message. They are
    three independent `v-if`s now, and this helper matches on
    `install.mode === '…'` so it keeps working whichever directive a future
    edit chooses, and fails loudly if a fourth workflow appears without a
    case here.
    """
    # HTML COMMENTS ARE STRIPPED FIRST. 5.2's own comment quotes
    # `@click="runInstall(` and `#install-source` while explaining why the
    # halves are three `v-if`s — so a region finder that reads comments
    # "finds" the runner half's controls inside the registry half and every
    # per-half assertion inverts. This is 4.7d's lesson, the fifth recorded
    # instance: a prose comment quoting an example is indistinguishable from
    # the example until the comments are gone.
    block = _install_block()
    block = re.sub(r"<!--.*?-->", "", block, flags=re.S)
    at = [block.index(f"""<template v-if="install.mode === '{m}'">""")
          for m in ("registry", "runner", "fetch")]
    if len(re.findall(r"""<template v-if="install\.mode === '""", block)) != 3:
        raise AssertionError("a fourth workflow appeared; classify it here first")
    # Slice between the anchors' own indices rather than searching for an
    # indentation prefix: the halves are separated by HTML comments, and a
    # prefix search runs straight past a comment to the next template.
    return tuple(block[at[i]:at[i + 1]] for i in range(2)) + (block[at[2]:],)


def _method_body(name):
    """As `_computed_body`, for a `methods:` entry — same reason, same trap."""
    match = re.search(r"\n    " + re.escape(name) + r"\(", APP)
    assert match, "no top-level method named " + name
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

    def test_nothing_on_the_registry_half_sends_an_install(self):
        """The page's promise is in its first sentence, so the test now asks
        the question 5.1b actually posed: WHICH half. The registry half still
        cannot write — the runner may, and the sentence under the heading says
        so when it does. Asserted per half rather than per page, because "the
        page does not write" and "the page's registry half does not write" are
        different claims and only one of them is still true."""
        registry, installer, fetch_half = _install_halves()
        for forbidden in ("commitRegistryReview", "prepareSnapshotReview", "doInstall", "runInstall"):
            self.assertNotIn("@click=\"" + forbidden, registry)
        self.assertIn('@click="runInstall(', installer)
        # 5.2: the fetch half is the ONE half that may commit, and the test has
        # to say which — otherwise "the registry half does not write" stays
        # true forever while a third half writes with no owner asserting it.
        self.assertIn('@click="commitRegistryReview"', fetch_half)
        self.assertNotIn('@click="runInstall(', fetch_half)
        # The no-write sentence must not be a literal in the markup any more:
        # it is now chosen by mode, and a literal would be a claim the reader
        # could read on the half that DOES write.
        self.assertNotIn("Nothing on this page writes to disk", HTML)

    def test_the_write_claim_is_chosen_by_mode_not_asserted_once(self):
        """Both halves of the sentence, from the getter itself — a test that
        only grepped the stylesheet would pass while the template rendered a
        stale literal, which is the defect 5.1a shipped once already."""
        getter = _computed_body("installScopeNote")
        self.assertIn('this.install.mode === "runner"', getter)
        self.assertIn("writes into the agent scope roots", getter)
        self.assertIn("Nothing on this page writes to disk", getter)


class InstallerWorkflowContracts(unittest.TestCase):
    """5.1b — the installer half of the Install view.

    The form used to live only in the `install` dialog, behind a "Workflow"
    select whose default was `runner` — so the surface the rail button named
    offered no installer at all, and the dialog was the second, older copy of
    the three registry controls the view already owned.
    """

    def test_the_workflow_choice_is_two_pressed_buttons_and_not_a_source_tab(self):
        block = _install_block()
        self.assertIn('class="install-workflow"', block)
        self.assertIn('v-for="w in installWorkflows"', block)
        self.assertIn(":aria-pressed=", block)
        # It must not join the source tablist: a strip that put `npx` beside
        # `Search` claims four equivalent ways to get a skill, and they are not.
        self.assertNotIn('data-install-tab="w.id"', block)
        self.assertIn("installWorkflows()", APP)
        self.assertIn('{ id: "registry", label: "Registry" }', APP)
        self.assertIn('{ id: "runner", label: "Installer" }', APP)

    def test_the_registry_source_strip_still_owns_exactly_the_three_reads(self):
        """Control for the row above: the mode toggle must not have replaced
        the strip, only sat above it."""
        sources = _computed_body("installSources")
        for op in ("curated", "browse", "search"):
            self.assertIn(f'{{ id: "{op}"', sources)
        self.assertNotIn('"runner"', sources)

    def test_there_is_exactly_one_install_branch_and_one_door(self):
        """5.2b. Two defects, one root: **a second `v-else-if="view ===
        'install'"` that never rendered.**

        Vue honours the first matching branch of a chain and ignores the rest,
        so the block 5.1a added ("Install / update inbox": the registry form,
        the review evidence table, the inventory, and an "Open full install
        workflow" button) was dead markup the day it was written — the branch
        above it, 5.1's `.install-shell`, matches first. Three source-level
        contract tests stayed green throughout, because the strings were in the
        file. This asserts the invariant that would have caught it, and which
        the delete is what makes true.
        """
        self.assertEqual(HTML.count("""<div v-else-if="view === 'install'" """.strip()), 2,
                         "expected only the sidepanel and the install shell")
        self.assertNotIn('data-modal="install"', HTML)
        self.assertNotIn("install-center", HTML)
        # The inventory was the one part of the dead block that was not a
        # duplicate of anything, so it moved into the branch that renders.
        shell = _install_block()
        self.assertIn("data-install-inventory", shell)
        self.assertIn("filteredRegistryInventory", shell)

    def test_the_live_view_owns_the_operation_selector_the_dialog_had(self):
        """The deleted second block carried a `<select>` bound to
        `install.registryOp`; the live view chooses the operation with the
        source tab strip instead. Assert the control that survives IS the one
        the reader uses — a test that only checked the deleted id would have
        passed while the page offered no operation control at all."""
        view = _install_block()
        for binding in ('v-model.trim="install.source"', 'v-model="install.view"',
                        'v-model="install.allowStale"', 'v-model="install.runner"'):
            self.assertIn(binding, view, f"{binding} is not in the Install view")
        self.assertIn("install.registryOp === s.id", view)  # the tab strip
        self.assertIn("selectInstallSource(s.id)", view)
        # And the runner half still has exactly one owner.
        self.assertEqual(HTML.count('id="install-runner"'), 1)

    def test_the_one_door_is_the_view_not_a_modal(self):
        """`openInstall` is still the name three call sites use (the Overview
        action row, the palette entry, the actions map). It must navigate.
        Opening a modal that no longer exists would set `modals.install`,
        which `activeModal` reads — so the assertion is on what it does, and
        on the state key being gone, not on the comment."""
        self.assertIn("openInstallCenter()", APP)
        self.assertNotIn("this.modals.install = true", APP)
        # `modals` has no `install` key left for `activeModal` to find.
        modals = APP[APP.index("modals: {"):APP.index("modals: {") + 2400]
        self.assertNotIn("\n        install:", modals)

    def test_the_agents_field_parses_in_one_place_and_both_sites_use_it(self):
        """The comma split was an inline `@change` expression. It is a method
        now, so a second form cannot ship a different parser."""
        self.assertIn("syncInstallAgents()", APP)
        self.assertNotIn("split(',').map(s=>s.trim())", HTML)
        self.assertEqual(HTML.count("@change=\"syncInstallAgents\""), 1)

    def test_the_command_shown_is_the_command_that_runs(self):
        """4.7's rule: one sentence must not name one thing while the request
        sends another. The shown command, the copied command, the previewed
        command and the executed command are one expression — asserted as four
        call SITES, because counting four invocations inside the half was
        counting the wrong thing (the two buttons call `runInstall`, which
        reads the same getter)."""
        _, installer, _ = _install_halves()
        self.assertEqual(installer.count("installPreview()"), 2)  # displayed, copied
        self.assertEqual(installer.count('@click="runInstall('), 2)  # preview, run
        # And it is the SAME expression that assembles the command.
        preview = _method_body("installPreview")
        self.assertIn('this.install.mode === "registry"', preview)
        self.assertIn("npx skills add", preview)

    def test_the_primary_button_does_not_say_run_during_a_dry_run(self):
        """`-l` makes the press a listing and nothing else. The label said
        "Run" with the dry-run box already ticked, which is the one claim on
        this view that could overstate what a press would do."""
        self.assertIn("this.install.listOnly", _computed_body("installRunnerActionLabel"))
        self.assertIn("{{ installRunnerActionLabel }}", _install_halves()[1])

    def test_a_runner_result_is_told_apart_from_a_listing_by_its_exit_code(self):
        """Both halves write `install.lastResult`. Deriving "which half is
        this" from whichever one asked last would put a listing under
        "Exit 0", and an install route response has an `exit_code` a listing
        never carries."""
        getter = _computed_body("installRunnerResult")
        self.assertIn('typeof result.exit_code === "number"', getter)
        # 5.2b: the `!installRunnerResult` guard lived in the deleted dialog's
        # result dump. The separation it enforced is now structural -- the
        # listing renders from `installRows` and the runner's exit line from
        # `installRunnerOutcome`, and no branch renders both.
        view = _install_block()
        self.assertIn("installRows", view)
        self.assertIn("installRunnerOutcome", view)
        self.assertNotIn("lastResult", view)

    def test_the_outcome_names_the_exit_code_and_never_interprets_it(self):
        outcome = _computed_body("installRunnerOutcome")
        self.assertIn("Exit ${result.exit_code}", outcome)
        self.assertIn("result.exit_code === 0", outcome)

    def test_arriving_with_fetch_selected_leaves_no_tablist_without_a_selection(self):
        """`fetch` is not one of the three READ sources the strip owns, and the
        dialog still sets it. A tablist where no tab is selected is an ARIA
        failure, so both the toggle and `switchView` restore a source."""
        select = _method_body("selectInstallWorkflow")
        self.assertIn("installSources.some", select)
        view = APP[APP.index("switchView(v) {"):]
        view = view[:view.index("\n    },")]
        self.assertIn("installSources.some", view)

    def test_the_install_default_workflow_is_the_one_that_cannot_write(self):
        """`install.mode` defaulted to `runner`, which 5.1a's view ignored and
        the dialog's select showed first. It is `registry` now: the first paint
        of a destination that can install software should be the half that
        cannot."""
        line = APP[APP.index("install: {"):APP.index("\n") if False else APP.index("install: {") + 200]
        self.assertIn('mode: "registry"', line.split("},")[0])


if __name__ == "__main__":
    unittest.main()