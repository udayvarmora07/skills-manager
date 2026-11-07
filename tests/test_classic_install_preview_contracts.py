"""Classic-UI contracts: Workspace Enter key and the install preview panel.

Two small defects are pinned here, both in the classic interface only:

* Enter in the Workspaces project field did nothing while the same commit ran
  from the "Check project" button.
* ``runInstall(false)`` rendered a locally built command in a toast and never
  asked the backend, so the offline bridge plan's trust blockers could not be
  seen.  The preview now posts ``preview: true`` and the template renders that
  response with mustache interpolation only.

The behaviour checks run the *checked-in* sources under Node against the real
``domain.js`` transport, and the last test posts the exact payload the UI sends
to a loopback server, so the keys the template reads are proven to exist.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "skillsmgr" / "webui" / "app.js"
INDEX_HTML = ROOT / "skillsmgr" / "webui" / "index.html"

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node(script: str) -> dict:
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, check=True, cwd=str(ROOT),
    )
    return json.loads(result.stdout)


# Loads the real domain.js, then the real app.js on top of it.  Only `fetch` and
# the DOM are stubbed, so the app exercises its own shipped transport and the
# request body under assertion is the one the browser would send.
_APP_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const requests = [];
function replyFor(body) {
  if (!body) return {};
  if (body.preview) {
    return {command:'npx skills add owner/repo -g', runner:'npx',
            source:'owner/repo', executed:false,
            registry:{blockers:['registry metadata needs an authenticated read'],
                      may_install:false, trust_verified:false, audit_links:[]}};
  }
  if (body.run) return {command:'npx skills add owner/repo -g', runner:'npx',
                        source:'owner/repo', executed:true, exit_code:1,
                        stdout:'', stderr:'boom'};
  return {};
}
let fail = false;
const fakeFetch = async (url, opts) => {
  const body = opts && opts.body ? JSON.parse(String(opts.body)) : null;
  requests.push({url:String(url), body, headers:(opts && opts.headers) || {}});
  if (fail) throw new Error('network down');
  return {ok:true, status:200,
    headers:{get:(h)=> h === 'content-type' ? 'application/json' : null},
    json: async()=>replyFor(body), text: async()=>JSON.stringify(replyFor(body))};
};
const anchor = () => ({get style(){return {};}, setAttribute(){}, appendChild(){}, click(){}, remove(){}});
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
  fetch: fakeFetch, setTimeout, clearTimeout, console,
  URL: {createObjectURL(){return 'blob:x';}, revokeObjectURL(){}},
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const def = sandbox.app;
function makeContext() {
  const ctx = Object.assign({}, def.data(), def.methods);
  ctx.install = Object.assign({}, def.data().install, {source:'owner/repo'});
  return ctx;
}
(async () => {
  const results = {};
  const dry = makeContext();
  await dry.runInstall(false);
  results.dry = {requests:requests.slice(), preview:dry.install.preview, busy:dry.busy, toasts:dry.toasts.length};
  requests.length = 0;
  const run = makeContext();
  run.install.preview = {stale:true};
  await run.runInstall(true);
  results.run = {requests:requests.slice(), preview:run.install.preview, busy:run.busy};
  requests.length = 0;
  fail = true;
  const failed = makeContext();
  await failed.runInstall(false);
  results.failed = {requests:requests.length, preview:failed.install.preview,
                    busy:failed.busy, toasts:failed.toasts.map((t)=>t.text)};
  process.stdout.write(JSON.stringify(results));
})().catch((e) => { console.error(e); process.exit(1); });
"""


class InstallPreviewSourceContracts(unittest.TestCase):
    """The template and handler shapes the two fixes shipped."""

    def test_workspace_enter_runs_the_check_guarded_by_loading(self):
        html = _read(INDEX_HTML)
        match = re.search(r"<input id=\"workspace-project\"[^>]*>", html)
        self.assertIsNotNone(match, "workspace project input is missing")
        tag = match.group(0)
        self.assertIn('@keydown.enter.prevent="!loadingWorkspaces && loadWorkspaces()"', tag)
        # The button stays the same action and the same disabled condition.
        self.assertIn('@click="loadWorkspaces"', html)
        self.assertIn(':disabled="loadingWorkspaces"', html)

    def test_preview_panel_renders_the_response_without_v_html(self):
        html = _read(INDEX_HTML)
        start = html.index("install.mode !== 'registry' && install.preview")
        end = html.index('<div class="modal-foot">', start)
        block = html[start:end]
        self.assertIn('class="preview-panel" role="status" aria-live="polite"', block)
        self.assertIn("<code>{{ install.preview.command }}</code>", block)
        self.assertIn("'Ready to install'", block)
        self.assertIn("'Not ready to install'", block)
        self.assertIn("may_install", block)
        # Plain mustache text per blocker: the payload is untrusted.
        self.assertIn('v-for="blocker in install.preview.registry.blockers"', block)
        self.assertIn("{{ blocker }}", block)
        self.assertNotIn("v-html", block)

    def test_audit_links_render_only_https_targets(self):
        html = _read(INDEX_HTML)
        start = html.index("install.mode !== 'registry' && install.preview")
        end = html.index('<div class="modal-foot">', start)
        block = html[start:end]
        self.assertIn("item.url.startsWith('https://')", block)
        self.assertIn(':href="link.url"', block)
        self.assertIn("{{ link.provider }}", block)
        self.assertIn('rel="noopener noreferrer"', block)
        self.assertIn('target="_blank"', block)


class InstallPreviewBehaviourTests(unittest.TestCase):
    """runInstall(false) posts the backend preview; the local toast is the fallback."""

    @classmethod
    def setUpClass(cls):
        cls.result = _node(_APP_HARNESS)

    def test_dry_run_posts_preview_true_to_the_install_route(self):
        dry = self.result["dry"]
        self.assertEqual(len(dry["requests"]), 1)
        request = dry["requests"][0]
        self.assertEqual(request["url"], "/api/install")
        self.assertEqual(request["body"]["source"], "owner/repo")
        self.assertEqual(request["body"]["runner"], "npx")
        self.assertEqual(request["body"]["scope"], "global")
        self.assertIs(request["body"]["preview"], True)
        self.assertFalse(request["body"]["copy"])
        self.assertFalse(request["body"]["list_only"])
        self.assertNotIn("run", request["body"])

    def test_dry_run_stores_the_response_and_clears_busy(self):
        dry = self.result["dry"]
        self.assertIsNotNone(dry["preview"])
        self.assertEqual(dry["preview"]["registry"]["blockers"], ["registry metadata needs an authenticated read"])
        self.assertIs(dry["preview"]["registry"]["may_install"], False)
        self.assertFalse(dry["busy"])
        # Success does not fall back to the local toast.
        self.assertEqual(dry["toasts"], 0)

    def test_confirmed_run_clears_the_previous_preview(self):
        run = self.result["run"]
        self.assertEqual(len(run["requests"]), 1)
        self.assertIs(run["requests"][0]["body"]["run"], True)
        self.assertNotIn("preview", run["requests"][0]["body"])
        self.assertIsNone(run["preview"])
        self.assertFalse(run["busy"])

    def test_request_failure_falls_back_to_the_local_toast(self):
        failed = self.result["failed"]
        self.assertEqual(failed["requests"], 1)
        self.assertIsNone(failed["preview"])
        self.assertFalse(failed["busy"])
        self.assertEqual(len(failed["toasts"]), 1)
        self.assertIn("npx skills add owner/repo -g", failed["toasts"][0])


class InstallPreviewRouteTests(unittest.TestCase):
    """The exact UI payload returns the keys the template reads."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = {k: os.environ.get(k) for k in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore)
        home = Path(self._tmp.name) / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self._tmp.name) / "data")
        self.store = Store()
        self.store.init_db()
        self.server = WebAppServer(self.store, port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def post(self, path, payload):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Host": f"127.0.0.1:{self.server.port}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_preview_payload_returns_blockers_and_may_install(self):
        payload = {
            "source": "owner/repo",
            "runner": "npx",
            "scope": "global",
            "copy": False,
            "list_only": False,
            "preview": True,
        }
        status, data = self.post("/api/install", payload)
        self.assertEqual(status, 200)
        self.assertIs(data["executed"], False)
        self.assertIn("npx skills add owner/repo -g", data["command"])
        plan = data["registry"]
        self.assertIn("blockers", plan)
        self.assertIsInstance(plan["blockers"], list)
        self.assertIn("may_install", plan)
        self.assertIsInstance(plan["may_install"], bool)
        self.assertIn("audit_links", plan)
        self.assertIsInstance(plan["audit_links"], list)


if __name__ == "__main__":
    unittest.main()
