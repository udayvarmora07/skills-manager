"""Conciseness proposal tests with a local fake provider and real reviews."""
import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import ai, ai_concise, context, source_update
from skillsmgr.store import Store


class ConciseProvider(http.server.BaseHTTPRequestHandler):
    mode = 'valid'
    calls = []
    hook = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).calls.append(body)
        if type(self).hook:
            type(self).hook()
        path = {'traversal': '../escape.md', 'collision': 'references/existing.md',
                'absolute': '/tmp/escape.md'}.get(self.mode, 'references/details.md')
        answer = {'body': '# Summary\nRead [details](references/details.md).\n',
                  'references': [{'path': path, 'text': '# Details\nThe full details.\n'}]}
        if self.mode == 'no-savings':
            answer['body'] = 'expanded wording ' * 5000 + '\n[details](references/details.md)\n'
        if self.mode == 'oversized':
            answer['body'] = 'x' * 100001
        if self.mode == 'unlinked':
            answer['body'] = '# Summary\nNo reference link.\n'
        if self.mode == 'fenced-link':
            answer['body'] = '```md\n[details](references/details.md)\n```\n'
        if self.mode == 'comment-link':
            answer['body'] = '<!-- [details](references/details.md) -->'
        if self.mode == 'fenced-content':
            answer['body'] = '# Summary\nRead [details](references/details.md).\n```python\nprint(1)\n```\n'
        if self.mode == 'surrogate':
            answer['body'] = '\ud800'

        raw = json.dumps({'choices': [{'message': {'content': json.dumps(answer)}, 'finish_reason': 'stop'}],
                          'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY')
                     and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
                     and os.scandir in os.supports_fd, 'safe directory descriptor capture unavailable')
class ConciseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), ConciseProvider)
        cls.thread = threading.Thread(target=cls.provider.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.provider.shutdown()
        cls.provider.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.store = Store(data_dir=self.data)
        self.store.create('demo', 'Use demo for test tasks.', body='# Guide\n' + ('Original long detailed instructions and examples.\n' * 100))
        self.target = self.store.skills_dir / 'demo'
        (self.target / 'references').mkdir()
        (self.target / 'references' / 'existing.md').write_text('existing companion')
        (self.target / 'asset.bin').write_bytes(b'\0\xffunchanged')
        (self.target / 'asset.bin').chmod(0o755)
        self.target.chmod(0o755)
        ai.save_settings(self.data, {'provider': 'custom', 'model': 'fake',
                                    'base_url': f'http://127.0.0.1:{self.provider.server_port}/v1'})
        ConciseProvider.mode, ConciseProvider.calls, ConciseProvider.hook = 'valid', [], None
        self.addCleanup(context.set_active_store, None)

    def concise(self, **params):
        return ai_concise.concise_skill(self.data, {'scope': 'global', 'name': 'demo', **params})

    def test_review_roundtrip_preserves_tree_and_snapshots(self):
        old = (self.target / 'SKILL.md').read_bytes()
        result = self.concise()
        self.assertEqual(result['status'], 'review-required')
        self.assertEqual((self.target / 'SKILL.md').read_bytes(), old)
        self.assertEqual(result['review']['review_state'], 'pending')
        self.assertGreater(result['tokens']['reference_added'], 0)
        self.assertLess(result['tokens']['primary_after'], result['tokens']['primary_before'])
        applied = source_update.commit_update_review(self.data, result['review']['review_id'],
                                                      scope='global', name='demo', approve=True)
        self.assertTrue(applied['committed'])
        self.assertEqual((self.target / 'asset.bin').read_bytes(), b'\0\xffunchanged')
        self.assertEqual((self.target / 'asset.bin').stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.target / 'references' / 'existing.md').read_text(), 'existing companion')
        self.assertTrue((self.target / 'references' / 'details.md').exists())
        self.assertTrue(source_update.list_update_snapshots(self.data, 'demo', 'global'))

    def test_increased_primary_size_is_disclosed(self):
        ConciseProvider.mode = 'no-savings'
        result = self.concise()
        self.assertLess(result['tokens']['primary_saved'], 0)
        self.assertGreater(result['tokens']['primary_after'], result['tokens']['primary_before'])

    def test_estimate_is_read_only(self):
        result = self.concise(estimate=True)
        self.assertEqual(result['status'], 'estimate')
        self.assertEqual(ConciseProvider.calls, [])
        self.assertFalse((self.data / 'source-update-reviews').exists())
        self.assertFalse((self.data / 'ai' / 'runs').exists())

    def test_http_estimate_route(self):
        import urllib.request
        from smoke_fixtures import start_server, stop_server
        server, thread = start_server(self.store)
        try:
            data = json.dumps({'scope': 'global', 'name': 'demo', 'estimate': True}).encode()
            request = urllib.request.Request(server.url.rstrip('/') + '/api/ai/concise', data=data,
                                             headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=10) as response:
                self.assertEqual(json.load(response)['status'], 'estimate')
            self.assertFalse(ConciseProvider.calls)
        finally:
            stop_server(server, thread)

    def test_invalid_paths_collisions_limits_and_unlinked_refs(self):
        for mode in ('traversal', 'collision', 'absolute', 'oversized', 'unlinked', 'fenced-link', 'comment-link', 'surrogate'):
            ConciseProvider.mode = mode
            with self.subTest(mode=mode), self.assertRaises(ai.AiError):
                self.concise()
            self.assertFalse((self.data / 'source-update-reviews').exists())

    def test_target_changed_during_model_call(self):
        def change():
            (self.target / 'asset.bin').write_bytes(b'changed')
        ConciseProvider.hook = change
        with self.assertRaises(ai.AiError):
            self.concise()
        self.assertEqual((self.target / 'asset.bin').read_bytes(), b'changed')

    def test_symlink_refused_and_disabled_supported(self):
        (self.target / 'unsafe').symlink_to(self.root / 'missing')
        with self.assertRaises(ai.AiError):
            self.concise()
        self.assertFalse(ConciseProvider.calls)
        (self.target / 'unsafe').unlink()
        self.store.disable('demo')
        result = self.concise()
        self.assertTrue(result['review']['resulting_disabled'])

    def test_large_directory_is_rejected_before_provider_call(self):
        extra = self.target / 'many'
        extra.mkdir()
        for i in range(260):
            (extra / str(i)).mkdir()
        with self.assertRaises(ai.AiError):
            self.concise()
        self.assertEqual(ConciseProvider.calls, [])

    def test_sections_ignore_fenced_headings(self):
        sections = ai_concise._sections('Preamble\n# Real\n```md\n# not a heading\n```\n## Next\nbody\n')
        self.assertEqual([s['heading'] for s in sections], ['Preamble', 'Real', 'Next'])

    def test_cancel_review_if_recapture_fails(self):
        capture = ai_concise._capture
        calls = []
        def fail_second(path):
            calls.append(path)
            if len(calls) == 2:
                raise ai.AiError('changed', 'ai-input')
            return capture(path)
        with patch.object(ai_concise, '_capture', side_effect=fail_second), self.assertRaises(ai.AiError):
            self.concise()
        reviews = list((self.data / 'source-update-reviews').iterdir())
        self.assertEqual(len(reviews), 1)
        self.assertFalse((reviews[0] / 'candidate').exists())
        self.assertEqual(json.loads((reviews[0] / 'review.json').read_text())['status'], 'cancelled')

    def test_code_fence_survives_model_response(self):
        ConciseProvider.mode = 'fenced-content'
        result = self.concise()
        self.assertIn('```python\nprint(1)\n```', result['proposal']['body'])

    def test_run_save_failure_cancels_pending_review(self):
        with patch.object(ai_concise, '_save_run', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.concise()
        reviews = list((self.data / 'source-update-reviews').iterdir())
        self.assertEqual(len(reviews), 1)
        self.assertFalse((reviews[0] / 'candidate').exists())
        self.assertEqual(json.loads((reviews[0] / 'review.json').read_text())['status'], 'cancelled')

    def test_frontmatter_block_scalar_is_preserved(self):
        doc = self.target / 'SKILL.md'
        prefix = ('---\nname: demo\ndescription: Use demo for test tasks.\n'
                  'metadata:\n  note: |\n    an example\n    ---\n    more\n---\n')
        doc.write_text(prefix + '# Original\nSome text.\n')
        result = self.concise()
        candidate = self.data / 'source-update-reviews' / result['review']['review_id'] / 'candidate' / 'SKILL.md'
        self.assertTrue(candidate.read_text().startswith(prefix))

class JsonFenceTests(unittest.TestCase):
    def test_outer_json_fence_preserves_embedded_markdown_fence(self):
        content = '# Guide\n```python\nprint(1)\n```\n'
        response = '```json\n' + json.dumps({'body': content, 'skill': content}) + '\n```'
        parsed = ai.extract_json(response)
        self.assertEqual(parsed['body'], content)
        self.assertEqual(parsed['skill'], content)
        from skillsmgr import ai_draft
        draft_text = '---\nname: demo\ndescription: Use demo when testing.\n---\n' + content
        draft_response = '```json\n' + json.dumps({'skill': draft_text}) + '\n```'
        with tempfile.TemporaryDirectory() as tmp:
            draft, validation = ai_draft._validate_draft(ai.extract_json(draft_response), None, set(), Path(tmp))
        self.assertTrue(validation['valid'])
        self.assertEqual(draft['body'], content)
