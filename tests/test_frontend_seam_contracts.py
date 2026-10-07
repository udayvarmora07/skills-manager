"""Frontend seam contracts: one source of truth per policy (docs/24 C2/G6).

The frontend had three divergent copies of the observed-state predicate, a
16-way Escape ladder that hand-copied the ``data()`` key order, five raw
``fetch()`` calls that bypassed the transport seam, and a list refresh that
re-fetched the selected document on every navigation.

Every check here runs the *checked-in* sources under Node, so it fails when the
sources drift rather than when a mock is out of date. Structural assertions are
made on parsed structure (key sets, call graphs, tag trees), never on
substring presence in rendered output.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "skillsmgr" / "webui" / "app.js"
DOMAIN_JS = ROOT / "skillsmgr" / "webui" / "domain.js"
INDEX_HTML = ROOT / "skillsmgr" / "webui" / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node(script: str) -> dict:
    """Run a Node script against the real sources and return parsed JSON."""
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, check=True, cwd=str(ROOT),
    )
    return json.loads(result.stdout)


# Loads the real domain.js, then the real app.js on top of it. Only `fetch` and
# the DOM are stubbed, so the app exercises its own shipped transport.
_APP_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const requests = [];
let rows = [];
function reply(url) {
  const p = String(url).split('?')[0];
  if (p === '/api/skills') return rows;
  if (p === '/api/trash') return [];
  if (p === '/api/scopes') return [{id:'global',label:'Global',kind:'global',exists:true,count:rows.length}];
  if (p === '/api/catalog') return {version:1, tags:{}, profiles:{}};
  if (p === '/api/history') return [];
  if (p === '/api/stats') return {total:rows.length, active:rows.length, disabled:0, window_tokens:100, window:'claude'};
  if (p === '/api/doctor') return {hygiene:{findings:[], category_counts:{}}, explain:{}};
  if (p === '/api/workspaces') return {workspaces:[], project_observation:null};
  if (/^\/api\/skills\/[^/]+\/raw$/.test(p)) return '__RAW__';
  if (/^\/api\/skills\/[^/]+$/.test(p)) {
    const name = decodeURIComponent(p.split('/').pop());
    const row = rows.find(r => r.name === name) || rows[0] || {};
    return Object.assign({}, row, {body:'---\nname: '+name+'\n---\n\nbody text\n', path: row.path || ('/store/'+name)});
  }
  return {};
}
const fakeFetch = async (url) => {
  requests.push(String(url));
  const body = reply(url);
  const raw = body === '__RAW__';
  return {ok:true, status:200,
    headers:{get:(h)=> h === 'content-type' ? (raw ? 'text/plain' : 'application/json') : null},
    json: async()=>body, text: async()=> (raw ? '---\ncompatibility: >=3\n---\n\nbody\n' : JSON.stringify(body)),
    blob: async()=>({__blob:true})};
};
const anchor = () => ({get style(){return {};}, setAttribute(){}, appendChild(){}, click(){}, remove(){}});
// domain.js and app.js share ONE context, so the seam really is the app's.
const sandbox = {
  window: {},
  Vue: {createApp(def){ sandbox.app = def; return {mount(){}}; }, nextTick(fn){ if(fn) fn(); return Promise.resolve(); }},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {
    addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}},
    querySelectorAll(){return [];}, querySelector(){return null;}, getElementById(){return null;},
    createElement(){ return anchor(); },
    contains(){return false;}, activeElement: null, body:{appendChild(){}},
  },
  fetch: fakeFetch,
  setTimeout, clearTimeout, console,
  URL: {createObjectURL(){return 'blob:x';}, revokeObjectURL(){}},
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const def = sandbox.app;
const Domain = sandbox.window.SkillManagerDomain;
function makeContext(next) {
  rows = next;
  const ctx = Object.assign({}, def.data(), def.methods, {$nextTick(fn){ if(fn) fn(); return Promise.resolve(); }});
  ctx.scopes = [{id:'global',label:'Global',kind:'global',exists:true,count:rows.length}];
  // Seed the loaded records a real list read would have populated.
  ctx.skills = rows.slice();
  ctx.allSkills = rows.slice();
  for (const name of Object.keys(def.computed)) {
    Object.defineProperty(ctx, name, {get(){ return def.computed[name].call(ctx); }, configurable:true});
  }
  return ctx;
}
/* Swap what the server reports without rebuilding the context, so a test can
 * simulate the filesystem changing underneath a mounted app. */
function setRows(next) { rows = next; }
const tick = () => new Promise(r => setTimeout(r, 20));
"""


class DomainSeamOwnershipTests(unittest.TestCase):
    """C2: transport and state policy belong to the domain seam, not the app."""

    def test_app_makes_no_raw_fetch_calls(self):
        """Every request goes through domain.api/apiText/apiBlob.

        A raw ``fetch`` in app.js re-implements error handling against the seam
        whose stated purpose is to own it, so the count must be exactly zero.
        """
        app = _read(APP_JS)
        raw_calls = re.findall(r"(?<![\w.])fetch\s*\(", app)
        self.assertEqual(raw_calls, [], f"app.js bypasses domain.api at {len(raw_calls)} site(s)")
        for name in ("apiText", "apiBlob"):
            self.assertIn(name, app, f"{name} must be reachable from app.js")

    def test_domain_seam_exposes_the_transport_and_the_state_policy(self):
        exported = re.search(
            r"window\.SkillManagerDomain = Object\.freeze\(\{(.*?)\}\);",
            _read(DOMAIN_JS), re.S,
        )
        self.assertIsNotNone(exported, "domain seam export block not found")
        names = set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*,", exported.group(1), re.M))
        for required in ("api", "apiText", "apiBlob", "observeRecord",
                         "observedStateFor", "observedStateKeys", "OBSERVED_STATE_LABELS"):
            self.assertIn(required, names, f"{required} missing from the frozen seam")

    def test_app_has_no_local_copy_of_the_state_predicate(self):
        """The observed-state decision must not be restated in app.js.

        Each of these was a separate implementation that could disagree with the
        others; a test that merely counted them would not catch a fourth.
        """
        app = _read(APP_JS)
        for leaked in ('record.instance_states || record.states',
                       'states.includes("invalid")',
                       '["invalid", "malformed", "unaddressable"]',
                       'record.decode_error || states.includes'):
            self.assertNotIn(leaked, app, f"app.js restates the state predicate: {leaked!r}")
        self.assertIn("observeRecord", app)
        self.assertIn("observedStateFor", app)


class SingleStateVocabularyTests(unittest.TestCase):
    """C2: one classification, reachable from every surface that names a state."""

    #: Every state key the shared predicate can return, and the label each must
    #: have. A key with no label renders as a bare identifier in the UI.
    EXPECTED_LABELS = {
        "active": "Active", "disabled": "Disabled", "invalid": "Invalid",
        "malformed": "Malformed", "linked": "Linked outside root",
        "unaddressable": "Unaddressable", "divergent": "Divergent",
    }

    def test_every_state_the_backend_emits_has_a_label(self):
        script = _APP_HARNESS + r"""
console.log(JSON.stringify(Domain.OBSERVED_STATE_LABELS));
"""
        labels = _node(script)
        self.assertEqual(labels, self.EXPECTED_LABELS)

    def test_invalid_is_reported_rather_than_silently_absent(self):
        """The backend's own vocabulary includes `invalid`.

        Before this change the app recognised `invalid` while the domain label
        map did not, so a state present in one surface could be missing from the
        other. Both must now name it.
        """
        script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = { window: {}, document: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const D = sandbox.window.SkillManagerDomain;
console.log(JSON.stringify({
  key: D.observedStateFor({instance_states: ['invalid']}),
  label: D.OBSERVED_STATE_LABELS[D.observedStateFor({instance_states: ['invalid']})],
  badgeKeys: D.observedStateKeys({instance_states: ['invalid']}),
}));
"""
        out = _node(script)
        self.assertEqual(out["key"], "invalid")
        self.assertEqual(out["label"], "Invalid")

    def test_quality_and_library_agree_on_the_same_record(self):
        """Both surfaces must classify one record identically.

        This is the divergence the audit measured against the live API: a record
        the backend reports as ``invalid`` was badged "Malformed" in Library and
        "Invalid observed" in Quality.
        """
        script = _APP_HARNESS + r"""
const cases = [
  ['plain',        {}],
  ['flag_malformed', {malformed: true}],
  ['flag_decode',  {decode_error: 'bad utf8'}],
  ['flag_unaddr',  {addressable: false}],
  ['state_invalid',{instance_states: ['invalid']}],
  ['state_malformed', {instance_states: ['malformed']}],
  ['state_unaddr', {instance_states: ['unaddressable']}],
  ['state_disabled', {instance_states: ['disabled']}],
  ['flag_disabled', {disabled: true}],
  ['invalid_and_disabled', {instance_states: ['invalid'], disabled: true}],
];
const out = [];
for (const [name, extra] of cases) {
  const record = Object.assign({name, scope: 'global'}, extra);
  const ctx = makeContext([record]);
  const domainLabel = Domain.observedStateKeys(record)
    .map(k => Domain.OBSERVED_STATE_LABELS[k]).join(' · ');
  out.push({
    name,
    domainKeys: Domain.observedStateKeys(record),
    domainLabel,
    qualityLabel: def.methods.qualityStateLabel(record),
    qualityState: Domain.observedStateFor(record),
    countedActive: def.computed.overviewActiveCount.call(ctx),
    countedFlagged: def.computed.overviewInvalidRecords.call(ctx).length,
  });
}
console.log(JSON.stringify(out));
"""
        rows = {row["name"]: row for row in _node(script)}

        # An unreadable document is malformed everywhere, whatever shape the
        # backend used to say so.
        for name in ("flag_malformed", "flag_decode", "state_malformed"):
            self.assertIn("malformed", rows[name]["domainKeys"], name)
            self.assertEqual(rows[name]["qualityLabel"], "Malformed observed", name)
            self.assertEqual(rows[name]["countedFlagged"], 1, name)
            self.assertEqual(rows[name]["countedActive"], 0, name)

        # `invalid` keeps its own Quality wording; the Library badge folds it
        # into Malformed because that is one observation to a reader.
        self.assertEqual(rows["state_invalid"]["qualityState"], "invalid")
        self.assertEqual(rows["state_invalid"]["qualityLabel"], "Invalid observed")
        self.assertEqual(rows["state_invalid"]["domainLabel"], "Malformed")
        self.assertEqual(rows["state_invalid"]["countedFlagged"], 1)

        # Disabled is a state in both vocabularies, from either shape.
        for name in ("flag_disabled", "state_disabled"):
            self.assertEqual(rows[name]["domainKeys"], ["disabled"], name)
            self.assertEqual(rows[name]["countedActive"], 0, name)
        self.assertEqual(rows["flag_disabled"]["qualityLabel"], "Disabled observed")

        # An unaddressable name is never offered as active, either way it is said.
        for name in ("flag_unaddr", "state_unaddr"):
            self.assertEqual(rows[name]["countedActive"], 0, name)
            self.assertEqual(rows[name]["qualityLabel"], "Unaddressable observed", name)

        # Co-occurring states must not hide one another.
        self.assertEqual(rows["invalid_and_disabled"]["domainKeys"], ["malformed", "disabled"])

        # A clean record is active and is not presented as a validation verdict.
        self.assertEqual(rows["plain"]["domainKeys"], ["active"])
        self.assertEqual(rows["plain"]["countedActive"], 1)
        self.assertEqual(rows["plain"]["countedFlagged"], 0)
        self.assertEqual(rows["plain"]["qualityLabel"], "Observed; not a validation verdict")

    def test_quality_summary_buckets_stay_disjoint_and_total(self):
        """Every record lands in exactly one bucket — no silent disappearance."""
        script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = { window: {}, document: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const D = sandbox.window.SkillManagerDomain;
const records = [
  {name:'a'}, {name:'b', disabled:true}, {name:'c', malformed:true},
  {name:'d', instance_states:['invalid']}, {name:'e', addressable:false},
  {name:'f', instance_states:['unaddressable']}, {name:'g', decode_error:'x'},
];
const buckets = {};
for (const r of records) {
  const state = D.observedStateFor(r);
  buckets[state] = (buckets[state] || 0) + 1;
}
console.log(JSON.stringify({buckets, total: records.length}));
"""
        out = _node(script)
        self.assertEqual(sum(out["buckets"].values()), out["total"])
        self.assertEqual(out["buckets"].get("invalid"), 1)
        self.assertEqual(out["buckets"].get("malformed"), 2)   # flag + decode_error
        self.assertEqual(out["buckets"].get("unaddressable"), 2)
        self.assertEqual(out["buckets"].get("disabled"), 1)
        self.assertEqual(out["buckets"].get("active"), 1)


class ModalEscapeLadderTests(unittest.TestCase):
    """C2: Escape must close whatever ``activeModal`` reports, by construction."""

    def _modal_keys(self) -> list[str]:
        match = re.search(r"modals:\s*\{(.*?)\n      \},", _read(APP_JS), re.S)
        self.assertIsNotNone(match, "modals literal not found in data()")
        return re.findall(r"^\s*([a-z][a-zA-Z]*):", match.group(1), re.M)

    def test_escape_does_not_hand_copy_the_modal_key_order(self):
        app = _read(APP_JS)
        handler = re.search(r"onKeydown\(e\)\s*\{(.*?)\n    \},", app, re.S)
        self.assertIsNotNone(handler, "onKeydown not found")
        escape_branch = handler.group(1).split('e.key === "Escape"', 1)[-1]
        named = re.findall(r"this\.modals\.([a-z][a-zA-Z]*)", escape_branch)
        self.assertEqual(named, [], "Escape still enumerates modal keys by hand")

    def test_every_declared_modal_is_escape_closable(self):
        """Structural proof: the ladder no longer exists to fall out of sync.

        Each key in ``data().modals`` is closable because the handler closes
        ``activeModal`` rather than testing a hand-written list.
        """
        script = _APP_HARNESS + r"""
const ctx = makeContext([{name:'a', scope:'global'}]);
const keys = Object.keys(ctx.modals);
const closed = [];
for (const key of keys) {
  ctx.menuOpen = false;
  for (const other of keys) ctx.modals[other] = null;
  ctx.modals[key] = true;
  ctx.requestCloseUpdate = () => closed.push(key + ':requestCloseUpdate');
  ctx.closeModal = (k) => { ctx.modals[k] = null; closed.push(k); };
  ctx.activeModal = def.computed.activeModal.call(ctx);
  ctx.onKeydown({key:'Escape', target:{tagName:'BODY', isContentEditable:false}, preventDefault(){}});
}
console.log(JSON.stringify({keys, closed}));
"""
        out = _node(script)
        self.assertEqual(len(out["keys"]), 16, "expected the 16 declared dialogs")
        closed_keys = [entry.split(":")[0] for entry in out["closed"]]
        for key in out["keys"]:
            self.assertIn(key, closed_keys, f"{key} is not Escape-closable")
        # The update dialog keeps its confirm-before-close behaviour.
        self.assertIn("update:requestCloseUpdate", out["closed"])

    def test_escape_closes_the_modal_active_modal_reports(self):
        """Ordering must come from activeModal, so focus and Escape agree.

        Before this change the Escape ladder's order differed from the ``data()``
        key order that ``activeModal`` derives from, so with two dialogs open
        focus and Escape disagreed about which one was on top.
        """
        script = _APP_HARNESS + r"""
const ctx = makeContext([{name:'a', scope:'global'}]);
const keys = Object.keys(ctx.modals);
let mismatches = 0;
const pairs = [['skill','commands'], ['update','help'], ['batch','doctor']];
for (const [a, b] of pairs) {
  for (const other of keys) ctx.modals[other] = null;
  ctx.modals[a] = true; ctx.modals[b] = true;
  const reported = def.computed.activeModal.call(ctx);
  let closed = null;
  ctx.requestCloseUpdate = () => { closed = 'update'; ctx.modals.update = null; };
  ctx.closeModal = (k) => { closed = k; ctx.modals[k] = null; };
  ctx.activeModal = reported;
  ctx.menuOpen = false;
  ctx.onKeydown({key:'Escape', target:{tagName:'BODY', isContentEditable:false}, preventDefault(){}});
  if (closed !== reported) { mismatches += 1; }
}
console.log(JSON.stringify({mismatches}));
"""
        self.assertEqual(_node(script)["mismatches"], 0)

    def test_menu_still_takes_precedence_over_a_modal_on_escape(self):
        script = _APP_HARNESS + r"""
const ctx = makeContext([{name:'a', scope:'global'}]);
let menuClosed = false, modalClosed = false;
ctx.modals.doctor = {};
ctx.menuOpen = true;
ctx.activeModal = def.computed.activeModal.call(ctx);
ctx.closeActionsMenu = () => { menuClosed = true; };
ctx.closeModal = () => { modalClosed = true; };
ctx.onKeydown({key:'Escape', target:{tagName:'BODY', isContentEditable:false}, preventDefault(){}});
console.log(JSON.stringify({menuClosed, modalClosed}));
"""
        out = _node(script)
        self.assertTrue(out["menuClosed"])
        self.assertFalse(out["modalClosed"])


class RequestCoalescingTests(unittest.TestCase):
    """G6: identical in-flight reads fan in; completed reads are never cached."""

    def test_identical_concurrent_gets_share_one_request(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
let calls = 0;
const sandbox = {
  window: {},
  document: {},
  fetch: async () => { calls += 1; return {ok:true, status:200, headers:{get:()=>'application/json'}, json: async()=>({v: calls})}; },
  setTimeout, clearTimeout,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const api = sandbox.window.SkillManagerDomain.api;
(async () => {
  const [a, b, c] = await Promise.all([api('/api/skills?scope=all'), api('/api/skills?scope=all'), api('/api/skills?scope=all')]);
  const afterFanIn = calls;
  // A later read must re-read: the filesystem stays the source of truth.
  const d = await api('/api/skills?scope=all');
  console.log(JSON.stringify({afterFanIn, afterSequential: calls, sameObject: a === b && b === c, laterValue: d.v}));
})();
"""
        out = _node(script)
        self.assertEqual(out["afterFanIn"], 1, "concurrent identical GETs were not coalesced")
        self.assertEqual(out["afterSequential"], 2, "a completed read must not be cached")
        self.assertTrue(out["sameObject"])

    def test_different_urls_are_not_coalesced(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
let calls = 0;
const sandbox = {window:{}, document:{}, setTimeout, clearTimeout,
  fetch: async () => { calls += 1; return {ok:true, status:200, headers:{get:()=>'application/json'}, json: async()=>({v:calls})}; }};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const api = sandbox.window.SkillManagerDomain.api;
(async () => {
  await Promise.all([api('/api/skills?scope=all'), api('/api/skills?scope=agents'), api('/api/trash')]);
  console.log(JSON.stringify({calls}));
})();
"""
        self.assertEqual(_node(script)["calls"], 3)

    def test_mutations_are_never_coalesced(self):
        """Two POSTs are two mutations; sharing one would drop an operation."""
        script = r"""
const fs = require('fs'), vm = require('vm');
let calls = 0;
const sandbox = {window:{}, document:{}, setTimeout, clearTimeout,
  fetch: async () => { calls += 1; return {ok:true, status:200, headers:{get:()=>'application/json'}, json: async()=>({v:calls})}; }};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const api = sandbox.window.SkillManagerDomain.api;
(async () => {
  const opts = {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'};
  await Promise.all([api('/api/skills/x/disable', opts), api('/api/skills/x/disable', opts)]);
  console.log(JSON.stringify({calls}));
})();
"""
        self.assertEqual(_node(script)["calls"], 2)

    def test_a_failed_read_is_not_left_in_the_in_flight_table(self):
        """A rejected read must not poison the next attempt."""
        script = r"""
const fs = require('fs'), vm = require('vm');
let calls = 0;
const sandbox = {window:{}, document:{}, setTimeout, clearTimeout,
  fetch: async () => { calls += 1; const n = calls;
    return {ok:false, status:500, headers:{get:()=>'application/json'}, json: async()=>({error:'boom '+n})}; }};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const api = sandbox.window.SkillManagerDomain.api;
(async () => {
  const errs = [];
  for (let i = 0; i < 2; i += 1) {
    try { await api('/api/skills?scope=all'); } catch (e) { errs.push(e.message); }
  }
  console.log(JSON.stringify({calls, errs}));
})();
"""
        out = _node(script)
        self.assertEqual(out["calls"], 2, "the failed read was cached and reused")
        self.assertEqual(out["errs"], ["boom 1", "boom 2"])


class NavigationRequestVolumeTests(unittest.TestCase):
    """G6: a navigation must not re-read an unchanged selected document."""

    ROWS = [
        {"name": "alpha", "scope": "agents", "scope_label": "Agents",
         "path": "/a/alpha", "physical_path": "/a/alpha", "physical_root": "/a",
         "content_hash": "hash-alpha", "description": "A", "category": "x"},
        {"name": "beta", "scope": "global", "scope_label": "Global",
         "path": "/s/beta", "physical_path": "/s/beta", "physical_root": "/s",
         "content_hash": "hash-beta", "description": "B", "category": "x"},
    ]

    def _script(self, body: str) -> str:
        return _APP_HARNESS + f"const ROWS = {json.dumps(self.ROWS)};\n" + body

    def test_navigating_away_and_back_does_not_refetch_the_unchanged_detail(self):
        script = self._script(r"""
const ctx = makeContext(ROWS);
(async () => {
  await ctx.loadInitialData(); await tick();
  ctx.switchView('skills'); await tick();
  ctx.selectSkill(ROWS[0]); await tick();
  const afterSelect = requests.filter(u => u.includes('/api/skills/alpha'));
  requests.length = 0;
  for (const view of ['install', 'skills', 'recovery', 'skills', 'quality', 'skills', 'overview']) {
    ctx.switchView(view); await tick();
  }
  const detailReads = requests.filter(u => u.includes('/api/skills/alpha'));
  console.log(JSON.stringify({afterSelect, detailReads, selected: ctx.selectedName, total: requests.length}));
})();
""")
        out = _node(script)
        # Selecting a skill reads the record and its raw frontmatter exactly once.
        self.assertEqual(len(out["afterSelect"]), 2, out["afterSelect"])
        # Returning to Library must not re-download an unchanged document.
        self.assertEqual(out["detailReads"], [], f"detail re-read: {out['detailReads']}")
        self.assertEqual(out["selected"], "alpha")

    def test_a_changed_document_is_still_re_read(self):
        """The short-circuit must key on observed change, never on time."""
        script = self._script(r"""
const ctx = makeContext(ROWS);
(async () => {
  ctx.switchView('skills'); await tick();
  ctx.selectSkill(ROWS[0]); await tick();
  const before = requests.filter(u => u.includes('/api/skills/alpha')).length;
  // The file changed on disk: the list reports a different content hash.
  setRows([Object.assign({}, ROWS[0], {content_hash: 'hash-alpha-CHANGED'}), ROWS[1]]);
  requests.length = 0;
  await ctx.loadSkills(); await tick();
  const after = requests.filter(u => u.includes('/api/skills/alpha'));
  console.log(JSON.stringify({before, after, selectedHash: ctx.selected && ctx.selected.content_hash}));
})();
""")
        out = _node(script)
        self.assertEqual(out["before"], 2)
        self.assertEqual(len(out["after"]), 2, f"changed document was not re-read: {out['after']}")
        self.assertEqual(out["selectedHash"], "hash-alpha-CHANGED")

    def test_a_newly_disabled_instance_is_still_re_read(self):
        """Toggling changes observed state without changing the content hash."""
        script = self._script(r"""
const ctx = makeContext(ROWS);
(async () => {
  ctx.switchView('skills'); await tick();
  ctx.selectSkill(ROWS[0]); await tick();
  setRows([Object.assign({}, ROWS[0], {disabled: true}), ROWS[1]]);
  requests.length = 0;
  await ctx.loadSkills(); await tick();
  console.log(JSON.stringify({
    reads: requests.filter(u => u.includes('/api/skills/alpha')),
    disabled: ctx.selected && ctx.selected.disabled,
  }));
})();
""")
        out = _node(script)
        self.assertEqual(len(out["reads"]), 2, f"disabled change was not re-read: {out['reads']}")
        self.assertTrue(out["disabled"])

    def test_a_becoming_unreadable_is_still_re_read(self):
        """Healthy -> unreadable must re-read even though nothing else moved.

        The signature carries the ``malformed`` flag, so a document that becomes
        unreadable is detected as changed. This is the cheap half of the
        malformed contract; the hash-collision half is the test below.
        """
        script = self._script(r"""
const ctx = makeContext(ROWS);
(async () => {
  ctx.switchView('skills'); await tick();
  ctx.selectSkill(ROWS[0]); await tick();
  setRows([
    Object.assign({}, ROWS[0], {
      content_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      malformed: true,
      decode_error: 'SKILL.md changed to undecodable bytes at offset 0; fix it by hand',
    }),
    ROWS[1],
  ]);
  requests.length = 0;
  await ctx.loadSkills(); await tick();
  console.log(JSON.stringify({
    reads: requests.filter(u => u.includes('/api/skills/alpha')),
    malformed: ctx.selected && ctx.selected.malformed,
  }));
})();
""")
        out = _node(script)
        self.assertEqual(len(out["reads"]), 2, f"malformed change was not re-read: {out['reads']}")
        self.assertTrue(out["malformed"])

    def test_two_unreadable_versions_collide_on_hash_but_not_on_the_reason(self):
        """The two states that collide on hash must still both be visible.

        ``observations.document_observations`` hashes the document *text*, and a
        row for a document that could not be read is built with ``text=""``.
        So every unreadable version of a skill shares one ``content_hash`` --
        the sha256 of the empty string -- and the same ``malformed`` flag. Once a
        skill is already malformed, a *different* unreadable version therefore
        compares equal and the body is not re-downloaded. That is harmless for
        the body (a malformed row's body is empty either way) but only because
        the differing ``decode_error`` is carried across. Pin that, so dropping
        it from the carried set fails here instead of silently showing a stale
        repair instruction.
        """
        EMPTY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        broken = dict(self.ROWS[0], content_hash=EMPTY_HASH, malformed=True,
                      decode_error="first unreadable reason")
        script = self._script(r"""
// The document is already unreadable when it is first opened, so the detail
// record the app holds already carries the empty-text hash.
setRows(BROKEN);
const ctx = makeContext(BROKEN);
(async () => {
  ctx.selectSkill(BROKEN[0]); await tick();
  // Still malformed, same empty-text hash, a different reported reason.
  setRows([Object.assign({}, BROKEN[0], {
    decode_error: 'second unreadable reason: invalid byte at offset 12',
  }), BROKEN[1]]);
  requests.length = 0;
  await ctx.loadSkills(); await tick();
  console.log(JSON.stringify({
    reads: requests.filter(u => u.includes('/api/skills/alpha')),
    decodeError: ctx.selected && ctx.selected.decode_error,
    malformed: ctx.selected && ctx.selected.malformed,
  }));
})();
""").replace("BROKEN", json.dumps([broken, self.ROWS[1]]))
        out = _node(script)
        self.assertEqual(out["reads"], [], "an unreadable document re-downloaded its empty body")
        self.assertTrue(out["malformed"])
        self.assertEqual(out["decodeError"], "second unreadable reason: invalid byte at offset 12",
                         "the fresh decode_error was dropped instead of carried")

    def test_a_deselected_skill_is_cleared_rather_than_reused(self):
        script = self._script(r"""
const ctx = makeContext(ROWS);
(async () => {
  ctx.switchView('skills'); await tick();
  ctx.selectSkill(ROWS[0]); await tick();
  setRows([ROWS[1]]);
  await ctx.loadSkills(); await tick();
  console.log(JSON.stringify({selectedName: ctx.selectedName, selected: ctx.selected}));
})();
""")
        out = _node(script)
        self.assertIsNone(out["selectedName"])
        self.assertIsNone(out["selected"])


class TransportSeamBehaviourTests(unittest.TestCase):
    """The non-JSON transfers keep the seam's error contract."""

    def test_api_text_returns_the_body_and_throws_the_status(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
let status = 200;
const sandbox = {window:{}, document:{}, setTimeout, clearTimeout,
  fetch: async () => ({ok: status < 400, status, headers:{get:()=>'text/plain'}, text: async()=> 'raw body'})};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const apiText = sandbox.window.SkillManagerDomain.apiText;
(async () => {
  const ok = await apiText('/api/skills/x/raw');
  let err = null;
  status = 503;
  try { await apiText('/api/skills/x/raw'); } catch (e) { err = e.message; }
  console.log(JSON.stringify({ok, err}));
})();
"""
        out = _node(script)
        self.assertEqual(out["ok"], "raw body")
        self.assertEqual(out["err"], "HTTP 503")

    def test_api_blob_carries_the_server_filename(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {window:{}, document:{}, setTimeout, clearTimeout,
  fetch: async () => ({ok:true, status:200, headers:{get:(h)=> h === 'Content-Disposition' ? 'attachment; filename="export.tar.gz"' : null}, blob: async()=>({bytes:7})})};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
sandbox.window.SkillManagerDomain.apiBlob('/api/export').then(r => console.log(JSON.stringify(r)));
"""
        out = _node(script)
        self.assertEqual(out["filename"], "export.tar.gz")
        self.assertEqual(out["blob"], {"bytes": 7})

    def test_api_blob_falls_back_when_no_disposition_is_sent(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {window:{}, document:{}, setTimeout, clearTimeout,
  fetch: async () => ({ok:true, status:200, headers:{get:()=>null}, blob: async()=>({bytes:1})})};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
sandbox.window.SkillManagerDomain.apiBlob('/api/export').then(r => console.log(JSON.stringify(r)));
"""
        self.assertEqual(_node(script)["filename"], "")

    def test_export_uses_a_named_default_when_the_server_sends_none(self):
        script = _APP_HARNESS + r"""
const ctx = makeContext([{name:'a', scope:'global'}]);
(async () => {
  ctx.toast = (t) => { ctx.__lastToast = t; };
  await ctx.exportArchive(false);
  console.log(JSON.stringify({toast: ctx.__lastToast}));
})();
"""
        self.assertIn("skills-export.tar.gz", _node(script)["toast"])


class DomainLoadFailureTests(unittest.TestCase):
    """A missing seam must say so, not leave a blank page."""

    def test_missing_domain_reports_on_the_page(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
const appended = [];
const sandbox = {
  window: {},                       // no SkillManagerDomain at all
  Vue: {createApp(){ return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {
    body: {appendChild(el){ appended.push(el); }},
    createElement(){ const el = {style:{}, attrs:{},
      setAttribute(k,v){ this.attrs[k]=v; }, getAttribute(k){ return this.attrs[k] ?? null; },
      set textContent(v){ this.__t = v; }, get textContent(){ return this.__t; }};
      return el; },
    addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{}},
  },
  setTimeout, clearTimeout, console,
};
vm.createContext(sandbox);
let threw = null;
try { vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox); }
catch (e) { threw = e.message; }
console.log(JSON.stringify({threw, messages: appended.map(el => el.textContent), roles: appended.map(el => el.getAttribute('role'))}));
"""
        out = _node(script)
        self.assertEqual(len(out["messages"]), 1, "no failure message was rendered")
        self.assertIn("domain.js did not load", out["messages"][0])
        self.assertEqual(out["roles"][0], "alert")

    def test_app_guards_the_seam_before_destructuring_it(self):
        source = _read(APP_JS)
        guard = source.index("if (!SkillManagerDomain)")
        destructure = source.index("} = SkillManagerDomain;")
        self.assertLess(guard, destructure, "the seam is destructured before it is checked")


class MarkdownEscapingStillHoldsTests(unittest.TestCase):
    """The refactor must not weaken docs/08 locked rule 4."""

    def test_rendered_markdown_still_emits_only_its_own_tags(self):
        payloads = [
            "<script>alert(1)</script>",
            '<img src=x onerror="alert(1)">',
            "[x](javascript://alert(1))",
            "| a | b |\n|---|---|\n| <script>alert(1)</script> | x |",
            "**<svg/onload=alert(1)>**",
        ]
        script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const render = sandbox.window.SkillManagerDomain.renderMarkdown;
console.log(JSON.stringify(JSON.parse(process.argv[1]).map(render)));
"""
        rendered = json.loads(subprocess.run(
            ["node", "-e", script, json.dumps(payloads)],
            capture_output=True, text=True, check=True, cwd=str(ROOT),
        ).stdout)
        for payload, html in zip(payloads, rendered):
            with self.subTest(payload=payload):
                tags = set(re.findall(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)", html))
                self.assertLessEqual(tags, {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6",
                                            "ul", "ol", "li", "blockquote", "pre", "code",
                                            "a", "table", "thead", "tbody", "tr", "th", "td",
                                            "strong", "em", "hr", "div"}, tags)
                for match in re.finditer(r"<([a-zA-Z][^>]*)>", html):
                    self.assertNotRegex(match.group(1), r"\son[a-z]+\s*=")
                    self.assertNotIn("javascript:", match.group(1).lower())

    def test_the_two_v_html_bindings_still_route_through_the_escaping_renderer(self):
        html = _read(INDEX_HTML)
        bindings = re.findall(r'v-html="([^"]+)"', html)
        self.assertTrue(bindings, "expected the Markdown preview bindings to exist")
        for binding in bindings:
            # Either the block renderer or the inline one; both escape first.
            self.assertTrue(
                "renderMarkdown" in binding or "inlineMd" in binding,
                f"v-html binding is not routed through the escaping renderer: {binding!r}",
            )


if __name__ == "__main__":
    unittest.main()
