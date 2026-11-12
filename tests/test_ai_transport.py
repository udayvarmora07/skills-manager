"""Provider transport: retries, prompt caching, thinking headroom, day-cap reservations.

A scripted fake provider on 127.0.0.1 answers each request from a queue of
``(status, headers, payload)`` tuples, so the client's reaction to a transient
error, a quota error, a cached-token report or a thinking-only answer can be
pinned exactly.  ``time.sleep`` inside the client is replaced, so retry waits
are recorded rather than slept.
"""
import http.server
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import ai, ai_skills
from skillsmgr.atomic_io import register_lock_root

SECRET = "sk-test-0123456789abcdefSECRET"


def _ok_anthropic(text='{"ok": true}', **usage):
    return (200, {}, {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                      "usage": {"input_tokens": 100, "output_tokens": 20, **usage}})


def _ok_openai(text='{"ok": true}', usage=None):
    return (200, {}, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                      "usage": usage or {"prompt_tokens": 100, "completion_tokens": 20}})


class Scripted(http.server.BaseHTTPRequestHandler):
    queue: list = []
    seen: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Scripted.seen.append({"path": self.path, "body": body})
        status, headers, payload = Scripted.queue.pop(0) if Scripted.queue else _ok_openai()
        raw = json.dumps(payload).encode()
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class TransportBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Scripted)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Scripted.queue, Scripted.seen = [], []
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name).resolve()
        self.data.chmod(0o700)
        register_lock_root(self.data)
        self.sleeps = []
        sleeper = patch.object(ai, "_sleep", side_effect=self.sleeps.append)
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def configure(self, provider="custom", model="fake-model", **extra):
        base = f"http://127.0.0.1:{self.port}" + ("" if provider == "anthropic" else "/v1")
        payload = {"provider": provider, "model": model, "api_key": SECRET, "base_url": base}
        payload.update(extra)
        ai.save_settings(self.data, payload)

    def run_one(self, feature="test", **kwargs):
        run = ai.AiRun(self.data, feature)
        return run, run.ask_json("Reply with JSON only.", "Return it.", **kwargs)


class RetryTests(TransportBase):
    def test_overloaded_then_success_is_retried_once(self):
        self.configure(provider="anthropic")
        Scripted.queue = [(529, {}, {"error": {"type": "overloaded_error", "message": "busy"}}),
                          _ok_anthropic()]
        run, answer = self.run_one()
        self.assertEqual(answer, {"ok": True})
        self.assertEqual(len(Scripted.seen), 2)
        self.assertEqual(len(self.sleeps), 1)
        self.assertEqual(run.label()["retries"], 1)
        self.assertEqual(ai.usage_summary(self.data)["calls"], 1)

    def test_retry_after_is_honoured_and_capped(self):
        self.configure()
        Scripted.queue = [(429, {"retry-after": "3"}, {"error": {"type": "rate_limit_error"}}),
                          (503, {"retry-after": "9999"}, {"error": "down"}),
                          _ok_openai()]
        self.run_one()
        self.assertEqual(self.sleeps[0], 3.0)
        self.assertLessEqual(self.sleeps[1], ai.MAX_RETRY_WAIT)

    def test_client_errors_are_not_retried(self):
        self.configure()
        Scripted.queue = [(400, {}, {"error": {"message": "bad request"}})]
        with self.assertRaises(ai.AiError):
            self.run_one()
        self.assertEqual(len(Scripted.seen), 1)
        self.assertEqual(self.sleeps, [])

    def test_exhausted_quota_is_not_retried(self):
        self.configure()
        Scripted.queue = [(429, {}, {"error": {"type": "insufficient_quota", "code": "insufficient_quota",
                                               "message": "You exceeded your current quota"}})]
        with self.assertRaises(ai.AiError) as caught:
            self.run_one()
        self.assertEqual(len(Scripted.seen), 1)
        self.assertIn("quota", str(caught.exception))

    def test_retries_are_bounded(self):
        self.configure()
        Scripted.queue = [(500, {}, {"error": "x"})] * 10
        with self.assertRaises(ai.AiError) as caught:
            self.run_one()
        self.assertEqual(len(Scripted.seen), ai.MAX_RETRIES + 1)
        self.assertIn("HTTP 500", str(caught.exception))
        self.assertEqual(ai.usage_summary(self.data)["calls"], 0)

    def test_disconnected_client_stops_retrying(self):
        self.configure()
        Scripted.queue = [(503, {}, {"error": "x"})] * 5
        with ai.client_disconnect_check(lambda: len(Scripted.seen) >= 1):
            run = ai.AiRun(self.data, "trigger-test")
            with self.assertRaises(ai.ClientDisconnected):
                run.ask_json("Reply with JSON only.", "Return it.")
        self.assertEqual(len(Scripted.seen), 1)

    def test_retry_never_echoes_the_key(self):
        self.configure()
        Scripted.queue = [(500, {}, {"error": {"message": f"bad key {SECRET}"}})] * 5
        with self.assertRaises(ai.AiError) as caught:
            self.run_one()
        self.assertNotIn(SECRET, str(caught.exception))


class CachingTests(TransportBase):
    def test_anthropic_prefix_carries_a_cache_breakpoint(self):
        self.configure(provider="anthropic")
        Scripted.queue = [_ok_anthropic()]
        run = ai.AiRun(self.data, "trigger-test")
        run.ask_json("Return only JSON.", "the question", prefix="STABLE LISTING\n")
        message = Scripted.seen[0]["body"]["messages"][0]["content"]
        self.assertIsInstance(message, list)
        self.assertEqual(message[0]["text"], "STABLE LISTING\n")
        self.assertEqual(message[0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(message[1], {"type": "text", "text": "the question"})

    def test_openai_shape_keeps_plain_text_with_the_prefix_first(self):
        self.configure()
        Scripted.queue = [_ok_openai()]
        run = ai.AiRun(self.data, "trigger-test")
        run.ask_json("Return only JSON.", "the question", prefix="STABLE LISTING\n")
        user = Scripted.seen[0]["body"]["messages"][1]["content"]
        self.assertEqual(user, "STABLE LISTING\nthe question")

    def test_cached_anthropic_tokens_still_count_against_the_caps(self):
        self.configure(provider="anthropic")
        Scripted.queue = [_ok_anthropic(cache_creation_input_tokens=1000, cache_read_input_tokens=5000)]
        run, _answer = self.run_one(prefix="x")
        label = run.label()
        self.assertEqual(label["input_tokens"], 6100)
        self.assertEqual(label["cached_input_tokens"], 5000)
        self.assertEqual(ai.usage_summary(self.data)["input_tokens"], 6100)
        row = json.loads((self.data / "ai/usage.jsonl").read_text().splitlines()[-1])
        self.assertEqual(row["cached_input_tokens"], 5000)

    def test_openai_cached_tokens_are_reported_but_already_counted(self):
        self.configure()
        Scripted.queue = [_ok_openai(usage={"prompt_tokens": 3000, "completion_tokens": 5,
                                            "prompt_tokens_details": {"cached_tokens": 2048}})]
        run, _answer = self.run_one()
        self.assertEqual(run.label()["input_tokens"], 3000)
        self.assertEqual(run.label()["cached_input_tokens"], 2048)

    def test_routing_caches_the_listing_only_when_it_is_reused(self):
        self.configure(provider="anthropic")
        listing = {"scope": "s", "entries": [{"name": "alpha", "description": "Alpha things."},
                                              {"name": "beta", "description": "Beta things."}]}
        answer = _ok_anthropic(text='{"answers": []}')
        for count, cached in ((ai_skills.BATCH, False), (ai_skills.BATCH + 1, True)):
            Scripted.queue, Scripted.seen = [answer] * 3, []
            prompts = [{"id": f"p{i}", "text": f"request {i}", "expected": None} for i in range(count)]
            ai_skills._route(ai.AiRun(self.data, "trigger-test"), listing, prompts, {}, 0)
            first = Scripted.seen[0]["body"]["messages"][0]["content"]
            self.assertEqual(isinstance(first, list), cached, count)
            if cached:
                self.assertIn("alpha", first[0]["text"])
                second = Scripted.seen[1]["body"]["messages"][0]["content"]
                self.assertEqual(first[0], second[0])


class ThinkingHeadroomTests(TransportBase):
    def test_current_claude_models_get_low_effort_and_headroom(self):
        self.configure(provider="anthropic", model="claude-haiku-5-5")
        Scripted.queue = [_ok_anthropic()]
        self.run_one(max_output=200)
        body = Scripted.seen[0]["body"]
        self.assertEqual(body["output_config"], {"effort": "low"})
        self.assertEqual(body["max_tokens"], 200 + ai.THINKING_HEADROOM)

    def test_older_or_unknown_models_are_sent_unchanged(self):
        for model in ("claude-haiku-4-5", "fake-model"):
            Scripted.seen = []
            self.configure(provider="anthropic", model=model)
            Scripted.queue = [_ok_anthropic()]
            self.run_one(max_output=200)
            body = Scripted.seen[0]["body"]
            self.assertNotIn("output_config", body)
            self.assertEqual(body["max_tokens"], 200)

    def test_openai_reasoning_models_get_low_effort_and_headroom(self):
        self.configure(provider="openai", model="gpt-5-mini")
        Scripted.queue = [_ok_openai()]
        self.run_one(max_output=200)
        body = Scripted.seen[0]["body"]
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertEqual(body["max_completion_tokens"], 200 + ai.THINKING_HEADROOM)

    def test_thinking_only_cut_off_answer_says_what_happened(self):
        self.configure(provider="anthropic", model="claude-opus-5-5")
        Scripted.queue = [(200, {}, {"content": [{"type": "thinking", "thinking": ""}],
                                     "stop_reason": "max_tokens",
                                     "usage": {"input_tokens": 10, "output_tokens": 2200}})]
        with self.assertRaises(ai.AiError) as caught:
            self.run_one()
        self.assertIn("thinking", str(caught.exception))


class DayCapReservationTests(TransportBase):
    def test_a_concurrent_run_cannot_spend_tokens_another_has_reserved(self):
        self.configure(max_day_tokens=5000)
        entered, release = threading.Event(), threading.Event()
        results = {}

        def slow_call(*args):
            entered.set()
            release.wait(5)
            return '{"ok": true}', {"input_tokens": 3000, "output_tokens": 1}

        def first():
            run = ai.AiRun(self.data, "a")
            results["a"] = run.ask_json("s", "x " * 2500)

        with patch.object(ai, "_call", side_effect=slow_call):
            worker = threading.Thread(target=first)
            worker.start()
            self.assertTrue(entered.wait(5))
            second = ai.AiRun(self.data, "b")
            with self.assertRaises(ai.AiError) as caught:
                second.ask_json("s", "x " * 2500)
            release.set()
            worker.join(5)
        self.assertEqual(caught.exception.code, "ai-budget")
        self.assertEqual(results["a"], {"ok": True})
        self.assertEqual(ai._active_reservations(self.data), 0)
        self.assertEqual(ai.usage_summary(self.data)["input_tokens"], 3000)

    def test_usage_recorded_by_another_run_is_seen_by_the_next_call(self):
        self.configure(max_day_tokens=5000)
        with patch.object(ai, "_call", return_value=('{"ok": true}', {"input_tokens": 10, "output_tokens": 1})):
            run = ai.AiRun(self.data, "a")
            run.ask_json("s", "short")
            ai._record_usage(self.data, {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                         "input_tokens": 4990, "output_tokens": 0})
            with self.assertRaises(ai.AiError) as caught:
                run.ask_json("s", "short")
        self.assertEqual(caught.exception.code, "ai-budget")

    def test_failed_call_releases_its_reservation(self):
        self.configure()
        with patch.object(ai, "_call", side_effect=ai.AiError("boom", "ai-provider", 502)):
            with self.assertRaises(ai.AiError):
                ai.AiRun(self.data, "a").ask_json("s", "short")
        self.assertEqual(ai._active_reservations(self.data), 0)

    def test_stale_and_corrupt_reservations_are_ignored(self):
        self.configure(max_day_tokens=5000)
        path = self.data / "ai" / "reservations.json"
        path.write_text(json.dumps({"dead": {"tokens": 4999, "at": time.time() - ai.RESERVATION_TTL - 1}}))
        self.assertEqual(ai._active_reservations(self.data), 0)
        path.write_text("{not json")
        self.assertEqual(ai._active_reservations(self.data), 0)
        with patch.object(ai, "_call", return_value=('{"ok": true}', {"input_tokens": 10, "output_tokens": 1})):
            self.assertEqual(ai.AiRun(self.data, "a").ask_json("s", "short"), {"ok": True})

    def test_unwritable_reservation_fails_closed_without_sending(self):
        self.configure()
        with patch.object(ai, "_store_reservations", side_effect=OSError(28, "No space left on device")), \
                patch.object(ai, "_call") as call:
            with self.assertRaises(ai.AiError) as caught:
                ai.AiRun(self.data, "a").ask_json("s", "short")
        self.assertEqual(caught.exception.code, "ai-settings")
        call.assert_not_called()

    def test_estimate_mode_reserves_nothing(self):
        self.configure()
        run = ai.AiRun(self.data, "a", estimate_only=True)
        self.assertIsNone(run.ask_json("s", "short"))
        self.assertFalse((self.data / "ai" / "reservations.json").exists())


if __name__ == "__main__":
    unittest.main()
