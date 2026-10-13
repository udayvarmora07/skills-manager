"""5.8a - the Doctor dialog's findings ledger.

The dialog used to print "Issues found." and then render two of the nine
finding keys `/api/doctor` can return. On the seeded library it therefore
said a library was in bad order and showed one orphaned directory while six
undecodable documents and one conflicting document - the keys that actually
explain the words - appeared nowhere in the product.

These contracts run the real `app.js` in a Node VM, because the failure this
task fixes is invisible to a source slice: nothing was wrong with the text of
the getters, they were simply never called for most of the payload.

`MEASURED_DOCTOR_PAYLOAD` is a recording of
``GET /api/doctor?scope=all`` against the seeded sandbox on 2026-10-13, not
a fixture invented to pass. Re-derive it with ``curl`` if the API changes;
the two coverage assertions below exist so a NEW finding key added by the
backend fails here rather than silently rendering nothing.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "skillsmgr/webui/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "skillsmgr/webui/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr/webui/styles.css").read_text(encoding="utf-8")

MEASURED_DOCTOR_PAYLOAD = {
    "data_dir": "/tmp/skillsmgr-v2-sandbox/data/skills-manager",
    "repair": [],
    "dirs": {"skills": "...", "trash": "...", "templates": "...", "backups": "...", "db": "..."},
    "db_integrity": "ok",
    "skills_on_disk": 46,
    "db_rows": 48,
    "orphan_dirs": ["abandoned-draft"],
    "stale_rows": [],
    "filesystem_index_drift": [],
    "undecodable_documents": [
        ".hidden-skill", "Upper_Case_Name", "abandoned-draft",
        "legacy-import-notes", "trailing-hyphen-", "with_underscore",
    ],
    "conflicting_documents": ["half-migrated-skill"],
    "transaction_artifacts": [],
    "temporary_files": [],
    "incomplete_transactions": [],
    "stale_snapshots": [],
    "trash_count": 3,
    "templates_count": 3,
    "ok": False,
    "scopes": [],
    "duplicates": [
        {
            "name": "commit-signoff-policy",
            "scopes": ["claude-code", "global"],
            "count": 2,
            "descriptions_differ": True,
            "records": [
                {"scope": "claude-code", "scope_label": "Claude Code"},
                {"scope": "global", "scope_label": "Global"},
            ],
        }
    ],
}

# Payload keys that are list-valued but are NOT findings, with the reason each
# is somewhere else. An empty list here means "correctly not a finding row".
NON_FINDING_LIST_KEYS = {
    "repair": "a list of things the backend says it CAN fix; its item shape is "
              "not observed anywhere in the product, so rendering a guessed "
              "row for it would invent a capability (RULES #12)",
    "scopes": "the per-scope summary, already rendered by the rail and the "
              "Overview meter; not a fault",
    "duplicates": "same name in several scopes - evidence, not a fault, and it "
                  "has its own section with its own action",
}

_HARNESS = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}),
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const comp = sandbox.app.computed, meth = sandbox.app.methods;
const names = process.argv[1];
const out = {computed_names: Object.keys(comp), method_names: Object.keys(meth)};
function ctx(report) {
  return {
    modals: {doctor: {loading: false, report: report}},
    formatNumber: (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","),
    scopes: [],
  };
}
const report = JSON.parse(process.argv[2]);
const c = ctx(report);
// Vue UNWRAPS a computed to its value before any consumer sees it, so the
// context carries the array itself, not the getter. That unwrap is also
// exactly why a function CALLED from a template must live in `methods`
// instead (5.5's trap) - this binding is the mechanism, shown.
c.doctorFindings = comp.doctorFindings.call(c);
out.findings = comp.doctorFindings.call(c).map((f) => ({key: f.key, label: f.label,
                                                       hint: f.hint, n: f.names.length}));
out.verdict = meth.doctorVerdict.call(c);
const group = (report.duplicates || [])[0] || {scopes: []};
out.labels = group.scopes.map((s) => meth.doctorScopeLabel.call(c, s));
out.labels_unknown = meth.doctorScopeLabel.call(c, 'no-such-scope');
console.log(JSON.stringify(out));
'''


def _run(report: dict) -> dict:
    script = str(ROOT) and ""
    proc = subprocess.run(
        ["node", "-e", _HARNESS, "x", json.dumps(report)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise AssertionError("node harness failed:\n" + proc.stderr[-2000:])
    return json.loads(proc.stdout)


def _finding_keys() -> list[str]:
    block = APP_JS[APP_JS.index("const DOCTOR_FINDINGS"):]
    block = block[: block.index("\n]);") + 4]
    return re.findall(r'key: "([a-z_]+)"', block)


class DoctorFindingTableContracts(unittest.TestCase):
    def test_every_finding_key_the_backend_can_return_is_in_the_table(self):
        """The failure this task fixes was a key dropped by omission. Assert
        the omission is impossible: each list-valued key of the payload is
        either a finding row or a named non-finding."""
        for key, value in MEASURED_DOCTOR_PAYLOAD.items():
            if not isinstance(value, list):
                continue
            if key in NON_FINDING_LIST_KEYS:
                continue
            self.assertIn(key, _finding_keys(), f"/api/doctor can return {key!r} "
                                                 f"and the Doctor dialog has no row for it")

    def test_the_table_names_no_key_the_backend_does_not_return(self):
        """The other direction. A key the API never sends would render a
        permanently empty row and read as coverage."""
        for key in _finding_keys():
            self.assertIn(key, MEASURED_DOCTOR_PAYLOAD)

    def test_each_finding_row_carries_a_label_and_a_hint_in_words(self):
        """A bare slug is the defect 5.4c/5.5 found twice. Every row says what
        the finding is and what it does to the library, in English."""
        for key in _finding_keys():
            block = APP_JS[APP_JS.index("const DOCTOR_FINDINGS"):]
            row = re.search(r'\{ key: "%s".*?\}' % re.escape(key), block, re.S)
            self.assertIsNotNone(row, key)
            self.assertNotIn("_", row.group(0).split('label: "')[1].split('"')[0])


class DoctorLedgerBehaviorContracts(unittest.TestCase):
    def setUp(self):
        self.out = _run(MEASURED_DOCTOR_PAYLOAD)

    def test_only_non_empty_findings_are_rendered(self):
        keys = [f["key"] for f in self.out["findings"]]
        self.assertEqual(keys, ["undecodable_documents", "conflicting_documents", "orphan_dirs"])

    def test_a_key_absent_from_the_payload_does_not_throw(self):
        """A partial payload - `degraded` on the stats route, a 200 with a key
        missing - must not blank the dialog."""
        out = _run({"ok": True, "orphan_dirs": ["x"]})
        self.assertEqual([f["key"] for f in out["findings"]], ["orphan_dirs"])

    def test_the_verdict_counts_rather_than_saying_issues_found(self):
        """The old banner said "Issues found." on every unhealthy library, so
        one orphaned directory and a hundred broken documents read the same."""
        self.assertEqual(self.out["verdict"], "8 findings across 3 checks.")

    def test_the_verdict_is_singular_for_one_finding(self):
        out = _run({"ok": False, "orphan_dirs": ["one"]})
        self.assertEqual(out["verdict"], "1 finding across 1 check.")

    def test_a_clean_library_says_so_and_an_unexplained_flag_does_not(self):
        """`report.ok` is the BACKEND's verdict. If it says unhealthy while no
        listed key is populated, the dialog does not hold the reason - and a
        green banner there would be inventing a clean bill of health."""
        self.assertIn("Nothing to repair", _run({"ok": True})["verdict"])
        self.assertIn("no finding explains it",
                      _run({"ok": False, "undecodable_documents": []})["verdict"])

    def test_scope_names_come_from_the_payload_not_the_wire_slug(self):
        """`d.scopes.join(', ')` printed `claude-code, global` one object away
        from the `scope_label` the same payload already carries."""
        self.assertEqual(self.out["labels"], ["Claude Code", "Global"])

    def test_an_unlisted_scope_falls_back_to_the_value_it_was_given(self):
        """RULES #12: never invent a name for something not observed."""
        self.assertEqual(self.out["labels_unknown"], "no-such-scope")

    def test_the_two_helpers_are_defined_where_the_template_calls_them(self):
        """A function CALLED from a template must live in `methods` - Vue
        unwraps a computed before the template sees it, and the render throws
        with no gate failing. 5.5's trap, recorded again where the next edit
        lands."""
        self.assertIn("doctorVerdict", self.out["method_names"])
        self.assertIn("doctorFindings", self.out["computed_names"])
        self.assertNotIn("doctorVerdict", self.out["computed_names"])


class DoctorDialogMarkupContracts(unittest.TestCase):
    def test_the_sentence_that_named_nothing_is_gone(self):
        self.assertNotIn("Issues found.", INDEX)

    def test_the_scope_slugs_are_not_printed_where_a_reader_sees_them(self):
        self.assertNotIn("d.scopes.join(', ')", INDEX)
        self.assertIn("d.scopes.map(doctorScopeLabel).join(', ')", INDEX)

    def test_findings_render_above_the_steady_state_facts(self):
        """What is wrong first. The seven fine numbers used to sit above the
        one row about a library in bad order."""
        body = INDEX[INDEX.index('data-modal="doctor"'):]
        self.assertLess(body.index("doctor-ledger"), body.index('class="kv doctor-facts"'))

    def test_a_finding_is_never_stated_twice(self):
        """The two rows the ledger owns were copied out of the facts table by
        the first draft; a reader saw `abandoned-draft` twice with no way to
        tell the second mention was not a second problem."""
        body = INDEX[INDEX.index('data-modal="doctor"'):]
        facts = body[body.index('class="kv doctor-facts"'):]
        self.assertNotIn("orphan_dirs", facts)
        self.assertNotIn("stale_rows", facts)

    def test_the_dialog_describes_no_layout_with_inline_styles(self):
        """4.7 retired 31 of these between remove and sync; three were left in
        Doctor, which is why it read as a different product."""
        body = INDEX[INDEX.index('data-modal="doctor"'):]
        body = body[: body.index("<!-- Stats -->")]
        self.assertNotIn("style=", body)

    def test_the_ledger_is_not_a_grid_of_equal_cards(self):
        """§B's equal-tile tell. A library can be wrong in nine ways in any
        combination, so the rows are a ledger separated by hairlines."""
        block = CSS[CSS.index("5.8a DOCTOR LEDGER"):]
        block = block[: block.index(".doctor-facts")]
        self.assertNotIn("grid-template-columns", block)
        self.assertIn(".doctor-finding {", block)
        self.assertIn("border-top", block)

# --------------------------------------------------------------------------
# 5.8b - the Stats dialog's arithmetic and its `<label>` with no control.
# --------------------------------------------------------------------------

MEASURED_STATS_PAYLOAD = {
    "total": 48, "active": 45, "disabled": 2, "trashed": 3, "db_rows": 48,
    "size_bytes": 701652, "db_bytes": 749568,
    "categories": {"engineering": 14, "quality": 7, "operations": 6,
                   "uncategorized": 6, "performance": 5, "security": 4,
                   "release": 2, "reference": 1},
    "scopes": [], "all_total": 45, "all_tokens": 169498,
    "largest": [], "window_tokens": 200000, "all_pct_window": 84.7,
}

_STATS_HARNESS = _HARNESS.replace(
    "out.labels = group.scopes",
    "c.modals.stats = {loading:false, report: JSON.parse(process.argv[2])};\n"
    "out.statsPopulation = meth.statsPopulationNote.call(c);\n"
    "out.statsCategory = meth.statsCategoryNote.call(c);\n"
    "out.statsMethods = ['statsPopulationNote','statsCategoryNote'].map((n)=>typeof meth[n]);\n"
    "out.labels = group.scopes")


def _run_stats(report: dict) -> dict:
    proc = subprocess.run(["node", "-e", _STATS_HARNESS, "x", json.dumps(report)],
                          capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        raise AssertionError("node harness failed:\n" + proc.stderr[-2000:])
    return json.loads(proc.stdout)


class StatsDialogContracts(unittest.TestCase):
    def setUp(self):
        self.out = _run_stats(MEASURED_STATS_PAYLOAD)

    def test_the_dialog_says_the_figures_do_not_add_up(self):
        """48 / 45 / 2 / 3 with disabled a SUBSET of active: 45+2+3 = 50. The
        old strip invited that arithmetic six times over."""
        note = self.out["statsPopulation"]
        self.assertIn("45 installed", note)
        self.assertIn("2 of them disabled", note)
        self.assertIn("3 trashed", note)
        self.assertIn("index rows", note)
        self.assertIn("do not add up", note)

    def test_the_residue_count_is_the_difference_not_a_constant(self):
        """48 - 45 - 3 = 0 here; the sentence must follow the payload rather
        than print a number someone typed once."""
        self.assertIn("with no directory on disk", self.out["statsPopulation"])
        self.assertEqual(_run_stats({**MEASURED_STATS_PAYLOAD, "total": 60})["statsPopulation"]
                         .count("index rows"), 1)

    def test_a_store_with_nothing_disabled_does_not_say_zero_of_them_disabled(self):
        out = _run_stats({**MEASURED_STATS_PAYLOAD, "disabled": 0})
        self.assertIn("45 installed", out["statsPopulation"])
        self.assertNotIn("disabled", out["statsPopulation"])

    def test_the_category_note_states_which_population_it_covers(self):
        """The categories sum to exactly the INSTALLED set (45), which the old
        dialog never said — a reader could not tell a subset from the whole."""
        self.assertIn("45", self.out["statsCategory"])
        self.assertIn("every installed skill has one", self.out["statsCategory"])

    def test_a_gap_between_the_sum_and_the_population_is_stated_not_hidden(self):
        out = _run_stats({**MEASURED_STATS_PAYLOAD, "active": 60})
        self.assertIn("15 carry none", out["statsCategory"])

    def test_uncategorized_is_named_as_a_placeholder_not_a_category(self):
        """It arrives from the store beside seven author-written keys and is
        this app's own stand-in for a missing `category:` line."""
        self.assertIn("placeholder", self.out["statsCategory"])
        self.assertIn("not a category anyone chose", self.out["statsCategory"])

    def test_an_empty_category_map_does_not_promise_a_total_of_zero(self):
        out = _run_stats({**MEASURED_STATS_PAYLOAD, "categories": {}})
        self.assertIn("none of them carries one", out["statsCategory"])

    def test_both_sentences_are_methods_not_computeds(self):
        """Both are CALLED from the template; a computed would be unwrapped to
        its value and the render would throw. Fifth instance of 5.5's trap."""
        self.assertEqual(self.out["statsMethods"], ["function", "function"])


class StatsDialogMarkupContracts(unittest.TestCase):
    def _stats_body(self) -> str:
        body = INDEX[INDEX.index('data-modal="stats"'):]
        return body[: body.index("<!-- Safe local source update -->")]

    def test_the_categories_heading_is_not_a_form_label_with_no_control(self):
        """It was `<div class="form-field full"><label>Categories</label></div>`:
        a <label> with no `for` and nothing inside it to label. A heading is
        what it is."""
        body = self._stats_body()
        self.assertNotIn("<label>Categories</label>", body)
        self.assertIn("stats-categories-title", body)

    def test_the_dialog_describes_no_layout_with_inline_styles(self):
        self.assertNotIn("style=", self._stats_body())

    def test_a_disabled_file_is_labelled_as_part_of_the_installed_set(self):
        """`Disabled` beside `Active` implied a partition of a set that does
        not partition here. The label states the relationship instead."""
        self.assertIn("Disabled, of the installed", self._stats_body())

    def test_the_first_tile_names_its_population_rather_than_a_total(self):
        """`total` is `COUNT(*) FROM skills` - the same value as `db_rows`, and
        identical to `db_rows` on the seed. Calling it "Total skills" is how a
        reader concludes 96 skills are on disk when 46 are."""
        self.assertIn("Indexed rows", self._stats_body())
        self.assertNotIn(">Total skills<", self._stats_body())

    def test_both_sentences_render_above_the_strip_they_describe(self):
        """A reader adds the tiles before reading a footnote."""
        body = self._stats_body()
        self.assertLess(body.index("statsPopulationNote"),
                        body.index('class="stat-grid stats-strip"'))

    def test_a_category_key_is_rendered_as_the_author_wrote_it(self):
        """`{{ cat }}` is whatever a skill's own frontmatter says - not a
        system slug to be translated, and not a label to be invented."""
        self.assertIn("<code>{{ cat }}</code>", self._stats_body())
