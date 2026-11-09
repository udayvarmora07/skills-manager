"""An in-process CLI invocation resolves ``global`` through its own Store.

``WebAppServer`` binds its Store into the ``scopes`` ContextVar in the
constructing thread and leaves it bound. A later in-process ``cli.main`` call
on a different ``--data-dir`` used to resolve the ``global`` scope through that
stale Store, so ``doctor --scope all`` listed no duplicates (the order-dependent
failure recorded in task.md). The CLI now binds its requested Store for the
duration of the command and restores the previous binding afterwards.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import context
from skillsmgr import cli, scopes
from skillsmgr.store import Store


class CliGlobalStoreBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stale = tempfile.TemporaryDirectory()
        self.addCleanup(self.stale.cleanup)
        env = mock.patch.dict(os.environ, {"HOME": self.tmp.name, "SKILLS_MANAGER_DATA": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(context.set_active_store, None)

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", self.tmp.name, *argv])
        return code, out.getvalue(), err.getvalue()

    def test_stale_bound_store_does_not_hide_the_requested_global_scope(self):
        stale_store = Store(Path(self.stale.name))
        context.set_active_store(stale_store)
        self.assertEqual(self.invoke(["create", "shared", "-d", "Global copy"])[0], cli.EXIT_OK)
        document = Path(self.tmp.name) / ".agents" / "skills" / "shared" / "SKILL.md"
        document.parent.mkdir(parents=True)
        document.write_text("---\nname: shared\ndescription: Agent copy\n---\nbody\n", encoding="utf-8")

        code, out, err = self.invoke(["doctor", "--scope", "all", "--json"])
        self.assertEqual(code, cli.EXIT_OK, err)
        report = json.loads(out)
        self.assertEqual([d["scopes"] for d in report["duplicates"]], [["agents", "global"]])

    def test_previous_binding_is_restored_after_the_command(self):
        stale_store = Store(Path(self.stale.name))
        context.set_active_store(stale_store)
        self.invoke(["list", "--json"])
        self.assertIs(context.ACTIVE_STORE.get(), stale_store)

    def test_binding_is_restored_when_the_command_fails(self):
        stale_store = Store(Path(self.stale.name))
        context.set_active_store(stale_store)
        code, _, _ = self.invoke(["view", "missing-skill"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIs(context.ACTIVE_STORE.get(), stale_store)


if __name__ == "__main__":
    unittest.main()
