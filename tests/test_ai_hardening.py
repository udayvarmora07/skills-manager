"""Regression tests for AI usage retention and disconnected clients."""
import json
import socket
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from skillsmgr import ai, ai_skills, webapp
from skillsmgr.atomic_io import register_lock_root


class UsageRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        register_lock_root(self.root)
        self.path = self.root / 'ai' / 'usage.jsonl'
        self.path.parent.mkdir()
        self.today = datetime.now(timezone.utc)

    def row(self, age=0):
        return {'at': (self.today - timedelta(days=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'input_tokens': 1, 'output_tokens': 2}

    def test_empty_one_and_hundred_thousand(self):
        self.assertEqual(ai.usage_summary(self.root)['calls'], 0)
        ai._record_usage(self.root, self.row())
        self.assertEqual(ai.usage_summary(self.root)['calls'], 1)
        old = json.dumps(self.row(100)) + '\n'
        recent = json.dumps(self.row()) + '\n'
        self.path.write_text(old * 50000 + recent * 50000)
        self.assertEqual(ai.usage_summary(self.root)['calls'], 50000)
        lines = self.path.read_text().splitlines()
        self.assertEqual(len(lines), 50000)
        self.assertTrue(all(json.loads(line)['at'] == self.row()['at'] for line in lines))

    def test_recent_large_ledger_is_not_rewritten_and_cutoff_is_inclusive(self):
        recent = json.dumps(self.row()) + "\n"
        self.path.write_text(recent * 20000)
        with patch.object(ai.os, "replace", wraps=ai.os.replace) as replace:
            self.assertEqual(ai.usage_summary(self.root)["calls"], 20000)
            replace.assert_not_called()
        with self.path.open("a") as handle:
            handle.write(json.dumps(self.row(90)) + "\n")
            handle.write(json.dumps(self.row(91)) + "\n")
        ai.usage_summary(self.root)
        data = self.path.read_text()
        self.assertIn(self.row(90)["at"], data)
        self.assertNotIn(self.row(91)["at"], data)

    def test_corruption_and_concurrent_appends(self):
        self.path.write_bytes((b'invalid\n' * 160000) + b'\xff')
        threads = [threading.Thread(target=ai._record_usage, args=(self.root, self.row()))
                   for _ in range(20)]
        for thread in threads:
            thread.start()
        ai.usage_summary(self.root)
        for thread in threads:
            thread.join()
        self.assertEqual(ai.usage_summary(self.root)['calls'], 20)


class DisconnectTests(unittest.TestCase):
    def test_socket_closure_stops_between_calls_and_saves_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            register_lock_root(Path(tmp))
            server, client = socket.socketpair()
            self.addCleanup(server.close)
            self.addCleanup(client.close)
            config = {'provider': 'custom', 'label': 'fake', 'model': 'fake', 'local': True,
                      'max_run_tokens': 300000, 'max_day_tokens': 2000000}
            calls = []
            def fake_call(*args):
                calls.append(1)
                client.close()
                return '{}', {'input_tokens': 1, 'output_tokens': 1}
            with patch.object(ai, 'resolve_config', return_value=config), patch.object(ai, '_call', side_effect=fake_call):
                with ai.client_disconnect_check(lambda: webapp._client_disconnected(server)):
                    run = ai.AiRun(Path(tmp), 'trigger-test')
                    run.ask_json('system', 'first')
                    with self.assertRaises(ai.ClientDisconnected):
                        run.ask_json('system', 'second')
            self.assertEqual(len(calls), 1)
            runs = ai_skills.list_runs(Path(tmp))
            self.assertEqual(len(runs), 1)
            partial = ai_skills.read_run(Path(tmp), runs[0]['run_id'])
            self.assertEqual(partial['status'], 'disconnected')
            self.assertEqual(partial['run']['calls'], 1)

class PromptSetTests(unittest.TestCase):
    def test_replace_retains_500_and_detects_stale_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            register_lock_root(root)
            prompts = [{'text': f'Prompt {i}', 'expected': f'skill-{i // 20}'} for i in range(500)]
            result = ai_skills.save_prompt_set(root, {'scope': 'agents', 'prompts': prompts, 'replace': True})
            self.assertEqual(len(result['prompts']), 500)
            current = result['prompts']
            ai_skills.save_prompt_set(root, {'scope': 'agents', 'prompts': current[1:], 'replace': True,
                                            'expected_prompts': current})
            with self.assertRaises(ai.AiError) as error:
                ai_skills.save_prompt_set(root, {'scope': 'agents', 'prompts': current[2:], 'replace': True,
                                                'expected_prompts': current})
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(len(ai_skills.read_prompt_set(root, 'agents')['prompts']), 499)

class HttpDisconnectTests(unittest.TestCase):
    def test_closed_browser_stops_real_trigger_request(self):
        import http.server
        import time
        from smoke_fixtures import start_server, stop_server
        from skillsmgr.store import Store

        started, release = threading.Event(), threading.Event()
        calls = []
        class Provider(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                calls.append(1)
                started.set()
                release.wait(5)
                raw = json.dumps({'choices': [{'message': {'content': '{"answers": []}'},
                                              'finish_reason': 'stop'}],
                                  'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        thread = threading.Thread(target=provider.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(provider.server_close)
        self.addCleanup(provider.shutdown)
        self.addCleanup(release.set)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = Store(root)
            ai.save_settings(root, {'provider': 'custom', 'model': 'fake',
                                    'base_url': f'http://127.0.0.1:{provider.server_port}/v1'})
            server, server_thread = start_server(store)
            self.addCleanup(stop_server, server, server_thread)
            listing = {'scope': 'agents', 'entries': [{'name': 'demo', 'description': 'Demo'}],
                       'hidden': 0, 'over_cap': 0}
            body = json.dumps({'scope': 'agents', 'prompts': [{'text': f'request {i}', 'expected': 'demo'}
                                                               for i in range(11)]}).encode()
            with patch.object(ai_skills, 'build_listing', return_value=listing):
                client = socket.create_connection(("127.0.0.1", int(server.url.rstrip("/").rsplit(":", 1)[1])))
                self.addCleanup(client.close)
                client.sendall(b'POST /api/ai/trigger-test HTTP/1.1\r\nHost: ' + server.url.split('//')[1].rstrip('/').encode() + b'\r\n'
                               b'Content-Type: application/json\r\nContent-Length: '
                               + str(len(body)).encode() + b'\r\n\r\n' + body)
                self.assertTrue(started.wait(5))
                client.close()
                release.set()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not ai_skills.list_runs(root):
                    time.sleep(0.01)
                runs = ai_skills.list_runs(root)
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(runs), 1)
                self.assertEqual(runs[0]['status'], 'disconnected')
                self.assertEqual(runs[0]['scope'], 'agents')
                self.assertEqual(ai_skills.read_run(root, runs[0]['run_id'])['run']['calls'], 1)
