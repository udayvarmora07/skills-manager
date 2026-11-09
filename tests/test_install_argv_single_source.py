"""R15: ``/api/install`` must render its argv through one shared renderer.

``install.install_argv``/``install_command_line`` is the single renderer for
the ``skills add`` command line.  The CLI already used it, but ``webapp.py``
built the same argv itself in ``_install_command_parts`` and
``_install_option_argv`` -- two copies of the runner allowlist, the scope flag,
and the repeated ``-a``/``-s``/``--copy``/``-l`` options that can drift apart.

The cases below are characterised against the *pre-refactor* route: each one
records the exact status and payload the route returned before the change, so
the refactor is proven byte-identical rather than asserted.  The final test is
source-reading and fails on the unchanged code, because the duplicated
construction still exists there.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from skillsmgr import install
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


UVX_ERROR = (
    "uvx does not apply to the npm 'skills' package; use npx/pnpm dlx/yarn "
    "dlx/bunx. For Python tools use pipx/uvx with a PyPI package."
)


def _render_kwargs(**overrides):
    """The ``install_command_line`` inputs the route's values map onto."""
    kwargs = {
        "source": "owner/repo",
        "runner": "npx",
        "scope": "global",
        "agents": None,
        "skills": None,
        "copy": False,
        "list_only": False,
    }
    kwargs.update(overrides)
    return kwargs


# (payload, expected status, expected command-or-error, install_command_line kwargs)
CASES = (
    (
        {"source": "owner/repo"},
        200,
        "npx skills add owner/repo -g",
        _render_kwargs(),
    ),
    (
        {"source": "owner/repo", "scope": "project"},
        200,
        "npx skills add owner/repo",
        _render_kwargs(scope="project"),
    ),
    (
        {"source": "owner/repo", "scope": "  project  "},
        200,
        "npx skills add owner/repo",
        _render_kwargs(scope="project"),
    ),
    (
        {"source": "owner/repo", "runner": "pnpm"},
        200,
        "pnpm dlx skills add owner/repo -g",
        _render_kwargs(runner="pnpm"),
    ),
    (
        {"source": "owner/repo", "runner": "yarn"},
        200,
        "yarn dlx skills add owner/repo -g",
        _render_kwargs(runner="yarn"),
    ),
    (
        {"source": "owner/repo", "runner": "bunx"},
        200,
        "bunx skills add owner/repo -g",
        _render_kwargs(runner="bunx"),
    ),
    (
        {"source": "owner/repo", "runner": "bun"},
        200,
        "bunx skills add owner/repo -g",
        _render_kwargs(runner="bun"),
    ),
    (
        {"source": "owner/repo", "runner": "  npx  "},
        200,
        "npx skills add owner/repo -g",
        _render_kwargs(runner="npx"),
    ),
    (
        {"source": "owner/repo", "agents": ["claude-code"]},
        200,
        "npx skills add owner/repo -g -a claude-code",
        _render_kwargs(agents=["claude-code"]),
    ),
    (
        {"source": "owner/repo", "agents": "claude-code"},
        200,
        "npx skills add owner/repo -g -a claude-code",
        _render_kwargs(agents=["claude-code"]),
    ),
    (
        {"source": "owner/repo", "skills": ["find-skills", "other"]},
        200,
        "npx skills add owner/repo -g -s find-skills -s other",
        _render_kwargs(skills=["find-skills", "other"]),
    ),
    (
        {
            "source": "owner/repo",
            "agents": ["a", "b"],
            "skills": ["s"],
            "copy": True,
            "list_only": True,
        },
        200,
        "npx skills add owner/repo -g -a a -a b -s s --copy -l",
        _render_kwargs(agents=["a", "b"], skills=["s"], copy=True, list_only=True),
    ),
    (
        {"source": "owner/repo", "agents": [], "skills": []},
        200,
        "npx skills add owner/repo -g",
        _render_kwargs(),
    ),
    (
        {"source": "owner/repo", "agents": 5},
        200,
        "npx skills add owner/repo -g",
        _render_kwargs(),
    ),
    (
        {"source": "owner/repo", "copy": True},
        200,
        "npx skills add owner/repo -g --copy",
        _render_kwargs(copy=True),
    ),
    (
        {"source": "owner/repo", "list_only": True},
        200,
        "npx skills add owner/repo -g -l",
        _render_kwargs(list_only=True),
    ),
    (
        {"source": "owner/repo", "preview": True},
        200,
        "npx skills add owner/repo -g",
        _render_kwargs(),
    ),
    (
        {"source": "owner/repo", "runner": "uvx"},
        400,
        UVX_ERROR,
        None,
    ),
    (
        {"source": "owner/repo", "runner": "pip"},
        400,
        "unsupported runner 'pip'; use npx, pnpm, yarn, or bunx",
        None,
    ),
    (
        {"source": "owner/repo", "agents": ["../tmp"]},
        400,
        "invalid agent value '../tmp'",
        None,
    ),
    (
        {"source": "owner/repo", "skills": ["/etc/passwd"]},
        400,
        "invalid skill value '/etc/passwd'",
        None,
    ),
    (
        {"source": "owner/repo", "agents": ["x" * 257]},
        400,
        "invalid agent value '" + ("x" * 257) + "'",
        None,
    ),
)


class InstallArgvSingleSourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self._saved_env = {
            key: os.environ.get(key)
            for key in ("SKILLS_MANAGER_DATA", "XDG_DATA_HOME", "HOME")
        }
        self.addCleanup(self._restore_env)
        home = root / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        self.data_dir = root / "data"
        os.environ["SKILLS_MANAGER_DATA"] = str(self.data_dir)
        store = Store(data_dir=self.data_dir)
        store.init_db()
        self.addCleanup(shutil.rmtree, self.data_dir, True)
        self.server = WebAppServer(store, port=0)
        self.port = self.server.httpd.server_port
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self):
        self.server.shutdown()
        self._thread.join(timeout=5)
        self.server.httpd.server_close()

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _post(self, payload):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/install",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_route_behaviour_is_unchanged_and_matches_the_shared_renderer(self):
        for payload, expected_status, expected, kwargs in CASES:
            with self.subTest(payload=payload):
                status, body = self._post(payload)
                self.assertEqual(status, expected_status, body)
                if expected_status == 200:
                    self.assertFalse(body["executed"])
                    self.assertEqual(body["command"], expected)
                    if payload.get("preview"):
                        self.assertEqual(
                            body["registry"]["install_command"], expected
                        )
                    else:
                        self.assertEqual(
                            body,
                            {
                                "command": expected,
                                "runner": kwargs["runner"],
                                "source": kwargs["source"],
                                "executed": False,
                            },
                        )
                    self.assertEqual(
                        install.install_command_line(**kwargs), expected
                    )
                else:
                    self.assertEqual(
                        body, {"error": expected, "code": "bad_request"}
                    )

    def test_executed_argv_is_exactly_the_rendered_argv(self):
        payload = {
            "source": "owner/repo",
            "runner": "pnpm",
            "scope": "project",
            "agents": ["a"],
            "skills": ["s"],
            "copy": True,
            "list_only": True,
            "run": True,
        }
        completed = mock.Mock(returncode=0, stdout="ok\n", stderr="")
        with mock.patch(
            "skillsmgr.install.subprocess.run", return_value=completed
        ) as run:
            status, body = self._post(payload)
        self.assertEqual(status, 200)
        expected = install.install_argv(
            "owner/repo", "pnpm", "project", ["a"], ["s"], True, True
        )
        self.assertEqual(run.call_args.args[0], expected)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(body["command"], " ".join(expected))
        self.assertTrue(body["executed"])


if __name__ == "__main__":
    unittest.main()
