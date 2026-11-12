#!/usr/bin/env python3
"""Run the sandboxed CLASSIC web UI end-to-end suite (Install, Profiles,
Quality, Workspaces, Settings plus cross-cutting checks); see --help.

Everything happens inside a private temp root: isolated HOME and
SKILLS_MANAGER_DATA, an OS-selected loopback port, Chrome with its sandbox ON.
The unauthenticated service is bound to 127.0.0.1 only: that binding is its
sole security boundary, so never forward or tunnel the port.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from browser_harness import _chrome, _node  # noqa: E402
from skillsmgr.launcher_security import trusted_executable  # noqa: E402

SCOPE_DIRS = {  # scope key -> directory below HOME
    'claude': '.claude/skills',
    'codex': '.codex/skills',
    'opencode': '.config/opencode/skills',
    'agents': '.agents/skills',
}


def doc(name, text, description='Use this fixture when exercising the classic web UI.'):
    return f'---\nname: {name}\ndescription: {description}\n---\n# {name}\n\n{text}\n'


def build_fixture(root: Path):
    home, data = root / 'home', root / 'data'
    for p in (home, data):
        p.mkdir(mode=0o700)
    roots = {k: home / v for k, v in SCOPE_DIRS.items()}
    for p in roots.values():
        p.mkdir(parents=True)

    def put(scope, name, body, disabled=False, description=None):
        d = roots[scope] / name
        d.mkdir()
        text = doc(name, body) if description is None else doc(name, body, description)
        (d / ('SKILL.md.disabled' if disabled else 'SKILL.md')).write_text(text)

    # Profile members. Targets used by the tests: claude-code + codex.
    for s in ('claude', 'codex'):
        put(s, 'prof-observed', 'Identical enabled text.')
        put(s, 'prof-disabled', 'Identical disabled text.', disabled=True)
    put('claude', 'prof-mixed', 'Mixed enabled state.')
    put('codex', 'prof-mixed', 'Mixed enabled state.', disabled=True)
    put('claude', 'prof-divergent', 'Claude flavour of the text.')
    put('codex', 'prof-divergent', 'Codex flavour of the text.')
    # Outside the profile targets / profile membership: must never be touched.
    put('agents', 'prof-disabled', 'Identical disabled text.', disabled=True)
    put('claude', 'bystander', 'Not in any profile.', disabled=True)
    # Hygiene evidence.
    put('claude', 'broken-ref', 'See [the missing guide](references/missing-guide.md) for details.')
    put('claude', 'damaged-fm', 'Readable text.')
    put('codex', 'damaged-fm', 'Readable text.')
    (roots['codex'] / 'damaged-fm/SKILL.md').write_text('---\nname: [broken\n---\n')
    put('opencode', 'vague-desc', 'Body.', description='Helpful tool.')
    # Projects: one inside the data root, one outside, one missing.
    store_root = data / 'skills-manager'
    store_root.mkdir(mode=0o700)
    store_root.chmod(0o700)  # data-root trust policy: owner-only
    inside = store_root / 'projects' / 'inside-project'
    (inside / '.claude/skills').mkdir(parents=True)
    outside = root / 'outside-project'
    (outside / '.claude/skills').mkdir(parents=True)
    # Fake runners: if the server ever executes one, the sentinel appears.
    fakebin = root / 'fakebin'
    fakebin.mkdir(mode=0o700)
    sentinel = root / 'RUNNER-EXECUTED.txt'
    for runner in ('npx', 'pnpm', 'yarn', 'bunx'):
        script = fakebin / runner
        script.write_text(f'#!/bin/sh\necho "{runner} $@" >> "{sentinel}"\nexit 0\n')
        script.chmod(stat.S_IRWXU)
    return home, data


def main():
    parser = argparse.ArgumentParser(description='Create isolated fixtures and run the classic-UI Playwright suite.')
    parser.add_argument('--output-dir', required=True, type=Path,
                        help='Existing or new directory; a fresh private run folder is created inside it')
    args = parser.parse_args()
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    mode = stat.S_IMODE(args.output_dir.stat().st_mode)
    if mode & 0o022 and args.output_dir.stat().st_uid == os.getuid():
        # The data-root trust check rejects group/other-writable ancestors; only ever tighten.
        args.output_dir.chmod(mode & ~0o022)
        print(f'Tightened {args.output_dir} to {oct(mode & ~0o022)} (data-root trust policy)', flush=True)
    root = Path(tempfile.mkdtemp(prefix='skillsmgr-classic-', dir=args.output_dir.resolve()))
    root.chmod(0o700)
    (root / 'screens').mkdir(mode=0o700)
    home, data = build_fixture(root)
    env = {k: v for k, v in os.environ.items()
           if k not in ('VERCEL_OIDC_TOKEN', 'SKILLS_MANAGER_REGISTRY_TOKEN')}
    env.update(HOME=str(home), SKILLS_MANAGER_DATA=str(data), PYTHONDONTWRITEBYTECODE='1',
               BROWSER_TEST_ROOT=str(root), BROWSER_TEST_HOME=str(home),
               XDG_DATA_HOME=str(root / 'xdg'), XDG_CONFIG_HOME=str(root / 'xdgc'))
    server_env = dict(env, PATH=str(root / 'fakebin') + os.pathsep + env.get('PATH', ''))
    subprocess.run([sys.executable, '-m', 'skillsmgr', 'create', 'global-skill', '-d',
                    'Use this global fixture when checking the classic Library.', '--body', 'Global body.'],
                   cwd=REPO, env=server_env, check=True, stdout=subprocess.DEVNULL)
    node = _node()
    requested = env.get('CHROME_BIN')
    chrome = trusted_executable('chrome', which=lambda _: requested) if requested else _chrome()
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
    with (root / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-c', server_code], cwd=REPO, env=server_env,
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError('Server exited; inspect server.log')
                try:
                    env['BROWSER_TEST_BASE'] = (root / 'server-url.txt').read_text()
                    with urllib.request.urlopen(env['BROWSER_TEST_BASE'] + '/', timeout=.25):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Server did not start; inspect server.log')
            result = subprocess.run([node, str(Path(__file__).with_name('classic.cjs'))],
                                    cwd=REPO, env=env, timeout=600)
            sentinel = root / 'RUNNER-EXECUTED.txt'
            if sentinel.exists():
                print('FAIL: a package runner was executed by the server:\n' + sentinel.read_text())
                return 1
            print(f'Results: {root / "results.json"}')
            return result.returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == '__main__':
    sys.exit(main())
