"""Verified drafting with a local fake model and isolated scopes."""
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import ai, ai_draft
from skillsmgr.atomic_io import register_lock_root
from test_ai_features import FakeProvider


class DraftProvider(FakeProvider):
    mode = 'valid'
    calls = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).calls.append(body)
        system, user = body['messages'][0]['content'], body['messages'][1]['content']
        if 'draft a skill' in system.lower():
            name = ('bad_name' if self.mode == 'invalid' else
                    'existing' if self.mode == 'collision' else 'draft-demo')
            desc = 'Use for creating database reports and queries.'
            text = f'---\nname: {name}\ndescription: {desc}\n---\n# Guide\nRun the task.\n'
            if self.mode == 'bad-shape':
                text = '---\nname: [one, two]\ndescription: Use for reports.\n---\n# Test\nDo it.'
            if self.mode == 'oversized':
                text += 'line\n' * 501
            answer = {'skill': text}
        elif 'realistic test requests' in system:
            import re
            names = re.findall(r'^- ([a-z0-9-]+):', user, re.M)
            answer = {'prompts': [{'skill': n, 'text': f'please use {n} request {i}'}
                                  for n in names for i in range(3)],
                      'near_misses': [{'text': f'unrelated request {i}', 'better': None} for i in range(3)]}
            if self.mode == 'no-coverage':
                answer['near_misses'] = []
        elif self.mode == 'missing':
            answer = {'answers': []}
        else:
            import re
            ids = [json.loads(line) for line in re.findall(r'^\{"id".*\}$', user, re.M)]
            augmented = '- draft-demo:' in user
            answer = {'answers': [{'id': row['id'], 'skill':
                        ('draft-demo' if augmented and ('draft-demo' in row['request'] or self.mode == 'steal')
                         else 'existing' if 'existing' in row['request'] else None), 'runner_up': None}
                        for row in ids]}
        raw = json.dumps({'choices': [{'message': {'content': json.dumps(answer)}, 'finish_reason': 'stop'}],
                          'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class DraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), DraftProvider)
        cls.thread = threading.Thread(target=cls.provider.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.provider.shutdown()
        cls.provider.server_close()
        cls.thread.join()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        register_lock_root(self.root)
        ai.save_settings(self.root, {'provider': 'custom', 'model': 'fake',
                                    'base_url': f'http://127.0.0.1:{self.provider.server_port}/v1'})
        DraftProvider.mode, DraftProvider.calls = 'valid', []
        self.records = [{'name': 'existing', 'description': 'Use for database reporting.', 'enabled': True}]
        scope = ai_draft.scopes.Scope('agents', 'Agents', self.root / 'scope', 'agent', True)
        scope.base.mkdir()
        scope_patcher = patch.object(ai_draft.scopes, 'scope_by_id', return_value=scope)
        scope_patcher.start()
        self.addCleanup(scope_patcher.stop)
        peer_patcher = patch.object(ai_draft.scopes, '_peer_link_roots', return_value=())
        peer_patcher.start()
        self.addCleanup(peer_patcher.stop)
        patcher = patch.object(ai_draft, 'scan_dir', side_effect=lambda *args, **kwargs: list(self.records))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_draft(self, **extra):
        return ai_draft.draft_skill(self.root, {'scope': 'agents', 'brief': 'Create database reports', **extra})

    def test_valid_draft_and_stealing(self):
        DraftProvider.mode = 'steal'
        result = self.run_draft()
        self.assertEqual(result['status'], 'verified')
        self.assertTrue(result['validation']['valid'])
        self.assertGreater(result['verification']['draft_hit_rate'], 0)
        self.assertEqual(result['verification']['stolen'][0]['name'], 'existing')
        self.assertGreater(result['verification']['stolen'][0]['count'], 0)
        self.assertFalse((self.root / 'skills').exists())

    def test_invalid_and_oversized_are_not_verified(self):
        for mode in ('invalid', 'oversized', 'bad-shape', 'collision'):
            DraftProvider.mode = mode
            result = self.run_draft()
            self.assertEqual(result['status'], 'invalid')
            self.assertFalse(result['validation']['valid'])
            self.assertIsNone(result['verification'])

    def test_estimate_never_sends_or_persists(self):
        result = self.run_draft(estimate=True)
        self.assertEqual(result['status'], 'estimate')
        self.assertGreater(result['run']['estimated_input_tokens'], 0)
        self.assertEqual(DraftProvider.calls, [])
        self.assertFalse((self.root / 'ai' / 'runs').exists())

    def test_hidden_name_collision_and_empty_scope(self):
        self.records = [{'name': 'draft-demo', 'disabled': True}]
        with self.assertRaises(ai.AiError):
            self.run_draft(name='draft-demo')
        self.assertFalse(DraftProvider.calls)
        self.records = []
        (self.root / 'scope' / 'draft-demo').symlink_to(self.root / 'missing')
        with self.assertRaises(ai.AiError):
            self.run_draft(name='draft-demo')
        (self.root / 'scope' / 'draft-demo').unlink()
        result = self.run_draft()
        self.assertEqual(result['verification']['existing_skills_total'], 0)
        self.assertEqual(result['status'], 'verified')

    def test_no_routing_answers_is_unverifiable(self):
        DraftProvider.mode = 'missing'
        result = self.run_draft()
        self.assertEqual(result['status'], 'unverified')
        self.assertGreater(result['verification']['missing_answers'], 0)
        DraftProvider.mode = 'no-coverage'
        result = self.run_draft()
        self.assertEqual(result['status'], 'unverified')
        self.assertFalse(result['verification']['complete'])

    def test_bad_inputs(self):
        for params in ({'brief': ''}, {'brief': 'x' * 10001}, {'scope': 'all'}, {'name': '../bad'}):
            with self.assertRaises(ai.AiError):
                self.run_draft(**params)

    def test_http_route_estimate(self):
        import urllib.request
        from smoke_fixtures import start_server, stop_server
        from skillsmgr.store import Store
        server, thread = start_server(Store(self.root))
        try:
            body = json.dumps({'scope': 'agents', 'brief': 'Build reports', 'estimate': True}).encode()
            req = urllib.request.Request(server.url.rstrip('/') + '/api/ai/draft-skill', data=body,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                self.assertEqual(json.load(response)['status'], 'estimate')
            self.assertEqual(DraftProvider.calls, [])
        finally:
            stop_server(server, thread)
