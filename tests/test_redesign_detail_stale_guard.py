"""4.4 follow-up — the detail pane's stale-response guard, which had no test.

The 4.4 iteration recorded this as an honest gap: `detailIsCurrent` decides
whether a list refresh may REUSE the detail it already has or must re-fetch it,
and it decides that on a signature built from the fields that decide whether the
document on disk is the document on screen. It is the guard against the pane
quietly showing yesterday's body under today's row, and it shipped with **zero**
coverage — not because it is hard to reach, but because nothing renders the
template in the stdlib suite, so the seam is the only place it can be observed.

Two things it must get right, and they pull against each other:

  * reusing a detail when the document CHANGED shows stale content while the row
    above it says something else — the worse failure, and the silent one;
  * re-fetching on every list refresh re-downloads the body and frontmatter of
    every selected skill on every poll, which is the cost 4.4 added the guard to
    avoid. A guard that always returns false is correct-looking and useless.

So the tests assert BOTH directions: a change in each field must invalidate, and
no change at all must not. A test that only asserted `false` would pass against
a guard that always returns false.

The methods come off the REAL `app.js` via `createApp`, captured rather than
mounted — the same seam the branch's other contract suites use, and the reason a
helper written as a method or a computed cannot pass this file by accident.
"""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BASE_ROW = {
    "name": "commit-signoff-policy",
    "scope": "global",
    "scope_label": "Global",
    "physical_path": "/data/skills/commit-signoff-policy/SKILL.md",
    "content_hash": "abc123",
    "disabled": False,
    "malformed": False,
    "addressable": True,
}

# Every field detailSignature() folds in, with a value that differs from
# BASE_ROW. A field silently dropped from the signature fails here rather than
# in production, where the symptom is the pane showing the wrong document body.
CHANGES = {
    "name": "release-checklist",
    "scope": "claude-code",
    "physical_path": "/data/skills/commit-signoff-policy/OTHER.md",
    "content_hash": "def456",
    "disabled": True,
    "malformed": True,
    "addressable": False,
}

# The missing-field case, which is why the signature uses `(x ? "1" : "0")`
# rather than interpolating a possibly-undefined value.
ABSENT = {"content_hash": "", "physical_path": "", "disabled": None,
          "malformed": None, "addressable": None}

BODY = r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}), apiText: async () => '', apiBlob: async () => new Uint8Array(),
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(s){return s;}, parseFrontmatter(){return {};}, formatCompat(){return '';},
    formatTools(){return '';}, groupLogicalSkills(){return [];},
    deriveLogicalSkillIdentity(){return {identities:[]};}, observedIdentity(){return {};},
    observeRecord(){return {};}, observedStateFor(){return 'active';},
    observedStateKeys(){return ['active'];}, observedSeverity(){return 'ok';},
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const M = sandbox.app.methods;

/* `detailIsCurrent` calls `this.detailSignature(...)`, so the context must
 * carry it — binding the REAL method, not a re-implementation, or the test
 * would pass against a stub that agrees with it. An earlier draft of this file
 * built a context of `{selected}` alone and Node threw on the first call;
 * that is the harness failing loudly rather than silently, which is the only
 * reason the fixture below is worth trusting. */
const ctx = (selected) => ({ selected, detailSignature: M.detailSignature });
const current = (selected, row) => M.detailIsCurrent.call(ctx(selected), row);
const signature = (row) => M.detailSignature(row);

const BASE = __BASE__;
const CHANGES = __CHANGES__;
const ABSENT = __ABSENT__;
const out = { sig: signature(BASE) };
for (const k of Object.keys(CHANGES)) {
  out['sig_' + k] = signature(Object.assign({}, BASE, { [k]: CHANGES[k] }));
}
out.unchanged = current(BASE, BASE);
out.missing = current(null, BASE);
out.other = current(Object.assign({}, BASE, { name: 'other' }), BASE);
out.otherScope = current(Object.assign({}, BASE, { scope: 'claude-code' }), BASE);
out.changed = current(Object.assign({}, BASE, { content_hash: CHANGES.content_hash }), BASE);
out.absent = current(BASE, Object.assign({}, BASE, ABSENT));
console.log(JSON.stringify(out));
'''


def _run() -> dict:
    script = (BODY.replace("__BASE__", json.dumps(BASE_ROW))
                  .replace("__CHANGES__", json.dumps(CHANGES))
                  .replace("__ABSENT__", json.dumps(ABSENT)))
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, cwd=str(ROOT)
    )
    if result.returncode != 0:
        raise AssertionError(f"app.js did not load in a VM:\n{result.stderr[-1500:]}")
    return json.loads(result.stdout)


class DetailStaleGuardTests(unittest.TestCase):
    def setUp(self):
        self.r = _run()

    # -- the guard -----------------------------------------------------
    def test_an_unchanged_row_reuses_the_detail_it_already_has(self):
        """The half that makes the guard worth having.

        Returning false here is not a safety bug — it re-fetches a document
        that has not changed — but it is exactly the per-poll body download 4.4
        added this guard to avoid, so a guard that always returns false would
        pass every other test in this file.
        """
        self.assertTrue(
            self.r["unchanged"],
            "an unchanged row must not force a re-download of its document body",
        )

    def test_a_missing_selection_is_never_current(self):
        self.assertFalse(self.r["missing"])

    def test_a_different_skill_is_never_current(self):
        self.assertFalse(self.r["other"], "the guard must not match on scope alone")

    def test_the_same_name_in_another_scope_is_never_current(self):
        self.assertFalse(
            self.r["otherScope"],
            "two scopes can hold the same name with different documents",
        )

    def test_a_changed_document_is_never_current(self):
        self.assertFalse(self.r["changed"])

    # -- the signature -------------------------------------------------
    def test_every_field_the_guard_depends_on_changes_the_signature(self):
        for field in CHANGES:
            with self.subTest(field):
                self.assertNotEqual(
                    self.r[f"sig_{field}"], self.r["sig"],
                    f"a change in `{field}` must invalidate the cached detail, "
                    f"or the pane shows one document under another's row",
                )

    def test_a_row_missing_optional_fields_is_never_current(self):
        """The undefined-vs-false trap.

        `detailSignature` must encode absent and falsy the same way on both
        sides, or a row the API returned without a `content_hash` compares
        unequal to the selected row forever and re-fetches on every poll.
        """
        self.assertFalse(
            self.r["absent"],
            "a row whose fields the API did not report must not be treated as "
            "identical to one it did",
        )


class SourceShapeTests(unittest.TestCase):
    """Cheap guards on the thing that made this untestable in the first place."""

    def setUp(self):
        self.app = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")

    def test_both_functions_live_in_methods_not_computed(self):
        # 2.1's defect: a helper written into the wrong block is valid JS and an
        # option Vue never reads. `detailIsCurrent` as a computed would be an
        # object where a call expects a function — and it took the whole app
        # down inside render. Both must be callable.
        methods = self.app.split("\n  methods: {", 1)[-1]
        self.assertIn("detailSignature(record)", methods)
        self.assertIn("detailIsCurrent(row)", methods)

    def test_the_signature_is_built_from_observed_fields_only(self):
        body = self.app.split("detailSignature(record) {", 1)[1].split("\n    }", 1)[0]
        for field in ("content_hash", "physical_path", "disabled", "malformed", "addressable"):
            with self.subTest(field):
                self.assertIn(field, body)
        # Nothing that implies a verdict. This product states observations.
        for verdict in ("effectiveState", "qualityScore", "trustVerdict", "winning"):
            self.assertNotIn(verdict, body)


if __name__ == "__main__":
    unittest.main()