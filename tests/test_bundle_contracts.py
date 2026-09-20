"""Hermetic DEL-10 shared-secret manifest contracts."""

from __future__ import annotations

import unittest

from skillsmgr.bundles import BundleError, bundle_digest, canonical_manifest, sign_manifest, verify_manifest


class BundleContracts(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "version": 1,
            "files": [
                {"path": "skills/demo/SKILL.md", "sha256": "a" * 64},
                {"path": "skills/demo/references/guide.md", "sha256": "b" * 64},
            ],
        }

    def test_canonicalization_is_sorted_and_digest_stable(self):
        reversed_manifest = {"version": 1, "files": list(reversed(self.manifest["files"]))}
        self.assertEqual(canonical_manifest(self.manifest), canonical_manifest(reversed_manifest))
        self.assertEqual(len(bundle_digest(self.manifest)), 64)

    def test_signing_redacts_key_and_states_narrow_guarantee(self):
        signature = sign_manifest(self.manifest, "team-secret")
        self.assertNotIn("team-secret", str(signature))
        self.assertEqual(signature["algorithm"], "hmac-sha256")
        self.assertEqual(signature["authenticity"], "shared-secret group integrity only")

    def test_verification_distinguishes_valid_wrong_tampered_and_revoked(self):
        signature = sign_manifest(self.manifest, "team-secret")
        self.assertEqual(verify_manifest(self.manifest, signature, "team-secret")["reason"], "ok")
        self.assertEqual(verify_manifest(self.manifest, signature, "other-secret")["reason"], "wrong-key")
        changed = {"version": 1, "files": [{"path": "skills/demo/SKILL.md", "sha256": "c" * 64}]}
        self.assertEqual(verify_manifest(changed, signature, "team-secret")["reason"], "tampered")
        self.assertEqual(
            verify_manifest(self.manifest, signature, "team-secret", revoked_digests=[bundle_digest(self.manifest)])["reason"],
            "revoked",
        )

    def test_invalid_manifest_signature_and_paths_fail_closed(self):
        with self.assertRaises(BundleError):
            canonical_manifest({"version": 1, "files": [{"path": "../escape", "sha256": "a" * 64}]})
        with self.assertRaises(BundleError):
            sign_manifest(self.manifest, b"")
        signature = sign_manifest(self.manifest, "team-secret")
        signature["mac"] = signature["mac"][:-1]
        self.assertEqual(verify_manifest(self.manifest, signature, "team-secret")["reason"], "invalid-signature")


if __name__ == "__main__":
    unittest.main()
