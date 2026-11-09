"""Metadata-only project profile suggestions using a local fake provider."""
import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import ai, ai_profiles, context
from skillsmgr.store import Store


class ProfileProvider(http.server.BaseHTTPRequestHandler):
    mode = 'valid'
    calls = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).calls.append(body)
        answer = {'name': 'project-profile', 'description': 'Useful project skills.',
                  'skills': ['demo', 'disabled-skill', 'invented', 'demo']}
        if self.mode == 'malformed':
            answer['skills'] = {'unexpected': 'object'}
        if self.mode == 'bad-name':
            answer['name'] = '../bad'
        raw = json.dumps({'choices': [{'message': {'content': json.dumps(answer)}, 'finish_reason': 'stop'}],
                          'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY')
                     and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
                     and os.scandir in os.supports_fd, 'safe directory descriptor capture unavailable')
class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), ProfileProvider)
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
        self.project = self.data / 'workspace'
        self.project.mkdir(parents=True)
        self.store = Store(self.data)
        self.store.create('demo', 'Use to process /private/path-secret and projects.')
        self.store.create('disabled-skill', 'Use when managing projects.')
        self.store.disable('disabled-skill')
        (self.project / 'package.json').write_text('secret-project-file-content')
        (self.project / 'src').mkdir()
        (self.project / 'src' / 'main.py').write_text('secret-source-code')
        (self.project / 'src' / 'second.py').write_text('secret-source-code')
        ai.save_settings(self.data, {'provider': 'custom', 'model': 'fake',
                                    'base_url': f'http://127.0.0.1:{self.provider.server_port}/v1'})
        ProfileProvider.calls, ProfileProvider.mode = [], 'valid'
        self.addCleanup(context.set_active_store, None)

    def suggest(self, **params):
        return ai_profiles.suggest_profile(self.data, {'project': str(self.project), 'scope': 'global', **params})

    def test_suggested_profile_is_catalog_compatible_and_metadata_only(self):
        result = self.suggest()
        self.assertEqual(result['status'], 'suggested')
        self.assertEqual(result['profile']['targets'], ['global'])
        self.assertEqual(set(result['profile']['skills']), {'demo', 'disabled-skill'})
        self.assertGreaterEqual(result['dropped_names'], 1)
        self.assertIn('package.json', result['signals']['manifests'])
        sent = json.dumps(ProfileProvider.calls)
        for secret in ('secret-source-code', 'secret-project-file-content', '/private/path-secret', str(self.root)):
            self.assertNotIn(secret, sent)
        self.assertFalse((self.data / 'catalog' / 'metadata.json').exists())

    def test_outside_managed_roots_denied_before_scan_or_provider(self):
        with tempfile.TemporaryDirectory() as outside, patch.object(ai_profiles, '_signals') as scan:
            with self.assertRaises(ai.AiError) as error:
                self.suggest(project=outside)
            self.assertNotIn(outside, str(error.exception))
            scan.assert_not_called()
            self.assertFalse(ProfileProvider.calls)
            with self.assertRaises(ai.AiError):
                ai_profiles.suggest_profile(self.data, {'project': outside, 'scope': 'global'}, allowed_roots=[])

    def test_malformed_allowed_roots_never_expand_access(self):
        for roots in ([''], 'unrestricted'):
            with self.assertRaises(ai.AiError):
                ai_profiles.suggest_profile(self.data, {'project': str(self.project), 'scope': 'global'},
                                            allowed_roots=roots)
        self.assertFalse(ProfileProvider.calls)

    def test_symlink_escape_and_empty_skill_set(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.project / 'outside').symlink_to(outside, target_is_directory=True)
            (Path(outside) / 'leak.py').write_text('outside-secret')
            result = self.suggest()
            self.assertNotIn('outside', result['signals']['top_level_dirs'])
            self.assertNotIn('outside-secret', json.dumps(ProfileProvider.calls))
        with patch.object(ai_profiles, '_skills', return_value=[]):
            ProfileProvider.calls = []
            result = self.suggest()
            self.assertEqual(result['status'], 'empty')
            self.assertFalse(ProfileProvider.calls)

    def test_estimate_and_malformed_results(self):
        result = self.suggest(estimate=True)
        self.assertEqual(result['status'], 'estimate')
        self.assertFalse(ProfileProvider.calls)
        self.assertFalse((self.data / 'ai' / 'runs').exists())
        for mode in ('malformed', 'bad-name'):
            ProfileProvider.mode = mode
            with self.assertRaises(ai.AiError):
                self.suggest()

    def test_scope_listing_discovers_filesystem_only_skill(self):
        offline = self.store.skills_dir / 'offline'
        offline.mkdir()
        (offline / 'SKILL.md').write_text('---\nname: offline\ndescription: Use for offline tasks.\n---\n# Guide\nInstructions.\n')
        names = {row['name'] for row in ai_profiles._skills(self.data, 'global')}
        self.assertIn('offline', names)
        self.assertIn('disabled-skill', names)

    def test_skill_cap_accepts_600_and_rejects_601(self):
        records = [{'name': f'skill-{i}', 'description': 'Description'} for i in range(600)]
        with patch.object(ai_profiles, 'scan_dir', return_value=records):
            self.assertEqual(len(ai_profiles._skills(self.data, 'global')), 600)
            records.append({'name': 'overflow', 'description': 'Description'})
            with self.assertRaises(ai.AiError):
                ai_profiles._skills(self.data, 'global')

    def test_project_symlink_to_outside_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            alias = self.data / 'alias'
            alias.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ai.AiError):
                self.suggest(project=str(alias))
        self.assertFalse(ProfileProvider.calls)

    def test_per_directory_bound(self):
        for i in range(1050):
            (self.project / f'file-{i}.txt').touch()
        result = self.suggest(estimate=True)
        self.assertTrue(result['signals']['truncated'])
        self.assertLessEqual(result['signals']['entries_scanned'], 10000)

    def test_project_swapped_to_symlink_is_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        original = self.root / 'moved-project'
        accepted = self.project
        def swapped(project, roots):
            accepted.rename(original)
            accepted.symlink_to(outside, target_is_directory=True)
            return accepted
        with patch.object(ai_profiles, '_project', side_effect=swapped):
            with self.assertRaises(ai.AiError):
                self.suggest()
        self.assertFalse(ProfileProvider.calls)

    def test_ten_thousand_files_respect_global_bound(self):
        for folder in range(11):
            directory = self.project / f'folder-{folder:02}'
            directory.mkdir()
            for i in range(910):
                (directory / f'f-{i:04}.py').touch()
        result = self.suggest(estimate=True)
        self.assertEqual(result['signals']['entries_scanned'], 10000)
        self.assertTrue(result['signals']['truncated'])

    def test_one_file_and_no_provider_body(self):
        single = self.data / 'single-project'
        single.mkdir()
        (single / 'only.rs').touch()
        result = self.suggest(project=str(single), estimate=True)
        self.assertEqual(result['signals']['entries_scanned'], 1)
        self.assertEqual(result['signals']['extensions'], [{'extension': '.rs', 'count': 1}])

    def test_http_server_managed_roots_are_enforced(self):
        import urllib.error
        import urllib.request
        from skillsmgr.webapp import WebAppServer
        with tempfile.TemporaryDirectory() as other:
            server = WebAppServer(self.store, port=0, extra_allowed_roots=[other])
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(project):
                payload = json.dumps({'project': project, 'scope': 'global', 'estimate': True}).encode()
                req = urllib.request.Request(server.url.rstrip('/') + '/api/ai/suggest-profile', data=payload,
                                             headers={'Content-Type': 'application/json'})
                return urllib.request.urlopen(req, timeout=10)
            try:
                with request(other) as response:
                    self.assertEqual(json.load(response)['status'], 'estimate')
                with tempfile.TemporaryDirectory() as outside:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request(outside)
                    self.assertEqual(error.exception.code, 403)
                    self.assertNotIn(outside, error.exception.read().decode())
                self.assertFalse(ProfileProvider.calls)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.httpd.server_close()

    def test_no_files_still_produces_signal(self):
        empty = self.data / 'empty-project'
        empty.mkdir()
        result = self.suggest(project=str(empty), estimate=True)
        self.assertEqual(result['signals']['entries_scanned'], 0)
        self.assertEqual(result['signals']['extensions'], [])
