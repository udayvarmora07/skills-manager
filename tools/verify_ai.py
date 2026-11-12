#!/usr/bin/env python3
"""Run free AI contracts, saved-evidence checks, and an optional wheel probe."""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'tools/ai_fidelity/evidence/2026-11-09'
EVIDENCE_SHA256 = ('689478e1307680ec906bb7b3c66dc706975f364dba9775cb7dd942f7d493ab7a',
                   'd883349c691d62185f9965bb68c210daddfd591ec9e45f38bae1d1788c45a42b',
                   'faf64a11f771784aebc7ac52e633c5bcebd7a0354f21c5e5663036a6d7c866e5')
sys.path.insert(0, str(ROOT / 'tools/ai_fidelity'))
import run as fidelity  # noqa: E402


TEST_TIMEOUT = 300


def _test_command():
    redirect = "import runpy,sys; sys.stderr=sys.stdout; sys.argv=['unittest']+sys.argv[1:]; runpy.run_module('unittest',run_name='__main__')"
    return [sys.executable, '-c', redirect, 'tests.test_ai_cli', 'tests.test_ai_fidelity',
            'tests.test_ai_features', 'tests.test_ai_automation']


def run_tests():
    try:
        with tempfile.TemporaryDirectory(prefix='skills-ai-tests-') as home:
            env = {'PATH': os.defpath, 'HOME': home, 'PYTHONDONTWRITEBYTECODE': '1'}
            if os.name == 'nt' and 'SystemRoot' in os.environ:
                env['SystemRoot'] = os.environ['SystemRoot']
            code, output = _bounded(_test_command(), ROOT, env, TEST_TIMEOUT)
        print(output.decode('utf-8', errors='replace'), end='')
        return code == 0
    except (OSError, ValueError, subprocess.SubprocessError):
        print('AI test subprocess failed or exceeded its limits.', file=sys.stderr)
        return False


def _validate_cases(joined, report):
    cases = report['cases']
    if len(cases) != len(joined) or report['status'] != 'complete':
        raise ValueError('incomplete report')
    for row, case in zip(joined, cases):
        digest = hashlib.sha256(row['text'].encode()).hexdigest()
        if (case['prompt_sha256'] != digest or case['expected'] != row['expected']
                or case['simulated'] != row['simulated'] or case['status'] != 'conclusive'
                or case['actual'] != case['observed_skills'][0] or case['multiple']
                or len(case['observed_skills']) != 1 or case['agree'] != (case['actual'] == row['simulated'])):
            raise ValueError('inconsistent case')
    if report['agreement'] != fidelity._agreement(cases):
        raise ValueError('inconsistent agreement')
    coverage = report['coverage']
    if (coverage != {'available': len(joined), 'requested': len(cases), 'unselected': 0,
                     'conclusive': len(cases), 'inconclusive': 0, 'multiple': 0}):
        raise ValueError('inconsistent coverage')


def check_evidence(root=EVIDENCE):
    try:
        prompt_path, run_path = root / 'prompts.json', root / 'simulation.json'
        prompts, prompt_hash = fidelity._read_json(str(prompt_path))
        simulation, run_hash = fidelity._read_json(str(run_path))
        report, report_hash = fidelity._read_json(str(root / 'report.json'))
        if ((prompt_hash, run_hash, report_hash) != EVIDENCE_SHA256
                or report['simulation']['prompt_set_sha256'] != prompt_hash
                or report['simulation']['run_sha256'] != run_hash):
            raise ValueError('evidence hash mismatch')
        joined, _ = fidelity._joined(prompts, simulation)
        _validate_cases(joined, report)
        return True
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError):
        print('AI study evidence is missing, malformed or inconsistent.', file=sys.stderr)
        return False


class FakeProvider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.server.calls += 1
        length = min(int(self.headers.get('Content-Length', 0)), 1024 * 1024)
        self.rfile.read(length)
        answer = {'answers': [{'id': 'p1', 'skill': 'demo-skill' if self.server.match else None,
                               'runner_up': None}]}
        result = {'choices': [{'message': {'content': json.dumps(answer)}, 'finish_reason': 'stop'}],
                  'usage': {'prompt_tokens': 20, 'completion_tokens': 10}}
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _fixture(root, port):
    home, base = root / 'home', root / 'data'
    home.mkdir(mode=0o700)
    base.mkdir(mode=0o700)
    manager = base / 'skills-manager'
    manager.mkdir(mode=0o700)
    ai = manager / 'ai'
    ai.mkdir(mode=0o700)
    (ai / 'prompt-sets').mkdir(mode=0o700)
    (ai / 'settings.json').write_text(json.dumps({'provider': 'custom', 'model': 'fake-model',
        'base_url': f'http://127.0.0.1:{port}/v1', 'api_key': 'fake-test-key'}))
    (ai / 'prompt-sets/claude-code.json').write_text(json.dumps({'scope': 'claude-code',
        'prompts': [{'text': 'demo task', 'expected': 'demo-skill'}]}))
    skill = home / '.claude/skills/demo-skill/SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('---\nname: demo-skill\ndescription: Handles demo tasks.\n---\nDemo.\n')
    return home, base


def _bounded(command, cwd, env, timeout):
    if os.name != 'posix':
        raise ValueError('bounded process groups require POSIX')
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        output, error = fidelity._drain(process, timeout)
        if error:
            raise ValueError('subprocess failed its output or time limit')
        return process.returncode, output
    finally:
        fidelity._stop(process)
        process.stdout.close()
        process.stderr.close()


def _cli(python, root, env, *extra):
    command = [str(python), '-m', 'skillsmgr', 'ai', 'trigger-test', '--scope', 'claude-code',
               '--saved', '--json', *extra]
    code, output = _bounded(command, root, env, 30)
    try:
        return code, json.loads(output)
    except (ValueError, TypeError):
        raise ValueError('installed CLI did not return JSON') from None


def _run_artifact(python, root, server):
    home, base = _fixture(root, server.server_port)
    env = {'HOME': str(home), 'SKILLS_MANAGER_DATA': str(base), 'PATH': os.defpath,
           'PYTHONDONTWRITEBYTECODE': '1', 'PIP_NO_INDEX': '1'}
    server.match, server.calls = True, 0
    code, estimate = _cli(python, root, env)
    if code or estimate['status'] != 'estimate' or server.calls:
        raise ValueError('estimate sent or failed')
    code, baseline = _cli(python, root, env, '--run')
    if code or baseline['status'] != 'completed' or server.calls != 1:
        raise ValueError('baseline failed')
    server.match = False
    code, report = _cli(python, root, env, '--run', '--fail-on-regression', '--baseline',
                        baseline['result']['run_id'])
    if code != 1 or report['status'] != 'regression' or server.calls != 2:
        raise ValueError('regression gate failed')
    if (base / 'skills-manager/skills-manager.db').exists():
        raise ValueError('CLI initialized the SQLite index')


def _install_and_probe(wheel, root, server):
    venv.EnvBuilder(with_pip=True).create(root / 'venv')
    python = root / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    env = {'HOME': str(root), 'PATH': os.defpath, 'PIP_NO_INDEX': '1'}
    code, _ = _bounded([str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)], root, env, 90)
    if code:
        raise ValueError('wheel install failed')
    probe = 'import pathlib,skillsmgr,sys; assert pathlib.Path(skillsmgr.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())'
    code, _ = _bounded([str(python), '-c', probe], root, env, 30)
    if code:
        raise ValueError('installed package import escaped virtual environment')
    _run_artifact(python, root, server)


def check_artifact(wheel):
    try:
        wheel = wheel.resolve(strict=True)
        with zipfile.ZipFile(wheel) as archive:
            if any('ai_fidelity' in Path(name).parts or Path(name).name == 'verify_ai.py'
                   or 'tests' in Path(name).parts for name in archive.namelist()):
                raise ValueError('development files packaged')
        with tempfile.TemporaryDirectory(prefix='skills-ai-wheel-') as directory:
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeProvider)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                _install_and_probe(wheel, Path(directory), server)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        return True
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError):
        print('Installed wheel AI verification failed.', file=sys.stderr)
        return False


def _dry_fixture():
    try:
        with tempfile.TemporaryDirectory(prefix='skills-ai-dry-') as home:
            env = {'HOME': home, 'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'}
            code, _ = _bounded([sys.executable, str(ROOT / 'tools/ai_fidelity/study_fixture.py')], ROOT, env, 30)
        return code == 0
    except (OSError, ValueError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests', action='store_true')
    parser.add_argument('--evidence', action='store_true')
    parser.add_argument('--artifact', type=Path, metavar='WHEEL')
    args = parser.parse_args(argv)
    default = not (args.tests or args.evidence or args.artifact)
    checks = []
    if args.tests or default:
        checks.append(run_tests())
    if args.evidence or default:
        checks.append(check_evidence())
        checks.append(_dry_fixture())
    if args.artifact:
        checks.append(check_artifact(args.artifact))
    print('AI verification ' + ('passed' if all(checks) else 'failed'))
    return 0 if all(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
