"""Red-first regression tests for the deep-audit batch 5 (medium security) findings.

Covers SEC-4, SEC-5, SEC-6, SEC-7, SEC-8 and SEC-9:

* ``SEC-4`` — the in-DOM Vue template needs ``script-src 'unsafe-eval'``; the
  trade-off is recorded (and pinned here) instead of being silently relaxed.
* ``SEC-5`` — the CSP has no ``form-action`` directive.
* ``SEC-6`` — a multipart upload whose parts mix a file and a directory with the
  same name crashed with a raw ``IsADirectoryError`` (HTTP 500) and leaked the
  Python error text for a NUL-byte filename.
* ``SEC-7`` — the ``contents: write`` release job executed a distribution
  fetched from PyPI at release time.
* ``SEC-8`` — the build backend was an unpinned ``setuptools>=61``, so the
  attested artifacts were not reproducible.
* ``SEC-9`` — the vendored ``vue.global.prod.js`` (which executes same-origin
  with access to every mutation endpoint) had no integrity assertion on any gate.

Stdlib only.  Every test drives the real seam the audit described: a live
loopback server, the real workflow files, the real lock file, and the real
vendored payload (plus a deliberately tampered copy of it).
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import io
import json
import os
import re
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

import check_package_data


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
_VENDORED_VUE = (ROOT / check_package_data.VUE_MEMBER).read_bytes()


def _workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _job_blocks(text: str) -> dict[str, str]:
    """Split a workflow into ``job id -> job body`` blocks."""

    starts = [(match.group(1), match.start()) for match in re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", text)]
    blocks: dict[str, str] = {}
    for index, (name, start) in enumerate(starts):
        end = starts[index + 1][1] if index + 1 < len(starts) else len(text)
        blocks[name] = text[start:end]
    return blocks


class BatchFiveCase(unittest.TestCase):
    """Base: fresh HOME + data root per test, no environment leakage."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self._old = {key: os.environ.get(key) for key in ("HOME", "SKILLS_MANAGER_DATA")}
        os.environ["HOME"] = str(self.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.base / "data")
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    @classmethod
    def _serve(cls, store):
        from skillsmgr import webapp

        server = webapp.WebAppServer(store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def _store(self):
        from skillsmgr.store import Store

        store = Store()
        store.init_db()
        store.create("demo", "A demo skill for HTTP tests.")
        return store

    def _live_server(self):
        server, thread = self._serve(self._store())
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server

    def _request(self, port, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        conn.close()
        return response.status, payload, response_headers


# ----------------------------------------------------------------- SEC-4 / SEC-5

SKILL_DOCUMENT = b"---\nname: staged-skill\ndescription: A staged upload skill.\n---\nbody\n"


class ContentSecurityPolicyTests(BatchFiveCase):
    def test_csp_denies_form_action(self):
        # SEC-5: `form-action` does not fall back to `default-src`, so an
        # injected <form action="https://attacker/"> was unconstrained.
        server = self._live_server()
        status, _, headers = self._request(server.port, "GET", "/")
        self.assertEqual(status, 200)
        csp = headers["content-security-policy"]
        self.assertIn("form-action 'none'", csp)

    def test_every_routed_response_carries_the_form_action_denial(self):
        server = self._live_server()
        for method, path in (("GET", "/api/skills"), ("GET", "/api/nope"), ("OPTIONS", "/api/skills")):
            with self.subTest(method=method, path=path):
                _, _, headers = self._request(server.port, method, path)
                self.assertIn("form-action 'none'", headers.get("content-security-policy", ""))

    def test_script_src_keeps_the_recorded_eval_tradeoff(self):
        # SEC-4: the vendored bundle is the runtime+compiler build, so the
        # in-DOM template compiles with `Function(code)()`; dropping
        # 'unsafe-eval' breaks the app and the only real fix needs a build step,
        # which locked constraint 4 forbids.  Pin the decision: the directive
        # stays, 'unsafe-inline' never joins script-src, and the trade-off is
        # written down in the authoritative web UI doc.
        server = self._live_server()
        _, _, headers = self._request(server.port, "GET", "/")
        csp = headers["content-security-policy"]
        script_src = next(part.strip() for part in csp.split(";") if part.strip().startswith("script-src"))
        self.assertIn("'unsafe-eval'", script_src)
        self.assertNotIn("'unsafe-inline'", script_src)

        documented = (ROOT / "docs" / "08-web-ui.md").read_text(encoding="utf-8")
        self.assertIn("'unsafe-eval'", documented)
        self.assertIn("build step", documented)


# ------------------------------------------------------------------------ SEC-6


class UploadStagingTests(BatchFiveCase):
    @staticmethod
    def _multipart(parts, boundary="batch5boundary"):
        body = b""
        for name, content in parts:
            body += (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="files"; filename="{name}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8") + content + b"\r\n"
        body += f"--{boundary}--\r\n".encode("utf-8")
        return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    def _upload(self, parts):
        server = self._live_server()
        body, headers = self._multipart(parts)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status, payload, _ = self._request(server.port, "PUT", "/api/import", body, headers)
        return status, payload, stderr.getvalue()

    def test_a_directory_named_like_an_uploaded_file_is_a_clean_400(self):
        # SEC-6: part `a/b/SKILL.md` creates directory `a`; the next part `a`
        # then hit `IsADirectoryError` -> HTTP 500 "internal error" and a raw
        # diagnostic on the server's stderr.
        status, payload, stderr = self._upload(
            [("a/b/SKILL.md", SKILL_DOCUMENT), ("a", b"collision")]
        )
        self.assertEqual(status, 400)
        message = json.loads(payload)["error"]
        self.assertIn("share the name", message)
        self.assertIn("'a'", message)
        self.assertNotIn("IsADirectory", message)
        self.assertNotIn("webui internal error", stderr)

    def test_a_file_named_like_an_uploaded_directory_is_a_clean_400(self):
        # The opposite order used to fail inside parent creation with a raw
        # `NotADirectoryError`.
        status, payload, stderr = self._upload(
            [("a", b"collision"), ("a/b/SKILL.md", SKILL_DOCUMENT)]
        )
        self.assertEqual(status, 400)
        message = json.loads(payload)["error"]
        self.assertIn("share the name", message)
        self.assertIn("'a'", message)
        self.assertNotIn("NotADirectory", message)
        self.assertNotIn("webui internal error", stderr)

    def test_a_nul_byte_filename_reports_an_actionable_error(self):
        # SEC-6: the raw `ValueError("embedded null byte")` text was returned
        # verbatim to the client as the whole error message.
        status, payload, stderr = self._upload(
            [("bad\x00name/SKILL.md", SKILL_DOCUMENT), ("good/SKILL.md", SKILL_DOCUMENT)]
        )
        self.assertEqual(status, 400)
        message = json.loads(payload)["error"]
        self.assertIn("NUL", message)
        self.assertNotEqual(message, "embedded null byte")
        self.assertNotIn("webui internal error", stderr)

    def test_a_normal_folder_upload_still_imports(self):
        status, payload, _ = self._upload([("skills/staged-skill/SKILL.md", SKILL_DOCUMENT)])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["imported"], ["staged-skill"])


# ------------------------------------------------------------------------ SEC-7


class ReleaseWorkflowSplitTests(unittest.TestCase):
    def test_no_write_capable_job_executes_a_distribution_fetched_from_an_index(self):
        # SEC-7: the github-release job holds `contents: write` (push refs,
        # create/delete releases) yet `pip install`ed a distribution fetched
        # from public PyPI, so a poisoned index entry executed attacker code
        # while that token was live.
        jobs = _job_blocks(_workflow_text("release.yml"))
        writers = [name for name, body in jobs.items() if "contents: write" in body]
        self.assertTrue(writers, "the release workflow must still have a contents: write job")
        for name in writers:
            with self.subTest(job=name):
                body = jobs[name]
                self.assertNotIn("skill-control-plane==", body)
                for line in body.splitlines():
                    if "pip install" in line:
                        self.assertIn(
                            "--no-index",
                            line,
                            f"{name}: a write-capable job may only install local artifacts",
                        )

    def test_post_publish_pypi_verification_runs_without_a_write_token(self):
        jobs = _job_blocks(_workflow_text("release.yml"))
        holders = [name for name, body in jobs.items() if "skill-control-plane==" in body]
        self.assertEqual(len(holders), 1, "exactly one job verifies the published distribution")
        body = jobs[holders[0]]
        self.assertIn("contents: read", body)
        self.assertNotIn("contents: write", body)
        self.assertNotIn("id-token: write", body)
        self.assertIn("SKILLS_MANAGER_DATA=$(mktemp -d)", body)


# ------------------------------------------------------------------------ SEC-8


def _build_system_block(pyproject: str) -> str:
    """Return the ``[build-system]`` block with comments removed.

    Comments are stripped because the pin rationale quotes the historical
    ``setuptools>=61`` requirement, and that text must not be mistaken for the
    live configuration (Python 3.10 has no ``tomllib``, so this is text-based).
    """

    block = pyproject.split("[build-system]", 1)[1].split("\n[", 1)[0]
    return "\n".join(line.split("#", 1)[0] for line in block.splitlines())


def _lock_requirements(text: str) -> list[tuple[str, list[str]]]:
    requirements: list[tuple[str, list[str]]] = []
    for line in text.replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        hashes = [field.split("=", 1)[1] for field in fields[1:] if field.startswith("--hash=")]
        requirements.append((fields[0], hashes))
    return requirements


class BuildToolchainPinTests(unittest.TestCase):
    def test_the_build_backend_is_pinned_to_an_exact_version(self):
        block = _build_system_block((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertNotIn(">=", block)
        match = re.search(r"(?m)^\s*requires\s*=\s*\[([^\]]*)\]", block)
        self.assertIsNotNone(match, "[build-system] requires is missing")
        specs = re.findall(r'"([^"]+)"', match.group(1))
        self.assertTrue(specs, "[build-system] requires is empty")
        for requirement in specs:
            with self.subTest(requirement=requirement):
                self.assertRegex(requirement, r"^[A-Za-z0-9_.-]+==\d[\w.]*$")

    def test_the_build_toolchain_lock_pins_versions_and_hashes(self):
        lock = ROOT / "requirements-build.txt"
        self.assertTrue(lock.is_file(), "the build toolchain lock file must exist")
        text = lock.read_text(encoding="utf-8")
        requirements = _lock_requirements(text)
        self.assertTrue(requirements)
        names = set()
        for spec, hashes in requirements:
            self.assertRegex(spec, r"^[A-Za-z0-9_.-]+==\d[\w.]*$")
            self.assertTrue(hashes, f"{spec} has no hash")
            for digest in hashes:
                self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
            names.add(spec.split("==", 1)[0].lower())
        self.assertIn("setuptools", names)
        self.assertIn("build", names)

        backend = re.search(r'"([A-Za-z0-9_.-]+==[\w.]+)"', _build_system_block(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        ))
        self.assertIsNotNone(backend)
        self.assertIn(backend.group(1), text, "the lock must pin the same backend as pyproject.toml")

    def test_the_workflows_install_and_use_the_lock(self):
        for name in ("ci.yml", "release.yml"):
            text = _workflow_text(name)
            with self.subTest(workflow=name):
                self.assertIn("--require-hashes -r requirements-build.txt", text)
                self.assertIn("--no-isolation", text)
                self.assertIn("python3 -m build --no-isolation --wheel --sdist --outdir dist", text)


# ------------------------------------------------------------------------ SEC-9


class VendoredBundleIntegrityTests(unittest.TestCase):
    def test_the_shipped_bundle_matches_the_recorded_upstream_artifact(self):
        payload = (ROOT / check_package_data.VUE_MEMBER).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), check_package_data.VUE_SHA256)
        self.assertEqual(len(payload), check_package_data.VUE_SIZE)
        self.assertIn(check_package_data.VUE_VERSION, check_package_data.VUE_UPSTREAM_URL)
        check_package_data.verify_vendored_bundle(ROOT)

    def test_a_tampered_payload_is_rejected(self):
        payload = bytearray((ROOT / check_package_data.VUE_MEMBER).read_bytes())
        payload[0] = payload[0] ^ 0x20
        with self.assertRaises(AssertionError) as ctx:
            check_package_data.verify_vendored_vue(bytes(payload), source="vue.global.prod.js")
        self.assertIn("sha256", str(ctx.exception))

    def test_a_tampered_archive_member_is_rejected(self):
        members = {
            name: (b"/* compromised bundle */" if name == check_package_data.VUE_MEMBER else b"asset")
            for name in check_package_data.expected_webui_members()
        }
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / "skill_control_plane-1.0.1-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, data in sorted(members.items()):
                    archive.writestr(name, data)
            with self.assertRaises(AssertionError) as ctx:
                check_package_data.inspect_archive(wheel)
            self.assertIn("sha256", str(ctx.exception))

    def test_the_packaging_gate_fails_when_the_source_bundle_is_tampered(self):
        # The gate must check the source tree too, because it reports
        # UNAVAILABLE (no optional build tooling) in the default local run.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / check_package_data.VUE_MEMBER).parent.mkdir(parents=True)
            (root / check_package_data.VUE_MEMBER).write_bytes(b"/* compromised bundle */")
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                status = check_package_data.run_check(project_root=root)
            self.assertEqual(status, 1)
            self.assertIn("sha256", stderr.getvalue())

    def test_gitattributes_keeps_the_bundle_byte_stable(self):
        lines = [
            line.strip()
            for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertIn(f"{check_package_data.VUE_MEMBER} -text", lines)


# ------------------------------------------------------------- SEC-13 (settled)


class SdistMemberVisibilityTests(unittest.TestCase):
    """SEC-13's open `[?]` was settled by building the real artifacts.

    Building with the pinned toolchain showed the sdist shipping all 29 test
    modules *and* the gate staying silent, because ``read_archive_files`` dropped
    every sdist member outside ``skillsmgr/`` before the forbidden-member policy
    could see it.  Both halves are pinned here.
    """

    @staticmethod
    def _sdist(root: Path, members: dict[str, bytes]) -> Path:
        import tarfile

        path = root / "skill_control_plane-1.0.1.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
        return path

    def test_a_non_package_sdist_member_is_no_longer_invisible(self):
        members = {
            name: (_VENDORED_VUE if name == check_package_data.VUE_MEMBER else b"asset")
            for name in check_package_data.expected_webui_members()
        }
        members["skill_control_plane-1.0.1/tests/test_store.py"] = b"# test"
        with tempfile.TemporaryDirectory() as directory:
            sdist = self._sdist(Path(directory), members)
            kind, files = check_package_data.read_archive_files(sdist)
            self.assertEqual(kind, "sdist")
            self.assertIn("tests/test_store.py", files)
            with self.assertRaises(AssertionError) as ctx:
                check_package_data.inspect_archive(sdist)
            self.assertIn("tests/test_store.py", str(ctx.exception))

    def test_the_sdist_root_component_is_stripped_for_package_members(self):
        members = {
            name: (_VENDORED_VUE if name == check_package_data.VUE_MEMBER else b"asset")
            for name in check_package_data.expected_webui_members()
        }
        with tempfile.TemporaryDirectory() as directory:
            root = "skill_control_plane-1.0.1/"
            members.update(
                {
                    root + "PKG-INFO": (
                        b"Metadata-Version: 2.4\nName: skill-control-plane\nVersion: 1.0.1\n"
                        b"License-Expression: MIT\nLicense-File: LICENSE\n\n"
                    ),
                    root + "LICENSE": (ROOT / "LICENSE").read_bytes(),
                }
            )
            sdist = self._sdist(
                Path(directory),
                {root + name if not name.startswith(root) else name: data for name, data in members.items()},
            )
            report = check_package_data.inspect_archive(sdist)
            self.assertEqual(report.webui_members, check_package_data.expected_webui_members())

    def test_the_sdist_is_configured_not_to_ship_the_test_suite(self):
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        directives = [
            line.strip()
            for line in manifest.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertIn("prune tests", directives)


if __name__ == "__main__":
    unittest.main()
