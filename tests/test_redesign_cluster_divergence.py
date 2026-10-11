"""4.2e — divergence belongs to the cluster, not to any one copy inside it.

A chip labelled *Claude Code* read "Active · Divergent", asserting that Claude
Code's own document was defective. What is observed is narrower: two copies do
not match each other. Neither copy is malformed, unreachable, or disabled.

This module pins the separation in both directions, because either half alone
is satisfied by the wrong fix:

  * a single copy is never `Divergent` — the per-copy claim is gone;
  * the group still reports `Divergent` — the observation moved, it did not
    disappear;
  * identical copies are not divergent — the control that stops "delete it"
    from passing.

The seam is loaded in a Node VM rather than read, so a predicate moved outside
the object literal cannot pass these.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_JS = ROOT / "skillsmgr" / "webui" / "domain.js"
APP_JS = ROOT / "skillsmgr" / "webui" / "app.js"
INDEX_HTML = ROOT / "skillsmgr" / "webui" / "index.html"

SCOPES = [
    {"id": "global", "label": "Global", "kind": "global", "consumer": "skills-manager"},
    {"id": "claude-code", "label": "Claude Code", "kind": "agent", "consumer": "claude-code"},
    {"id": "agents", "label": "Agents", "kind": "agent", "consumer": "shared-agent-skills"},
]

# Two copies of one logical skill whose CONTENT disagrees, neither of which is
# disabled, unaddressable or malformed. Exactly the seeded shape: 6 of 96 rows.
DIVERGENT_PAIR = [
    {"name": "commit-signoff-policy", "scope": "claude-code", "scope_label": "Claude Code",
     "consumer": "claude-code", "physical_path": "/a/one", "content_hash": "aaa"},
    {"name": "commit-signoff-policy", "scope": "global", "scope_label": "Global",
     "consumer": "skills-manager", "physical_path": "/b/two", "content_hash": "bbb"},
]

LONE_COPY = [
    {"name": "api-contract-auditor", "scope": "global", "scope_label": "Global",
     "consumer": "skills-manager", "physical_path": "/only/one", "content_hash": "aaa"},
]


def _groups(records, scopes=SCOPES):
    script = (
        "const fs = require('fs'), vm = require('vm');\n"
        f"const s = {{ window: {{}} }};\n"
        f"vm.runInNewContext(fs.readFileSync({json.dumps(str(DOMAIN_JS))}, 'utf8'), s);\n"
        f"console.log(JSON.stringify(s.window.SkillManagerDomain.groupLogicalSkills("
        f"{json.dumps(records)}, {json.dumps(scopes)})));\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class DivergenceIsAClusterFactTests(unittest.TestCase):
    def test_no_single_copy_is_ever_called_divergent(self):
        group = _groups(DIVERGENT_PAIR)[0]
        self.assertTrue(group["divergent"])
        self.assertEqual(len(group["identities"]), 2)
        for identity in group["identities"]:
            with self.subTest(identity["scopeLabel"]):
                self.assertNotIn("divergent", identity["stateKeys"])
                self.assertNotIn("Divergent", identity["stateLabel"])
                # The per-copy observation survives intact.
                self.assertEqual(identity["stateLabel"], "Active")
                self.assertEqual(identity["severity"], "ok")

    def test_the_group_still_reports_the_disagreement(self):
        # The half that stops "delete it" from being a fix.
        group = _groups(DIVERGENT_PAIR)[0]
        self.assertIn("divergent", group["states"])
        self.assertIn("Divergent", group["stateLabels"])
        self.assertFalse(group["identical"])

    def test_identical_copies_are_not_divergent(self):
        same = [dict(r, content_hash="identical") for r in DIVERGENT_PAIR]
        group = _groups(same)[0]
        self.assertFalse(group["divergent"])
        self.assertNotIn("Divergent", group["stateLabels"])
        self.assertTrue(group["identical"], "two matching copies ARE identical")
        for identity in group["identities"]:
            self.assertEqual(identity["stateLabel"], "Active")

    def test_a_lone_copy_can_never_be_divergent(self):
        group = _groups(LONE_COPY)[0]
        self.assertFalse(group["divergent"])
        self.assertFalse(group["identical"], "one copy is not a cluster")
        self.assertEqual(group["identities"][0]["stateLabel"], "Active")

    def test_a_disabled_copy_of_a_divergent_cluster_keeps_both_facts(self):
        # The interesting overlap: one copy is off AND the cluster disagrees.
        # Removing the per-copy claim must not remove either observation.
        mixed = [dict(DIVERGENT_PAIR[0]), dict(DIVERGENT_PAIR[1], disabled=True)]
        group = _groups(mixed)[0]
        self.assertTrue(group["divergent"])
        self.assertIn("Divergent", group["stateLabels"])
        by_scope = {i["scopeLabel"]: i for i in group["identities"]}
        self.assertEqual(by_scope["Claude Code"]["stateLabel"], "Active")
        self.assertEqual(by_scope["Claude Code"]["severity"], "ok")
        self.assertEqual(by_scope["Global"]["stateLabel"], "Disabled")
        self.assertEqual(by_scope["Global"]["severity"], "off")

    def test_a_malformed_copy_still_warns_while_its_sibling_does_not(self):
        # Divergence must not become a way to stop reporting a real defect.
        mixed = [dict(DIVERGENT_PAIR[0]), dict(DIVERGENT_PAIR[1], malformed=True)]
        group = _groups(mixed)[0]
        by_scope = {i["scopeLabel"]: i for i in group["identities"]}
        self.assertEqual(by_scope["Claude Code"]["severity"], "ok")
        self.assertEqual(by_scope["Global"]["stateLabel"], "Malformed")
        self.assertEqual(by_scope["Global"]["severity"], "warn")


class TheRowStatesItOnceTests(unittest.TestCase):
    """`clusterDisagreement` is the other half of the move."""

    def setUp(self):
        self.app = APP_JS.read_text(encoding="utf-8")
        self.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_the_row_binds_the_cluster_statement(self):
        # The ELEMENT must be gated on the call, not merely contain it. An
        # earlier draft asserted `"clusterDisagreement(s)" in html`, which a
        # `v-if="false"` still satisfies — the mutation that exposed this
        # rendered nothing and passed. Extracting the tag and requiring the
        # `v-if` to BE the call is what can fail.
        tag = re.search(r'<span v-if="clusterDisagreement\(s\)"[^>]*>', self.html)
        self.assertIsNotNone(
            tag, "the disagreement element must be gated on clusterDisagreement(s)"
        )
        self.assertIn("identity-disagreement", tag.group(0))
        # And the chips above it still bind per-copy severity, so the row has
        # both halves: each copy's own state, and the disagreement between them.
        self.assertIn("group.severity", self.html)
        self.assertIn("identity.severity", self.html)

    def test_it_refuses_to_speak_when_there_is_nothing_to_say(self):
        # 0 and 1 item cases. A single copy is not a cluster, so a divergence
        # claim on it would be the exact class of invented claim this product
        # is built not to make.
        for guard in ("this.libraryMode !== \"library\"",
                      "if (!item.divergent) return null",
                      "if (size < 2) return null"):
            with self.subTest(guard):
                self.assertIn(guard, self.app)

    def test_it_states_an_observed_count_not_a_computed_conclusion(self):
        self.assertIn("this.formatNumber(size)", self.app)
        self.assertIn('state: "Divergent"', self.app)

    def test_no_scope_name_is_attributed_the_divergence(self):
        # The label is the copy count, never a scope: naming a scope is what
        # made the original chip a false claim.
        self.assertNotIn("scopeLabel", self.app.split("clusterDisagreement(item) {")[1].split("setLibraryMode")[0])


if __name__ == "__main__":
    unittest.main()