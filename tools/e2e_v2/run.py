#!/usr/bin/env python3
"""Run sandboxed local browser regression checks; see --help."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from browser_harness import _chrome, _node
from skillsmgr.launcher_security import trusted_executable

def main():
    parser = argparse.ArgumentParser(description='Create isolated fixtures and run the optional Playwright browser suite.')
    parser.add_argument('--output-dir', required=True, type=Path, help='Existing or new directory for a fresh private run folder and evidence')
    args = parser.parse_args()
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='skillsmgr-e2e-', dir=args.output_dir.resolve()))
    root.chmod(0o700)
    home, data = root / ('home-' + 'long-path-' * 16), root / 'data'
    for p in (home, data): p.mkdir(mode=0o700)
    roots = { 'claude': home/'.claude/skills', 'codex': home/'.codex/skills', 'opencode': home/'.config/opencode/skills', 'agents': home/'.agents/skills' }
    for p in roots.values(): p.mkdir(parents=True)
    def doc(name, text): return f'---\nname: {name}\ndescription: Use this fixture for browser testing.\n---\n# {name}\n\n{text}\n'
    def put(scope, name, body):
        d = roots[scope]/name; d.mkdir(); (d/'SKILL.md').write_text(doc(name, body))
    for scope in roots:
        put(scope, 'same-everywhere', 'Identical text.')
        put(scope, 'majority-minor', 'Different text.' if scope == 'codex' else 'Majority text.')
        put(scope, 'split-even', 'First text.' if scope in ('claude', 'codex') else 'Second text.')
    for scope in ('claude', 'opencode', 'agents'): put(scope, 'damaged-one', 'Readable text.')
    d = roots['codex']/'damaged-one'; d.mkdir(); (d/'SKILL.md').write_bytes(b'\xff\xfe')
    for name, disabled_scope in (('target-disabled', 'codex'), ('source-disabled', 'claude')):
        for scope in ('claude', 'codex'):
            put(scope, name, scope + ' original text')
        d = roots[disabled_scope]/name
        (d/'SKILL.md').rename(d/'SKILL.md.disabled')
    put('claude', 'sole-copy', 'A single fixture copy.')
    for scope in ('claude', 'codex', 'agents'):
        put(scope, 'share-three', 'A fixture awaiting its fourth agent copy.')
    for scope in ('claude', 'codex'):
        put(scope, 'damaged-fm', 'Readable text.')
    (roots['codex']/'damaged-fm/SKILL.md').write_text('---\nname: [broken\n---\n')
    (roots['claude']/'.system').mkdir()
    (home/'.claude/settings.json').write_text(json.dumps({'skillOverrides': {'same-everywhere': 'off'}}))
    (home/'.config/opencode/opencode.json').write_text(json.dumps({'permission': {'skill': {'same-everywhere': 'deny'}}}))
    env = dict(os.environ, HOME=str(home), SKILLS_MANAGER_DATA=str(data), PYTHONDONTWRITEBYTECODE='1')
    env['BROWSER_TEST_ROOT'] = str(root)
    env['BROWSER_TEST_HOME'] = str(home)
    subprocess.run([sys.executable, '-m', 'skillsmgr', 'create', 'library-fixture', '-d', 'Use this for browser recovery checks.', '--body', 'Fixture body.'], cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)
    node = _node()
    requested_chrome = env.get('CHROME_BIN')
    chrome = trusted_executable('chrome', which=lambda _: requested_chrome) if requested_chrome else _chrome()
    if not chrome:
        raise RuntimeError('CHROME_BIN must identify a trusted Chrome executable')
    env['CHROME_BIN'] = chrome
    server_code = (
        'import os; from pathlib import Path; '
        'from skillsmgr.store import Store; from skillsmgr.webapp import WebAppServer; '
        'from skillsmgr.atomic_io import atomic_write_text; '
        'server=WebAppServer(Store(), host="127.0.0.1", port=0); '
        'atomic_write_text(Path(os.environ["BROWSER_TEST_ROOT"], "server-url.txt"), '
        '"http://127.0.0.1:"+str(server.port)); server.serve_forever()'
    )
    print(f'Fixture and evidence directory: {root}', flush=True)
    print('The unauthenticated service is bound to localhost only; do not forward or tunnel it.', flush=True)
    with (root/'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-c', server_code], cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if server.poll() is not None: raise RuntimeError('Server exited; inspect server.log')
                try:
                    env['BROWSER_TEST_BASE'] = (root/'server-url.txt').read_text()
                    with urllib.request.urlopen(env['BROWSER_TEST_BASE']+'/v2/', timeout=.25): break
                except OSError: time.sleep(.1)
            else: raise RuntimeError('Server did not start; inspect server.log')
            result = subprocess.run([node, str(Path(__file__).with_name('browser.cjs'))], cwd=REPO, env=env, timeout=360)
            return result.returncode
        finally:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait()

if __name__ == '__main__': sys.exit(main())
