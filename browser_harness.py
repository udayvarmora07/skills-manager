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

from skillsmgr.launcher_security import trusted_executable
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer

ROOT = Path(__file__).resolve().parent
VIEWPORTS = ((320, 700), (400, 800), (640, 900), (900, 800), (1280, 900), (1440, 900))


def _chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = trusted_executable(name, which=shutil.which)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium is required for browser_harness.py")


def _node() -> str:
    """Return a trusted Node executable for the small CDP client."""
    path = trusted_executable("node", which=shutil.which)
    if path:
        return path
    raise RuntimeError("a trusted Node executable is required for browser_harness.py")


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


def _run_probe(
    url: str, width: int, height: int, port: int,
    screenshot: Path | None = None, scenario: str = "populated",
) -> dict:
    """Use Chrome's remote debugging endpoint through a tiny Node CDP client."""
    script = r"""
const http = require('http');
if (typeof globalThis.WebSocket !== 'function') {
  console.error('browser_harness.py needs Node >= 22 for the global WebSocket used by the CDP client');
  process.exit(2);
}
const WebSocket = globalThis.WebSocket;
const url = process.argv[1], width = Number(process.argv[2]), height = Number(process.argv[3]), port = Number(process.argv[4]), screenshot = process.argv[5] || '', scenario = process.argv[6] || 'populated';
const navigationStarted = Date.now();
function getJson(path) { return new Promise((resolve, reject) => { const req=http.request('http://127.0.0.1:' + port + path, {method:'PUT'}, r => { let b=''; r.on('data', x=>b+=x); r.on('end',()=>resolve(JSON.parse(b))); }); req.on('error',reject); req.end(); }); }
(async () => {
  const tabs = await getJson('/json/new?' + encodeURIComponent(url));
  const ws = new WebSocket(tabs.webSocketDebuggerUrl);
  let id = 0, pending = new Map(), errors = [], warnings = [], failed = [];
  ws.onmessage = event => { const m = JSON.parse(event.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else if (m.method === 'Runtime.consoleAPICalled') { const t=m.params.type; const text=(m.params.args||[]).map(a=>a.value||a.description||'').join(' '); (t==='error'?errors:warnings).push(text); } else if (m.method === 'Runtime.exceptionThrown') { const d=m.params.exceptionDetails; errors.push(d.exception && (d.exception.description || d.exception.value) || d.text || 'runtime exception'); } else if (m.method === 'Network.loadingFailed') failed.push(m.params.errorText); };
  const send = (method, params={}) => new Promise(resolve => { const n=++id; pending.set(n, resolve); ws.send(JSON.stringify({id:n,method,params})); });
  await new Promise(resolve => ws.onopen=resolve);
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', {width,height,deviceScaleFactor:1,mobile:false});
  if (scenario === 'scope-failure' || scenario === 'inventory-failure' || scenario === 'unavailable-root') {
    const failedRoute = scenario === 'scope-failure' ? '/api/scopes' : '/api/skills?scope=all';
    const preload = scenario === 'unavailable-root'
      ? `(() => { const original=window.fetch; window.fetch=function(input,init){ const target=typeof input==='string'?input:(input && input.url)||''; return original.call(this,input,init).then(response=>{ if(!target.includes('/api/scopes')) return response; return response.clone().json().then(scopes=>{ scopes.push({id:'unavailable-fixture',label:'Unavailable fixture',path:'/private/unavailable-root',kind:'agent',writable:false,availability:'unsupported',recursive:false,supported:false,exists:true,count:0,tokens:0}); return new Response(JSON.stringify(scopes),{status:response.status,headers:{'Content-Type':'application/json'}}); }); }); }; })();`
      : `(() => { const original=window.fetch; window.fetch=function(input,init){ const target=typeof input==='string'?input:(input && input.url)||''; if(target.includes(${JSON.stringify(failedRoute)})) return Promise.reject(new Error('synthetic first-scan failure')); return original.call(this,input,init); }; })();`;
    await send('Page.addScriptToEvaluateOnNewDocument', {source:preload});
  }
  await send('Page.navigate',{url});
  const readyExpression = `(() => {
    const app = document.querySelector('#app');
    const overview = document.querySelector('[data-overview-ready="true"]');
    const heading = document.querySelector('#overview-title');
    const representative = overview && (overview.querySelector('.overview-health') || overview.querySelector('[data-overview-empty="true"]') || overview.querySelector('.first-scan-guide'));
    const guide = overview && overview.querySelector('.first-scan-guide');
    const status = guide && guide.querySelector('.first-scan-status');
    return {ready: !!app && !app.hasAttribute('v-cloak') && !!heading && !!representative && !!status, scanComplete: !!(status && status.innerText.startsWith('Scan complete:')), marker: overview ? overview.innerText.slice(0, 400) : ''};
  })()`;
  let previousMarker = null, stableChecks = 0, ready = false, lastState = null;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const probe = await send('Runtime.evaluate', {expression: readyExpression, returnByValue:true});
    const state = probe.result && probe.result.result && probe.result.result.value;
    lastState = state;
    if (state && state.ready && state.marker === previousMarker) stableChecks += 1;
    else stableChecks = 0;
    previousMarker = state ? state.marker : null;
    if (state && state.ready && stableChecks >= 2) { ready = true; break; }
    await new Promise(r=>setTimeout(r,100));
  }
  if (!ready) throw new Error('Vue overview did not reach a stable rendered state: ' + JSON.stringify({lastState, errors, failed}));
  const firstUsefulMs = Date.now() - navigationStarted;
  await send('Runtime.evaluate', {expression:`(() => { const trigger=document.querySelector('[aria-label="Open actions menu"]'); if (trigger) { trigger.focus(); trigger.click(); } return !!trigger; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,80));
  const menuOpen = await send('Runtime.evaluate', {expression:`(() => { const menu=document.querySelector('#actions-menu'); const items=[...document.querySelectorAll('#actions-menu [role="menuitem"]:not([disabled])')]; return {open:!!menu, focusedFirst:!!(items[0] && document.activeElement === items[0]), count:items.length}; })()`, returnByValue:true});
  const menuOpenState = menuOpen.result && menuOpen.result.result && menuOpen.result.result.value;
  if (!menuOpenState || !menuOpenState.open || !menuOpenState.focusedFirst || !menuOpenState.count) errors.push('Actions menu did not open with focus on its first available item');
  await send('Runtime.evaluate', {expression:`(() => { const item=document.activeElement; if (item) item.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true})); return true; })()`, returnByValue:true});
  const menuArrow = await send('Runtime.evaluate', {expression:`(() => { const items=[...document.querySelectorAll('#actions-menu [role="menuitem"]:not([disabled])')]; return {focusedSecond:!!(items[1] && document.activeElement === items[1])}; })()`, returnByValue:true});
  const menuArrowState = menuArrow.result && menuArrow.result.result && menuArrow.result.result.value;
  if (!menuArrowState || !menuArrowState.focusedSecond) errors.push('Actions menu ArrowDown did not move focus to the next available item');
  await send('Runtime.evaluate', {expression:`(() => { const menu=document.querySelector('#actions-menu'); if (menu) menu.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); return true; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,80));
  const menuClosed = await send('Runtime.evaluate', {expression:`(() => ({open:!!document.querySelector('#actions-menu'),trigger:document.activeElement === document.querySelector('[aria-label="Open actions menu"]')}))()`, returnByValue:true});
  const menuClosedState = menuClosed.result && menuClosed.result.result && menuClosed.result.result.value;
  if (!menuClosedState || menuClosedState.open || !menuClosedState.trigger) errors.push('Actions menu did not close safely or return focus to its trigger');
  await send('Runtime.evaluate', {expression:`(() => { const trigger=document.querySelector('.command-trigger'); if (trigger) trigger.focus(); document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true})); return true; })()`, returnByValue:true});
  let commandReady = false, commandState = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const command = await send('Runtime.evaluate', {expression:`(() => { const dialog=document.querySelector('[data-modal="commands"]'); const input=document.querySelector('#command-palette-input'); const status=document.querySelector('#command-palette-status'); return {dialog:!!dialog, focused:document.activeElement === input, results:document.querySelectorAll('#command-palette-results [role="option"]').length, status:status ? status.textContent.trim() : ''}; })()`, returnByValue:true});
    commandState = command.result && command.result.result && command.result.result.value;
    if (commandState && commandState.dialog && commandState.focused && commandState.results > 0 && /command/.test(commandState.status)) { commandReady = true; break; }
    await new Promise(r=>setTimeout(r,50));
  }
  if (!commandReady) errors.push('Commands shortcut did not open a focused, populated command palette: ' + JSON.stringify(commandState));
  const commandKeyboard = await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (!input) return {active:'',end:'',home:'',endVisible:false,homeVisible:false}; input.dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true})); return true; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,220));
  const commandEnd = await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); const options=[...document.querySelectorAll('#command-palette-results [role="option"]')]; const activeId=input && input.getAttribute('aria-activedescendant') || ''; const active=activeId ? document.getElementById(activeId) : null; const list=document.querySelector('#command-palette-results'); const epsilon=0.5; const optionVisible=!!(active && list && active.getBoundingClientRect().top >= list.getBoundingClientRect().top - epsilon && active.getBoundingClientRect().bottom <= list.getBoundingClientRect().bottom + epsilon); return {active:document.activeElement && document.activeElement.id,end:activeId,last:options.length ? options[options.length - 1].id : '',endVisible:optionVisible}; })()`, returnByValue:true});
  const commandHome = await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (input) input.dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true})); return true; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,220));
  const commandHomeState = await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); const options=[...document.querySelectorAll('#command-palette-results [role="option"]')]; const activeId=input && input.getAttribute('aria-activedescendant') || ''; const active=activeId ? document.getElementById(activeId) : null; const list=document.querySelector('#command-palette-results'); const epsilon=0.5; const optionVisible=!!(active && list && active.getBoundingClientRect().top >= list.getBoundingClientRect().top - epsilon && active.getBoundingClientRect().bottom <= list.getBoundingClientRect().bottom + epsilon); return {active:document.activeElement && document.activeElement.id,home:activeId,first:options.length ? options[0].id : '',homeVisible:optionVisible}; })()`, returnByValue:true});
  const commandKeyboardState = {end: commandEnd.result && commandEnd.result.result && commandEnd.result.result.value, home: commandHomeState.result && commandHomeState.result.result && commandHomeState.result.result.value};
  if (!commandKeyboardState.end || commandKeyboardState.end.active !== 'command-palette-input' || commandKeyboardState.end.end !== commandKeyboardState.end.last || !commandKeyboardState.end.endVisible || !commandKeyboardState.home || commandKeyboardState.home.active !== 'command-palette-input' || commandKeyboardState.home.home !== commandKeyboardState.home.first || !commandKeyboardState.home.homeVisible) errors.push('Commands palette did not retain input focus and keep Home/End options visible');
  const commandTab = await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (input) { input.focus(); input.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true})); } return {focus:document.activeElement && document.activeElement.id,option:!!(document.activeElement && document.activeElement.closest('[role="option"]')),interactive:document.querySelectorAll('[role="option"] button, [role="option"] input, [role="option"] a, [role="option"][tabindex]:not([tabindex="-1"])').length}; })()`, returnByValue:true});
  const commandTabState = commandTab.result && commandTab.result.result && commandTab.result.result.value;
  if (!commandTabState || commandTabState.option || commandTabState.interactive) errors.push('Tab entered a command option row');
  await send('Runtime.evaluate', {expression:`(() => { document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); return true; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,100));
  const commandClosed = await send('Runtime.evaluate', {expression:`(() => ({open:!!document.querySelector('[data-modal="commands"]'),focus:document.activeElement && document.activeElement.className || '',trigger:document.querySelector('.command-trigger') === document.activeElement}))()`, returnByValue:true});
  const commandClosedState = commandClosed.result && commandClosed.result.result && commandClosed.result.result.value;
  if (!commandClosedState || commandClosedState.open || !commandClosedState.trigger) errors.push('Commands palette did not close safely or return focus to its trigger');
  await send('Runtime.evaluate', {expression:`(() => { const trigger=document.querySelector('.command-trigger'); if (trigger) trigger.click(); return true; })()`, returnByValue:true});
  let settingsReady = false, settingsState = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const state = await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (!input) return {open:false}; const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; set.call(input,'settings'); input.dispatchEvent(new Event('input',{bubbles:true})); return {open:true,focus:document.activeElement === input}; })()`, returnByValue:true});
    settingsState = state.result && state.result.result && state.result.result.value;
    if (settingsState && settingsState.open && settingsState.focus) { settingsReady = true; break; }
    await new Promise(r=>setTimeout(r,50));
  }
  if (settingsReady) {
    await new Promise(r=>setTimeout(r,50));
    await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (input) input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); return true; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,100));
    const settingsFocus = await send('Runtime.evaluate', {expression:`(() => ({view:document.querySelector('#view-title') && document.querySelector('#view-title').textContent.trim(), focused:document.activeElement && document.activeElement.id}))()`, returnByValue:true});
    const settingsFocusState = settingsFocus.result && settingsFocus.result.result && settingsFocus.result.result.value;
    if (!settingsFocusState || settingsFocusState.view !== 'Settings' || settingsFocusState.focused !== 'view-title') errors.push('Settings command did not focus its destination heading');
  } else errors.push('Settings command palette did not open');
  const settingsTrigger = await send('Runtime.evaluate', {expression:`(() => { const trigger=document.querySelector('.command-trigger'); if (trigger) trigger.click(); return true; })()`, returnByValue:true});
  if (settingsTrigger.result && settingsTrigger.result.result && settingsTrigger.result.result.value) {
    await new Promise(r=>setTimeout(r,50));
    await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; if (input) { set.call(input,'create'); input.dispatchEvent(new Event('input',{bubbles:true})); } return true; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,50));
    await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (input) input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); return true; })()`, returnByValue:true});
    let createReady = false, createState = null;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const state = await send('Runtime.evaluate', {expression:`(() => ({dialog:!!document.querySelector('[data-modal="skill"]'),commands:!!document.querySelector('[data-modal="commands"]')}))()`, returnByValue:true});
      createState = state.result && state.result.result && state.result.result.value;
      if (createState && createState.dialog && !createState.commands) { createReady = true; break; }
      await new Promise(r=>setTimeout(r,50));
    }
    if (!createReady) errors.push('Create command did not open its destination dialog');
    await send('Runtime.evaluate', {expression:`(() => { document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); return true; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,100));
    const createClosed = await send('Runtime.evaluate', {expression:`(() => ({dialog:!!document.querySelector('[data-modal="skill"]'),trigger:document.querySelector('.command-trigger') === document.activeElement}))()`, returnByValue:true});
    const createClosedState = createClosed.result && createClosed.result.result && createClosed.result.result.value;
    if (!createClosedState || createClosedState.dialog || !createClosedState.trigger) errors.push('Closing Create did not return focus to Commands trigger: ' + JSON.stringify(createClosedState));
  }
  const libraryTrigger = await send('Runtime.evaluate', {expression:`(() => { const trigger=document.querySelector('.command-trigger'); if (trigger) trigger.click(); return !!trigger; })()`, returnByValue:true});
  if (libraryTrigger.result && libraryTrigger.result.result && libraryTrigger.result.result.value) {
    await new Promise(r=>setTimeout(r,80));
    await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; if (input) { set.call(input,'library'); input.dispatchEvent(new Event('input',{bubbles:true})); } return true; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,80));
    await send('Runtime.evaluate', {expression:`(() => { const input=document.querySelector('#command-palette-input'); if (input) input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); return true; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,140));
    const libraryFocus = await send('Runtime.evaluate', {expression:`(() => ({view:document.querySelector('#library-view-title') ? 'skills' : '', focused:document.activeElement && document.activeElement.id, visible:!!(document.querySelector('#library-view-title') && document.querySelector('#library-view-title').getClientRects().length)}))()`, returnByValue:true});
    const libraryFocusState = libraryFocus.result && libraryFocus.result.result && libraryFocus.result.result.value;
    if (!libraryFocusState || libraryFocusState.view !== 'skills' || libraryFocusState.focused !== 'library-view-title' || !libraryFocusState.visible) errors.push('Library command did not focus the visible Library destination');
  }
  const qualityTab = await send('Runtime.evaluate', {expression:`(() => { const tab = [...document.querySelectorAll('.viewtabs button')].find(el => (el.innerText || '').trim() === 'Quality'); if (tab) tab.click(); return !!tab; })()`, returnByValue:true});
  const qualityTabFound = !!(qualityTab.result && qualityTab.result.result && qualityTab.result.result.value);
  if (!qualityTabFound) errors.push('Quality navigation tab was not found');
  let qualityReady = false;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const quality = await send('Runtime.evaluate', {expression:`(() => ({view: document.querySelector('#view-title') ? document.querySelector('#view-title').textContent.trim() : '', evidence: !!document.querySelector('.quality-overview, .quality-section'), overflow: document.documentElement.scrollWidth > window.innerWidth}))()`, returnByValue:true});
    const state = quality.result && quality.result.result && quality.result.result.value;
    if (state && state.view === 'Quality' && state.evidence && !state.overflow) { qualityReady = true; break; }
    await new Promise(r=>setTimeout(r,50));
  }
  if (!qualityReady) errors.push('Quality view did not render bounded evidence without overflow');
  await send('Runtime.evaluate', {expression:`(() => { const tab = [...document.querySelectorAll('.viewtabs button')].find(el => (el.innerText || '').trim() === 'Overview'); if (tab) tab.click(); return !!tab; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,100));
  const guideInitial = await send('Runtime.evaluate', {expression:`(() => { const guide=document.querySelector('.first-scan-guide'); const attention=[...document.querySelectorAll('.attention-item h3')].map(node=>node.innerText); return {visible:!!guide,status:(document.querySelector('.first-scan-status') || {}).innerText || '',empty:!!document.querySelector('[data-overview-empty="true"]'),loadError:!!document.querySelector('.overview-load-error'),unavailable:!!(guide && guide.innerText.includes('detected root is missing or unsupported')),malformedAttention:attention.some(text=>text.includes('malformed or unaddressable')),divergentAttention:attention.some(text=>text.includes('divergent copies')),instanceActionDisabled:!!(document.querySelector('[data-first-scan-library]') && document.querySelector('[data-first-scan-library]').disabled),overflow:document.documentElement.scrollWidth>window.innerWidth}; })()`, returnByValue:true});
  const guideInitialState = guideInitial.result && guideInitial.result.result && guideInitial.result.result.value;
  const scanExpected = scenario === 'scope-failure'
    ? guideInitialState && /root details are unavailable/i.test(guideInitialState.status) && !guideInitialState.empty
    : scenario === 'inventory-failure'
      ? guideInitialState && /inventory scan failed/i.test(guideInitialState.status) && guideInitialState.loadError && !guideInitialState.empty
      : scenario === 'unavailable-root'
        ? guideInitialState && guideInitialState.status.startsWith('Scan complete:') && guideInitialState.unavailable
      : guideInitialState && guideInitialState.status.startsWith('Scan complete:')
        && (scenario !== 'empty' || guideInitialState.empty)
        && (scenario !== 'populated' || (guideInitialState.malformedAttention && guideInitialState.divergentAttention));
  if (!guideInitialState || !guideInitialState.visible || !scanExpected || guideInitialState.overflow) errors.push('First-scan guide did not represent the expected scan state without overflow: ' + JSON.stringify(guideInitialState));
  if (scenario === 'empty') {
    await send('Runtime.evaluate', {expression:`(() => { const action=[...document.querySelectorAll('.overview-empty-actions button')].find(button => button.innerText.includes('Create your first skill')); if(action) action.click(); return !!action; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,80));
    const emptyCreate = await send('Runtime.evaluate', {expression:`(() => ({open:!!document.querySelector('[data-modal="skill"]')}))()`, returnByValue:true});
    if (!(emptyCreate.result && emptyCreate.result.result && emptyCreate.result.result.value && emptyCreate.result.result.value.open)) errors.push('Empty first-run Create action did not open its existing dialog');
    await send('Runtime.evaluate', {expression:`(() => { document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); return true; })()`, returnByValue:true});
    await new Promise(r=>setTimeout(r,80));
  }
  await send('Runtime.evaluate', {expression:`(() => { const skip=document.querySelector('[data-first-scan-skip]'); if (skip) skip.click(); return !!skip; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,80));
  const guideSkipped = await send('Runtime.evaluate', {expression:`(() => ({hidden:!document.querySelector('.first-scan-guide'),restart:!!document.querySelector('[data-first-scan-restart]')}))()`, returnByValue:true});
  const guideSkippedState = guideSkipped.result && guideSkipped.result.result && guideSkipped.result.result.value;
  if (!guideSkippedState || !guideSkippedState.hidden || !guideSkippedState.restart) errors.push('First-scan guide skip did not hide the guide or offer restart');
  await send('Runtime.evaluate', {expression:`(() => { const restart=document.querySelector('[data-first-scan-restart]'); if (restart) restart.click(); return !!restart; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,80));
  const guideRestarted = await send('Runtime.evaluate', {expression:`(() => ({visible:!!document.querySelector('.first-scan-guide'),focused:document.activeElement && document.activeElement.id==='first-scan-title'}))()`, returnByValue:true});
  const guideRestartedState = guideRestarted.result && guideRestarted.result.result && guideRestarted.result.result.value;
  if (!guideRestartedState || !guideRestartedState.visible || !guideRestartedState.focused) errors.push('First-scan guide restart did not restore the guide and focus its heading');
  await send('Runtime.evaluate', {expression:`(() => { const explain=document.querySelector('[data-first-scan-explain]'); if (explain) explain.click(); return !!explain; })()`, returnByValue:true});
  let explainReady = false, explainState = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const state = await send('Runtime.evaluate', {expression:`(() => ({result:!!document.querySelector('.first-scan-result'),error:!!document.querySelector('.first-scan-caution[role="status"]'),text:(document.querySelector('.first-scan-result') || document.querySelector('.first-scan-caution[role="status"]') || {}).innerText || ''}))()`, returnByValue:true});
    explainState = state.result && state.result.result && state.result.result.value;
    if (explainState && (explainState.result || explainState.error)) { explainReady = true; break; }
    await new Promise(r=>setTimeout(r,50));
  }
  if (!explainReady || !/unresolved/.test(explainState.text)) errors.push('Read-only effective explanation did not return a clearly unresolved result');
  const previewClicked = await send('Runtime.evaluate', {expression:`(() => { const preview=document.querySelector('[data-first-scan-preview-target]'); if (preview && !preview.disabled) preview.click(); return !!(preview && !preview.disabled); })()`, returnByValue:true});
  const previewWasClicked = !!(previewClicked.result && previewClicked.result.result && previewClicked.result.result.value);
  let previewReady = false, previewState = null;
  for (let attempt = 0; previewWasClicked && attempt < 40; attempt += 1) {
    const state = await send('Runtime.evaluate', {expression:`(() => ({heading:document.querySelector('#view-title') && document.querySelector('#view-title').textContent.trim(),action:!!document.querySelector('button[aria-label="Update this exact skill instance from a folder"]'),guide:!!document.querySelector('.first-scan-guide')}))()`, returnByValue:true});
    previewState = state.result && state.result.result && state.result.result.value;
    if (previewState && previewState.heading && previewState.action && !previewState.guide) { previewReady = true; break; }
    await new Promise(r=>setTimeout(r,50));
  }
  const previewDisabledForEmpty = scenario === 'empty' && !previewWasClicked
    && !!(guideInitialState && guideInitialState.instanceActionDisabled);
  if (scenario === 'populated' && !previewReady) errors.push('First-scan preview link did not land on the exact writable instance surface: ' + JSON.stringify(previewState));
  if (scenario === 'empty' && !previewDisabledForEmpty) errors.push('Empty inventory did not disable exact-instance actions');
  await send('Runtime.evaluate', {expression:`(() => { const tab = [...document.querySelectorAll('.viewtabs button')].find(el => (el.innerText || '').trim() === 'Overview'); if (tab) tab.click(); return !!tab; })()`, returnByValue:true});
  await new Promise(r=>setTimeout(r,100));
  const guideFinal = await send('Runtime.evaluate', {expression:`(() => ({visible:!!document.querySelector('.first-scan-guide'),overflow:document.documentElement.scrollWidth>window.innerWidth,focusable:!!document.querySelector('[data-first-scan-skip]:not([disabled])'),result:!!document.querySelector('.first-scan-result')}))()`, returnByValue:true});
  const guideFinalState = guideFinal.result && guideFinal.result.result && guideFinal.result.result.value;
  if (!guideFinalState || !guideFinalState.visible || guideFinalState.overflow || !guideFinalState.focusable || !guideFinalState.result) errors.push('First-scan guide lost its accessible state after returning from the exact Library detail');
  if (screenshot) {
    const capture = await send('Page.captureScreenshot', {format:'png', captureBeyondViewport:true});
    require('fs').writeFileSync(screenshot, Buffer.from(capture.result.data, 'base64'));
  }
  const value = await send('Runtime.evaluate',{expression:'JSON.stringify({title:document.title,modalCount:document.querySelectorAll("[role=dialog]").length,overflow:document.documentElement.scrollWidth>window.innerWidth})',returnByValue:true});
  ws.close(); console.log(JSON.stringify({width,height,scenario,document:JSON.parse(value.result.result.value),firstScan:{first_useful_ms:firstUsefulMs,scan_state:guideInitialState && guideInitialState.status,malformed_attention:!!(guideInitialState && guideInitialState.malformedAttention),divergent_attention:!!(guideInitialState && guideInitialState.divergentAttention),unavailable_root:!!(guideInitialState && guideInitialState.unavailable),scan_complete:!!(guideFinalState && guideFinalState.visible),skip_restart:!!(guideSkippedState && guideSkippedState.hidden && guideRestartedState && guideRestartedState.visible),effective_explain:!!explainReady,exact_preview_target:!!previewReady,preview_disabled_for_empty:previewDisabledForEmpty},errors,warnings,failed}));
})().catch(e=>{ console.error(e.stack||String(e)); process.exit(1); });
"""
    screenshot_arg = str(screenshot) if screenshot is not None else ""
    result = subprocess.run([_node(), "-e", script, url, str(width), str(height), str(port), screenshot_arg, scenario], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-profile", action="store_true")
    parser.add_argument(
        "--screenshots-dir",
        type=Path,
        help="also save one PNG per viewport in this developer-selected directory",
    )
    args = parser.parse_args()
    screenshot_dir = None
    if args.screenshots_dir is not None:
        screenshot_dir = args.screenshots_dir.expanduser().resolve()
        screenshot_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(screenshot_dir, 0o700)
    with tempfile.TemporaryDirectory(prefix="skillsmgr-browser-") as directory:
        root = Path(directory)
        home = root / "home"
        data_dir = root / "data"
        home.mkdir(parents=True, exist_ok=True)
        os.environ["HOME"] = str(home)
        os.environ["XDG_DATA_HOME"] = str(home / ".local" / "share")
        os.environ["SKILLS_MANAGER_DATA"] = str(data_dir)
        store = Store(data_dir)
        store.init_db()
        store.create("browser-probe", "A browser harness fixture skill", body="# Browser probe\n\nA healthy active fixture.\n")
        store.create("disabled-probe", "A disabled fixture skill")
        store.disable("disabled-probe")
        store.create("recoverable-probe", "A recoverable fixture skill")
        store.remove("recoverable-probe")
        store.create("long-context-skill-name-for-responsive-proof", "A deliberately long description that checks wrapping and reflow without hiding the action text on narrow screens.", body="# Long context\n\nThis fixture keeps the overview and Library honest at narrow widths.\n")
        # Scope fixtures use the existing filesystem adapter so aggregate
        # observations exercise the same path as a real installation.
        from skillsmgr import scopes

        scopes.set_global_store(store)
        scopes.create_skill("agents", "browser-probe", "A divergent agent copy of the browser probe", body="# Browser probe\n\nDivergent copy.\n")
        scope = next((item for item in scopes.known_scopes() if item.id == "agents"), None)
        if scope:
            malformed = scope.base / "malformed-observed"
            malformed.mkdir(parents=True, exist_ok=True)
            (malformed / "SKILL.md").write_text("---\nname: [broken\n---\n", encoding="utf-8")
            unaddressable = scope.base / "not addressable"
            unaddressable.mkdir(parents=True, exist_ok=True)
            (unaddressable / "SKILL.md").write_text("---\nname: not-addressable\ndescription: observed\n---\n", encoding="utf-8")
        server = WebAppServer(store, port=0)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        profile = Path(directory) / "chrome"
        chrome = subprocess.Popen([_chrome(), "--headless=new", "--disable-gpu", "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "--user-data-dir=" + str(profile), "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        try:
            port = _devtools_port(chrome, profile)
            results = [
                _run_probe(
                    server.url,
                    width,
                    height,
                    port,
                    screenshot_dir / f"viewport-{width}x{height}.png" if screenshot_dir else None,
                )
                for width, height in VIEWPORTS
            ]
            scenario_results = {
                scenario: _run_probe(server.url, 1280, 900, port, scenario=scenario)
                for scenario in ("scope-failure", "inventory-failure", "unavailable-root")
            }

            # Repoint HOME and the manager data directory to a separate empty
            # fixture so the empty-state browser path is observed end to end.
            empty_home = root / "empty-home"
            empty_data = root / "empty-data"
            empty_home.mkdir(parents=True, exist_ok=True)
            os.environ["HOME"] = str(empty_home)
            os.environ["XDG_DATA_HOME"] = str(empty_home / ".local" / "share")
            os.environ["SKILLS_MANAGER_DATA"] = str(empty_data)
            empty_store = Store(empty_data)
            empty_store.init_db()
            empty_server = WebAppServer(empty_store, port=0)
            empty_thread = Thread(target=empty_server.serve_forever, daemon=True)
            empty_thread.start()
            try:
                scenario_results["empty"] = _run_probe(
                    empty_server.url, 1280, 900, port, scenario="empty"
                )
            finally:
                empty_server.shutdown()
                empty_thread.join(timeout=5)

            all_results = [*results, *scenario_results.values()]
            failures = [r for r in all_results if r["errors"] or r["failed"] or r["document"]["overflow"]]
            print(json.dumps({"viewports": results, "scenarios": scenario_results, "passed": not failures}, indent=2))
            return 1 if failures else 0
        finally:
            chrome.terminate()
            chrome.wait(timeout=5)
            server.shutdown()
            server_thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(run())
