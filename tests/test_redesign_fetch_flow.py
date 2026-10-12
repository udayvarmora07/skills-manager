"""Contracts for the 5.2 registry Fetch -> Review -> Trust -> Commit stepper.

`fetch` is the one registry operation that WRITES. Stage one stages a private,
expiring review under the data dir and installs nothing; stage two is the
reader looking at it; stage three sends `review_id` + `trust_confirmed` and
writes the skill into the global store. The route enforces the split itself
(`webapp.py:128` refuses a commit without `trust_confirmed`, `:130` refuses
`trust_confirmed` without a `review_id`), so the UI's job is to make a three
step transaction legible without turning it into a score.

**Every test here is written to be able to fail.** Where a test could pass
with the feature deleted outright, the control it must not swallow is
asserted in the same test — see
`test_the_steps_are_derived_from_the_response_and_not_from_a_variable`.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

WEBUI = Path(__file__).resolve().parents[1] / "skillsmgr" / "webui"
APP_JS = WEBUI / "app.js"
INDEX_HTML = WEBUI / "index.html"
STYLES_CSS = WEBUI / "styles.css"
TOKEN_GATE = Path(__file__).resolve().parents[1] / "check_design_tokens.py"

APP = APP_JS.read_text(encoding="utf-8")
HTML = INDEX_HTML.read_text(encoding="utf-8")
CSS = STYLES_CSS.read_text(encoding="utf-8")


def _getter(name):
    """Brace-balanced source of ONE top-level getter or method.

    The optional `async ` matters: without it `commitRegistryReview` and
    `runRegistry` are simply not found, and a helper that reports "no such
    method" for two of the three methods a file owns is a helper that would
    have been written to hide a regression.
    """
    match = re.search(r"\n    (?:async )?" + re.escape(name) + r"\(", APP)
    assert match, "no top-level definition named " + name
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


def _fetch_half():
    """The Fetch & trust half of the Install view, sliced at its own boundary.

    Keyed on the MODE, not on the directive. The three halves were
    `v-if`/`v-else`/`v-else` and Vue silently dropped the middle one, so
    `mode === "runner"` rendered the fetch half with no error anywhere. They
    are three independent `v-if`s now; matching on the mode means this helper
    is correct either way, and `test_all_three_workflow_halves_are_reachable`
    is what keeps it honest.
    """
    block = HTML[HTML.index('<div v-else-if="view === \'install\'" class="install-shell"'):]
    block = block[:block.index('<div v-else-if="view === \'skills\'" class="detail-inner">')]
    block = re.sub(r"<!--.*?-->", "", block, flags=re.S)
    return block[block.index("<template v-if=\"install.mode === 'fetch'\">"):]


# A registry `fetch` response, shaped from `registry_review_public`
# (`registry.py:435`) and the enrichment `_prepare_registry_skill` adds
# (`cli_handlers.py:1518`). Deliberately RAGGED in the ways the real payloads
# are: the upstream hash is present and NOT verified, one warning carries no
# message, and the risk list holds a finding with no `why`.
REVIEW = {
    "review_id": "a1b2c3",
    "review_expires_at": "2026-10-13T12:00:00+00:00",
    "registry": {
        "id": "vercel-labs/agent-skills/web-perf",
        "source": "vercel-labs/agent-skills",
        "slug": "web-perf",
        "page_url": "https://skills.sh/vercel-labs/agent-skills/web-perf",
        "remote_hash": "deadbeef",
        "snapshot_hash": "aaa111",
        "registry_hash": "bbb222",
        "hash_verified": False,
        "normalization": "frontmatter.name 'web-perf-2' normalized to slug 'web-perf'",
        "cache_state": "miss",
        "file_count": 3,
    },
    "inspection": {
        "validation": {"valid": True, "warnings": [
            {"level": "warning", "key": "description-length", "message": "description is 312 characters"},
            {"level": "info", "key": "no-description"},
        ]},
        "risk": {
            "policy": "advisory-only; heuristic evidence is not a safety or trust verdict",
            "findings": [
                {"kind": "script", "severity": "high", "evidence": "rm -rf ./build", "confidence": "heuristic", "why": "destructive shell pattern", "advisory": True},
                {"kind": "tool-grant", "severity": "low", "evidence": "allowed-tools: Bash(*)", "advisory": True},
            ],
        },
        "reviewed_before_install": False,
        "review_required": True,
        "target_scope": "global",
    },
}


def _load_options():
    """Evaluate the real `options` object in a Node VM and return it."""
    script = r'''
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
  setTimeout, clearTimeout, console
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const o = sandbox.app;
const out = {};
for (const name of JSON.parse(process.argv[1])) {
  const fn = (o.computed && o.computed[name]) || o.methods[name];
  out[name] = String(fn);
}
console.log(JSON.stringify(out));
'''
    names = ["installFetchSteps", "installFetchStepIndex", "installFetchFacts",
             "installFetchWarnings", "installFetchRisk", "installFetchExpiry",
             "installFetchOutcome", "installWorkflows", "installScopeNote"]
    result = subprocess.run(["node", "-e", script, json.dumps(names)],
                            capture_output=True, text=True, cwd=str(WEBUI.parent.parent), check=True)
    return json.loads(result.stdout)


def _run_getters(state_patch, names):
    """Call real getters against a patched `install` object and return JSON."""
    script = r'''
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
  setTimeout, clearTimeout, console
};
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const o = sandbox.app;
const ctx = { install: JSON.parse(process.argv[1]) };
// Vue makes one computed able to read another; a plain object cannot. The two
// that cross-reference are bound first, so `installFetchStepIndex` sees the
// same steps the stepper getter produced rather than `undefined`.
for (const dep of ['installFetchSteps']) { ctx[dep] = o.computed[dep].call(ctx); }
const out = {};
for (const name of JSON.parse(process.argv[2])) {
  // Vue's options object holds these as PLAIN functions, not ES getters, so
  // `getOwnPropertyDescriptor(...).get` is undefined and a `.call` on it is
  // the classic "cannot read properties of undefined" — which reads as a
  // product failure and is not one.
  const fn = (o.computed && o.computed[name]) || o.methods[name];
  try { out[name] = fn.call(ctx); } catch (e) { out[name] = 'THREW: ' + e.message; }
}
console.log(JSON.stringify(out));
'''
    return json.loads(subprocess.run(
        ["node", "-e", script, json.dumps(state_patch), json.dumps(names)],
        capture_output=True, text=True, cwd=str(WEBUI.parent.parent), check=True).stdout)


class FetchStepperContracts(unittest.TestCase):
    def test_the_view_owns_the_fetch_operation_and_the_read_strip_still_has_three_tabs(self):
        """`fetch` is a workflow, not a fourth source. It writes, so it must not
        sit inside a strip whose three members are reads — and it must not be
        typed twice, or the strip and the workflow could disagree."""
        self.assertIn('{ id: "fetch", label: "Fetch & trust" }', APP)
        self.assertNotIn('{ id: "fetch", label: "Fetch" }', APP)
        strip = _getter("installSources")
        for forbidden in ('"fetch"', "'fetch'"):
            self.assertNotIn(forbidden, strip)
        self.assertEqual(strip.count('id: "'), 3)

    def test_switching_to_fetch_writes_the_operation_the_route_switches_on(self):
        """`runRegistry` sends `fetch: op === "fetch"`, so the workflow has to
        put `fetch` on `registryOp`. A workflow that only set `mode` would
        leave the press sending `browse` — a read, on the half whose sentence
        promises to write a review."""
        body = _getter("selectInstallWorkflow")
        self.assertIn('this.install.registryOp = "fetch"', body)
        # ... and coming BACK must restore a tab the strip can show, or the
        # tablist renders with no tab selected.
        self.assertIn('id === "registry" && !this.installSources.some', body)

    def test_the_steps_are_derived_from_the_response_and_not_from_a_variable(self):
        """A step that a handler could set would let the strip claim a fetch
        that never happened. Asserted by running the real getters against a
        hostile patch: claiming step 2 with no `review` in state must produce
        the IDLE steps, and the test also pins the full step-3 shape so the
        three branches cannot be collapsed into one."""
        options = _load_options()
        self.assertIn("this.install.review", options["installFetchSteps"])
        self.assertIn("this.install.committed", options["installFetchSteps"])

        names = ["installFetchSteps", "installFetchStepIndex"]
        idle = _run_getters({"mode": "fetch", "review": None, "committed": None}, names)
        self.assertEqual([s["state"] for s in idle["installFetchSteps"]], ["current", "todo", "todo"])
        self.assertEqual(idle["installFetchStepIndex"], 0)

        reviewing = _run_getters({"mode": "fetch", "review": REVIEW, "committed": None}, names)
        self.assertEqual([s["state"] for s in reviewing["installFetchSteps"]], ["done", "current", "todo"])
        self.assertEqual(reviewing["installFetchStepIndex"], 1)

        done = _run_getters({"mode": "fetch", "review": None,
                             "committed": {"name": "web-perf", "path": "/tmp/web-perf"}}, names)
        self.assertEqual([s["state"] for s in done["installFetchSteps"]], ["done", "done", "done"])
        self.assertEqual(done["installFetchStepIndex"], 3)
        self.assertIn("web-perf", done["installFetchSteps"][2]["detail"])

    def test_the_stepper_uses_the_declared_primitive_and_leaves_the_gate_exemption(self):
        """`.stepper`/`.step` were declared in 1.5 with this exact flow written
        on them and wired to nothing. A second hand-rolled stepper would leave
        both the gate's exemption and the stylesheet's declaration true and the
        markup speaking a vocabulary of its own."""
        self.assertIn('class="stepper"', HTML)
        self.assertIn('class="step"', HTML)
        self.assertIn('.stepper {', CSS)
        self.assertIn('.step[aria-current="step"]', CSS)
        gate = TOKEN_GATE.read_text(encoding="utf-8")
        pending = gate[gate.index("PRIMITIVE_PENDING_ADOPTION = {"):]
        pending = pending[:pending.index("\n}\n")]
        self.assertNotIn('".stepper"', pending)
        self.assertNotIn('".step"', pending)

    def test_position_is_carried_by_aria_current_and_not_by_colour_alone(self):
        """Forced-colors drops `background: var(--accent)`, so a filled marker
        is not enough on its own."""
        self.assertIn(':aria-current="step.state === \'current\' ? \'step\' : undefined"', HTML)
        self.assertIn(':data-done="step.state === \'done\' ? \'true\' : undefined"', HTML)

    def test_the_stepper_is_a_list_and_the_list_markers_are_switched_off(self):
        """The separators are `<li>` too. The primitive was written for a `<div>`
        flow, so adopting it in an `<ol>` printed "1." and "2." BESIDE the rules
        — found by looking at the capture, and pin-able: an ordered list whose
        rule does not say `list-style: none`."""
        self.assertIn('<ol class="stepper"', HTML)
        # 5.2 DECLARED the markers off in its own block rather than editing the
        # primitive — and the primitive is the one every future stepper reads,
        # so the assertion follows the declaration this task actually made.
        block = CSS[CSS.index("5.2 fetch stepper"):]
        block = block[block.index(".stepper {"):block.index(".stepper {") + 200]
        self.assertIn("list-style: none", block)
        self.assertIn("padding: 0", block)

    def test_one_sentence_lives_under_the_strip_and_not_in_three_steps(self):
        """Three sentences in one 1280 row wrapped the strip onto two lines and
        stranded a separator at the head of the second. The detail is the
        CURRENT step's, so the two older ones are not silently dropped — the
        commit banner says what the finished step did."""
        self.assertIn("{{ installFetchDetail }}", HTML)
        half = _fetch_half()
        self.assertEqual(half.count("step.detail"), 0)
        names = ["installFetchDetail"]
        reviewing = _run_getters({"review": REVIEW, "committed": None}, names)
        self.assertIn("Nothing is installed until you confirm",
                      reviewing["installFetchDetail"])
        done = _run_getters({"review": None, "committed": {"name": "web-perf"}}, names)
        self.assertIn("web-perf", done["installFetchDetail"])

    def test_the_commit_response_is_its_own_state_and_not_written_into_lastresult(self):
        """`lastResult` is read by three unrelated getters. A commit response
        has no `exit_code` (so it reads as a runner failure), no `data` (so it
        reads as an empty listing) and no `_registry` (so it reads as
        uncached). Writing it there is how one response gets three false
        readings."""
        body = _getter("commitRegistryReview")
        self.assertIn("this.install.committed = res", body)
        self.assertNotIn("this.install.lastResult = res", body)
        self.assertIn('committed: null', APP)

    def test_a_failed_commit_keeps_the_review_and_states_the_failure_on_the_pane(self):
        """The review is still pending server-side after a failed commit, so
        clearing it would strand a transaction that is still committable. The
        message also goes to `install.error`, because a toast is gone in four
        seconds and this pane's whole content is this transaction."""
        body = _getter("commitRegistryReview")
        catch = body[body.index("} catch"):body.index("} finally")]
        self.assertIn("this.install.error", catch)
        self.assertNotIn("this.install.review = null", catch)
        self.assertNotIn("this.install.committed = null", catch)

    def test_a_new_fetch_retires_the_prior_review_and_the_prior_commit(self):
        """Without retiring `committed`, the stepper stays on step three after
        a second fetch — an installed banner for a skill nothing has fetched
        since."""
        body = _getter("runRegistry")
        self.assertIn("this.install.review = null", body)
        self.assertIn("this.install.committed = null", body)


class FetchEvidenceContracts(unittest.TestCase):
    def test_the_facts_are_read_defensively_because_the_payload_is_not_ours(self):
        """`_prepare_registry_skill` builds `registry` from a snapshot the
        registry chose. Every field is optional at the point of use."""
        body = _getter("installFetchFacts")
        self.assertIn('typeof review.registry === "object"', body)
        names = ["installFetchFacts"]
        empty = _run_getters({"review": {"registry": None}}, names)
        self.assertTrue(empty["installFetchFacts"])
        self.assertIn("not recorded", json.dumps(empty["installFetchFacts"]))

    def test_an_unverified_remote_hash_is_never_reported_as_verified(self):
        """registry.py:835 is explicit that the upstream `hash` comes from an
        undocumented algorithm and is retained rather than asserted verified.
        A truthy `remote_hash` must not read as a green tick."""
        names = ["installFetchFacts"]
        out = _run_getters({"review": REVIEW}, names)
        rows = {r["label"]: r["value"] for r in out["installFetchFacts"]}
        self.assertIn("not verified", rows["Hash verified"])
        self.assertIn("aaa111", rows["Snapshot hash"])
        self.assertIn("frontmatter.name", rows["Normalization"])

        verified = _run_getters({"review": {"registry": dict(REVIEW["registry"], hash_verified=True)}}, names)
        self.assertIn("verified", {r["label"]: r["value"] for r in verified["installFetchFacts"]}["Hash verified"])

    def test_a_warning_with_no_message_is_still_a_row_and_does_not_print_undefined(self):
        """The fixture's second warning carries no `message`; rendering the raw
        object would print `[object Object]` or `undefined`."""
        names = ["installFetchWarnings"]
        out = _run_getters({"review": REVIEW}, names)
        self.assertEqual(len(out["installFetchWarnings"]), 2)
        self.assertEqual(out["installFetchWarnings"][1]["message"],
                         "the validator reported a warning with no message")
        blank = _run_getters({"review": {"inspection": {"validation": {"warnings": "not a list"}}}}, names)
        self.assertEqual(blank["installFetchWarnings"], [])

    def test_the_risk_policy_is_rendered_verbatim_and_never_scored(self):
        """`risk.policy` says out loud that the findings are not a verdict. A
        count, a badge or a percentage would be a verdict the product is not
        entitled to (RULES #12)."""
        names = ["installFetchRisk"]
        out = _run_getters({"review": REVIEW}, names)
        self.assertEqual(out["installFetchRisk"]["policy"],
                         "advisory-only; heuristic evidence is not a safety or trust verdict")
        self.assertEqual([f["kind"] for f in out["installFetchRisk"]["findings"]], ["script", "tool-grant"])
        self.assertEqual(_run_getters({"review": {"inspection": {}}}, names)["installFetchRisk"], None)

    def test_the_expiry_is_rendered_because_the_window_it_describes_is_real(self):
        """registry.py:68 sets a 24h window and the commit fails after it, so a
        reader told only "installed" is told nothing about the window."""
        names = ["installFetchExpiry"]
        self.assertTrue(_run_getters({"review": REVIEW}, names)["installFetchExpiry"])
        self.assertEqual(_run_getters({"review": None}, names)["installFetchExpiry"], "")
        # An unparseable value must not render as `Invalid Date` to the reader;
        # the backend's own string is the better of the two answers.
        self.assertEqual(_run_getters({"review": {"review_expires_at": "whenever"}}, names)["installFetchExpiry"],
                         "whenever")

    def test_no_interpolation_is_butted_against_a_following_word(self):
        """`<strong>..</strong> {{ x }}` renders as "Installed.web-perf" and
        `{{ evidence }}<span> {{ why }}</span>` as "./distmatched" — Vue drops
        the whitespace between an interpolation and a sibling element. Both
        shipped in the first capture and neither was catchable by reading the
        template, so the rule is asserted: every text node that ends in an
        interpolation must carry its own separator, never borrow one from the
        template's formatting."""
        half = _fetch_half()
        # A `}}<` with no intervening character is a butt joint.
        for match in re.finditer(r"(\}\}|\{\{)\s*<", half):
            before = half[max(0, match.start() - 40):match.start()]
            self.assertNotRegex(
                before, r"[A-Za-z0-9.,;:)]$",
                "an interpolation butts against a following element: ..." + before)
        # ...and a strong element that opens a sentence must be followed by a
        # separator that is INSIDE the text node, not a template space.
        for match in re.finditer(r"<strong>[^<]*</strong>([^<]*)<", half):
            tail = match.group(1)
            self.assertTrue(tail.strip() == "" or tail.strip()[0] in "—-&middot;·-",
                            "a <strong> is followed by whitespace the template drops: " + repr(tail))
        self.assertIn('<strong>{{ install.committed.name }}</strong> — {{ installFetchOutcome }}', half)
        self.assertIn('{{ f.evidence }}<span v-if="f.why" class="hint"> &middot; {{ f.why }}</span>', half)

    def test_the_three_halves_are_independent_ifs_and_not_an_else_chain(self):
        """The defect this task's own e2e caught, and no source assertion could.

        The halves were `v-if` / `v-else` / `v-else`. With three branches and
        an HTML comment between two of them, Vue's compiler **silently dropped
        the middle one** — `install.mode === "runner"` rendered the FETCH
        half. No throw, no console message, and every text-level contract
        green, including 5.1b's which asserted `@click="runInstall(` exists
        inside "the installer half". Only a test that clicks the button and
        asks whether `#install-source` is in the DOM could see it.

        Three independent `v-if`s cannot be lost to a rule about sibling
        adjacency. Each half must carry its OWN condition, and each must own a
        control no other half renders, so the three conditions cannot be
        satisfied by one shared branch.
        """
        block = HTML[HTML.index('<div v-else-if="view === \'install\'" class="install-shell"'):]
        block = block[:block.index('<div v-else-if="view === \'skills\'" class="detail-inner">')]
        # Comments stripped first: this file's own prose quotes `@click="runInstall(`.
        block = re.sub(r"<!--.*?-->", "", block, flags=re.S)
        self.assertNotIn("<template v-else>", block,
                         "a v-else chain lost its middle branch in this very view")
        for mode in ("registry", "runner", "fetch"):
            self.assertEqual(1, block.count(f"""<template v-if="install.mode === '{mode}'">"""),
                             f"the {mode} half does not carry its own condition")
        at = [block.index(f"""<template v-if="install.mode === '{m}'">""")
              for m in ("registry", "runner", "fetch")]
        registry, runner = (block[at[i]:at[i + 1]] for i in range(2))
        fetch = block[at[2]:]
        # `id="…"` not `#…` — a selector never appears in the markup, and the
        # e2e that found this defect asks about `#install-source` while the
        # source can only see the attribute.
        self.assertIn('id="install-source"', runner)
        self.assertNotIn('id="install-source"', registry)
        self.assertIn("class=\"stepper\"", fetch)
        self.assertNotIn("class=\"stepper\"", runner)

    def test_the_commit_note_does_not_claim_the_skill_is_safe(self):
        half = _fetch_half()
        self.assertIn("does not claim the skill is safe", half)
        self.assertNotIn("verified safe", half)
        self.assertNotIn("trusted skill", half)

    def test_the_command_line_names_the_operation_the_press_performs(self):
        """Before a review it is a fetch that writes to the REVIEW, not to the
        global store; after one it is the commit that carries the review id.
        Falling through to the runner assembler would print `npx skills add`
        for a press that runs no runner."""
        preview = _getter("installPreview")
        self.assertIn('this.install.mode === "fetch"', preview)
        self.assertIn("→ review (not the global store)", preview)
        self.assertIn("→ global store", preview)
        names = ["installPreview"]
        before = _run_getters({"mode": "fetch", "source": "owner/repo/skill", "review": None}, names)
        after = _run_getters({"mode": "fetch", "source": "owner/repo/skill", "review": REVIEW}, names)
        self.assertIn("owner/repo/skill", before["installPreview"])
        self.assertNotIn("npx", before["installPreview"])
        self.assertIn("a1b2c3", after["installPreview"])

    def test_the_scope_note_makes_a_third_claim_for_the_third_workflow(self):
        """Two sentences for three workflows would leave the fetch half showing
        a sentence about the registry — or, worse, the 'nothing writes to disk'
        claim the page made before the fetch half existed."""
        options = _load_options()
        self.assertIn('this.install.mode === "fetch"', options["installScopeNote"])
        names = ["installScopeNote"]
        self.assertIn("Nothing on this page writes to disk",
                      _run_getters({"mode": "registry"}, names)["installScopeNote"])
        self.assertIn("review", _run_getters({"mode": "fetch"}, names)["installScopeNote"])


class FetchBehaviorContracts(unittest.TestCase):
    def test_fetch_then_commit_sends_two_separate_transactions(self):
        """The split is the backend's contract (webapp.py:128/130). Asserted by
        RUNNING the two methods against a stubbed transport, not by reading the
        body, so a future refactor that merges them fails."""
        script = r'''
const fs = require('fs'), vm = require('vm');
const calls = [];
const sandbox = {
  window: {SkillManagerDomain: {
    api: async (path, options) => {
      calls.push({path, body: JSON.parse(options.body)});
      return calls.length === 1
        ? {review_id:'review-9', review_expires_at:'later', registry:{slug:'demo'}, inspection:{}}
        : {name:'demo', path:'/store/demo'};
    },
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
const m = sandbox.app.methods;
const ctx = {
  install:{mode:'fetch', registryOp:'fetch', source:'owner/repo/demo', allowStale:false,
           page:0, perPage:25, view:'all-time', review_id:null, review:null,
           committed:null, lastResult:null, error:null},
  busy:false, registryReady:() => true, toast(){},
  loadScopes:async()=>{}, loadSkills:async()=>{}
};
(async()=>{
  await m.runRegistry.call(ctx);
  const afterFetch = {review: !!ctx.install.review, committed: ctx.install.committed};
  await m.commitRegistryReview.call(ctx);
  console.log(JSON.stringify({calls, afterFetch, committed: ctx.install.committed,
                              review: ctx.install.review, error: ctx.install.error}));
})();
'''
        out = json.loads(subprocess.run(["node", "-e", script], capture_output=True,
                                       text=True, check=True).stdout)
        self.assertEqual(out["calls"][0]["body"]["fetch"], True)
        self.assertEqual(out["calls"][0]["body"]["source"], "owner/repo/demo")
        self.assertNotIn("trust_confirmed", out["calls"][0]["body"])
        self.assertEqual(out["calls"][1]["body"], {"fetch": True, "review_id": "review-9", "trust_confirmed": True})
        self.assertTrue(out["afterFetch"]["review"])
        self.assertIsNone(out["afterFetch"]["committed"])
        self.assertEqual(out["committed"]["name"], "demo")
        self.assertIsNone(out["review"])
        self.assertIsNone(out["error"])

    def test_a_failed_commit_leaves_the_review_committable(self):
        """Same two methods, a transport that rejects the second call. The
        review must survive: it is still `pending` on disk and still committable,
        and clearing it would leave the reader with a stepper on step two and
        nothing to press."""
        script = r'''
const fs = require('fs'), vm = require('vm');
let n = 0;
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => {
      n += 1;
      if (n === 1) return {review_id:'review-7', registry:{slug:'demo'}, inspection:{}};
      throw new Error('registry review is unreadable');
    },
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
const m = sandbox.app.methods;
const ctx = {
  install:{mode:'fetch', registryOp:'fetch', source:'owner/repo/demo', allowStale:false,
           page:0, perPage:25, view:'all-time', review_id:null, review:null,
           committed:null, lastResult:null, error:null},
  busy:false, registryReady:() => true, toast(){}, loadScopes:async()=>{}, loadSkills:async()=>{}
};
(async()=>{
  await m.runRegistry.call(ctx);
  await m.commitRegistryReview.call(ctx);
  console.log(JSON.stringify({reviewId: ctx.install.review && ctx.install.review.review_id,
                              committed: ctx.install.committed, error: ctx.install.error}));
})();
'''
        out = json.loads(subprocess.run(["node", "-e", script], capture_output=True,
                                       text=True, check=True).stdout)
        self.assertEqual(out["reviewId"], "review-7")
        self.assertIsNone(out["committed"])
        self.assertEqual(out["error"], "registry review is unreadable")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()