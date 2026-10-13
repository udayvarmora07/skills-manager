"""5.5 — the Quality hygiene report's contracts.

Four defects, all measured on the seeded sandbox rather than reasoned about,
which is why the numbers are in the docstrings:

  1. The summary was twelve `.overview-metrics` cells on a `repeat(3, 1fr)`
     grid — four rows of identical boxes, the shape DESIGN-V2 §B refuses. On the
     real seed five of the nine category tiles read **0**, because the category
     cannot fire in that scope, and the reader could not tell a clean check
     from a check that never ran.
  2. One tile ADDED three independent category counts
     (`same-name-identical + exact-document-duplicate + exact-instruction-duplicate`)
     and labelled the total "independent groups", eleven lines below a hint that
     says "findings overlap by design". On the seed the three are 3 / 1 / 0 —
     a total of 4 that means nothing, built out of a category that never fires.
  3. Each finding group was headed by its **wire slug**: `activation-description`,
     `context-over-limit`, `missing-document`. `text-transform: capitalize` was
     doing the work of a label. Same class as 5.4c's `outside-managed-roots`,
     ten more instances of it.
  4. The severity `<select>` offered **Unavailable** — a value no finding in
     the list ever carries (`summary.unavailable` counts checks that could not
     run: 109 of them, against 92 findings that are all error/warning/info).
     The control could only ever render its own empty state.

The ledger is a pure function in `domain.js`, so it is exercised in a Node VM
against the real module and the real payload rather than by reading its
source — MAP.md records five cases of a comment describing behaviour the
markup does not implement, and source reading is how that class of test
stays green.
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
DOMAIN = (ROOT / "skillsmgr/webui/domain.js").read_text()

# The seeded sandbox's real histogram, captured from
# `curl 'localhost:8791/api/doctor?scope=all&hygiene=1'` on 2026-10-13.
SEED_COUNTS = {
    "activation-description": 59,
    "context-over-limit": 3,
    "divergent-name": 6,
    "document-conflict": 1,
    "exact-document-duplicate": 1,
    "missing-document": 1,
    "same-name-identical": 3,
    "unaddressable": 4,
    "unreadable-document": 7,
    "validation": 7,
}
SEED_SUMMARY = {
    "observed_records": 106, "physical_instances": 106, "logical_names": 97,
    "errors": 23, "warnings": 65, "informational": 4, "unavailable": 109,
    "finding_count": 92, "findings_returned": 92,
    "findings_truncated": False, "partial": False,
}

LEDGER_JS = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = { window: {}, document: {}, URL, setTimeout, clearTimeout, console };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const D = sandbox.window.SkillManagerDomain;
const counts = JSON.parse(process.argv[1]);
console.log('###' + JSON.stringify(D.hygieneCategoryLedger(counts)));
console.log('@@@' + JSON.stringify({
  order: D.HYGIENE_CATEGORIES.map((c) => c.slug),
  labels: D.HYGIENE_CATEGORIES.map((c) => c.label),
  details: D.HYGIENE_CATEGORIES.map((c) => c.detail),
}));
console.log('%%%' + JSON.stringify([
  D.hygieneCategoryLabel('same-name-identical'),
  D.hygieneCategoryLabel('a-category-this-build-has-never-seen'),
  D.hygieneCategoryLabel(null),
]));
'''


def ledger(counts):
    """Run the REAL `hygieneCategoryLedger` against a counts payload."""
    out = subprocess.run(
        ["node", "-e", LEDGER_JS, json.dumps(counts)],
        cwd=str(ROOT), capture_output=True, text=True, check=True,
    ).stdout
    result = None
    meta = {}
    for line in out.splitlines():
        if line.startswith("###"):
            result = json.loads(line[3:])
        elif line.startswith("@@@"):
            meta = json.loads(line[3:])
        elif line.startswith("%%%"):
            meta["label_probe"] = json.loads(line[3:])
    assert result is not None, out
    return result, meta


class HygieneLedger(unittest.TestCase):
    """The pure function, run in Node against the real domain module."""

    def test_observed_rows_carry_a_label_a_sentence_and_the_real_count(self):
        rows, _ = ledger(SEED_COUNTS)
        self.assertEqual(len(rows["observed"]), 10)
        by_slug = {r["slug"]: r for r in rows["observed"]}
        self.assertEqual(by_slug["activation-description"]["count"], 59)
        self.assertEqual(
            by_slug["activation-description"]["label"], "Activation description")
        self.assertTrue(by_slug["activation-description"]["detail"])
        for row in rows["observed"]:
            self.assertNotIn("-", row["label"].split()[0],
                             "a wire slug leaked into a label: %r" % row["label"])

    def test_a_zero_is_reported_as_a_check_that_ran_not_as_a_finding(self):
        rows, _ = ledger(SEED_COUNTS)
        silent = {r["slug"] for r in rows["silent"]}
        # Six of the sixteen categories cannot fire on the seed. Each one is a
        # check that RAN, so it belongs in `silent` — never dropped, never
        # rendered as a zero tile beside five that matter.
        self.assertIn("near-duplicate", silent)
        self.assertIn("broken-reference", silent)
        self.assertIn("source-lock-drift", silent)
        self.assertEqual(len(rows["silent"]), 6)
        self.assertEqual(rows["observed"] + rows["silent"],
                         rows["observed"] + rows["silent"])
        every = {r["slug"] for r in rows["observed"]} | silent
        self.assertEqual(len(every), 16, "a category went missing from the ledger")

    def test_the_three_duplicate_categories_are_three_rows_not_one_total(self):
        """The old tile summed three independent histograms and called the
        result "independent groups" while the copy above it said findings
        overlap. They must never be added again."""
        rows, _ = ledger(SEED_COUNTS)
        slugs = [r["slug"] for r in rows["observed"]]
        for slug in ("same-name-identical", "exact-document-duplicate"):
            self.assertIn(slug, slugs)
        self.assertNotIn("exact-instruction-duplicate", slugs)
        self.assertNotIn(APP, "qualityCategoryCount")

    def test_an_unlabelled_category_is_named_not_dropped(self):
        rows, _ = ledger({**SEED_COUNTS, "a-brand-new-category": 4})
        self.assertEqual(rows["unlabelled"], ["a-brand-new-category"])
        self.assertEqual(len(rows["observed"]), 10,
                         "a server-side category must not push a known one out")

    def test_an_unknown_slug_falls_back_to_the_wire_value_not_to_an_invention(self):
        """RULES #12: inventing a label for a state this build has never
        observed would be a claim."""
        _, meta = ledger({})
        known, unknown, nullish = meta["label_probe"]
        self.assertEqual(known, "Same name, identical copies")
        self.assertEqual(unknown, "a-category-this-build-has-never-seen")
        self.assertEqual(nullish, "")

    def test_the_ledger_order_is_the_order_the_server_ranks_findings_in(self):
        _, meta = ledger({})
        self.assertEqual(meta["order"][:4], [
            "missing-document", "unreadable-document", "document-conflict", "unaddressable"])
        self.assertEqual(len(set(meta["labels"])), len(meta["labels"]),
                         "two categories would print the same heading")
        self.assertTrue(all(d.endswith(".") for d in meta["details"]))


class HygieneMarkup(unittest.TestCase):
    """The block itself."""

    def setUp(self):
        block = re.search(
            r'<section class="quality-section quality-hygiene"(.*?)</section>\s*\n\s*</template>',
            HTML, re.S)
        self.assertIsNotNone(block, "the hygiene section is gone from index.html")
        self.block = block.group(1)

    def test_no_grid_of_equal_metric_cells_is_left(self):
        self.assertNotIn("quality-hygiene-metrics", HTML)
        self.assertNotIn("quality-hygiene-metrics", CSS)
        self.assertNotIn("overview-metrics quality-hygiene", self.block)

    def test_the_strip_is_a_sentence_and_a_ledger_not_twelve_boxes(self):
        self.assertIn('<div class="quality-strip" role="group"', self.block)
        self.assertIn("qualitySeverityLedger", self.block)
        for key in ("physical_instances", "finding_count", "findings_truncated", "partial"):
            self.assertIn(key, self.block, "%s is not accounted for" % key)

    def test_the_ledger_is_a_table_with_a_scoped_header_and_the_wire_slug_kept(self):
        self.assertIn('<table v-else class="quality-ledger">', self.block)
        self.assertIn('scope="col"', self.block)
        self.assertIn('scope="row"', self.block)
        self.assertIn('<code class="quality-ledger-slug">{{ row.slug }}</code>', self.block)

    def test_a_group_heading_is_a_sentence_and_not_the_wire_slug(self):
        self.assertIn("<h3>{{ qualityCategoryLabel(group.category) }}</h3>", HTML)
        self.assertNotIn("<h3>{{ group.category }}</h3>", HTML)

    def test_the_severity_filter_offers_no_value_no_finding_carries(self):
        select = re.search(r'<select id="quality-severity-filter".*?</select>', self.block, re.S)
        self.assertIsNotNone(select)
        options = re.findall(r'<option value="([^"]+)"', select.group(0))
        self.assertEqual(sorted(options), ["all", "error", "info", "warning"])
        self.assertNotIn("unavailable", options)
        # 109 unavailable checks, 92 findings, none of them unavailable.
        self.assertGreater(SEED_SUMMARY["unavailable"], SEED_SUMMARY["finding_count"])
        self.assertEqual(SEED_SUMMARY["finding_count"],
                         SEED_SUMMARY["errors"] + SEED_SUMMARY["warnings"]
                         + SEED_SUMMARY["informational"])

    def test_degraded_evidence_is_still_shown_after_the_tile_was_dropped(self):
        self.assertIn("qualityHygiene.degraded", self.block)
        self.assertIn("Degraded sections", self.block)

    def test_the_copy_still_refuses_a_combined_score(self):
        for phrase in ("No combined quality score", "no combined score",
                       "do not produce a combined score"):
            self.assertIn(phrase, HTML)


class HygieneComputed(unittest.TestCase):
    """`qualitySeverityLedger` and `qualityCategoryLedger`, run against the
    real app options the way Vue would bind them."""

    SCRIPT = r'''
const fs = require('fs'), vm = require('vm');
const dom = { window: {}, document: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), dom);
const sandbox = {
  window: { SkillManagerDomain: dom.window.SkillManagerDomain },
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  URL, setTimeout, clearTimeout, console
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
'''

    def test_the_severity_ledger_names_the_unavailable_number(self):
        """`unavailable` counts checks that could not run. Rendering it in the
        same column as `errors` invites reading it as a count of findings."""
        script = self.SCRIPT + r'''
const o = sandbox.app;
const ctx = { qualityHygiene: { summary: JSON.parse(process.argv[1]),
                                category_counts: JSON.parse(process.argv[2]) } };
ctx.qualityHygieneSummary = o.computed.qualityHygieneSummary.call(ctx);
const sev = o.computed.qualitySeverityLedger.call(ctx);
const led = o.computed.qualityCategoryLedger.call(ctx);
console.log('###' + JSON.stringify({ sev, observed: led.observed.length,
                                    silent: led.silent.length, unlabelled: led.unlabelled }));
'''
        out = subprocess.run(
            ["node", "-e", script, json.dumps(SEED_SUMMARY), json.dumps(SEED_COUNTS)],
            cwd=str(ROOT), capture_output=True, text=True, check=True).stdout
        payload = json.loads(
            [l for l in out.splitlines() if l.startswith("###")][0][3:])
        self.assertEqual([row["severity"] for row in payload["sev"]],
                         ["error", "warning", "info", "unavailable"])
        self.assertEqual([row["count"] for row in payload["sev"]],
                         [23, 65, 4, 109])
        unavailable = [r for r in payload["sev"] if r["severity"] == "unavailable"][0]
        self.assertIn("not observed", unavailable["label"])
        self.assertNotIn("finding", unavailable["label"].lower())
        self.assertEqual((payload["observed"], payload["silent"], payload["unlabelled"]),
                         (10, 6, []))


class HygieneStyle(unittest.TestCase):
    def test_the_new_block_exists_and_the_old_grid_rule_is_gone(self):
        self.assertIn("5.5 — the hygiene report's summary", CSS)
        self.assertNotIn(".quality-hygiene-metrics {", CSS)

    def test_the_strip_is_a_flex_row_not_a_grid_of_cards(self):
        block = CSS.split("5.5 — the hygiene report's summary")[1]
        strip = block.split(".quality-strip {")[1].split("}")[0]
        self.assertIn("border-top: 1px solid var(--border)", strip)
        self.assertIn("border-bottom: 1px solid var(--border)", strip)
        self.assertNotIn("grid-template-columns", strip)
        self.assertIn("list-style: none", block.split(".quality-severity-ledger {")[1].split("}")[0])

    def test_severity_colours_use_declared_tokens(self):
        for token in ("var(--err)", "var(--warn)"):
            self.assertIn(token, CSS)

    def test_the_ledger_table_is_fixed_and_scrolls_only_in_its_own_wrap(self):
        self.assertIn("table-layout: fixed", CSS)
        self.assertIn(".quality-ledger .num", CSS)