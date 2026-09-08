"""Non-persisted observations for skill documents and frontmatter."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PORTABLE_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "license",
        "compatibility",
        "version",
        "allowed-tools",
        "metadata",
    }
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def document_observations(
    skill_dir: Path,
    text: str,
    frontmatter: dict,
    *,
    scope: str | None = None,
    consumer: str | None = None,
) -> dict:
    """Return derived hashes, provenance, and frontmatter partitioning."""
    portable = {key: value for key, value in frontmatter.items() if key in PORTABLE_FRONTMATTER_KEYS}
    extensions = {key: value for key, value in frontmatter.items() if key not in PORTABLE_FRONTMATTER_KEYS}
    return {
        "portable_frontmatter": portable,
        "frontmatter_extensions": extensions,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "metadata_hash": hashlib.sha256(_canonical_json(frontmatter)).hexdigest(),
        "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provenance": {
            "path": str(Path(skill_dir)),
            "scope": scope,
            "consumer": consumer,
        },
    }