"""Developer browser launchers publish only complete startup URLs."""
import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def server_program(relative_path):
    tree = ast.parse((ROOT / relative_path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "server_code"
                for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("browser launcher has no server startup program")


class BrowserLauncherStartupTests(unittest.TestCase):
    def assert_complete_publication(self, launcher):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "server-url.txt"
            incomplete = []
            server = mock.Mock(port=12345)
            started_urls = []
            server.serve_forever.side_effect = lambda: started_urls.append(target.read_text())

            def observe_write(path, text, *args, **kwargs):
                # Force a reader between file creation and the first write.
                with path.open("w", encoding="utf-8") as stream:
                    if path == target:
                        incomplete.append(target.read_text())
                    return stream.write(text)

            with mock.patch.dict(os.environ, {"BROWSER_TEST_ROOT": str(root)}), \
                 mock.patch("skillsmgr.store.Store"), \
                 mock.patch("skillsmgr.webapp.WebAppServer", return_value=server), \
                 mock.patch.object(Path, "write_text", autospec=True, side_effect=observe_write):
                exec(server_program(launcher), {})
            self.assertEqual(started_urls, ["http://127.0.0.1:12345"])
            self.assertEqual(incomplete, [], "a reader observed an incomplete startup URL")

    def test_classic_publishes_complete_url(self):
        self.assert_complete_publication("tools/e2e_classic/run.py")

    def test_v2_publishes_complete_url(self):
        self.assert_complete_publication("tools/e2e_v2/run.py")
