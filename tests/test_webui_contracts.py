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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FrontendSourceContractTests(unittest.TestCase):
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
        self.assertIn("trust_confirmed: op === \"fetch\" ? true : undefined", source)
        self.assertIn('value="registry"', html)
        self.assertIn('value="fetch"', html)
        self.assertIn("Use an expired cache if the registry is unavailable", html)
        self.assertIn("Fetch and install", html)

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


if __name__ == "__main__":
    unittest.main()
