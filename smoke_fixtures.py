"""Minimal hermetic fixtures shared by the repository smoke scripts."""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


def make_store(prefix: str) -> tuple[str, Store]:
    """Create an initialized Store rooted in a disposable temporary directory."""
    tmp = tempfile.mkdtemp(prefix=prefix)
    try:
        store = Store(data_dir=tmp)
        store.init_db()
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp, store


def cleanup_store(tmp: str | Path) -> None:
    """Remove a temporary smoke-test data directory."""
    shutil.rmtree(tmp, ignore_errors=True)


def start_server(store: Store) -> tuple[WebAppServer, threading.Thread]:
    """Start a Store-backed web server on an ephemeral loopback port."""
    server = WebAppServer(store, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while True:
        try:
            with urlopen(server.url, timeout=0.25):
                break
        except OSError:
            if time.monotonic() >= deadline:
                server.shutdown()
                thread.join(timeout=5)
                raise
            time.sleep(0.01)
    return server, thread


def stop_server(server: WebAppServer, thread: threading.Thread) -> None:
    """Stop a smoke-test web server and wait for its worker thread."""
    server.shutdown()
    thread.join(timeout=5)
