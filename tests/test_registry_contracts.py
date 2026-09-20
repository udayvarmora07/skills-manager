"""Hermetic contracts for registry reads, snapshots, cache, and provenance."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from skillsmgr import registry


def _files():
    return [
        {"path": "SKILL.md", "contents": "---\nname: demo\ndescription: Demo.\n---\n# Demo\n"},
        {"path": "references/readme.txt", "contents": "reference\n"},
    ]


def _snapshot():
    files = _files()
    return {"id": "owner/repo/demo", "files": files, "hash": registry.registry_snapshot_hash(files)}


class Response:
    def __init__(self, payload, *, status=200, content_type="application/json",
                 cache_control="max-age=300", final_url=None):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status = status
        self.headers = {"Content-Type": content_type, "Cache-Control": cache_control}
        self.final_url = final_url
        self.closed = False

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]

    def getcode(self):
        return self.status

    def geturl(self):
        return self.final_url or "https://skills.sh/api/v1/skills"

    def close(self):
        self.closed = True


class RegistryClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.responses = []
        self.requests = []

        def opener(request, timeout):
            self.requests.append((request, timeout))
            if not self.responses:
                raise AssertionError("unexpected network request")
            return self.responses.pop(0)

        self.opener = opener
        self.client = registry.RegistryClient(self.tmp.name, opener=opener, token="secret")

    def test_browse_auth_and_url_contract(self):
        self.responses.append(Response({"data": [], "pagination": {"page": 0}}))
        result = self.client.browse(page=2, per_page=7, view="trending")
        request, timeout = self.requests[0]
        self.assertEqual(result["data"], [])
        self.assertIn("page=2", request.full_url)
        self.assertIn("per_page=7", request.full_url)
        self.assertIn("view=trending", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertGreater(timeout, 0)

    def test_search_and_curated_validate_inputs(self):
        for operation in (
            lambda: self.client.search("x"),
            lambda: self.client.search("ok", limit=201),
            lambda: self.client.browse(view="popular"),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(registry.RegistryError):
                    operation()
        self.responses.append(Response({"data": []}))
        self.assertEqual(self.client.curated()["data"], [])

    def test_detail_and_fetch_use_encoded_registry_paths(self):
        self.responses.append(Response(
            _snapshot(), final_url="https://skills.sh/api/v1/skills/owner/repo/demo"
        ))
        self.client.detail("https://skills.sh/owner/repo/demo?utm=1")
        result = self.client.fetch("owner/repo/demo")
        self.assertEqual(result["registry_hash"], result["hash"])
        self.assertNotEqual(result["snapshot_hash"], result["hash"])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0][0].full_url, "https://skills.sh/api/v1/skills/owner/repo/demo")

    def test_cache_hit_and_stale_fallback_are_explicit(self):
        clock = [1000.0]
        client = registry.RegistryClient(
            self.tmp.name, opener=self.opener, token="secret", now=lambda: clock[0]
        )
        self.responses.append(Response({"data": []}, cache_control="max-age=10"))
        self.assertEqual(client.browse()["_registry"]["cache_state"], "miss")
        self.assertEqual(client.browse()["_registry"]["cache_state"], "fresh")
        self.assertEqual(len(self.requests), 1)
        clock[0] = 1011.0
        self.responses.append(Response({"data": ["fresh"]}, cache_control="max-age=10"))
        self.assertEqual(client.browse()["_registry"]["cache_state"], "refreshed")
        clock[0] = 1022.0
        self.responses.clear()
        client._opener = lambda request, timeout: (_ for _ in ()).throw(URLError("offline"))
        self.assertEqual(client.browse(allow_stale=True)["_registry"], {
            "cache_state": "stale", "stale": True,
            "url": "https://skills.sh/api/v1/skills?page=0&per_page=100&view=all-time",
        })

    def test_cache_is_private_and_never_contains_token(self):
        self.responses.append(Response({"data": []}))
        self.client.browse()
        cache_dir = Path(self.tmp.name) / registry.REGISTRY_CACHE_DIRNAME
        self.assertEqual(cache_dir.stat().st_mode & 0o777, 0o700)
        cache = next(cache_dir.glob("*.json"))
        self.assertEqual(cache.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("secret", cache.read_text(encoding="utf-8"))

    def test_cache_isolated_by_auth_scope(self):
        self.responses.append(Response({"data": ["private"]}))
        self.client.browse()
        anonymous = registry.RegistryClient(self.tmp.name, opener=self.opener)
        self.responses.append(Response({"data": ["public"]}))
        self.assertEqual(anonymous.browse()["data"], ["public"])
        self.assertEqual(len(self.requests), 2)

    def test_http_json_size_and_redirect_fail_closed(self):
        self.responses.append(Response({"error": "bad"}, status=401))
        with self.assertRaisesRegex(registry.RegistryError, "HTTP 401"):
            self.client.browse()
        self.responses.append(Response({"data": []}, content_type="text/html"))
        with self.assertRaisesRegex(registry.RegistryError, "not JSON"):
            self.client.browse()
        self.responses.append(Response({"data": []}, final_url="https://evil.example/api/v1/skills"))
        with self.assertRaisesRegex(registry.RegistryError, "skills.sh HTTPS"):
            self.client.browse()

    def test_snapshot_validation_rejects_bad_hash_paths_and_limits(self):
        for path in ("../escape", "references//readme.txt", "references/./readme.txt", "references/readme.txt/"):
            with self.subTest(path=path), self.assertRaises(registry.RegistryError):
                registry.validate_snapshot({"files": [{"path": "SKILL.md", "contents": "x"}, {"path": path, "contents": "x"}]})
        with self.assertRaises(registry.RegistryError):
            registry.validate_snapshot({"files": [{"path": "SKILL.md", "contents": "x"}], "hash": "0" * 64})
        with self.assertRaises(registry.RegistryError):
            registry.validate_snapshot({"files": [{"path": "SKILL.md", "contents": "x"}, {"path": "SKILL.md", "contents": "y"}]})
        with self.assertRaises(registry.RegistryError):
            registry.validate_snapshot({"files": [{"path": "SKILL.md", "contents": "x" * (registry.MAX_FILE_BYTES + 1)}]})

    def test_expected_hash_and_materialization(self):
        self.responses.append(Response(_snapshot()))
        result = self.client.fetch("owner/repo/demo", expected_hash=registry.registry_snapshot_hash(_files()))
        with tempfile.TemporaryDirectory() as staging:
            root = registry.materialize_snapshot(result, staging)
            self.assertEqual((root / "SKILL.md").read_text(encoding="utf-8"), _files()[0]["contents"])
            self.assertEqual((root / "references/readme.txt").read_text(encoding="utf-8"), "reference\n")
            self.assertEqual((root / "SKILL.md").stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(registry.RegistryError, "expected_hash"):
            self.client.fetch("owner/repo/demo", expected_hash="a" * 64)

    def test_materialization_rejects_existing_symlink(self):
        with tempfile.TemporaryDirectory() as staging:
            root = Path(staging)
            (root / "outside").mkdir()
            (root / "references").symlink_to(root / "outside", target_is_directory=True)
            with self.assertRaises(registry.RegistryError):
                registry.materialize_snapshot(_snapshot(), root)

    def test_materialization_rejects_symlink_file(self):
        with tempfile.TemporaryDirectory() as staging:
            root = Path(staging)
            outside = root / "outside.txt"
            outside.write_text("keep", encoding="utf-8")
            (root / "SKILL.md").symlink_to(outside)
            with self.assertRaises(registry.RegistryError):
                registry.materialize_snapshot(_snapshot(), root)
            self.assertEqual(outside.read_text(encoding="utf-8"), "keep")

    def test_provenance_round_trip_is_credential_free(self):
        self.responses.append(Response(_snapshot()))
        snapshot = self.client.fetch("owner/repo/demo")
        provenance = registry.provenance_for_snapshot(snapshot)
        with tempfile.TemporaryDirectory() as skill_dir:
            registry.materialize_snapshot(snapshot, skill_dir)
            path = registry.write_provenance(skill_dir, provenance)
            self.assertEqual(path.name, registry.PROVENANCE_FILENAME)
            loaded = registry.read_provenance(skill_dir)
            self.assertEqual(loaded["local_snapshot_hash"], snapshot["snapshot_hash"])
            self.assertNotIn("secret", path.read_text(encoding="utf-8"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_registry_review_is_private_expiring_and_single_use(self):
        snapshot = registry.validate_snapshot(_snapshot())
        snapshot.update({
            "id": "owner/repo/demo",
            "source": "owner/repo",
            "slug": "demo",
            "api_url": "https://skills.sh/api/v1/skills/owner/repo/demo",
            "_registry": {"cache_state": "miss", "stale": False},
        })
        review = registry.write_registry_review(
            self.tmp.name,
            snapshot,
            {"validation": {"valid": True}, "risk": {"findings": []}},
        )
        review_dir = Path(self.tmp.name) / registry.REGISTRY_REVIEW_DIRNAME
        self.assertEqual(review_dir.stat().st_mode & 0o777, 0o700)
        review_path = review_dir / f"{review['review_id']}.json"
        self.assertEqual(review_path.stat().st_mode & 0o777, 0o600)
        loaded = registry.read_registry_review(self.tmp.name, review["review_id"])
        self.assertEqual(loaded["snapshot"]["slug"], "demo")
        self.assertNotIn("contents", str(registry.registry_review_public(loaded)))
        committed = registry.mark_registry_review_committed(self.tmp.name, review["review_id"])
        self.assertEqual(committed["status"], "committed")
        with self.assertRaisesRegex(registry.RegistryError, "already been committed"):
            registry.read_registry_review(self.tmp.name, review["review_id"])
        with self.assertRaisesRegex(registry.RegistryError, "credential fields"):
            registry.write_registry_review(
                self.tmp.name,
                snapshot,
                {"validation": {"valid": True}, "risk": {"access_token": "redacted"}},
            )

    def test_provenance_rejects_unsafe_or_malformed_sidecars(self):
        with tempfile.TemporaryDirectory() as skill_dir:
            sidecar = Path(skill_dir) / registry.PROVENANCE_FILENAME
            sidecar.write_text(json.dumps({"version": 1, "kind": "skills.sh", "token": "x"}), encoding="utf-8")
            with self.assertRaises(registry.RegistryError):
                registry.read_provenance(skill_dir)
            valid = registry.provenance_for_snapshot(_snapshot())
            valid["page_url"] = "https://skills.sh/owner/repo/demo?token=secret"
            with self.assertRaises(registry.RegistryError):
                registry.write_provenance(skill_dir, valid)
            sidecar.write_text(json.dumps({
                "version": 1, "kind": "skills.sh", "id": "owner/repo/demo",
                "source": "owner/repo", "slug": "demo",
                "api_url": "https://skills.sh/api/v1/skills/owner/repo/demo",
                "local_snapshot_hash": "a" * 64, "hash_verified": False,
                "files": [{"path": "SKILL.md", "sha256": "b" * 64, "bytes": 1},
                          {"path": "SKILL.md", "sha256": "c" * 64, "bytes": 1}],
            }), encoding="utf-8")
            with self.assertRaises(registry.RegistryError):
                registry.read_provenance(skill_dir)
            sidecar.write_text("not json", encoding="utf-8")
            with self.assertRaises(registry.RegistryError):
                registry.read_provenance(skill_dir)

    def test_loader_exposes_valid_provenance_and_marks_drift(self):
        from skillsmgr.loader import load_skill

        snapshot = registry.validate_snapshot(_snapshot())
        snapshot.update({
            "id": "owner/repo/demo",
            "source": "owner/repo",
            "slug": "demo",
            "api_url": "https://skills.sh/api/download/owner/repo/demo",
            "_registry": {"cache_state": "miss"},
        })
        provenance = registry.provenance_for_snapshot(snapshot)
        with tempfile.TemporaryDirectory() as skill_dir:
            root = registry.materialize_snapshot(snapshot, skill_dir)
            registry.write_provenance(root, provenance)
            loaded = load_skill(root)
            self.assertEqual(loaded["registry_provenance"]["id"], "owner/repo/demo")
            (root / "references" / "readme.txt").write_text("changed\n", encoding="utf-8")
            drifted = load_skill(root)
            self.assertTrue(drifted["malformed"])
            self.assertIn("registry_provenance_error", drifted)


class ImportAndPathTests(unittest.TestCase):
    def test_no_network_request_at_module_import_and_url_policy(self):
        self.assertTrue(registry.REGISTRY_BASE_URL.startswith("https://"))
        for url in (
            "http://skills.sh/api/v1/skills",
            "https://evil.example/api/v1/skills",
            "https://skills.sh:8443/api/v1/skills",
            "https://skills.sh/not-api",
        ):
            with self.subTest(url=url):
                with self.assertRaises(registry.RegistryError):
                    registry._registry_url(url)


if __name__ == "__main__":
    unittest.main()
