"""Development fidelity harness: fake executables only."""
import importlib.util
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'tools' / 'ai_fidelity' / 'run.py'
spec = importlib.util.spec_from_file_location('fidelity_runner', PATH)
fidelity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fidelity)


def saved_inputs(root):
    prompt_set = {'scope': 'claude-code', 'prompts': [{'text': 'Do a task', 'expected': 'demo'},
                                                       {'text': 'Another task', 'expected': None}]}
    run = {'kind': 'trigger-test', 'scope': 'claude-code', 'prompt_source': 'saved',
           'repeats': 1, 'missing_answers': 0, 'invalid_answers': 0,
           'run': {'model': 'test-model', 'provider': 'fake', 'started': '2026-11-09T00:00:00Z',
                   'estimate_only': False},
           'prompts': [{'text': 'Do a task', 'expected': 'demo', 'answered': 1, 'choices': {'demo': 1}},
                       {'text': 'Another task', 'expected': None, 'answered': 1, 'choices': {'(none)': 1}}]}
    p, r = root / 'prompts.json', root / 'simulation.json'
    p.write_text(json.dumps(prompt_set))
    r.write_text(json.dumps(run))
    return p, r


class FidelityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prompts, self.run = saved_inputs(self.root)
        self.base = ['--prompt-set', str(self.prompts), '--simulation', str(self.run)]

    def test_dry_run_and_two_flags_spawn_nothing(self):
        with patch.object(fidelity.subprocess, 'Popen', side_effect=AssertionError('must not spawn')):
            report = fidelity.execute(self.base)
            self.assertEqual(report['status'], 'dry-run')
            self.assertIsNone(report['agreement']['rate'])
            self.assertEqual(report['coverage']['available'], 2)
            subset = fidelity.execute(self.base + ['--limit', '1'])
            self.assertEqual(subset['coverage']['unselected'], 1)
            with self.assertRaises(fidelity.FidelityError):
                fidelity.execute(self.base + ['--run-agent'])
            with self.assertRaises(fidelity.FidelityError):
                fidelity.execute(self.base + ['--maintainer-present'])

    def test_complete_tuple_join_rejects_ties_invalids_and_incomplete(self):
        original = json.loads(self.run.read_text())
        variants = []
        partial = dict(original, status='disconnected'); variants.append(partial)
        variants.append(dict(original, invalid_answers=1))
        variants.append(dict(original, missing_answers=1))
        tie = json.loads(json.dumps(original)); tie['repeats'] = 2; tie['prompts'][0].update(answered=2, choices={'demo': 1, '(none)': 1}); variants.append(tie)
        missing = json.loads(json.dumps(original)); missing['prompts'].pop(); variants.append(missing)
        repeated = json.loads(json.dumps(original)); repeated['prompts'].append(repeated['prompts'][0]); variants.append(repeated)
        for value in variants:
            self.run.write_text(json.dumps(value))
            with self.subTest(value=value), self.assertRaises(fidelity.FidelityError):
                fidelity.execute(self.base)

    def test_stream_requires_successful_tool_result_and_terminal(self):
        invocation = {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'one',
                        'name': 'Skill', 'input': {'skill': 'demo'}}]}}
        result = {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'one', 'is_error': False}]}}
        final = {'type': 'result', 'subtype': 'success', 'is_error': False}
        stream = lambda rows: b''.join(json.dumps(r).encode() + b'\n' for r in rows)
        self.assertEqual(fidelity.parse_stream(stream([invocation, result, final]))['actual'], 'demo')
        assistant = {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Done.'}]}}
        self.assertEqual(fidelity.parse_stream(stream([assistant, final]))['actual'], None)
        self.assertEqual(fidelity.parse_stream(stream([final]))['status'], 'inconclusive')
        stopped = {'type': 'assistant', 'message': {'stop_reason': 'max_tokens',
                   'content': [{'type': 'text', 'text': 'cut off'}]}}
        self.assertEqual(fidelity.parse_stream(stream([stopped, final]))['status'], 'inconclusive')
        self.assertEqual(fidelity.parse_stream(stream([{}, assistant, final]))['status'], 'inconclusive')
        unknown = {'type': 'assistant', 'message': {'content': [{'type': 'mystery'}]}}
        self.assertEqual(fidelity.parse_stream(stream([assistant, unknown, final]))['status'], 'inconclusive')
        for rows in ([invocation, final], [result, final], [invocation, result],
                     [invocation, dict(result, message={'content': [{'type': 'tool_result', 'tool_use_id': 'one', 'is_error': True}]}), final]):
            self.assertEqual(fidelity.parse_stream(stream(rows))['status'], 'inconclusive')

    @unittest.skipUnless(os.name == 'posix', 'process groups require POSIX')
    def test_fake_executable_execution_and_redaction(self):
        fake = self.root / 'fake-agent'
        fake.write_text('''#!/usr/bin/env python3
import json, sys
prompt = sys.stdin.read()
if prompt == 'Do a task':
 print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'t1','name':'Skill','input':{'skill':'demo'}}]}}))
 print(json.dumps({'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'t1','is_error':False}]}}))
print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'done'}]}}))
print(json.dumps({'type':'result','subtype':'success','is_error':False}))
''')
        fake.chmod(stat.S_IRWXU)
        report = fidelity.execute(self.base + ['--run-agent', '--maintainer-present', '--agent-bin', str(fake),
                                               '--cwd', str(self.root)])
        self.assertEqual(report['coverage']['conclusive'], 2)
        self.assertEqual(report['agreement']['matched'], 2)
        encoded = json.dumps(report)
        self.assertNotIn('Do a task', encoded)
        self.assertNotIn('Another task', encoded)
        self.assertNotIn(str(self.root), encoded)

    def test_bounds_and_json_input_corruption(self):
        for args in (['--limit', '0'], ['--limit', '21'], ['--timeout', 'nan'],
                     ['--timeout', '121'], ['--max-budget-usd', '0'], ['--max-budget-usd', '1.01']):
            with self.subTest(args=args), self.assertRaises(fidelity.FidelityError):
                fidelity.execute(self.base + args)
        run = json.loads(self.run.read_text())
        run['prompts'][0]['answered'] = True
        self.run.write_text(json.dumps(run))
        with self.assertRaises(fidelity.FidelityError):
            fidelity.execute(self.base)

    def test_deeply_nested_json_is_cleanly_rejected(self):
        deep = '{"x":' * 2000 + '0' + '}' * 2000
        self.prompts.write_text(deep)
        with self.assertRaises(fidelity.FidelityError):
            fidelity.execute(self.base)
        self.assertEqual(fidelity.parse_stream(deep.encode())['status'], 'inconclusive')

    def test_multiple_skill_order_and_stream_errors(self):
        def call(identifier, skill):
            return {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': identifier,
                    'name': 'Skill', 'input': {'skill': skill}}]}}
        def complete(identifier):
            return {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': identifier}]}}
        system = {'type': 'system', 'subtype': 'init', 'model': 'claude-test'}
        final = {'type': 'result', 'subtype': 'success', 'is_error': False}
        raw = b'\n'.join(json.dumps(row).encode() for row in
                         [system, call('a', 'demo'), call('b', 'other'), complete('b'), complete('a'), final])
        result = fidelity.parse_stream(raw)
        self.assertEqual(result['actual'], 'demo')
        self.assertEqual(result['observed_skills'], ['demo', 'other'])
        self.assertEqual(result['observed_model'], 'claude-test')
        self.assertTrue(result['multiple'])
        self.assertEqual(fidelity.parse_stream(raw + b'\ninvalid-json')['status'], 'inconclusive')
        self.assertEqual(fidelity.parse_stream(json.dumps({'type': 'result', 'subtype': 'success',
                                                           'is_error': True}).encode())['status'], 'inconclusive')
        self.assertEqual(fidelity.parse_stream(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'id': 'x', 'input': {}}]}}).encode())['status'], 'inconclusive')

    def test_end_conversation_is_auxiliary_and_must_complete(self):
        call = {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'end',
                'name': 'EndConversation', 'input': {}}]}}
        reply = {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'end'}]}}
        final = {'type': 'result', 'subtype': 'success', 'is_error': False}
        stream = lambda rows: b'\n'.join(json.dumps(item).encode() for item in rows)
        self.assertIsNone(fidelity.parse_stream(stream([call, reply, final]))['actual'])
        self.assertEqual(fidelity.parse_stream(stream([call, final]))['status'], 'inconclusive')

    def test_agreement_explicitly_uses_first_skill_and_reports_multiple(self):
        cases = [{'status': 'conclusive', 'actual': 'demo', 'simulated': 'demo', 'expected': 'demo',
                  'observed_skills': ['demo', 'other'], 'multiple': True, 'agree': True},
                 {'status': 'inconclusive', 'expected': None, 'multiple': False, 'agree': None}]
        result = fidelity._agreement(cases)
        self.assertEqual(result['metric'], 'first-successful-skill')
        self.assertEqual(result['matched'], 1)
        none = next(item for item in result['by_expected'] if item['skill'] == '(none)')
        self.assertEqual(none['requested'], 1)
        self.assertIsNone(none['rate'])

    @unittest.skipUnless(os.name == 'posix' and Path('/proc').is_dir(), 'requires Linux process state')
    def test_timeout_terminates_fake_descendant(self):
        fake = self.root / 'fake-agent'
        pidfile = self.root / 'child.pid'
        fake.write_text('#!/usr/bin/env python3\nimport subprocess, sys, time\n'
                        + "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
                        + 'open(' + repr(str(pidfile)) + ", 'w').write(str(child.pid))\n"
                        + 'time.sleep(20)\n')
        fake.chmod(stat.S_IRWXU)
        report = fidelity.execute(self.base + ['--run-agent', '--maintainer-present', '--agent-bin', str(fake),
                                               '--cwd', str(self.root), '--timeout', '0.5', '--limit', '1'])
        self.assertEqual(report['cases'][0]['reason'], 'timeout')
        pid = int(pidfile.read_text())
        status = Path('/proc') / str(pid) / 'status'
        try:
            child_status = status.read_text()
        except FileNotFoundError:
            return  # Reaping may remove the entry before the status read.
        self.assertIn('State:\tZ', child_status)

    @unittest.skipUnless(os.name == 'posix', 'process groups require POSIX')
    def test_fake_timeout_and_output_flood_are_inconclusive(self):
        fake = self.root / 'fake-agent'
        for script, reason in (("import time; time.sleep(5)", 'timeout'),
                               ("import sys; sys.stdout.write('x' * 1200000); sys.stdout.flush()", 'output-limit'),
                               ("import sys; sys.stderr.write('sensitive-value' * 5000); sys.stderr.flush()", 'output-limit')):
            fake.write_text('#!/usr/bin/env python3\n' + script + '\n')
            fake.chmod(stat.S_IRWXU)
            started = time.monotonic()
            report = fidelity.execute(self.base + ['--run-agent', '--maintainer-present', '--agent-bin', str(fake),
                                                   '--cwd', str(self.root), '--timeout', '0.5', '--limit', '1'])
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual(report['coverage']['inconclusive'], 1)
            self.assertEqual(report['cases'][0]['reason'], reason)
            self.assertNotIn('sensitive-value', json.dumps(report))
            self.assertIsNone(report['agreement']['rate'])

    @unittest.skipUnless(os.name == 'posix', 'process groups require POSIX')
    def test_fake_receives_unmodified_stdin_and_restricted_flags(self):
        fake = self.root / 'fake-agent'
        captured = self.root / 'capture.json'
        fake.write_text('#!/usr/bin/env python3\nimport json, sys\n'
                        + 'open(' + repr(str(captured)) + ", 'w').write(json.dumps({'argv': sys.argv[1:], 'stdin': sys.stdin.read()}))\n"
                        + "print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'done'}]}}))\n"
                        + "print(json.dumps({'type':'result','subtype':'success','is_error':False}))\n")
        fake.chmod(stat.S_IRWXU)
        fidelity.execute(self.base + ['--run-agent', '--maintainer-present', '--agent-bin', str(fake),
                                      '--cwd', str(self.root), '--limit', '1'])
        got = json.loads(captured.read_text())
        self.assertEqual(got['stdin'], 'Do a task')
        argv = got['argv']
        self.assertEqual(argv[argv.index('--tools') + 1], 'Skill')
        self.assertEqual(argv[argv.index('--allowedTools') + 1], 'Skill')
        self.assertEqual(argv[argv.index('--mcp-config') + 1], '{"mcpServers":{}}')
        self.assertEqual(argv[argv.index('--disallowedTools') + 1], 'mcp__*')
        self.assertEqual(argv[argv.index('--max-turns') + 1], '2')
        self.assertNotIn('--bare', argv)
        self.assertNotIn('Do a task', argv)

    def test_manifest_prunes_dev_harness(self):
        self.assertIn('prune tools/ai_fidelity', (PATH.parents[2] / 'MANIFEST.in').read_text())
