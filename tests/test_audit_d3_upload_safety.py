"""Red-first regressions: an unsafe upload part must not vanish silently
(docs/24 §D3-5).

``upload_folder`` skipped an unsafe part with ``continue`` and still answered
``200`` with ``{"imported": [...], "skipped": []}`` — so a part the client sent
and the user expected was dropped, and the response actively claimed nothing
was skipped.  Reproduced on the live route:

```text
safe + parent-traversal + absolute  -> 200 {"imported": ["good"], "skipped": []}
only unsafe parts                  -> 200 {"imported": [], "skipped": []}
```

The second shape is the damaging one: a success response, nothing installed, and
no indication that anything went wrong.

The sibling ``staged_single_skill`` already **raises** for exactly these
conditions, so the two upload paths had drifted into disagreeing about the same
input.  These tests pin the raising behaviour and the "decide before writing"
order.
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
import uuid
from pathlib import Path

from skillsmgr.store import Store, StoreError
from skillsmgr.web_upload import staged_single_skill, upload_folder
from skillsmgr.webapp import WebAppServer

SKILL_BYTES = b"---\nname: good\ndescription: A good skill.\n---\nbody\n"


def _part(filename: str, content: bytes = SKILL_BYTES) -> dict:
    return {"filename": filename, "content": content}


def _recording_add(installed: list[str]):
    def add_skill(source_dir: Path) -> dict:
        installed.append(source_dir.name)
        return {"name": source_dir.name}
    return add_skill


class UnsafeUploadPartTests(unittest.TestCase):
    """An unsafe path rejects the whole upload; nothing is installed."""

    def _assert_rejected(self, filename: str) -> None:
        installed: list[str] = []
        with self.assertRaises(StoreError) as caught:
            upload_folder(
                [_part("good/SKILL.md"), _part(filename)],
                _recording_add(installed),
            )
        message = str(caught.exception)
        # ``repr`` is deliberate in the product: the filename is client-controlled,
        # so it is rendered in Python-literal form (a backslash shows as ``\\``).
        self.assertIn(
            repr(filename),
            message,
            "the error must name the part the client sent, or the user cannot act on it",
        )
        self.assertIn("unsafe", message)
        self.assertEqual(
            [], installed,
            "an unsafe part must abort the upload before any skill is installed",
        )

    def test_a_parent_traversing_part_is_rejected(self):
        self._assert_rejected("../evil/SKILL.md")

    def test_an_absolute_part_is_rejected(self):
        self._assert_rejected("/abs/SKILL.md")

    def test_a_backslash_separated_part_is_rejected(self):
        self._assert_rejected("..\\evil\\SKILL.md")

    def test_a_deep_traversal_is_rejected(self):
        self._assert_rejected("a/b/../../../evil/SKILL.md")

    def test_an_upload_of_only_unsafe_parts_installs_nothing_and_says_so(self):
        installed: list[str] = []
        with self.assertRaises(StoreError):
            upload_folder(
                [_part("../evil/SKILL.md"), _part("/abs/SKILL.md")],
                _recording_add(installed),
            )
        self.assertEqual([], installed)

    def test_a_clean_upload_still_succeeds(self):
        installed: list[str] = []
        result = upload_folder(
            [
                _part("alpha/SKILL.md"),
                _part("alpha/references/notes.md", b"notes\n"),
                _part("beta/SKILL.md"),
            ],
            _recording_add(installed),
        )
        self.assertEqual({"imported": ["alpha", "beta"], "skipped": []}, result)
        self.assertEqual(["alpha", "beta"], sorted(installed))

    def test_a_part_with_no_filename_is_not_treated_as_an_unsafe_path(self):
        """A form field carries no file; there is no path to judge."""
        installed: list[str] = []
        result = upload_folder(
            [{"filename": "", "content": b"x"}, _part("alpha/SKILL.md")],
            _recording_add(installed),
        )
        self.assertEqual(["alpha"], result["imported"])


class UploadPathPolicyParityTests(unittest.TestCase):
    """The two upload paths must agree on what an unsafe path is."""

    UNSAFE = ("../evil/SKILL.md", "/abs/SKILL.md", "..\\evil\\SKILL.md")

    def test_both_upload_helpers_reject_the_same_paths(self):
        for filename in self.UNSAFE:
            with self.subTest(filename=filename):
                installed: list[str] = []
                with self.assertRaises(StoreError):
                    upload_folder([_part(filename)], _recording_add(installed))
                self.assertEqual([], installed)
                with self.assertRaises(StoreError):
                    with staged_single_skill([_part(filename)]):
                        pass

    def test_a_rejected_upload_leaves_no_staging_residue(self):
        before = set(Path(tempfile.gettempdir()).glob("skillsmgr-add-*"))
        installed: list[str] = []
        with self.assertRaises(StoreError):
            upload_folder([_part("../evil/SKILL.md")], _recording_add(installed))
        after = set(Path(tempfile.gettempdir()).glob("skillsmgr-add-*"))
        self.assertEqual(before, after, "a rejected upload left a staging tree behind")


class UnsafeUploadOverHTTPTests(unittest.TestCase):
    """The live route must not answer 200 with a lying payload."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = {k: os.environ.get(k) for k in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore)
        home = Path(self._tmp.name) / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        self.store = Store(data_dir=Path(self._tmp.name) / "data")
        self.store.init_db()
        self.server = WebAppServer(self.store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _upload(self, filenames):
        boundary = "----probe" + uuid.uuid4().hex
        chunks = []
        for name in filenames:
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="files"; filename="{name}"\r\n'
                    "Content-Type: application/octet-stream\r\n\r\n"
                ).encode()
                + SKILL_BYTES
                + b"\r\n"
            )
        chunks.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}/api/import",
            data=b"".join(chunks),
            headers={
                "Host": f"127.0.0.1:{self.server.port}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_a_traversing_part_is_a_400_not_a_success(self):
        status, payload = self._upload(["good/SKILL.md", "../evil/SKILL.md"])
        self.assertEqual(400, status)
        self.assertIn("error", payload)
        self.assertIn("evil", payload["error"])

    def test_an_absolute_part_is_a_400_not_a_success(self):
        status, payload = self._upload(["good/SKILL.md", "/abs/SKILL.md"])
        self.assertEqual(400, status)
        self.assertIn("error", payload)

    def test_an_upload_of_only_unsafe_parts_is_not_a_silent_success(self):
        status, payload = self._upload(["../evil/SKILL.md", "/abs/SKILL.md"])
        self.assertEqual(400, status)
        self.assertNotIn("imported", payload)

    def test_the_rejected_upload_installed_nothing(self):
        self._upload(["good/SKILL.md", "../evil/SKILL.md"])
        installed = sorted(
            p.name for p in self.store.skills_dir.iterdir() if p.is_dir()
        )
        self.assertEqual([], installed, "a rejected upload installed something")

    def test_a_clean_upload_still_returns_200(self):
        status, payload = self._upload(["good/SKILL.md"])
        self.assertEqual(200, status)
        self.assertEqual(["good"], payload["imported"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()