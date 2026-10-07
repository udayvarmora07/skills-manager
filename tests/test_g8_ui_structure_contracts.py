"""Contracts for the docs/24 §G8 structural UI changes.

Three presentation changes, none of which may move an observation:

1. The Overview hero became a single status line, the attention queue is the
   first block, the duplicate "Observed state" panel was deleted, and the
   first-run guide moved *below* the queue.
2. The Library filter stack collapsed into one control bar, rows tightened to
   ~56px with an 11px type floor, and a value shared by every visible row is
   suppressed visually while staying in the accessibility tree.
3. Absolute filesystem paths moved behind disclosures with a Copy button, and
   the `Largest:` chip row was deleted from the context-budget card.

Every assertion here is about *presentation*. The observed-evidence contract
(`malformed` / `decode_error` / `addressable` reach the UI, no state is
inferred) and the single observed-state seam are asserted too, because the
cheapest way to make a list denser is to drop the signal it repeats.
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBUI = ROOT / "skillsmgr" / "webui"
APP_JS = WEBUI / "app.js"
INDEX_HTML = WEBUI / "index.html"
CSS = WEBUI / "styles.css"
DOMAIN_JS = WEBUI / "domain.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slice(markup: str, start_marker: str, end_marker: str) -> str:
    """Return the slice between two markers, failing loudly on a bad bound.

    A slice whose bounds cross silently is worse than no assertion: it passes
    every check on an empty string. Every use of this helper asserts a
    non-trivial length.
    """
    start = markup.index(start_marker)
    end = markup.index(end_marker, start)
    segment = markup[start:end]
    assert len(segment) > 200, f"slice {start_marker!r}..{end_marker!r} collapsed to {len(segment)} chars"
    return segment


class OverviewStructureTests(unittest.TestCase):
    def setUp(self):
        self.html = _read(INDEX_HTML)
        self.css = _read(CSS)
        self.source = _read(APP_JS)

    def test_hero_is_replaced_by_one_status_line(self):
        # The poster headline and its intro paragraph are gone; the h1 stays
        # because it is the programmatic focus target and the shell's
        # accessible name (asserted in test_webui_contracts).
        self.assertNotIn("class=\"overview-hero\"", self.html)
        self.assertNotIn("class=\"overview-intro\"", self.html)
        self.assertNotIn("Keep your local skills ready.", self.html)
        self.assertIn('class="overview-status"', self.html)
        self.assertIn('id="overview-title" tabindex="-1"', self.html)
        self.assertIn("class=\"overview-statusline\"", self.html)
        self.assertIn(".overview-status {", self.css)
        # One line: the counts, in the order the audit specified.
        for expression in (
            "formatNumber(overviewLogicalCount)",
            "formatNumber(overviewActiveCount)",
            "formatNumber(overviewAttentionCount)",
        ):
            self.assertIn(expression, self.html)

    def test_status_line_never_claims_an_empty_library_while_loading_or_failed(self):
        line = _slice(self.html, 'class="overview-statusline"', "</p>")
        # A pending scan and a failed scan must not read as "0 skills".
        self.assertIn('v-if="loadingList"', line)
        self.assertIn('v-else-if="banner"', line)
        self.assertIn("Reading the observed skill inventory", line)
        self.assertIn("Observed library unavailable", line)
        self.assertIn("<template v-else>", line)

    def test_attention_queue_is_the_first_block_below_the_status_line(self):
        shell = _slice(self.html, 'class="overview-shell"', 'class="detail-inner"')
        order = [
            shell.index('class="overview-status"'),
            shell.index('class="attention-queue"'),
            shell.index('class="overview-health"'),
            shell.index('class="overview-compact"'),
            shell.index('class="first-scan-guide"'),
        ]
        self.assertEqual(order, sorted(order), "Overview blocks are out of order")

    def test_first_run_guidance_sits_below_the_queue(self):
        shell = _slice(self.html, 'class="overview-shell"', 'class="detail-inner"')
        self.assertLess(
            shell.index('class="attention-queue"'), shell.index('class="first-scan-guide"')
        )
        # The empty state (which owns "Create your first skill") precedes the guide too.
        self.assertLess(
            shell.index('class="overview-empty"'), shell.index('class="first-scan-guide"')
        )
        self.assertIn("Create your first skill", self.html)

    def test_duplicate_observed_state_panel_is_deleted_but_its_counts_remain(self):
        self.assertNotIn('aria-labelledby="observed-title"', self.html)
        self.assertNotIn(">Observed state<", self.html)
        source = self.read_source()
        # Every count the deleted panel rendered is still computed and still shown.
        metrics = _slice(self.html, 'class="overview-metrics"', "</dl>")
        for label in ("Logical skills", "Active instances", "Observed copies",
                      "Malformed", "Unaddressable", "Recovery"):
            self.assertIn(f"<dt>{label}</dt>", metrics)
        for expression in ("overviewInstanceCount", "overviewMalformedCount",
                           "overviewUnaddressableCount", "overviewDivergentGroups"):
            self.assertIn(expression, source)
        # Divergent groups were already stated by the queue item, so they are
        # not repeated a third time.
        self.assertIn("unequal observed instances", self.source)

    def test_metrics_stay_a_definition_list(self):
        self.assertIn('<dl class="overview-metrics"', self.html)
        self.assertIn("<dt>", self.html)
        self.assertIn("<dd>", self.html)
        self.assertIn(".overview-metrics small { display: block;", self.css)

    def test_queue_and_load_error_contracts_are_unchanged(self):
        # Guards the v-if / v-else-if / v-else chain the reorder had to keep adjacent.
        self.assertIn('v-if="!loadingList && !banner && overviewInstanceCount === 0"', self.html)
        self.assertIn('v-else-if="!banner"', self.html)
        self.assertIn("No empty-state conclusion is being made", self.html)
        self.assertIn("Attention queue", self.html)
        self.assertIn("no validation or provenance status is inferred", self.html)

    @staticmethod
    def read_source() -> str:
        return _read(APP_JS)


class LibraryDensityTests(unittest.TestCase):
    def setUp(self):
        self.html = _read(INDEX_HTML)
        self.css = _read(CSS)
        self.source = _read(APP_JS)

    def test_filter_stack_is_one_control_bar(self):
        self.assertIn('class="library-bar"', self.html)
        bar = _slice(self.html, 'class="library-bar"', "<!-- The tag disclosure")
        for group in ('class="filters"', 'class="library-switch"'):
            self.assertIn(group, bar)
        # Each control keeps its group role, label, and pressed state.
        self.assertIn('class="filters" role="group" aria-label="Filter by state"', self.html)
        self.assertIn('class="library-switch" role="group" aria-label="Skill list mode"', self.html)
        self.assertIn('class="browse-switch" role="group" aria-label="Library presentation"', self.html)
        self.assertIn(":aria-pressed=\"libraryMode === 'library'\"", self.html)
        self.assertIn(":aria-pressed=\"browseMode === 'grid'\"", self.html)
        self.assertIn(".library-bar {", self.css)
        self.assertIn("min-height: 40px;", self.css)

    def test_narrow_panes_hide_the_whole_bar_as_one_control(self):
        narrow = _slice(self.css, "@media (max-width: 760px)", "@media (max-width: 420px)")
        self.assertIn(".sidebar.list-pane .library-bar { display: none; }", narrow)
        # The old rule hid four separate rows; one rule now hides the bar.
        self.assertNotIn(".sidebar.list-pane .filters,\n  .layout:not", narrow)

    def test_empty_tag_disclosure_is_not_rendered(self):
        self.assertIn("tagNames.length || tagFilter", self.html)

    def test_rows_target_56px_and_the_type_floor_is_11px(self):
        rule = re.search(
            r"\.skilllist > li:not\(\.batchbar\):not\(\.selection-hint\):not\(\.skeleton\):not\(\.empty\) \{(.*?)\}",
            self.css,
            re.S,
        )
        self.assertIsNotNone(rule)
        self.assertIn("min-height: 56px;", rule.group(1))

        # Every font-size the Library row rules declare, at or above 0.6875rem.
        rem_per_px = 16
        floor = 11 / rem_per_px
        row_selectors = (
            ".row-name", ".row-desc", ".identity-observation", ".identity-state",
            ".identity-label", ".row-badges .tag",
        )
        for selector in row_selectors:
            block = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
            self.assertIsNotNone(block, f"{selector} not found")
            for size in re.findall(r"font-size:\s*([0-9.]+)rem", block.group(1)):
                self.assertGreaterEqual(
                    float(size), floor - 1e-9,
                    f"{selector} renders at {float(size) * 16:g}px, below the 11px floor",
                )

    def test_row_badge_track_is_omitted_when_empty(self):
        self.assertIn('v-if="rowBadgeItems(s).length"', self.html)
        # Badges sit on their own track so they cannot collide with the identity line.
        self.assertIn(".row-badges { grid-column: 3; grid-row: 3;", self.css)
        self.assertIn("rowBadgeItems(s) {", self.source)


class UniformSuppressionTests(unittest.TestCase):
    """A value repeated on every row may lose its *visual*, never its name."""

    def setUp(self):
        self.html = _read(INDEX_HTML)
        self.source = _read(APP_JS)
        self.css = _read(CSS)

    def test_uniform_helpers_are_computed_not_methods(self):
        # As methods they are truthy function objects in a template, so the
        # `sr-only` binding fires unconditionally and hides every real state.
        computed = _slice(self.source, "computed: {", "\n  methods: {")
        for name in ("visibleIdentityItems()", "uniformIdentityLabel()", "uniformStateLabel()"):
            self.assertIn(name, computed, f"{name} is not a computed property")
        methods = _slice(self.source, "\n  methods: {", '}).mount("#app");')
        for name in ("visibleIdentityItems()", "uniformIdentityLabel()", "uniformStateLabel()"):
            self.assertNotIn(name, methods, f"{name} is duplicated as a method")

    def test_template_binds_suppression_to_sr_only_not_removal(self):
        summary = _slice(self.html, 'v-else class="identity-summary"', "</div>")
        self.assertIn("identityItems(s)", summary)
        self.assertIn("{ 'sr-only': uniformIdentityLabel }", summary)
        # This used to assert the literal "{ 'sr-only': uniformStateLabel }".
        # It now asserts the invariant instead, because the literal stopped
        # being the thing worth protecting: suppression must be a class that
        # leaves the text in the accessibility tree, never a `v-if` that removes
        # it, and it must cover every uniform case rather than one of them.
        # (Asserting the exact expression is the "assert the mechanism, not the
        # property" defect this repository has now shipped twice.)
        self.assertIn("'sr-only'", summary)
        self.assertIn("uniformStateLabel", summary)
        self.assertIn("uniformProblemLabel", summary)
        state_binding = _slice(summary, 'class="identity-state"', "</span>")
        self.assertIn("{ 'sr-only':", state_binding)
        self.assertNotIn('v-if="identity.stateLabel"', summary)
        # The seam still supplies the values; nothing is re-derived here.
        for expression in ("identity.label", "identity.stateLabel", "identity.problem"):
            self.assertIn(expression, summary)

    def test_a_uniform_problem_state_is_stated_once_not_on_every_row(self):
        # A badge that is true of 100% of rows is not per-row information: it
        # is a wall of colour that makes the rows which differ impossible to
        # see. The per-row chip is suppressed and promoted to the pane header.
        # This is deliberately independent of whether the underlying
        # observation is correct — a banner is actionable; 329 identical badges
        # are not.
        self.assertIn("uniformProblemLabel()", _slice(self.source, "computed: {", "\n  methods: {"))
        self.assertIn("uniformProblemCount()", _slice(self.source, "computed: {", "\n  methods: {"))
        self.assertIn('v-if="uniformProblemLabel" class="uniform-state-note"', self.html)
        self.assertIn("{{ uniformProblemLabel }}", self.html)
        # It must require *every* visible item to share one problem label —
        # a mixed list must keep its per-row badges, because that is exactly
        # the case where they discriminate.
        computed = _slice(self.source, "uniformProblemLabel() {", "\n    uniformProblemCount()")
        self.assertIn("items.every((item) => item.problem)", computed)
        self.assertIn("states.length === 1", computed)

    def test_a_row_with_no_visible_identity_takes_no_track(self):
        self.assertIn(
            ".skilllist > li:not(.batchbar) .identity-summary:not(:has(.identity-observation :not(.sr-only))) { display: none; }",
            self.css,
        )

    def test_grid_cards_keep_the_full_observation_stack(self):
        # §G9 calls the divergent-copy grid treatment excellent; suppressing a
        # value there would hide the very thing the card exists to show.
        card = _slice(self.html, 'v-if="browseMode === \'grid\'" class="card-meta"', "</div>")
        self.assertNotIn("sr-only", card)
        self.assertIn("identity.label", card)
        self.assertIn("identity.stateLabel", card)

    def test_uniform_state_is_suppressed_only_when_every_row_is_active(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
const domainSandbox = { window: {}, document: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), domainSandbox);
const sandbox = {
  window: { SkillManagerDomain: domainSandbox.window.SkillManagerDomain },
  Vue: { createApp(app) { sandbox.app = app; return { mount() {} }; }, nextTick() {} },
  localStorage: { getItem() { return null; }, setItem() {} },
  document: { addEventListener() {}, removeEventListener() {}, documentElement: { dataset: {} }, querySelectorAll() { return []; }, querySelector() { return null; } },
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const definition = sandbox.app;
const data = definition.data();
const identity = (label, state, problem) => ({ key: label + state, label, stateLabel: state, problem, count: 1 });
const run = (visibleSkills) => {
  // `identityItems` is a method, so the computed has to be exercised with it bound.
  const context = Object.assign(data, { libraryMode: 'library', visibleSkills,
    identityItems: definition.methods.identityItems });
  for (const key of ['visibleIdentityItems', 'uniformIdentityLabel', 'uniformStateLabel']) {
    Object.defineProperty(context, key, { get() { return definition.computed[key].call(context); }, configurable: true });
  }
  return { label: context.uniformIdentityLabel, state: context.uniformStateLabel };
};
console.log(JSON.stringify({
  allActive: run([
    { identities: [identity('Global', 'Active', false)] },
    { identities: [identity('Global', 'Active', false)] },
  ]),
  mixedStates: run([
    { identities: [identity('Global', 'Active', false)] },
    { identities: [identity('Agents', 'Disabled', true)] },
  ]),
  allProblemStates: run([
    { identities: [identity('Global', 'Active', false)] },
    { identities: [identity('Agents', 'Malformed', true)] },
  ]),
  empty: run([]),
  // One visible row is not "uniform": every value is trivially shared, and
  // hiding its only badge would remove evidence instead of repetition.
  singleRow: run([{ identities: [identity('Global', 'Active', false)] }]),
}));
"""
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, check=True, cwd=str(ROOT)
        )
        values = json.loads(result.stdout)
        # Every row Active -> the state is uniform and suppressible.
        self.assertEqual(values["allActive"], {"label": "Global", "state": "Active"})
        # One disabled row and the scope is no longer uniform: nothing is suppressed.
        self.assertEqual(values["mixedStates"], {"label": None, "state": None})
        self.assertEqual(values["allProblemStates"], {"label": None, "state": None})
        # An empty list suppresses nothing (there is no uniform value to name).
        self.assertEqual(values["empty"], {"label": None, "state": None})
        self.assertEqual(values["singleRow"], {"label": None, "state": None})


class PathDemotionTests(unittest.TestCase):
    def setUp(self):
        self.html = _read(INDEX_HTML)
        self.css = _read(CSS)
        self.source = _read(APP_JS)

    def test_instance_panel_leads_with_scope_and_state_not_a_path(self):
        choice = _slice(self.html, 'class="instance-choice"', "</button>")
        self.assertIn("scopeLabel", choice)
        self.assertIn("stateLabel", choice)
        self.assertNotIn("instance.path", choice)
        self.assertNotIn("physical_path", choice)

    def test_every_instance_path_is_still_reachable_and_copyable(self):
        disclosure = _slice(self.html, 'class="instance-path"', "</details>")
        self.assertIn("<summary>Path</summary>", disclosure)
        self.assertIn("instance.path || instance.physical_path", disclosure)
        self.assertIn('class="copybtn"', disclosure)
        self.assertIn('aria-label="\'Copy path for \' + instance.name"', disclosure)
        self.assertIn("copy(instance.path || instance.physical_path)", disclosure)

    def test_skill_details_disclosure_still_carries_the_selected_path_and_copy(self):
        block = _slice(self.html, '<dl class="meta" style="margin-top:8px;">', "</dl>")
        self.assertIn("<dt>Path</dt>", block)
        self.assertIn("selected.path", block)
        self.assertIn('class="copybtn"', block)
        self.assertIn(".copybtn", self.css)

    def test_quality_copies_put_the_path_behind_a_disclosure(self):
        row = _slice(self.html, 'class="quality-observations"', "</ul>")
        self.assertIn('class="quality-path"', row)
        self.assertIn("<summary>Path</summary>", row)
        self.assertIn("instance.path || instance.physical_path", row)
        self.assertIn(".quality-path", self.css)

    def test_largest_chip_row_is_deleted_from_the_context_budget_card(self):
        self.assertNotIn('class="budgetbar-largest"', self.html)
        self.assertNotIn("Largest:", self.html)
        self.assertNotIn(".budgetbar-largest", self.css)
        # The same evidence is still available in Quality, under its own heading.
        self.assertIn("Largest context observations", self.html)
        # Nothing reads the removed field any more.
        self.assertNotIn("budget.largest", self.html)


class EvidenceContractTests(unittest.TestCase):
    """The seam and the honesty rules must survive a presentation-only change."""

    def test_observed_state_still_has_exactly_one_source(self):
        html = _read(INDEX_HTML)
        self.assertIn("identityItems(item)", _read(APP_JS))
        self.assertIn("Observed identity and state", html)
        self.assertIn("identity-state-warn", _read(CSS))
        # No template-local re-derivation of malformed / addressable / disabled.
        self.assertNotIn("s.states && s.states.includes('malformed')", html)

    def test_no_combined_score_or_inferred_state_was_introduced(self):
        for path in (INDEX_HTML, APP_JS):
            text = _read(path)
            self.assertNotIn("qualityScore", text)
            self.assertNotIn("trustVerdict", text)
            self.assertNotIn("effectiveState =", text)

    def test_no_inline_script_and_csp_directives_untouched(self):
        html = _read(INDEX_HTML)
        self.assertNotIn("<script>", html)
        self.assertNotIn("onclick=", html)
        self.assertIn("preferences.js", html)

    def test_reduced_motion_still_respected(self):
        css = _read(CSS)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("animation-iteration-count: 1 !important;", css)

    def test_keyboard_and_a11y_contracts_intact(self):
        html = _read(INDEX_HTML)
        source = _read(APP_JS)
        self.assertIn('class="skip-link" href="#main-workspace"', html)
        self.assertIn('id="view-title" tabindex="-1"', html)
        self.assertIn('role="status" aria-live="polite"', html)
        # The command palette combobox contract.
        self.assertIn("aria-activedescendant", html)
        self.assertIn('data-modal="commands"', html)
        # Escape still closes exactly the active modal.
        self.assertIn("activeModal", source)
        self.assertIn("async function api(", _read(DOMAIN_JS), "transport seam moved")
        # No transport re-implemented: app.js routes every read through the seam.
        app = _read(APP_JS)
        self.assertNotIn("window.fetch(", app)
        self.assertNotIn("fetch(url", app)


if __name__ == "__main__":
    unittest.main()
