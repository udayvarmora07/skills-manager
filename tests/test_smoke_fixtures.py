"""Tests for the minimal fixtures used by both executable smoke suites."""

import os
import unittest
from urllib.request import urlopen

from smoke_fixtures import cleanup_store, make_store, start_server, stop_server


class SmokeFixtureTests(unittest.TestCase):
    def test_make_store_initializes_and_cleanup_removes_directory(self):
        tmp, store = make_store("skillsmgr-fixture-test-")
        try:
            self.assertTrue(os.path.isdir(tmp))
            self.assertTrue(store.db_path.is_file())
        finally:
            cleanup_store(tmp)
        self.assertFalse(os.path.exists(tmp))

    def test_start_and_stop_server_uses_ephemeral_loopback_port(self):
        tmp, store = make_store("skillsmgr-fixture-web-test-")
        server, thread = start_server(store)
        try:
            self.assertTrue(thread.is_alive())
            self.assertTrue(server.url.startswith("http://127.0.0.1:"))
            with urlopen(server.url) as response:
                self.assertEqual(response.status, 200)
        finally:
            stop_server(server, thread)
            cleanup_store(tmp)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
