"""Frontend state contracts for the local Web UI.

Stdlib unittest only, no browser: each check reads the checked-in
``skillsmgr/webui`` sources and pins a behaviour that was fixed.  A Vue
template or handler regression is invisible to the REST tests, so these
assertions are the guard for the UI-side findings (BUG-3..BUG-7).
"""

from __future__ import annotations

import re
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "skillsmgr" / "webui" / "app.js"
INDEX_HTML = ROOT / "skillsmgr" / "webui" / "index.html"
DOMAIN_JS = ROOT / "skillsmgr" / "webui" / "domain.js"
PREFERENCES_JS = ROOT / "skillsmgr" / "webui" / "preferences.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FrontendSourceContractTests(unittest.TestCase):
    def test_overview_is_default_and_keeps_library_navigation(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn('view: "overview"', source)
        self.assertIn("@click=\"switchView('overview')\"", html)
        self.assertIn(">Library</button>", html)
        self.assertIn(">Recovery</button>", html)
        self.assertNotIn("Trash / Recovery", html)
        self.assertIn(':data-overview-ready="!loadingList && !loadingHistory ? \'true\' : null"', html)
        self.assertIn("loadingList: true", source)
        self.assertIn("loadingHistory: true", source)

    def test_overview_uses_existing_history_and_observed_state_only(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn('this.overviewHistory = await api("/api/history?limit=8")', source)
        for expression in ("overviewDivergentGroups", "overviewMalformedCount", "overviewUnaddressableCount", "overviewInvalidRecords", "overviewDisabledCount"):
            self.assertIn(expression, source)
        self.assertIn("malformed or unaddressable", source)
        self.assertIn("no validation or provenance status is inferred", html)
        self.assertIn("Attention queue", html)

    def test_overview_metrics_exclude_invalid_observations_and_search_leaves_focus(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn("overviewInvalidRecords.length", source)
        self.assertIn('!record.malformed', source)
        self.assertIn('record.addressable !== false', source)
        self.assertIn('if (value.trim() && !["skills", "trash", "install", "recovery", "quality"].includes(this.view))', source)
        self.assertIn('this.view = "skills";', source)
        self.assertIn('enabled, parsed, addressable', html)

    def test_quality_center_has_bounded_evidence_sections_and_existing_actions(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn(">Quality</button>", html)
        self.assertLess(html.index(">Quality</button>"), html.index(">Settings</button>"))
        self.assertIn("Search quality evidence", html)
        for label in ("Specification and observed validity", "Physical copies and state", "Provenance", "Content and context estimate", "Signals not observed"):
            self.assertIn(label, html)
        for phrase in ("no combined score", "No risk scan", "No eval result", "No precedence-resolved consumer load", "Validity flagged", "Stats</button>"):
            self.assertIn(phrase, html)
        for action in ("openValidate", "openDoctor", "openStats", "inspectQualityInLibrary"):
            self.assertIn(action, html if action.startswith("open") else source)
        self.assertIn("filteredQualitySkills", source)
        self.assertIn('"quality"', source)
        self.assertIn(".quality-center .btn { min-height: 44px; }", css)
        self.assertIn('.sidepanel[aria-label="Quality skills"] .sidepanel-row { min-height: 44px; }', css)

    def test_quality_center_uses_observed_summary_and_exact_library_drilldown(self):
        script = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api(){}, formatBytes(){}, formatTokens(v){return String(v || 0);}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(rows){return [{divergent: rows.some(row => row.content_hash === 'different')}];},
    deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){sandbox.app = app; return {mount(){}};}, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return[];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const methods = sandbox.app.methods;
const records = [
  {name:'active', disabled:false},
  {name:'disabled', disabled:true},
  {name:'broken', malformed:true},
  {name:'invalid', instance_states:['invalid']},
  {name:'divergent', content_hash:'different', registry_provenance:{id:'owner/repo/divergent'}}
];
const context = {qualityRecords: records, scopes: [], selected: records[4], query:'divergent', filter:'disabled', tagFilter:'old', switchView(view){this.view=view;}, $nextTick(fn){fn();}, selectSkill(record){this.drilled=record;}};
const summary = sandbox.app.computed.qualitySummary.call(context);
const filtered = sandbox.app.computed.filteredQualitySkills.call(context);
methods.inspectQualityInLibrary.call(context);
console.log(JSON.stringify({summary, invalidLabel: methods.qualityStateLabel(records[3]), filtered: filtered.map(record => record.name), view: context.view, query: context.query, filter: context.filter, tagFilter: context.tagFilter, drilled: context.drilled.name}));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {
            "summary": {"observed": 5, "active": 2, "disabled": 1, "malformed": 1, "unaddressable": 0, "validityFlagged": 2, "divergent": 1, "provenance": 1},
            "invalidLabel": "Invalid observed",
            "filtered": ["divergent"],
            "view": "skills",
            "query": "",
            "filter": "",
            "tagFilter": "",
            "drilled": "divergent",
        })

    def test_skill_form_associates_errors_and_focuses_first_invalid_field(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn('firstInvalid.focus()', source)
        self.assertIn(':aria-invalid="modals.skill.errors.name ? \'true\' : undefined"', html)
        self.assertIn("'f-name-hint f-name-error'", html)
        self.assertIn('id="f-name-error"', html)
        self.assertIn('id="f-description-error"', html)

    def test_overview_focus_and_skip_link_are_keyboard_contracts(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('class="skip-link" href="#main-workspace"', html)
        self.assertIn('id="main-workspace"', html)
        self.assertIn('id="overview-title" tabindex="-1"', html)
        self.assertIn('document.querySelector("#view-title, #overview-title")', source)
        self.assertIn(".skip-link:focus", css)
        self.assertIn("prefers-reduced-motion", css)

    def test_navigation_groups_and_mobile_actions_keep_orientation(self):
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        for label in ("Workspace", "Operations", "Preferences"):
            self.assertIn(f'class="nav-group-label">{label}</span>', html)
        self.assertGreaterEqual(html.count('class="nav-group"'), 3)
        self.assertIn('class="command-trigger-icon" aria-hidden="true"', html)
        self.assertIn('class="actions-label">Actions</span>', html)
        self.assertIn('class="actions-glyph" aria-hidden="true"', html)
        self.assertIn(".navigation-rail .viewtabs .nav-group { display: contents; }", css)
        self.assertIn(".command-trigger-icon { display: block; }", css)
        self.assertIn(".actions-trigger .actions-label, .actions-trigger .actions-chevron { display: none; }", css)

    def test_topbar_names_and_metric_definitions_are_accessible(self):
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('<meta name="description" content="A local-first workspace for inspecting, organizing, and safely managing AI coding-agent skills.">', html)
        self.assertIn('<span class="sr-only">Go to Overview</span>', html)
        self.assertIn('<span class="sr-only">Open command palette</span>', html)
        self.assertNotIn('class="brand" type="button" @click="switchView(\'overview\')" aria-label=', html)
        self.assertNotIn('class="btn btn-secondary command-trigger" type="button" @click="toggleCommandPalette" aria-label=', html)
        self.assertIn('<dd>{{ formatNumber(overviewLogicalCount) }}<small>deduplicated names</small></dd>', html)
        self.assertIn('<dd>{{ formatNumber(qualitySummary.provenance) }}<small>present when returned</small></dd>', html)
        self.assertIn('.overview-metrics small { display: block;', css)

    def test_browser_harness_is_hermetic_and_waits_for_stable_overview(self):
        source = _read(ROOT / "browser_harness.py")
        self.assertIn('os.environ["HOME"]', source)
        self.assertIn('os.environ["SKILLS_MANAGER_DATA"]', source)
        self.assertIn('data-overview-ready="true"', source)
        self.assertIn("stableChecks", source)
        self.assertIn("1440, 900", source)
        self.assertIn("malformed-observed", source)
        self.assertIn("recoverable-probe", source)
        self.assertIn("Quality navigation tab", source)
        self.assertIn("quality-overview, .quality-section", source)

    def test_overview_surfaces_load_errors_without_first_run_claim(self):
        html = _read(INDEX_HTML)
        self.assertIn("<div v-if=\"banner\" :class=\"'banner banner-' + banner.type\" role=\"alert\"", html)
        self.assertIn("!loadingList && !banner && overviewInstanceCount === 0", html)
        self.assertIn("v-else-if=\"!banner\"", html)
        self.assertIn("No empty-state conclusion is being made", html)

    def test_detail_views_are_exclusive_and_overview_deeplink_pins_target(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn('<div v-else-if="view === \'skills\'" class="detail-inner">', html)
        self.assertIn("this.selectedName = record.name;", source)
        self.assertIn("this.selected = null;", source)
        self.assertIn("this.mobileReturnKey = (record.scope || \"\") + \"/\" + record.name;", source)
        self.assertIn("if (record) this.$nextTick(() => this.selectSkill(record));", source)

    def test_modal_focus_restore_has_one_owner(self):
        source = _read(APP_JS)
        close = re.search(r"closeModal\(key\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(close, "closeModal handler not found")
        self.assertNotIn("restoreModalFocus", close.group(1))
        watcher = re.search(r"activeModal\(value\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(watcher, "activeModal watcher not found")
        self.assertIn("this.restoreModalFocus()", watcher.group(1))

    def test_disabled_overview_route_clears_stale_detail(self):
        source = _read(APP_JS)
        branch = re.search(r'if \(key === "disabled"\) \{(.*?)\n      \}', source, re.S)
        self.assertIsNotNone(branch, "disabled overview route not found")
        self.assertIn('this.filter = "disabled";', branch.group(1))
        self.assertIn("this.selectedName = null;", branch.group(1))
        self.assertIn("this.selected = null;", branch.group(1))

    def test_select_skill_compares_the_scope_too(self):
        # BUG-3: comparing only selectedName made selecting a same-named skill
        # in another scope a no-op, so the detail pane stayed on the first
        # scope's record (with its path and body) while the user believed they
        # had selected the second.
        source = _read(APP_JS)
        match = re.search(r"selectSkill\(s\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(match, "selectSkill handler not found")
        body = match.group(1)
        self.assertIn("this.selected.scope", body)
        self.assertIn("s.scope", body)

    def test_remove_modal_binds_the_scope_it_was_opened_for(self):
        # BUG-5: the scope was re-derived from live this.selected at confirm
        # time, so a selection change between opening and confirming removed a
        # different skill than the dialog named -- irreversibly when purging.
        source = _read(APP_JS)
        match = re.search(r"confirmRemove\(record\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(match, "confirmRemove handler not found")
        self.assertIn("scope:", match.group(1))
        do_remove = re.search(r"async doRemove\(\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(do_remove, "doRemove handler not found")
        self.assertIn("m.scope", do_remove.group(1))
        remove_skill = re.search(r"async removeSkill\((.*?)\)\s*\{", source)
        self.assertIsNotNone(remove_skill, "removeSkill handler not found")
        self.assertIn("scope", remove_skill.group(1))

    def test_scope_change_and_view_switch_reapply_a_live_query(self):
        # BUG-4: the search box kept showing a term while the list showed
        # unfiltered data after a scope change or a Trash round-trip.
        source = _read(APP_JS)
        self.assertIn("refreshList()", source)
        self.assertIn("this.refreshList();", source)

    def test_validate_modal_renders_its_error(self):
        # BUG-6: modals.validate.error was assigned but never rendered, so
        # validation failures were completely silent.
        html = _read(INDEX_HTML)
        self.assertIn("modals.validate.error", html)

    def test_budget_template_guards_a_missing_window_tokens(self):
        # BUG-7: budget.window_tokens.toLocaleString() threw in the template
        # when the backend's swallowed stats failure omitted the key.
        html = _read(INDEX_HTML)
        self.assertNotIn("window_tokens.toLocaleString()", html)
        self.assertIn("formatTokens(budget.window_tokens)", html)
        domain = _read(DOMAIN_JS)
        self.assertIn("function formatTokens(", domain)
        self.assertIn('if (n == null) return "—";', domain)

    def test_domain_format_compat_handles_arrays_before_objects(self):
        source = _read(DOMAIN_JS)
        array_branch = 'if (Array.isArray(v)) return v.join(", ");'
        object_branch = 'if (typeof v === "object") return Object.entries(v)'
        self.assertIn(array_branch, source)
        self.assertLess(source.index(array_branch), source.index(object_branch))

    def test_domain_markdown_normalizes_crlf(self):
        source = _read(DOMAIN_JS)
        self.assertIn('String(md).replace(/\\r\\n?/g, "\\n").split("\\n")', source)

    def test_detail_path_metadata_uses_definition_list(self):
        html = _read(INDEX_HTML)
        self.assertRegex(
            html,
            r'<dl class="meta" style="margin-top:8px;">\s*<div>\s*<dt>Path</dt>',
        )

    def test_chip_count_does_not_reduce_contrast(self):
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        match = re.search(r"\.chip-count\s*\{([^}]*)\}", css)
        self.assertIsNotNone(match)
        self.assertNotIn("opacity", match.group(1))

    def test_detail_surfaces_raw_metadata_failure(self):
        source = _read(APP_JS)
        self.assertIn(
            "Could not load full metadata (compatibility may be missing).", source
        )
        self.assertIn("else if (mySeq === this.detailSeq)", source)

    def test_install_workflow_surfaces_registry_reads_and_fetch(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn('registryOp: "browse"', source)
        self.assertIn('async runRegistry()', source)
        self.assertIn('"/api/install"', source)
        self.assertNotIn("review_id: op === \"fetch\" ? this.install.review_id : undefined", source)
        self.assertNotIn("trust_confirmed: op === \"fetch\" ? true : undefined", source)
        self.assertIn('value="registry"', html)
        self.assertIn('value="fetch"', html)
        self.assertIn("Use an expired cache if the registry is unavailable", html)
        self.assertIn("Fetch review snapshot", html)

    def test_task_centers_and_registry_review_boundary_are_explicit(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn("view === 'install'", html)
        self.assertIn("view === 'recovery'", html)
        self.assertIn("switchView('install')", html)
        self.assertIn("switchView('recovery')", html)
        self.assertIn("registryInventory", source)
        self.assertIn("registry_provenance", source)
        self.assertIn("commitRegistryReview", source)
        self.assertIn("review_id: review.review_id", source)
        self.assertIn("trust_confirmed: true", source)
        self.assertIn("Trust and install reviewed snapshot", html)
        self.assertIn("Global store only", html)
        self.assertIn("No update is claimed", html)

    def test_registry_fetch_payload_is_two_step_and_does_not_claim_updates(self):
        source = _read(APP_JS)
        fetch_body = re.search(r"async runRegistry\(\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(fetch_body)
        body = fetch_body.group(1)
        self.assertNotIn("review_id: op === \"fetch\" ? this.install.review_id : undefined", body)
        self.assertIn("fetch: op === \"fetch\" ? true : undefined", body)
        self.assertNotIn("trust_confirmed: op === \"fetch\"", body)
        self.assertIn("async commitRegistryReview()", source)
        self.assertIn("No update is claimed unless registry evidence proves it.", html if (html := _read(INDEX_HTML)) else "")

    def test_registry_review_behavior_sends_fetch_then_exact_trust_commit(self):
        script = r'''
const fs = require('fs'), vm = require('vm');
const calls = [];
const sandbox = {
  window: {SkillManagerDomain: {
    api: async (path, options) => { calls.push({path, body: JSON.parse(options.body)}); return calls.length === 1 ? {review_id:'review-1', review_expires_at:'later', inspection:{}, registry:{}} : {name:'demo'}; },
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){}, renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){}, groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const methods = sandbox.app.methods;
const context = {
  install:{registryOp:'fetch', source:'owner/repo/demo', allowStale:false, page:0, perPage:25, view:'all-time', review_id:null, lastResult:null},
  busy:false, registryReady:methods.registryReady, toast(){}, loadScopes:async()=>{}, loadSkills:async()=>{}
};
(async()=>{ await methods.runRegistry.call(context); await methods.commitRegistryReview.call(context); console.log(JSON.stringify(calls)); })();
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        calls = json.loads(result.stdout)
        self.assertEqual(calls[0]["body"], {"fetch": True, "source": "owner/repo/demo", "allow_stale": False, "page": 0, "per_page": 25, "view": "all-time"})
        self.assertEqual(calls[1]["body"], {"fetch": True, "review_id": "review-1", "trust_confirmed": True})

    def test_install_and_recovery_centers_keep_search_and_scope_truthful(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn("filteredRegistryInventory()", source)
        self.assertIn("provenance.id, provenance.source, provenance.slug", source)
        self.assertIn("filteredRegistryInventory", html)
        self.assertIn("Search registry sources", html)
        self.assertIn("Search recovery", html)
        self.assertIn("registry-backed skills", html)
        self.assertIn("Fetch for review", html)
        self.assertIn("@click=\"openHistory('global')\"", html)
        self.assertIn("openHistory(scopeOverride = null)", source)
        self.assertIn("scope: scopeOverride || \"\"", source)
        self.assertIn("const scope = m.scope ||", source)
        self.assertIn("this.modals.history && this.modals.history.scope", source)

    def test_review_commit_is_bound_to_returned_evidence_and_new_requests_retire_it(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        run = re.search(r"async runRegistry\(\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(run)
        body = run.group(1)
        self.assertIn("this.install.review_id = null", body)
        self.assertIn("this.install.review = null", body)
        self.assertIn("this.install.lastResult = null", body)
        commit = re.search(r"async commitRegistryReview\(\)\s*\{(.*?)\n    \},", source, re.S)
        self.assertIsNotNone(commit)
        self.assertIn("const review = this.install.review", commit.group(1))
        self.assertIn("review_id: review.review_id", commit.group(1))
        self.assertIn("install.review.review_id", html)
        self.assertIn("current form values do not change it", html)

    def test_settings_surface_has_accessible_theme_and_text_size_controls(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('view === \'settings\'', html)
        self.assertIn("Settings", html)
        self.assertIn('theme: ["light", "dark", "system"].includes(savedTheme) ? savedTheme : "system"', source)
        self.assertIn('textSize: localStorage.getItem("skillsmgr-text-size") === "large" ? "large" : "standard"', source)
        self.assertIn('matchMedia("(prefers-color-scheme: dark)")', source)
        self.assertIn("themeMediaQuery.addListener", source)
        self.assertIn("themeMediaQuery.removeListener", source)
        self.assertIn("beforeUnmount()", source)
        self.assertIn('data-text-size="large"', css)
        self.assertIn('min-height: 44px', css)
        self.assertIn('type="radio"', html)
        self.assertIn('aria-describedby="settings-theme-hint"', html)
        self.assertIn('aria-describedby="settings-text-size-hint"', html)

    def test_regional_format_preference_is_localized_without_false_translation_claims(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        domain = _read(ROOT / "skillsmgr" / "webui" / "domain.js")
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('localStorage.getItem("skillsmgr-locale")', source)
        self.assertIn('resolvedLocale: "en-US"', source)
        self.assertIn("new Intl.NumberFormat", source)
        self.assertIn("new Intl.DateTimeFormat", source)
        self.assertIn("document.documentElement.lang = \"en\"", source)
        self.assertIn("function localizedNumber", domain)
        self.assertIn("Regional formats", html)
        self.assertIn("Interface copy remains English until translated resources are available.", html)
        self.assertIn('id="settings-locale"', html)
        self.assertIn('aria-describedby="settings-locale-hint"', html)
        self.assertIn("settings-locale-preview", css)
        self.assertNotIn("toLocaleString()", html)

        script = r'''
const fs = require('fs'), vm = require('vm');
const store = {};
const sandbox = {
  navigator: {language: 'en-IN'},
  window: {SkillManagerDomain: {api(){}, formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){}, renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){}, groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}}},
  Vue: {createApp(app){sandbox.app = app; return {mount(){}};}, nextTick(){}},
  localStorage: {getItem(k){return store[k] || null;}, setItem(k,v){store[k]=String(v);}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}, lang:'en'}, querySelectorAll(){return [];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const ctx = {...sandbox.app.data(), ...sandbox.app.methods, $nextTick(){}};
ctx.applyLocale('en-IN');
const expectedDate = new Intl.DateTimeFormat('en-IN', {dateStyle:'medium', timeStyle:'short'}).format(new Date('2026-09-22T13:45:00Z'));
if (ctx.resolvedLocale !== 'en-IN' || sandbox.document.documentElement.dataset.locale !== 'en-IN') throw new Error('regional locale failed');
if (ctx.formatNumber(1234567) !== '12,34,567') throw new Error('regional number failed');
if (ctx.formatDate('2026-09-22T13:45:00Z') !== expectedDate) throw new Error('regional date failed');
if (ctx.normalizeLocale('not-supported') !== 'system') throw new Error('invalid locale was accepted');
ctx.applyLocale('not-supported');
if (ctx.resolvedLocale !== 'en-IN' || sandbox.document.documentElement.lang !== 'en') throw new Error('system fallback or language boundary failed');
console.log(JSON.stringify({locale:ctx.resolvedLocale, number:ctx.formatNumber(1234567), date:ctx.formatDate('2026-09-22T13:45:00Z')}));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        values = json.loads(result.stdout)
        self.assertEqual(values["locale"], "en-IN")
        self.assertEqual(values["number"], "12,34,567")

    def test_regional_formatting_covers_secondary_counts_and_status_context(self):
        html = _read(INDEX_HTML)
        self.assertIn("Theme, text size, and regional formats are stored only in this browser.", html)
        self.assertIn("formatNumber(budget.all_pct_window)", html)
        self.assertIn("selected.tokens_pct != null ? formatNumber(selected.tokens_pct)", html)
        self.assertNotIn("selected.tokens_pct != null ? selected.tokens_pct + '%'", html)
        self.assertIn("formatNumber(Object.keys(catalog.profiles || {}).length)", html)
        self.assertIn("Settings · {{ themeModeLabel }} theme · {{ textSize }} text · {{ resolvedLocale }} formats", html)
        for expression in (
            "{{ (profilePreview.summary || {}).observed || 0 }}",
            "{{ (profilePreview.summary || {}).disabled || 0 }}",
            "{{ (profilePreview.summary || {}).divergent || 0 }}",
            "{{ (profilePreview.summary || {}).missing || 0 }}",
            "{{ modals.doctor.report.skills_on_disk }}",
            "{{ modals.doctor.report.db_rows }}",
            "{{ modals.doctor.report.trash_count }}",
            "{{ modals.doctor.report.templates_count }}",
            "{{ modals.stats.report.total }}",
            "{{ modals.stats.report.active }}",
            "{{ modals.stats.report.disabled }}",
            "{{ modals.stats.report.trashed }}",
        ):
            self.assertNotIn(expression, html)

    def test_theme_preference_listener_and_text_size_behavior(self):
        script = r'''
const fs = require('fs'), vm = require('vm');
const listeners = [];
const media = {matches:true, addEventListener(type, fn){listeners.push(fn);}, removeEventListener(type, fn){this.removed = fn;}};
const store = {};
const sandbox = {
  window: {SkillManagerDomain: {api(){}, formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){}, renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){}, groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}}, matchMedia(){return media;}},
  Vue: {createApp(app){sandbox.app = app; return {mount(){}};}, nextTick(){}},
  localStorage: {getItem(k){return store[k] || null;}, setItem(k,v){store[k]=String(v);}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const ctx = {...sandbox.app.data(), ...sandbox.app.methods, $nextTick(){}};
ctx.setupThemeListener();
if (listeners.length !== 1) throw new Error('system theme listener not installed');
media.matches = false; listeners[0]();
if (ctx.resolvedTheme !== 'light' || sandbox.document.documentElement.dataset.theme !== 'light') throw new Error('system theme change not applied');
ctx.setThemePreference('dark');
ctx.applyThemePreference(ctx.theme); ctx.setupThemeListener(); store['skillsmgr-theme'] = ctx.theme;
if (ctx.theme !== 'dark' || ctx.resolvedTheme !== 'dark' || listeners.length !== 1) throw new Error('explicit theme failed');
ctx.setThemePreference('system');
ctx.applyThemePreference(ctx.theme); ctx.setupThemeListener(); store['skillsmgr-theme'] = ctx.theme;
if (listeners.length !== 2) throw new Error('system listener not restored');
ctx.setTextSize('large');
ctx.applyTextSize(ctx.textSize); store['skillsmgr-text-size'] = ctx.textSize;
if (ctx.textSize !== 'large' || sandbox.document.documentElement.dataset.textSize !== 'large' || store['skillsmgr-text-size'] !== 'large') throw new Error('text size failed');
ctx.removeThemeListener();
if (media.removed !== listeners[1]) throw new Error('theme listener not cleaned up');
console.log(JSON.stringify({theme:ctx.theme, resolved:ctx.resolvedTheme, size:ctx.textSize, stored:store}));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        state = json.loads(result.stdout)
        self.assertEqual(state["theme"], "system")
        self.assertEqual(state["resolved"], "light")
        self.assertEqual(state["size"], "large")
        self.assertEqual(state["stored"]["skillsmgr-theme"], "system")

    def test_system_theme_evidence_is_independent_of_explicit_app_theme(self):
        script = r'''
const fs = require('fs'), vm = require('vm');
const media = {matches:false, addEventListener(){}, removeEventListener(){}};
const sandbox = {
  window: {SkillManagerDomain: {api(){}, formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){}, renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){}, groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}}, matchMedia(){return media;}},
  Vue: {createApp(app){sandbox.app = app; return {mount(){}};}, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const ctx = {...sandbox.app.data(), ...sandbox.app.methods, $nextTick(){}};
ctx.applyThemePreference('dark');
const systemThemeLabel = () => sandbox.app.computed.systemThemeLabel.call(ctx);
if (ctx.resolvedTheme !== 'dark' || systemThemeLabel() !== 'light') throw new Error('OS evidence was replaced by explicit app theme');
console.log(JSON.stringify({resolved:ctx.resolvedTheme, os:systemThemeLabel()}));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {"resolved": "dark", "os": "light"})

    def test_preference_bootstrap_resolves_saved_values_before_stylesheet(self):
        source = _read(PREFERENCES_JS) if PREFERENCES_JS.exists() else ""
        html = _read(INDEX_HTML)
        self.assertTrue(source, "preference bootstrap must exist")
        self.assertIn('<script src="/preferences.js"></script>', html)
        self.assertLess(html.index('<script src="/preferences.js"></script>'), html.index('<link rel="stylesheet" href="/styles.css">'))
        self.assertIn('skillsmgr-theme', source)
        self.assertIn('skillsmgr-text-size', source)
        self.assertIn('(prefers-color-scheme: dark)', source)
        script = r'''
const fs = require('fs'), vm = require('vm');
function run(savedTheme, savedSize, matches, fail) {
  const root = {dataset:{}};
  const sandbox = {document:{documentElement:root}, window:{localStorage:{getItem(key){if (fail) throw new Error('storage'); return key === 'skillsmgr-theme' ? savedTheme : savedSize;}}, matchMedia(){if (fail) throw new Error('media'); return {matches};}}};
  vm.runInNewContext(fs.readFileSync('skillsmgr/webui/preferences.js', 'utf8'), sandbox);
  return root.dataset;
}
console.log(JSON.stringify([run('dark','large',false,false), run('system','bad',true,false), run('invalid','invalid',true,true)]));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        values = json.loads(result.stdout)
        self.assertEqual(values[0], {"themePreference": "dark", "theme": "dark", "textSize": "large"})
        self.assertEqual(values[1], {"themePreference": "system", "theme": "dark", "textSize": "standard"})
        self.assertEqual(values[2], {"themePreference": "system", "theme": "light", "textSize": "standard"})

    def test_large_type_scale_uses_rem_for_representative_ui_text(self):
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('html[data-text-size="large"] { font-size: 1.125rem; }', css)
        self.assertNotIn('html[data-text-size="large"] body', css)
        self.assertRegex(css, r"\.row-name \{[^}]*font-size: 0\.875rem")
        self.assertRegex(css, r"\.meta dd \{[^}]*font-size: 0\.875rem")
        self.assertRegex(css, r"\.form-field \.hint \{ font-size: 0\.75rem")
        self.assertRegex(css, r"\.modal-head h2 \{ margin: 0; font-size: 1\.1875rem")
        self.assertNotRegex(css, r"font-size:\s*[^;]*px")

    def test_logical_library_groups_aliases_but_keeps_divergence(self):
        script = """
const fs = require('fs'), vm = require('vm');
const sandbox = {window: {}};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const rows = [
  {name:'alpha', scope:'global', scope_label:'Global', physical_path:'/root/alpha', content_hash:'same'},
  {name:'alpha', scope:'agents', scope_label:'Agents', physical_path:'/root/alpha', content_hash:'same'},
  {name:'alpha', scope:'claude-code', scope_label:'Claude Code', physical_path:'/claude/alpha', content_hash:'different'}
];
console.log(JSON.stringify(sandbox.window.SkillManagerDomain.groupLogicalSkills(rows)));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        groups = json.loads(result.stdout)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["instanceCount"], 2)
        self.assertTrue(groups[0]["divergent"])
        self.assertEqual(len(groups[0]["badges"]), 2)
        self.assertIn("groupLogicalSkills", _read(DOMAIN_JS))

    def test_domain_identity_keeps_alias_consumers_and_observed_states(self):
        script = """
const fs = require('fs'), vm = require('vm');
const sandbox = {window: {}};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const scopes = [
  {id:'global', label:'Global', kind:'global', consumer:'skills-manager'},
  {id:'agents', label:'Agents', kind:'agent', consumer:'shared-agent-skills'},
  {id:'project-agents', label:'Project .agents', kind:'project', consumer:'shared-agent-skills'},
  {id:'mystery', label:'Mystery', kind:'agent', consumer:null}
];
const rows = [
  {name:'alpha', scope:'global', scope_label:'Global', consumer:'skills-manager', physical_path:'/same/alpha', content_hash:'a'},
  {name:'alpha', scope:'agents', scope_label:'Agents', consumer:'shared-agent-skills', physical_path:'/same/alpha', content_hash:'b', disabled:true},
  {name:'alpha', scope:'project-agents', scope_label:'Project .agents', consumer:'shared-agent-skills', physical_path:'/project/alpha', content_hash:'c'},
  {name:'mystery', scope:'mystery', scope_label:'Mystery', consumer:null, addressable:false}
];
console.log(JSON.stringify(sandbox.window.SkillManagerDomain.groupLogicalSkills(rows, scopes)));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        groups = json.loads(result.stdout)
        alpha = groups[0]
        labels = [item["label"] for item in alpha["identities"]]
        self.assertTrue(any("Global" in label and "skills-manager" in label for label in labels))
        self.assertTrue(any("Agents agent" in label and "shared-agent-skills" in label for label in labels))
        self.assertTrue(any("Project .agents workspace" in label for label in labels))
        self.assertIn("Divergent", " ".join(item["stateLabel"] for item in alpha["identities"]))
        mystery = groups[1]
        self.assertIn("Unknown consumer", mystery["identities"][0]["label"])
        self.assertEqual(mystery["identities"][0]["stateLabel"], "Unaddressable")
        self.assertEqual(alpha["instanceCount"], 2, "alias rows still collapse to exact physical instances")

    def test_library_rows_render_identity_and_state_as_text(self):
        html = _read(INDEX_HTML)
        source = _read(APP_JS)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn("deriveLogicalSkillIdentity", _read(DOMAIN_JS))
        self.assertIn("identityItems(item)", source)
        self.assertIn("Observed identity and state", html)
        self.assertIn("identity.label", html)
        self.assertIn("identity.stateLabel", html)
        self.assertIn("Unknown consumer", _read(DOMAIN_JS))
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("identity-state-warn", css)
        self.assertNotIn("effective/winning", html)

    def test_instance_mode_and_detail_keep_scope_qualified_observations(self):
        html = _read(INDEX_HTML)
        source = _read(APP_JS)
        self.assertIn("libraryMode === 'instances'", html)
        self.assertIn("observedIdentity(instance, scopes).scopeLabel", html)
        self.assertIn("observedIdentity(instance, scopes).label", html)
        self.assertIn("observedIdentity(selected, scopes).label", html)
        self.assertIn("targetKey(record)", source)

    def test_startup_fetches_each_source_once_and_stats_are_secondary(self):
        source = _read(APP_JS)
        self.assertIn("this.loadInitialData();", source)
        self.assertIn("Promise.all([this.loadScopes(), this.loadSkills(), this.loadTrash()])", source)
        self.assertIn("await this.loadStatsTokens();", source)

    def test_mobile_detail_has_back_navigation_and_focus_return(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn("mobileDetailOpen", source)
        self.assertIn("closeMobileDetail()", source)
        self.assertIn("data-skill-key", html)
        self.assertIn('class="mobile-back"', html)
        self.assertIn("mobile-controls-toggle", html)
        self.assertIn(".layout.mobile-detail-open .sidebar", css)

    def test_empty_library_has_local_first_run_onboarding_with_expert_escape(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn("onboardingDismissed: false", source)
        self.assertIn("onboardingVisible()", source)
        self.assertIn("onboardingRoots()", source)
        self.assertIn("skipOnboarding()", source)
        self.assertIn("restartOnboarding()", source)
        self.assertIn("filesystem as the source of truth", html)
        self.assertIn("openDoctor", html)
        self.assertIn("Import archive", html)
        self.assertIn(".onboarding-steps", css)

    def test_library_browse_mode_defaults_to_list_and_grid_is_local_opt_in(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('browseMode: localStorage.getItem("skillsmgr-browse-mode") === "grid" ? "grid" : "list"', source)
        self.assertIn('setBrowseMode(mode)', source)
        self.assertIn('this.browseMode = mode === "grid" ? "grid" : "list";', source)
        self.assertIn('localStorage.setItem("skillsmgr-browse-mode", v);', source)
        self.assertIn('aria-label="Library presentation"', html)
        self.assertIn('browseMode === \'list\'', html)
        self.assertIn('browseMode === \'grid\'', html)
        self.assertIn('.skill-grid', css)

    def test_grid_browse_widens_desktop_pane_without_changing_mobile_layout(self):
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn("'grid-browse': view === 'skills' && browseMode === 'grid'", html)
        self.assertIn('.layout.grid-browse { grid-template-columns: 220px minmax(460px, 42vw) minmax(0, 1fr); }', css)
        self.assertIn('.layout.grid-browse { grid-template-columns: 136px minmax(360px, 46vw) minmax(0, 1fr); }', css)
        self.assertIn('.layout.grid-browse .skill-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }', css)
        self.assertIn('.layout { display: flex; flex-direction: column; }', css)
        self.assertIn('grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));', css)
        self.assertNotIn('border-left: 3px solid var(--border-strong)', css)

    def test_browse_mode_controls_and_cards_are_keyboard_accessible(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn(':aria-pressed="browseMode === \'list\'"', html)
        self.assertIn(':aria-pressed="browseMode === \'grid\'"', html)
        self.assertIn('@keydown.enter.self.prevent="libraryMode === \'library\' ? selectLogicalSkill(s) : selectSkill(s)"', html)
        self.assertIn('@keydown.space.self.prevent="libraryMode === \'library\' ? selectLogicalSkill(s) : selectSkill(s)"', html)
        self.assertIn('class="browse-switch" role="group"', html)
        self.assertIn('.skill-grid > li:not(.batchbar)', css)
        self.assertIn(':focus-visible', css)

    def test_actions_menu_and_import_dropzone_have_complete_keyboard_contracts(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('ref="menuTrigger"', html)
        self.assertIn('aria-controls="actions-menu"', html)
        self.assertIn('id="actions-menu" class="menu" role="menu"', html)
        self.assertIn('@keydown="onMenuKeydown"', html)
        for key in ("ArrowDown", "ArrowUp", "Home", "End", "Escape"):
            self.assertIn('e.key === "' + key + '"', source)
        self.assertIn('this.$nextTick(() => this.focusFirstMenuItem())', source)
        self.assertIn('@keydown.space.prevent="pickImportFile"', html)
        self.assertIn('.modal-close { min-width: 44px; min-height: 44px;', css)
        self.assertIn('.copybtn { min-width: 44px; min-height: 44px; }', css)

    def test_focus_appearance_is_explicit_and_detail_is_not_a_broad_live_region(self):
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn(':focus-visible {\n  outline: 2px solid var(--accent);', css)
        self.assertIn('outline-offset: 2px;', css)
        self.assertIn('scroll-margin-top: 16px;', css)
        self.assertIn('<section class="detail">', html)
        self.assertNotIn('<section class="detail" aria-live=', html)
        self.assertIn('class="command-palette-status" role="status" aria-live="polite"', html)

    def test_grid_keeps_drilldown_and_exact_batch_target_contracts(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn(':class="[\'skilllist\', { \'skill-grid\': browseMode === \'grid\' }]"', html)
        self.assertIn('@click="libraryMode === \'library\' ? selectLogicalSkill(s) : selectSkill(s)"', html)
        self.assertIn('@change="toggleSelection(s, $event.target.checked)"', html)
        self.assertIn(':data-skill-key="libraryMode === \'library\' ? ((s.primary && s.primary.scope) || \'\') + \'/\' + s.name : s.scope + \'/\' + s.name"', html)
        self.assertIn('toggleSelection(record, checked)', source)
        self.assertIn('selectedTargets()', source)
        self.assertIn('this.mobileDetailOpen = true;', source)
        self.assertIn('class="card-meta"', html)

    def test_batch_plans_freeze_targets_and_profile_apply_reuses_exact_snapshot(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn("targets: modal.targets", source)
        self.assertGreaterEqual(source.count("targets: modal.targets"), 2)
        self.assertIn("profileTargets()", source)
        self.assertIn("openProfileBatch", source)
        self.assertIn("this.profilePreview = await api", source)
        self.assertIn("await this.previewProfile", source)
        self.assertIn("Review enable plan", html)

    def test_profile_target_derivation_dedupes_name_scope_path_and_keeps_unresolved_members(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        self.assertIn("const seen = new Set()", source)
        self.assertRegex(source, r"member\.instances")
        self.assertIn("profilePreview.summary", html)
        self.assertIn("member.state === 'missing' || member.state === 'divergent'", html)
        self.assertIn("unresolved", html.lower())

    def test_profile_target_derivation_behavior_dedupes_exact_physical_keys(self):
        script = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api(){}, formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const targets = sandbox.app.methods.profileTargets.call({profilePreview: {members: [
  {name:'review', state:'divergent', instances:[
    {scope:'agents', path:'/skills/review'},
    {scope:'agents', path:'/skills/review'},
    {scope:'codex', path:'/codex/review'}
  ]},
  {name:'missing', state:'missing', instances:[]}
]}});
console.log(JSON.stringify(targets));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [
            {"name": "review", "scope": "agents", "path": "/skills/review"},
            {"name": "review", "scope": "codex", "path": "/codex/review"},
        ])

    def test_profile_open_batch_passes_exact_targets_and_computed_unresolved_context(self):
        script = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api(){}, formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){sandbox.app = app; return {mount(){}};}, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return[];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const methods = sandbox.app.methods;
let received = null;
const context = {
  profilePreview: {name:'ops', members:[
    {name:'alpha', state:'observed', instances:[
      {scope:'global', path:'/store/alpha'},
      {scope:'agents', path:'/agents/alpha'},
      {scope:'global', path:'/store/alpha'}
    ]},
    {name:'missing-skill', state:'missing', instances:[]},
    {name:'divergent-skill', state:'divergent', instances:[
      {scope:'codex', path:'/codex/divergent'}
    ]}
  ]},
  profileTargets: methods.profileTargets,
  openBatch(operation, targets, ctx){received = {operation, targets, ctx};},
  toast(){}
};
Object.defineProperty(context, 'profileUnresolvedMembers', {
  value: sandbox.app.computed.profileUnresolvedMembers.call(context)
});
methods.openProfileBatch.call(context);
console.log(JSON.stringify(received));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {
            "operation": "enable",
            "targets": [
                {"name": "alpha", "scope": "global", "path": "/store/alpha"},
                {"name": "alpha", "scope": "agents", "path": "/agents/alpha"},
                {"name": "divergent-skill", "scope": "codex", "path": "/codex/divergent"},
            ],
            "ctx": {
                "profileName": "ops",
                "unresolvedCount": 2,
                "unresolvedMembers": ["missing-skill", "divergent-skill"],
            },
        })

    def test_mobile_toggle_labels_scope_controls_not_filters(self):
        html = _read(INDEX_HTML)
        self.assertIn("Show scope controls", html)
        self.assertIn("Hide scope controls", html)
        self.assertNotIn("Show filters", html)
        self.assertNotIn("Hide filters", html)

    def test_grid_identity_cards_stack_observations_and_keep_desktop_two_column_contract(self):
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertRegex(css, r"\.card-meta\s*\{[^}]*display: grid;[^}]*\}")
        self.assertIn('.card-meta .identity-observation { width: 100%; }', css)
        self.assertIn('grid-template-columns: minmax(0, 1fr) auto;', css)
        self.assertIn('.skill-grid .card-meta .identity-observation { grid-template-columns: minmax(0, 1fr);', css)
        self.assertIn('text-overflow: ellipsis; white-space: nowrap;', css)
        self.assertIn('grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));', css)
        self.assertIn('grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));', css)

    def test_mobile_view_navigation_keeps_active_tab_visible(self):
        source = _read(APP_JS)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn("scrollActiveViewTab();", source)
        self.assertIn('scrollIntoView({ block: "nearest", inline: "center" })', source)
        self.assertIn('scroll-snap-type: x proximity;', css)

    def test_mobile_forms_keep_text_readable_and_auxiliary_context_does_not_duplicate(self):
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn("'aux-context-pane': ['install', 'recovery', 'settings'].includes(view)", html)
        self.assertIn('id="history-skill"', html)
        for field_id in ("install-source", "install-runner", "install-scope", "install-agents", "install-filter"):
            self.assertIn(f'id="{field_id}"', html)
            self.assertIn(f'for="{field_id}"', html)
        self.assertIn('.searchwrap input, .form-field input, .form-field textarea, .form-field select, .workspace-project-form input, .command-palette-input { font-size: 1rem; }', css)
        self.assertIn('.layout.mobile-aux-view .sidebar.list-pane.aux-context-pane { display: none; }', css)

    def test_brand_returns_to_overview_and_grid_rendering_is_deferred(self):
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('class="brand" type="button" @click="switchView(\'overview\')"', html)
        self.assertIn('content-visibility: auto;', css)
        self.assertIn('text-wrap: balance;', css)

    def test_install_checkbox_is_compact_and_does_not_change_row_target(self):
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('.check-row input[type="checkbox"], .check-row input[type="radio"]', css)
        self.assertIn('width: 18px; height: 18px; min-height: 18px; max-height: 18px; flex: none;', css)
        self.assertIn('.check-row { display: flex; gap: var(--s2); align-items: center; min-height: 44px;', css)

    def test_batch_modal_explains_profile_before_after_and_recovery_policy(self):
        html = _read(INDEX_HTML)
        self.assertIn("Disabled → Active", html)
        self.assertIn("Active → No state change", html)
        self.assertIn("partial-failure", html)
        self.assertIn("recovery", html)
        self.assertIn("modals.batch.targets", html)

    def test_command_palette_is_labelled_and_keyboard_operable(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('class="btn btn-secondary command-trigger"', html)
        self.assertIn('aria-keyshortcuts="Control+K Meta+K"', html)
        self.assertIn('role="dialog" aria-modal="true" aria-labelledby="commands-modal-title"', html)
        self.assertIn('role="combobox" aria-autocomplete="list"', html)
        self.assertIn('aria-controls="command-palette-results"', html)
        self.assertIn('role="listbox"', html)
        self.assertIn('role="status" aria-live="polite"', html)
        for key in ("ArrowDown", "ArrowUp", "Home", "End", "Enter", "Escape"):
            self.assertIn(f'e.key === "{key}"', source)
        self.assertIn("commandPaletteTransfer", source)
        self.assertRegex(css, r"\.command-palette-option\s*\{[^}]*min-height: 44px;")

    def test_command_palette_keeps_active_descendant_rows_non_tabbable_and_transfers_focus(self):
        source = _read(APP_JS)
        html = _read(INDEX_HTML)
        css = _read(ROOT / "skillsmgr" / "webui" / "styles.css")
        self.assertIn('class="command-palette-option" role="option"', html)
        self.assertNotIn('<button class="command-palette-option"', html)
        self.assertIn('@mousedown.prevent="commandPaletteActiveIndex = index"', html)
        self.assertIn("scrollIntoView({ block: \"nearest\" })", source)
        self.assertIn("if (!(this.commandPaletteTransfer && this.modalRestoreFocus))", source)
        self.assertIn('id: "import-archive"', source)
        self.assertIn('label: "Import archive"', source)
        self.assertIn('id: "add-folder"', source)
        self.assertIn('action: "openAdd" },', source)
        self.assertRegex(css, r"\.command-trigger\s*\{[^}]*min-height: 44px;")
        self.assertIn('id="library-view-title" class="sr-only" tabindex="-1">Library', html)

    def test_command_palette_filters_keywords_and_hides_unavailable_record_actions(self):
        script = r'''
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
function palette(context) {
  Object.defineProperty(context, 'commandPaletteCommands', {get(){return computed.commandPaletteCommands.call(context);}});
  return computed.filteredCommandPaletteCommands.call(context);
}
const base = {view:'overview', selectedName:null, selected:null, selectedDisabled:false, commandPaletteQuery:'install'};
const overview = palette(base).map(item => item.id);
const selectedContext = {view:'skills', selectedName:'alpha', selected:{name:'alpha', disabled:false}, selectedDisabled:false, commandPaletteQuery:'disable'};
const selected = palette(selectedContext).map(item => item.id);
console.log(JSON.stringify({overview, selected}));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertEqual(value["overview"], ["nav-install", "install-workflow"])
        self.assertEqual(value["selected"], ["selected-toggle"])


if __name__ == "__main__":
    unittest.main()
