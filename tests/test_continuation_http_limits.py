"""Unusable parameters and declared huge bodies must fail promptly."""

import http.client
import json
import socket

from test_continuation_http import RequestCase


class RequestLimits(RequestCase):
    def test_history_zero_and_blank_window_are_rejected(self):
        for path in ("/api/history?limit=0", "/api/history?limit=0&snapshots=1&name=demo",
                     "/api/stats?window=", "/api/tokens?window="):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 400)

    def test_overdeclared_body_is_rejected_without_drain_or_reuse(self):
        with socket.create_connection(("127.0.0.1", self.server.port), timeout=2) as conn:
            conn.sendall((f"POST /api/skills HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n"
                          "Content-Type: application/json\r\nContent-Length: 99999999999\r\n"
                          "Connection: keep-alive\r\n\r\n{}").encode())
            response = http.client.HTTPResponse(conn)
            response.begin()
            self.assertEqual(response.status, 413)
            self.assertEqual(json.loads(response.read())["code"], "too_large")
            self.assertEqual(conn.recv(1), b"")
