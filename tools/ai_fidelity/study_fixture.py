#!/usr/bin/env python3
"""Reproduce the bounded synthetic CLI-adapter study; default sends nothing."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from skillsmgr import ai_skills  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as fidelity  # noqa: E402

ENTRIES = [
    {'name': 'haiku-poem', 'description': 'Use when asked to compose a haiku poem, especially about nature or seasons.',
     'body': 'Write a short haiku poem.'},
    {'name': 'unit-conversion', 'description': 'Use when asked to convert a quantity between measurement units such as meters and feet.',
     'body': 'Calculate the requested unit conversion.'},
]
SIM_TIMEOUT = 90
PROMPTS = [{'text': 'Write a haiku about autumn leaves.', 'expected': 'haiku-poem'},
           {'text': 'Convert 12 meters to feet.', 'expected': 'unit-conversion'}]


def setup(root):
    settings = root / '.claude' / 'settings.json'
    settings.parent.mkdir()
    settings.write_text(json.dumps({'disableAllHooks': True, 'disableBundledSkills': True,
                                    'disableSkillShellExecution': True}))
    for entry in ENTRIES:
        skill = root / '.claude' / 'skills' / entry['name'] / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: ' + entry['name'] + '\ndescription: ' + entry['description']
                         + '\n---\n' + entry['body'] + '\n')
    wrapper = root / 'claude-isolated'
    wrapper.write_text('#!/bin/sh\nunset CLAUDECODE\nexec claude --setting-sources project "$@"\n')
    wrapper.chmod(0o700)
    return wrapper


class CliRouter:
    def __init__(self, root):
        self.root = root
        self.usage = None

    def ask_json(self, system, user, *, max_output):
        command = ['claude', '-p', '--output-format', 'json', '--tools', '', '--strict-mcp-config',
                   '--mcp-config', '{"mcpServers":{}}', '--setting-sources', 'project',
                   '--no-session-persistence', '--max-turns', '1', '--max-budget-usd', '0.10',
                   '--permission-prompts', 'none', '--model', 'haiku', '--system-prompt', system]
        env = os.environ.copy()
        env.pop('CLAUDECODE', None)
        with tempfile.TemporaryFile() as stdin:
            stdin.write(user.encode('utf-8'))
            stdin.seek(0)
            try:
                process = subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, cwd=self.root, env=env,
                                           start_new_session=True)
            except OSError:
                raise ValueError('simulator unavailable') from None
            try:
                raw, error = fidelity._drain(process, SIM_TIMEOUT)
                if error:
                    raise ValueError('simulator ' + error)
                if process.returncode != 0:
                    raise ValueError('simulator failed')
            finally:
                fidelity._stop(process)
                process.stdout.close()
                process.stderr.close()
        answer, self.usage = decode_response(raw)
        return answer


def _valid_answer(row):
    return (isinstance(row, dict) and isinstance(row.get('id'), str)
            and all(value is None or isinstance(value, str)
                    for value in (row.get('skill'), row.get('runner_up'))))


def decode_response(raw):
    try:
        response = json.loads(raw)
        if (not isinstance(response, dict) or response.get('is_error') is not False
                or response.get('subtype') != 'success' or not isinstance(response.get('result'), str)
                or not isinstance(response.get('modelUsage'), dict)):
            raise ValueError
        models = response['modelUsage']
        if not all(isinstance(name, str) for name in models):
            raise ValueError
        answer = json.loads(response['result'].removeprefix('```json').removesuffix('```').strip())
        if not isinstance(answer, dict) or not isinstance(answer.get('answers'), list):
            raise ValueError
        if not all(_valid_answer(row) for row in answer['answers']):
            raise ValueError
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError('simulator invalid response') from None
    return answer, {'reported_cost_usd': response.get('total_cost_usd'), 'models': sorted(models)}


def execute_study(root):
    wrapper = setup(root)
    entries = [{k: e[k] for k in ('name', 'description')} for e in ENTRIES]
    prompts = ai_skills.normalize_prompts(PROMPTS, {e['name'] for e in ENTRIES})
    router = CliRouter(root)
    answers = ai_skills._route(router, {'entries': entries}, prompts, {}, 0)
    if len(answers) != len(prompts) or any(choice == '?invalid' for choice, _ in answers.values()):
        raise ValueError('simulator returned incomplete or invalid choices')
    rows = [{'text': p['text'], 'expected': p['expected'], 'answered': 1,
             'choices': {answers[p['id']][0] or '(none)': 1}} for p in prompts]
    started = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    simulation = {'kind': 'trigger-test', 'scope': 'claude-code', 'prompt_source': 'saved',
                  'status': 'complete', 'repeats': 1, 'missing_answers': 0, 'invalid_answers': 0,
                  'run': {'model': 'haiku', 'provider': 'claude-cli-adapter', 'started': started,
                          'estimate_only': False}, 'prompts': rows}
    prompt_path, simulation_path = root / 'prompts.json', root / 'simulation.json'
    prompt_path.write_text(json.dumps({'scope': 'claude-code', 'prompts': prompts}))
    simulation_path.write_text(json.dumps(simulation))
    report = fidelity.execute(['--prompt-set', str(prompt_path), '--simulation', str(simulation_path),
        '--cwd', str(root), '--agent-bin', str(wrapper), '--model', 'haiku', '--limit', '2',
        '--timeout', '90', '--max-budget-usd', '0.10', '--run-agent', '--maintainer-present'])
    return {'simulator_usage': router.usage, 'report': report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-agent', action='store_true')
    parser.add_argument('--maintainer-present', action='store_true')
    args = parser.parse_args(argv)
    if args.run_agent != args.maintainer_present:
        print('Both --run-agent and --maintainer-present are required.', file=sys.stderr)
        return 2
    if not args.run_agent:
        print('Dry run: no CLI or provider call. Two fixture cases; three calls capped at $0.10 each.')
        return 0
    try:
        with tempfile.TemporaryDirectory(prefix='ai-fidelity-') as directory:
            print(json.dumps(execute_study(Path(directory)), indent=2, sort_keys=True))
    except (OSError, ValueError, subprocess.SubprocessError, fidelity.FidelityError):
        print('Study failed; no raw output or stderr retained.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
