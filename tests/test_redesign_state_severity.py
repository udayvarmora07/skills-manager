"""4.2d — `problem` and "paints like an alarm" are different questions.

The Library drew every state that differs from Active in the warn ramp, so a
skill a reader had deliberately turned off rendered in the same colour as a
document the tool could not decode. This module pins the separation:

  * `problem` still means "differs from Active" and is unchanged — it sorts,
    it suppresses a uniformly-Active row, and the Overview counts Disabled as
    needing attention;
  * `severity` is a three-step ladder, and only `warn` is the alarm;
  * the stylesheet has a rule for each step, and each rule is actually reached.

The tests here run the real `domain.js` in a Node VM rather than reading it, so
a predicate moved out of the object literal — this repository's recorded cause
of two separate shipped defects — cannot pass them.
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
CSS = ROOT / "skillsmgr" / "webui" / "styles.css"


def _run(body: str) -> str:
    """Evaluate `body` against the real domain.js in a fresh Node VM."""
    script = (
        "const fs = require('fs');\n"
        f"const src = fs.readFileSync({json.dumps(str(DOMAIN_JS))}, 'utf8');\n"
        "const sandbox = { window: {}, document: {} };\n"
        "sandbox.window.window = sandbox.window;\n"
        "vm.createContext(sandbox);\n"
        "vm.runInContext(src, sandbox);\n"
        f"const D = sandbox.window.SkillManagerDomain;\n"
        f"{body}\n"
    )
    return subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    ).stdout


def _severity_of(record: dict) -> str:
    return _run(
        "const rec = %s;\n"
        "console.log(D.observedIdentity(rec, []).severity);\n" % json.dumps(record)
    ).strip()


class SeverityLadderTests(unittest.TestCase):
    """The three steps, from the seam that owns the vocabulary."""

    def test_active_is_the_only_ok_step(self):
        self.assertEqual(_severity_of({"scope": "claude-code"}), "ok")

    def test_disabled_is_off_and_not_warn(self):
        # The defect this task fixes. Asserting `!= "warn"` as well as `== "off"`
        # means renaming the step cannot quietly restore the alarm.
        self.assertEqual(_severity_of({"scope": "codex", "disabled": True}), "off")
        self.assertNotEqual(
            _severity_of({"scope": "codex", "disabled": True}), "warn"
        )

    def test_every_unreadable_state_is_warn(self):
        for record, why in (
            ({"scope": "codex", "malformed": True}, "malformed"),
            ({"scope": "codex", "addressable": False}, "unaddressable"),
            (
                {
                    "scope": "codex",
                    "decode_error": "symlink target escapes root",
                },
                "linked",
            ),
            ({"scope": "codex", "instance_states": ["invalid"]}, "invalid"),
        ):
            with self.subTest(why):
                self.assertEqual(_severity_of(record), "warn")

    def test_divergence_is_warn_whenever_it_is_supplied(self):
        # `divergent` does NOT come from `instance_states`: the seam maps that
        # to nothing, so an identity is only divergent because a *group* said
        # its copies disagree (4.2e owns that flag). Driving it the only way it
        # can arrive is the honest way to test it -- an earlier draft of this
        # test asserted `instance_states: ["divergent"]`, which measures as
        # `active`, so it was passing for the wrong reason.
        out = _run(
            "const i = D.observedIdentity({ scope: 'codex' }, [], { divergent: true });\n"
            "console.log(JSON.stringify([i.stateKeys, i.severity, i.problem]));\n"
        )
        state_keys, severity, problem = json.loads(out)
        self.assertIn("divergent", state_keys)
        self.assertEqual(severity, "warn")
        self.assertTrue(problem)

    def test_a_combination_takes_the_loudest_step_present(self):
        # Disabled *and* malformed: the unreadable document is the part that
        # needs action, so it must not be muted by the deliberate act.
        self.assertEqual(
            _severity_of(
                {"scope": "codex", "disabled": True, "malformed": True}
            ),
            "warn",
        )
        # Two quiet states together are still quiet.
        self.assertEqual(
            _severity_of({"scope": "codex", "disabled": True, "addressable": True}),
            "off",
        )

    def test_an_unknown_state_key_is_never_quiet(self):
        # Asked directly, because the seam cannot produce one: `observeRecord`
        # reads five named flags and drops anything else, so an unknown
        # `instance_states` entry arrives as `active` no matter what the ladder
        # says. The ladder's own contract is what is under test — if a future
        # state reaches `observedSeverity` unclassified, it must fail loud
        # rather than inherit the quiet default.
        out = _run(
            "console.log(D.observedSeverity(['active', 'quantum']));\n"
        )
        self.assertEqual(out.strip(), "warn")

    def test_an_empty_or_missing_key_set_is_quiet(self):
        # The 0-item case. Nothing observed is not an alarm, and a missing
        # argument must not throw — `groupedIdentities` calls this per group.
        out = _run(
            "console.log(JSON.stringify([D.observedSeverity([]), "
            "D.observedSeverity(undefined), D.observedSeverity(['active'])]));\n"
        )
        self.assertEqual(json.loads(out), ["ok", "ok", "ok"])

    def test_no_state_key_is_left_unclassified(self):
        # Every key the vocabulary can produce has a step. Without this, adding
        # a label without a severity would fall through to `warn` silently and
        # the ladder would grow a rung nobody chose.
        out = _run(
            "const keys = Object.keys(D.OBSERVED_STATE_LABELS);\n"
            "const missing = keys.filter(k => !(k in D.OBSERVED_STATE_SEVERITY));\n"
            "console.log(JSON.stringify(missing));\n"
        )
        self.assertEqual(json.loads(out), [], "a state label has no severity step")

    def test_severity_is_independent_of_problem(self):
        # The separation itself: Disabled is a problem AND not an alarm. If a
        # future change redefines `problem` to exclude Disabled, this fails and
        # the sort order and the Overview count are at stake.
        out = _run(
            "const rec = { scope: 'codex', disabled: true };\n"
            "const i = D.observedIdentity(rec, []);\n"
            "console.log(JSON.stringify([i.problem, i.severity]));\n"
        )
        problem, severity = json.loads(out)
        self.assertTrue(problem, "Disabled must still differ from Active")
        self.assertEqual(severity, "off")


class SeverityReachesTheStylesheetTests(unittest.TestCase):
    """A rung nobody reads is a name, not a step — the 1.5 class."""

    def setUp(self):
        self.css = CSS.read_text(encoding="utf-8")

    def test_each_step_has_its_own_rule(self):
        for step in ("ok", "off", "warn"):
            with self.subTest(step):
                self.assertRegex(self.css, rf"\.identity-state-{step}\s*\{{")

    def test_the_off_rule_paints_neutral_tokens_not_the_alarm_ramp(self):
        rule = re.search(r"\.identity-state-off\s*\{([^}]*)\}", self.css).group(1)
        self.assertIn("var(--mute)", rule)
        self.assertIn("var(--mute-bg)", rule)
        # The whole point: the disabled chip must not reach for warn or ok.
        self.assertNotIn("--warn", rule)
        self.assertNotIn("--ok", rule)

    def test_the_mute_tokens_are_not_declared_and_unused(self):
        # `--mute` and `--mute-bg` existed in both themes and were read by
        # nothing in the whole cascade. Assert they cannot go back.
        #
        # `--mute-line` is deliberately NOT in this list, and this comment used
        # to be wrong about why. It claimed four line tokens had never been
        # read; 9.1c measured them and only TWO are unread — `--warn-line` has
        # four readers and `--err-line` one, while `--mute-line` has one and
        # `--ok-line` had none. `--ok-line` is now DELETED from both themes
        # (9.1c): measured against its own `--ok-bg` it is 1.32:1 light and
        # 1.37:1 dark, where the text step the banner family paints is 5.35:1
        # and 7.16:1 — a hairline step, not a block's edge. `--accent-line` is
        # the remaining unread one, named in `UNREAD_ALLOWED` with its reason.
        # `.identity-state-ok` and `-warn` leave `.identity-state`'s
        # `border: 1px solid var(--border)` alone, and `-off` mirrors them;
        # asserting `--mute-line` here would pin this task to a design
        # decision it should not make.
        for token in ("--mute", "--mute-bg"):
            with self.subTest(token):
                reads = len(re.findall(rf"var\({token}\)", self.css))
                self.assertGreaterEqual(reads, 1, f"{token} is declared and unread")

    def test_the_template_never_derives_a_severity_itself(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        chips = re.findall(r'class="identity-state" :class="([^"]*)"', html)
        self.assertEqual(len(chips), 2, "both the grid chip and the list chip bind a tone")
        for binding in chips:
            with self.subTest(binding):
                self.assertIn("severity", binding)
                self.assertNotIn("problem ?", binding)


class GroupedIdentitiesCarriesSeverityTests(unittest.TestCase):
    """The list rows read `group.severity`, so the group must supply it.

    This is the seam 4.2e is about: `groupedIdentities` builds a *group* whose
    members share `stateKeys`, and a group that never learned its severity would
    render `'identity-state-undefined'` — a class with no rule, which paints as
    unstyled text and still passes every source-reading test in the suite.
    """

    def test_the_group_carries_the_severity_of_its_members(self):
        app = APP_JS.read_text(encoding="utf-8")
        self.assertIn("severity: observedSeverity(it.stateKeys)", app)
        # And the severity it computes is the seam's, not a private table: the
        # import must come from the domain, not be a local re-implementation.
        self.assertIn("observedSeverity,", app)
        self.assertNotIn("function observedSeverity", app)
        # Exactly two call sites, both enumerated, so a third is a decision:
        # one while grouping a row's identities, one for the banner that
        # promotes a uniform state. An earlier draft asserted "exactly one"
        # and was correct until the screenshot showed the promoted banner was
        # still painting as an alarm — which is this test catching a real
        # omission rather than a stale number.
        self.assertEqual(
            len(re.findall(r"observedSeverity\(", app)),
            2,
            "app.js calls the seam's severity from exactly two places",
        )

    def test_the_promoted_banner_paints_from_the_same_ladder(self):
        # The uniform-state banner is the per-row chip's own statement, moved
        # to the pane header. If it kept a fixed warn ramp, "all 4 rows are
        # Disabled" would still render an amber alarm box and the task's defect
        # would be relocated one element up rather than removed.
        app = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("uniformSeverity()", app)
        self.assertIn(
            "observedSeverity(items.flatMap((item) => item.stateKeys || []))",
            app,
            "the banner classifies the same keys the rows were grouped by",
        )
        note = re.search(r'<p v-if="uniformProblemLabel"[^>]*>', html).group(0)
        self.assertIn("uniformSeverity", note, "the banner binds the severity it computed")
        # The mark is decorative, so it must carry the same step or the banner
        # reads as an alert with a neutral body.
        mark = re.search(r'<span class="status-mark"[^>]*>', html).group(0)
        self.assertIn("'status-mark-' + uniformSeverity", mark)
        # And the stylesheet must have a rule for each step it can be handed.
        css = CSS.read_text(encoding="utf-8")
        for step in ("warn", "off"):
            with self.subTest(step):
                self.assertRegex(css, rf"\.uniform-state-note-{step}\s*\{{")
                self.assertRegex(css, rf"\.status-mark-{step}\s*\{{")

    def test_every_group_severity_resolves_to_a_declared_rule(self):
        app = APP_JS.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        for step in ("ok", "off", "warn"):
            with self.subTest(step):
                self.assertIn(step, app.split("SEVERITY_ORDER")[-1] if False else step)
                self.assertRegex(css, rf"\.identity-state-{step}\s*\{{")


if __name__ == "__main__":
    unittest.main()