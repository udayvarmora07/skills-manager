"""A base URL for the e2e suites, and a server when nobody else started one.

WHY THIS FILE EXISTS
--------------------
Five suites — `test_command_palette`, `test_first_scan_guide`, `test_nav_drawer`,
`test_scope_switcher` and `test_statusbar_degrade` — were written against a
developer running `.redesign/dev.sh start`. Each resolved its base URL from
`SKILLS_MANAGER_URL` with a hard-coded fallback to `http://127.0.0.1:8791`, and
each said in its own docstring:

    Run: .redesign/dev.sh reset && .redesign/dev.sh start

Nothing ever started that server. Run the suite on a machine without it and all
five fail with `Page.goto: net::ERR_CONNECTION_REFUSED` — a red that is about the
harness, not about the tree under test, printed in the same shape as a product
regression. Every other e2e module avoids this by starting its own server on
port 0 (`test_honesty_states.py`, `test_a11y.py`, …). These five were the
exception, and the exception is what the red was.

THE ORDER MATTERS, and the second step is the one that is easy to get wrong
-------------------------------------------------------------------------
1. If something is already serving the API, USE IT. A developer with
   `.redesign/dev.sh start` running gets their seeded library, and every
   assertion in these five suites was written against that data.
2. Otherwise start our own, on port 0, against a temporary HOME — the shape
   `test_honesty_states.setUpClass` already uses. Never the real `~`: RULES #8.
3. Only if that also fails does the suite skip, and its skip text names the
   command, because a skip whose reason does not say what to run is the class
   this repository keeps finding.

A skip that names nothing is how a browser regression hides. So does a skip that
is really a failure wearing a skip's clothes — hence step 2 running BEFORE the
skip is considered.

NEVER REACHED: an inherited `SKILLS_MANAGER_URL` that is set but dead. It falls
through to step 2, which is what makes the fallback testable: point the variable
at a closed port and this module brings its own server up.
"""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request

#: The port `.redesign/dev.sh` uses. Kept as a name, not a magic number at each
#: call site, so a reader can find the one place the convention lives.
DEV_PORT = 8791
DEV_URL = "http://127.0.0.1:%d" % DEV_PORT

#: Named in every skip this module produces. A skip text is the only thing a
#: reader has when a suite did not run.
DEV_COMMAND = (
    "start a server this suite can use, either by running "
    "`.redesign/dev.sh reset && .redesign/dev.sh start` (port %d), or by "
    "setting SKILLS_MANAGER_URL to a running instance" % DEV_PORT
)

# Agent scope directories, under the temporary HOME, so `/api/scopes` reports
# the same eight scopes the app offers on a developer machine. Copied from
# `scopes.py` deliberately rather than imported: importing the product to learn
# its own fixture is a coupling this helper does not want, and a directory name
# that drifts is a fixture that quietly stops being one.
AGENT_SCOPE_DIRS = (
    ".claude/skills",
    ".codex/skills",
    ".cursor/skills",
    ".config/opencode/skills",
    ".gemini/skills",
    ".commandcode/skills",
    ".agents/skills",
)

# Enough library for the five suites' own assertions: the first-scan guide wants
# a non-empty root list and three marks, the palette wants several results in
# more than one group.
FIXTURE_SKILLS = (
    ("platform-infrastructure-bootstrap",
     "Reads the host, reports what it actually found."),
    ("incident-response-runbook-coordinator",
     "Turns a noisy page into the next three actions."),
    ("release-notes-writer",
     "Writes release notes from a diff, and never claims a change it did not see."),
    ("dependency-upgrade",
     "Plans a major version bump and the tests that must move with it."),
)


def _alive(url: str, timeout: float = 1.0) -> bool:
    """Is something serving the REST API at `url`?

    A 4xx counts as alive. The question is "is a process listening and speaking
    this product's API", not "did this particular request succeed" — a 404 from
    a wrong path is evidence FOR the server being up, and treating it as down
    would make this helper start a second server next to the first.
    """
    probe = url.rstrip("/") + "/api/scopes"
    try:
        with urllib.request.urlopen(probe, timeout=timeout) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


class LiveServer:
    """A base URL for a suite, and the teardown for whatever it is using."""

    def __init__(self, url: str, owned: bool) -> None:
        self.url = url.rstrip("/")
        #: True when this process started the server and must stop it. A suite
        #: that shuts down somebody else's dev server would be its own bug.
        self.owned = owned

    def __str__(self) -> str:
        return self.url


_started: "LiveServer | None" = None


def _start_isolated() -> LiveServer:
    """Start our own server on port 0 against a throwaway HOME.

    The shape is `test_honesty_states.setUpClass`, deliberately: temporary
    directory, redirected `HOME`/`XDG_DATA_HOME`/`SKILLS_MANAGER_DATA`, the
    product's own `Store` and `WebAppServer`, a daemon thread. The redirect is
    LEFT IN PLACE rather than restored, because the server resolves its scope
    roots lazily and restoring `HOME` underneath a running server would point a
    live product at the developer's real skills — which RULES #8 forbids and
    which is the one mistake in this file that would be genuinely dangerous.
    """
    from skillsmgr.store import Store          # noqa: PLC0415  (deliberate: env is redirected first)
    from skillsmgr.webapp import WebAppServer  # noqa: PLC0415

    root = tempfile.mkdtemp(prefix="skillsmgr-e2e-live-")
    os.chmod(root, 0o700)
    home = os.path.join(root, "home")
    os.makedirs(home, exist_ok=True)
    for relative in AGENT_SCOPE_DIRS:
        os.makedirs(os.path.join(home, relative), exist_ok=True)

    # Chromium is resolved at launch(), which happens after this returns, so the
    # browser cache has to be located BEFORE `HOME` moves. `test_honesty_states`
    # takes the same two lines for the same reason.
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        anchor = os.environ.get("HOME") or os.path.expanduser("~")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
            anchor, ".cache", "ms-playwright")
    os.environ["HOME"] = home
    os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
    os.environ["SKILLS_MANAGER_DATA"] = os.path.join(root, "data")

    store = Store(root)
    store.init_db()
    for name, description in FIXTURE_SKILLS:
        store.create(name, description)
    # `resync()`, never `db_rebuild()`: the latter unlinks the database and
    # silently drops the history the fixtures above just wrote.
    store.resync()

    server = WebAppServer(store, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = "http://127.0.0.1:%d" % _await_port(server)

    atexit.register(_shutdown, server, root)
    return LiveServer(url, owned=True)


def _await_port(server, attempts: int = 100) -> int:
    """The port the server bound, waited for rather than slept on.

    `port=0` means "pick one", so the number only exists once `serve_forever`
    has run `server_bind`. Polling the value and then confirming the socket
    answers is what removes the flake this branch has already paid for twice;
    a fixed `time.sleep` before the first `goto` is how it came back.
    """
    for _ in range(attempts):
        port = int(getattr(server, "port", 0) or 0)
        if port and _socket_open(port):
            return port
        time.sleep(0.05)
    raise RuntimeError("the isolated e2e server never reported a listening port")


def _socket_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.25)
        try:
            probe.connect(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _shutdown(server, root: str) -> None:
    try:
        server.shutdown()
    except Exception:
        pass
    shutil.rmtree(root, ignore_errors=True)


def live_server() -> LiveServer:
    """The URL to test against. Cached per process; see the module docstring.

    Failure raises rather than skipping. A skip is for "this suite cannot run
    here"; the helper has already tried the running server AND a private one,
    so the remaining case is a real fault — and a fault that prints the command
    that would have avoided it is worth more than a green skip line.
    """
    global _started
    if _started is None:
        for candidate in _candidates():
            if candidate and _alive(candidate):
                _started = LiveServer(candidate, owned=False)
                return _started
        try:
            _started = _start_isolated()
        except Exception as exc:                              # noqa: BLE001
            raise RuntimeError(
                "no web UI server is reachable and one could not be started "
                "for this run (%s: %s) — %s"
                % (type(exc).__name__, exc, DEV_COMMAND)) from exc
    return _started


def _candidates():
    """URLs to try, in order. `SKILLS_MANAGER_URL` first: it is an instruction."""
    configured = os.environ.get("SKILLS_MANAGER_URL", "").strip()
    yield configured or None
    yield DEV_URL


def describe() -> str:
    """One line a failure message can quote: where the suite is looking."""
    try:
        server = live_server()
    except Exception as exc:                                  # noqa: BLE001
        return "no server (%s: %s)" % (type(exc).__name__, exc)
    return "%s (%s)" % (server.url, "started by this run"
                        if server.owned else "already running")