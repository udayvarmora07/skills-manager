#!/usr/bin/env python3
"""Dev-only Chromium smoke harness for the local Skills Manager UI.

This intentionally uses the system Chrome DevTools Protocol instead of adding
runtime or test dependencies. It starts a hermetic web server, launches
headless Chrome with a temporary profile, captures console/runtime/network
failures, and checks the supported viewport matrix. It is a developer check,
not part of the product CLI. Requirements: system Chrome/Chromium and Node >= 22
(the CDP client uses the global WebSocket, which older Node releases do not
provide).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Thread

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer

ROOT = Path(__file__).resolve().parent
VIEWPORTS = ((320, 700), (400, 800), (640, 900), (900, 800), (1280, 900))


def _chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium is required for browser_harness.py")


def _devtools_port(process: subprocess.Popen[str], profile: Path, timeout: float = 30.0) -> int:
    """Return the DevTools port Chrome actually bound.

    Chrome writes the port it bound to ``DevToolsActivePort`` inside its
    profile directory. Letting the OS choose the port (``--remote-debugging-
    port=0``) and reading that file keeps the probe working when 9222 is taken
    and gives a cold runner more than a few seconds to start Chrome.
    """
    port_file = profile / "DevToolsActivePort"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Chrome exited before DevTools became available")
        try:
            port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        except (OSError, ValueError, IndexError):
            time.sleep(0.05)
            continue
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.5) as response:
                if response.status == 200:
                    return port
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.05)
    raise RuntimeError("Chrome DevTools endpoint did not start")


def _run_probe(url: str, width: int, height: int, port: int) -> dict:
    """Use Chrome's remote debugging endpoint through a tiny Node CDP client."""
    script = r"""
const http = require('http');
if (typeof globalThis.WebSocket !== 'function') {
  console.error('browser_harness.py needs Node >= 22 for the global WebSocket used by the CDP client');
  process.exit(2);
}
const WebSocket = globalThis.WebSocket;
const url = process.argv[1], width = Number(process.argv[2]), height = Number(process.argv[3]), port = Number(process.argv[4]);
function getJson(path) { return new Promise((resolve, reject) => { const req=http.request('http://127.0.0.1:' + port + path, {method:'PUT'}, r => { let b=''; r.on('data', x=>b+=x); r.on('end',()=>resolve(JSON.parse(b))); }); req.on('error',reject); req.end(); }); }
(async () => {
  const tabs = await getJson('/json/new?' + encodeURIComponent(url));
  const ws = new WebSocket(tabs.webSocketDebuggerUrl);
  let id = 0, pending = new Map(), errors = [], warnings = [], failed = [];
  ws.onmessage = event => { const m = JSON.parse(event.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else if (m.method === 'Runtime.consoleAPICalled') { const t=m.params.type; const text=(m.params.args||[]).map(a=>a.value||a.description||'').join(' '); (t==='error'?errors:warnings).push(text); } else if (m.method === 'Runtime.exceptionThrown') { const d=m.params.exceptionDetails; errors.push(d.exception && (d.exception.description || d.exception.value) || d.text || 'runtime exception'); } else if (m.method === 'Network.loadingFailed') failed.push(m.params.errorText); };
  const send = (method, params={}) => new Promise(resolve => { const n=++id; pending.set(n, resolve); ws.send(JSON.stringify({id:n,method,params})); });
  await new Promise(resolve => ws.onopen=resolve);
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', {width,height,deviceScaleFactor:1,mobile:false}); await send('Page.navigate',{url});
  await new Promise(r=>setTimeout(r,1200));
  const value = await send('Runtime.evaluate',{expression:'JSON.stringify({title:document.title,modalCount:document.querySelectorAll("[role=dialog]").length,overflow:document.documentElement.scrollWidth>window.innerWidth})',returnByValue:true});
  ws.close(); console.log(JSON.stringify({width,height,document:JSON.parse(value.result.result.value),errors,warnings,failed}));
})().catch(e=>{ console.error(e.stack||String(e)); process.exit(1); });
"""
    result = subprocess.run(["node", "-e", script, url, str(width), str(height), str(port)], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-profile", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="skillsmgr-browser-") as directory:
        os.environ["SKILLS_MANAGER_DATA"] = directory
        store = Store()
        store.init_db()
        store.create("browser-probe", "A browser harness fixture skill")
        server = WebAppServer(store, port=0)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        profile = Path(directory) / "chrome"
        chrome = subprocess.Popen([_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=0", "--user-data-dir=" + str(profile), "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        try:
            port = _devtools_port(chrome, profile)
            results = [_run_probe(server.url, width, height, port) for width, height in VIEWPORTS]
            failures = [r for r in results if r["errors"] or r["failed"] or r["document"]["overflow"]]
            print(json.dumps({"viewports": results, "passed": not failures}, indent=2))
            return 1 if failures else 0
        finally:
            chrome.terminate()
            chrome.wait(timeout=5)
            server.shutdown()
            server_thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(run())
