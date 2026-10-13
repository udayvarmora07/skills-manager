"""5.4 — the Workspaces view's contracts.

Written against the three defects the redesign was for, plus the properties
that would let them come back unnoticed:

  1. The rail printed `tier` and `status`, which `adapters.py` derives from the
     SAME `policy == "ordered"` comparison — so three of six consumers read
     "verified · verified". Asserted by loading the real `catalog()` and
     checking the pair is not rendered twice, not by grepping for a word.
  2. The card grid rendered `candidate_roots` (the flat union of `tiers`), so
     the tier notes were dropped and the roots lost their meaning. Asserted as
     a property over the payload: every root appears under a tier, and every
     tier note is reachable from the template.
  3. `.tag` caps at `max-width: 90px`, so every candidate path rendered as
     "path unkno…". Asserted structurally — no `.tag` in this view at all.
  4. "not-requested" wore `badge-warn`, styling the page's resting state as a
     finding.

The Vue computeds are exercised in a Node VM (the `tests/test_redesign_fetch_flow.py`
harness), not by reading their source: MAP.md records a fifth case of a comment
describing behaviour the markup does not implement, and reading the source is
how that class of test passes.
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr/webui/index.html").read_text()
CSS = (ROOT / "skillsmgr/webui/styles.css").read_text()
APP = (ROOT / "skillsmgr/webui/app.js").read_text()

sys_path = str(ROOT)
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from skillsmgr.adapters import catalog  # noqa: E402

VIEW_RE = re.compile(
    r'<div v-else-if="view === \'workspaces\'" class="detail-inner">(.*?)\n      </div>', re.S)


def view_html() -> str:
    match = VIEW_RE.search(HTML)
    assert match, "the workspaces view block is gone from index.html"
    return match.group(1)


class WorkspacesMarkup(unittest.TestCase):
    """The shape of the view, asserted on the block itself."""

    def setUp(self):
        self.view = view_html()

    def test_catalogue_is_a_table_not_a_grid_of_equal_cards(self):
        self.assertIn('<table v-else-if="workspaceAdapters.length" class="adapter-table">', self.view)
        self.assertNotIn("adapter-grid", self.view)
        self.assertNotIn("adapter-card", self.view)
        block = CSS.split(".adapter-catalog {")[1].split(".compact-meta")[0]
        # rule text only: the comment above the block quotes the grid it
        # replaced, on purpose, and the split starts at the first declaration.
        self.assertNotIn("auto-fit", block)

    def test_table_has_a_caption_and_scoped_headers(self):
        self.assertIn("<caption class=\"sr-only\">", self.view)
        for column in ("col-consumer", "col-precedence", "col-roots"):
            self.assertIn(f'<th scope="col" class="{column}">', self.view)
        self.assertIn('<th scope="row" class="adapter-consumer">', self.view)

    def test_no_candidate_path_is_rendered_through_a_width_capped_tag(self):
        """The defect was `.tag { max-width: 90px }`, not the words on it."""
        self.assertNotIn("root-observation", self.view)
        self.assertNotIn('class="tag', self.view)
        rule = re.search(r"^\.tag \{.*?^\}", CSS, re.S | re.M)
        self.assertIsNotNone(rule)
        self.assertIn("max-width: 90px", rule.group(0))

    def test_roots_are_rendered_as_code_so_a_path_can_wrap(self):
        self.assertIn('<code>{{ root.label }}</code>', self.view)
        self.assertIn("overflow-wrap: anywhere", CSS)

    def test_tiers_and_their_notes_are_rendered(self):
        self.assertIn('v-for="tier in adapter.tiers"', self.view)
        self.assertIn('v-if="tier.note"', self.view)

    def test_evidence_date_and_source_are_rendered(self):
        self.assertIn("adapter.verified", self.view)
        self.assertIn("Last verified", self.view)
        self.assertIn(':href="adapter.source"', self.view)
        self.assertIn("{{ adapter.sourceHost }}", self.view)
        self.assertIn("<span v-else>no source recorded</span>", self.view)


class WorkspacesTemplateFacts(unittest.TestCase):
    """Facts that must be computed, not re-decided in the template."""

    def test_no_status_tone_is_a_template_ternary_any_more(self):
        for ternary in (
            "workspaces.project.status === 'accepted'",
            "adapter.status === 'verified'",
            "adapter.precedence.notes.join",
        ):
            self.assertNotIn(ternary, HTML, ternary)

    def test_the_computed_states_exist(self):
        for name in ("workspaceAdapters()", "workspaceObservation()",
                     "workspaceObservationSentence()", "workspaceIdleSentence()"):
            self.assertIn(name, APP, name)

    def test_the_rail_no_longer_repeats_the_catalogue(self):
        rail = re.search(
            r'<div v-else-if="view === \'workspaces\'" class="sidepanel"(.*?)</div>\s*\n\s*\n', HTML, re.S)
        self.assertIsNotNone(rail, "the workspaces rail is gone from index.html")
        block = rail.group(1)
        self.assertNotIn("adapters", block)
        self.assertNotIn("sidepanel-row", block)
        self.assertIn("workspace-notes", block)


class WorkspacesComputed(unittest.TestCase):
    """The computeds, run against the real payload."""

    SCRIPT = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}), formatBytes(){}, formatTokens(){}, tokenPctClass(){},
    tokenBarWidth(){}, renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){},
    formatTools(){}, groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  URL, setTimeout, clearTimeout, console
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const o = sandbox.app;
const ctx = JSON.parse(process.argv[1]);
// Vue lets one computed read another; a plain object cannot. Bind in
// dependency order, exactly as the fetch-flow harness does.
for (const dep of ['workspaceObservation']) {
  if (JSON.parse(process.argv[2]).includes(dep)) ctx[dep] = o.computed[dep].call(ctx);
}
const fn = (o.computed[process.argv[3]] || o.methods[process.argv[3]]);
// Vue's options object holds computeds as PLAIN functions, not ES getters, so
// `.call(ctx)` is right and `descriptor.get` is undefined — the reverse is the
// classic "cannot read properties of undefined" and is not a product failure.
try { console.log('###' + JSON.stringify(fn.call(ctx))); }
catch (e) { console.log('###THREW: ' + e.message); }
'''

    def _run(self, name, state, deps=()):
        out = subprocess.run(
            ["node", "-e", self.SCRIPT, json.dumps(state), json.dumps(list(deps)), name],
            capture_output=True, text=True, cwd=str(ROOT), check=True).stdout
        line = [ln for ln in out.splitlines() if ln.startswith("###")][0][3:]
        value = json.loads(line)
        if isinstance(value, str) and value.startswith("THREW: "):
            self.fail(f"{name} threw: {value[6:]}")
        return value

    def test_tier_and_status_are_the_same_fact_and_are_not_both_rendered(self):
        """adapters.py derives both from `policy == 'ordered'`."""
        for adapter in catalog():
            self.assertEqual(
                (adapter["tier"] == "verified"), (adapter["status"] == "verified"),
                f"{adapter['id']} disagrees with itself")
        rows = self._run("workspaceAdapters", {"workspaces": {"adapters": catalog()}})
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertTrue(row["state"])
            # exactly one tone word, never "verified · verified"
            self.assertNotIn("·", row["state"])
        self.assertEqual(sum(1 for r in rows if r["documented"]), 3)

    def test_every_candidate_root_is_reachable_under_a_tier(self):
        payload = {"workspaces": {"adapters": catalog()}}
        rows = self._run("workspaceAdapters", payload)
        for adapter, row in zip(catalog(), rows):
            flat = [r for tier in adapter["tiers"] for r in tier["roots"]]
            self.assertEqual(len(flat), len(adapter["candidate_roots"]), adapter["id"])
            tiered = [r for tier in row["tiers"] for r in tier["roots"]]
            self.assertEqual(len(tiered), len(flat), adapter["id"])
            self.assertEqual(
                sorted(r["label"] for r in tiered),
                sorted(((r["scope"] or r["relative_path"] or r["absolute_path"] or "") or "path unknown")
                       for r in flat), adapter["id"])
            notes = [t["note"] for t in row["tiers"] if t["note"]]
            self.assertEqual(
                sorted(notes),
                sorted(t["note"] for t in adapter["tiers"] if t.get("note")),
                f"{adapter['id']} lost a tier note")

    def test_an_unknown_root_is_named_not_dropped(self):
        rows = self._run("workspaceAdapters", {"workspaces": {"adapters": catalog()}})
        unknown = [r for row in rows for tier in row["tiers"] for r in tier["roots"] if not r["known"]]
        self.assertTrue(unknown, "expected at least one root with no recorded path")
        for root in unknown:
            self.assertEqual(root["label"], "path unknown")

    def test_the_source_link_names_its_host(self):
        rows = self._run("workspaceAdapters", {"workspaces": {"adapters": catalog()}})
        hosts = {row["id"]: row["sourceHost"] for row in rows}
        self.assertEqual(hosts["claude-code"], "code.claude.com")
        self.assertNotIn("primary source", hosts.values())
        self.assertTrue(all(hosts.values()), "every adapter records a source today")

    def test_not_requested_is_not_a_warning(self):
        base = {"adapters": [], "project": {"status": "not-requested", "path": None, "skills_roots": []}}
        empty = self._run("workspaceObservation", {"workspaces": base})
        self.assertFalse(empty["requested"])
        self.assertEqual(empty["tone"], "", "an unasked-for page must not wear a badge tone")
        for status in ("outside-managed-roots", "missing", "inaccessible"):
            seen = self._run(
                "workspaceObservation",
                {"workspaces": {"adapters": [], "project": dict(base["project"], status=status)}})
            self.assertTrue(seen["requested"], status)
            self.assertEqual(seen["tone"], "badge-warn", status)
        accepted = self._run(
            "workspaceObservation",
            {"workspaces": {"adapters": [], "project": dict(base["project"], status="accepted", path="/x")}})
        self.assertEqual(accepted["tone"], "badge-ok")

    def test_the_project_sentence_counts_what_is_actually_there(self):
        project = {"status": "accepted", "path": "/data/proj", "skills_roots": [
            {"relative": ".claude/skills", "exists": True},
            {"relative": ".cursor/skills", "exists": False}]}
        sentence = self._run("workspaceObservationSentence", {"workspaces": {"project": project}},
                             deps=["workspaceObservation"])
        self.assertEqual(sentence, "1 of 2 candidate roots exist there.")
        missing = self._run(
            "workspaceObservationSentence",
            {"workspaces": {"project": {"status": "missing", "path": "/x", "skills_roots": []}}},
            deps=["workspaceObservation"])
        self.assertIn("does not exist", missing)
        outside = self._run(
            "workspaceObservationSentence",
            {"workspaces": {"project": {"status": "outside-managed-roots", "path": "<redacted>", "skills_roots": []}}},
            deps=["workspaceObservation"])
        self.assertIn("outside the managed data root", outside)

    def test_the_idle_sentence_is_empty_once_a_path_has_been_observed(self):
        idle = self._run("workspaceIdleSentence", {
            "workspaces": {"project": {"status": "not-requested", "path": None, "skills_roots": []}},
            "loadingWorkspaces": False}, deps=["workspaceObservation"])
        self.assertIn("No project has been observed", idle)
        seen = self._run("workspaceIdleSentence", {
            "workspaces": {"project": {"status": "accepted", "path": "/x", "skills_roots": []}},
            "loadingWorkspaces": False}, deps=["workspaceObservation"])
        self.assertEqual(seen, "", "the idle line must not contradict the observation below it")

    def test_a_malformed_payload_does_not_throw(self):
        """Every field is optional: `_root_record` may carry none of the three."""
        rows = self._run("workspaceAdapters", {"workspaces": {"adapters": [
            {"id": "x", "tiers": [{"label": "T", "roots": [{}]}]},
            {"id": "y", "tiers": None, "precedence": None},
            {"id": "z"},
        ]}})
        self.assertEqual([r["id"] for r in rows], ["x", "y", "z"])
        self.assertEqual(rows[0]["tiers"][0]["roots"][0]["label"], "path unknown")
        self.assertEqual(rows[1]["tiers"], [])
        self.assertEqual(rows[1]["state"], "unknown precedence")
        self.assertEqual(rows[1]["sourceHost"], "")
        self.assertEqual(rows[2]["verified"], "")

    def test_null_payloads_are_empty_not_throwing(self):
        for state in ({"workspaces": None}, {"workspaces": {}}, {"workspaces": {"adapters": None, "project": None}}):
            self.assertEqual(self._run("workspaceAdapters", state), [])
            self.assertFalse(self._run("workspaceObservation", state)["requested"])


if __name__ == "__main__":
    unittest.main()