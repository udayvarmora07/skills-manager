"""Offline shared-secret integrity evidence for a future team bundle flow.

This module deliberately does not create or import archives, read keys from
the environment, publish bundles, or mutate a Store.  It signs only a small,
canonical manifest supplied by the caller and describes the narrow guarantee:
shared-secret group integrity, not named-person identity or content safety.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable


MAX_MANIFEST_BYTES = 1_000_000
MAX_FILES = 4096
MAX_PATH_LENGTH = 256
MAX_KEY_BYTES = 4096
MAX_KEY_ID = 16
_HEX = frozenset("0123456789abcdefABCDEF")


class BundleError(ValueError):
    """Raised when a manifest, key, or signature is unsafe or malformed."""


def _key_bytes(key: object) -> bytes:
    if isinstance(key, str):
        key = key.encode("utf-8")
    if not isinstance(key, bytes) or not key or len(key) > MAX_KEY_BYTES:
        raise BundleError("shared key must be non-empty bytes or text within the size limit")
    return key


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        raise BundleError(f"{label} must be a SHA-256 hex digest")
    return value.lower()


def _member_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_PATH_LENGTH:
        raise BundleError("manifest member path is invalid")
    if "\x00" in value or "\\" in value or value.startswith("/"):
        raise BundleError("manifest member path must be relative and slash-separated")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise BundleError("manifest member path contains an unsafe component")
    return value


def _normalized(manifest: object) -> dict:
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise BundleError("manifest must be an object with version 1")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or len(raw_files) > MAX_FILES:
        raise BundleError(f"manifest must contain at most {MAX_FILES} files")
    files = []
    seen = set()
    for raw in raw_files:
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256"}:
            raise BundleError("manifest files must contain only path and sha256")
        path = _member_path(raw["path"])
        if path in seen:
            raise BundleError(f"manifest contains duplicate member {path!r}")
        seen.add(path)
        files.append({"path": path, "sha256": _digest(raw["sha256"], path)})
    files.sort(key=lambda item: item["path"])
    return {"version": 1, "files": files}


def canonical_manifest(manifest: object) -> bytes:
    """Return the bounded deterministic byte representation covered by HMAC."""
    normalized = _normalized(manifest)
    payload = json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise BundleError("canonical manifest exceeds the size limit")
    return payload


def bundle_digest(manifest: object) -> str:
    """Return the SHA-256 digest of the canonical manifest."""
    return hashlib.sha256(canonical_manifest(manifest)).hexdigest()


def sign_manifest(manifest: object, key: object) -> dict:
    """Create detached HMAC evidence without embedding the shared key."""
    payload = canonical_manifest(manifest)
    key_bytes = _key_bytes(key)
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "algorithm": "hmac-sha256",
        "key_id": hashlib.sha256(key_bytes).hexdigest()[:MAX_KEY_ID],
        "digest": digest,
        "mac": hmac.new(key_bytes, payload, hashlib.sha256).hexdigest(),
        "authenticity": "shared-secret group integrity only",
    }


def verify_manifest(
    manifest: object,
    signature: object,
    key: object,
    *,
    revoked_digests: Iterable[str] = (),
) -> dict:
    """Verify detached HMAC evidence and return an honest trust explanation."""
    payload = canonical_manifest(manifest)
    key_bytes = _key_bytes(key)
    digest = hashlib.sha256(payload).hexdigest()
    result = {
        "verified": False,
        "reason": "invalid-signature",
        "digest": digest,
        "key_id": hashlib.sha256(key_bytes).hexdigest()[:MAX_KEY_ID],
        "authenticity": "shared-secret group integrity only",
        "safety_verdict": False,
        "secret_redacted": True,
    }
    if digest in set(revoked_digests):
        result["reason"] = "revoked"
        return result
    if not isinstance(signature, dict) or signature.get("algorithm") != "hmac-sha256":
        return result
    if signature.get("digest") != digest:
        result["reason"] = "tampered"
        return result
    if signature.get("key_id") != result["key_id"]:
        result["reason"] = "wrong-key"
        return result
    mac = signature.get("mac")
    expected = hmac.new(key_bytes, payload, hashlib.sha256).hexdigest()
    if not isinstance(mac, str) or len(mac) != len(expected) or not hmac.compare_digest(mac, expected):
        return result
    result["verified"] = True
    result["reason"] = "ok"
    return result


__all__ = ["BundleError", "bundle_digest", "canonical_manifest", "sign_manifest", "verify_manifest"]
