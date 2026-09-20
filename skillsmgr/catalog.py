"""Filesystem-owned tags, profiles, and batch-plan helpers.

Skill documents and the SQLite index remain authoritative for skill content and
discovery.  This small sidecar stores only manager-owned organization metadata
and is deliberately readable/rebuildable without SQLite.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .atomic_io import atomic_write_text, mutation_lock
from .validator import validate_skill_name

CATALOG_DIRNAME = "catalog"
CATALOG_FILENAME = "metadata.json"
CATALOG_VERSION = 1
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_TAGS_PER_SKILL = 32
_MAX_PROFILE_SKILLS = 1000
_MAX_PROFILE_TARGETS = 64


class CatalogError(ValueError):
    """Raised when manager metadata is malformed or outside its bounds."""


def catalog_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / CATALOG_DIRNAME / CATALOG_FILENAME


def empty_catalog() -> dict:
    return {"version": CATALOG_VERSION, "tags": {}, "profiles": {}}


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise CatalogError(f"{label} must contain only letters, digits, '.', '_' or '-' (max 64 chars)")
    return value


def _tag(value: object) -> str:
    if not isinstance(value, str):
        raise CatalogError("tags must be strings")
    value = value.strip()
    if not value or len(value) > 48 or any(ch in value for ch in "\r\n\x00"):
        raise CatalogError("tags must be 1-48 characters without newlines")
    return value


def _string_list(value: object, label: str, limit: int) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise CatalogError(f"{label} must be a list of at most {limit} strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or "\x00" in item:
            raise CatalogError(f"{label} must contain non-empty strings")
        result.append(item.strip())
    return sorted(set(result), key=str.casefold)


def normalize_catalog(raw: object) -> dict:
    if raw is None:
        return empty_catalog()
    if not isinstance(raw, dict):
        raise CatalogError("catalog must be a JSON object")
    if raw.get("version", CATALOG_VERSION) != CATALOG_VERSION:
        raise CatalogError(f"unsupported catalog version: {raw.get('version')!r}")
    tags_raw = raw.get("tags", {})
    profiles_raw = raw.get("profiles", {})
    if not isinstance(tags_raw, dict) or not isinstance(profiles_raw, dict):
        raise CatalogError("catalog tags and profiles must be objects")
    tags: dict[str, list[str]] = {}
    for name, values in tags_raw.items():
        try:
            name = validate_skill_name(name)
        except (TypeError, ValueError) as exc:
            raise CatalogError(f"invalid tagged skill name: {name!r}") from exc
        values = _string_list(values, f"tags for {name!r}", _MAX_TAGS_PER_SKILL)
        tags[name] = sorted({_tag(value) for value in values}, key=str.casefold)
    profiles: dict[str, dict] = {}
    for profile_name, profile in profiles_raw.items():
        profile_name = _identifier(profile_name, "profile name")
        if not isinstance(profile, dict):
            raise CatalogError(f"profile {profile_name!r} must be an object")
        description = profile.get("description", "")
        if not isinstance(description, str) or len(description) > 500:
            raise CatalogError(f"profile {profile_name!r} description is invalid")
        skills = _string_list(profile.get("skills", []), f"skills for profile {profile_name!r}", _MAX_PROFILE_SKILLS)
        for name in skills:
            try:
                validate_skill_name(name)
            except (TypeError, ValueError) as exc:
                raise CatalogError(f"invalid skill {name!r} in profile {profile_name!r}") from exc
        targets = _string_list(profile.get("targets", []), f"targets for profile {profile_name!r}", _MAX_PROFILE_TARGETS)
        profiles[profile_name] = {
            "description": description.strip(),
            "skills": skills,
            "targets": targets,
        }
    return {"version": CATALOG_VERSION, "tags": tags, "profiles": profiles}


def load_catalog(data_dir: str | Path) -> dict:
    path = catalog_path(data_dir)
    if not path.is_file():
        return empty_catalog()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise CatalogError(f"could not read catalog metadata: {exc}") from exc
    return normalize_catalog(raw)


def save_catalog(data_dir: str | Path, catalog: object) -> dict:
    normalized = normalize_catalog(catalog)
    path = catalog_path(data_dir)
    with mutation_lock(path):
        atomic_write_text(path, json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    return normalized


def enrich_rows(rows: list[dict], catalog: dict | None = None, *, data_dir: str | Path | None = None) -> list[dict]:
    catalog = catalog if catalog is not None else load_catalog(data_dir or ".")
    tags = catalog["tags"]
    for row in rows:
        row["tags"] = list(tags.get(row.get("name"), []))
    return rows


def update_tags(data_dir: str | Path, names: list[str], operation: str, values: list[str]) -> dict:
    if operation not in {"add", "remove", "replace"}:
        raise CatalogError("tag operation must be add, remove, or replace")
    clean_names: set[str] = set()
    for name in names:
        try:
            clean_names.add(validate_skill_name(name))
        except (TypeError, ValueError) as exc:
            raise CatalogError(f"invalid tagged skill name: {name!r}") from exc
    names = sorted(clean_names, key=str.casefold)
    values = sorted({_tag(value) for value in values}, key=str.casefold)
    catalog = load_catalog(data_dir)
    for name in names:
        current = set(catalog["tags"].get(name, []))
        if operation == "add":
            current.update(values)
        elif operation == "remove":
            current.difference_update(values)
        else:
            current = set(values)
        if current:
            catalog["tags"][name] = sorted(current, key=str.casefold)
        else:
            catalog["tags"].pop(name, None)
    return save_catalog(data_dir, catalog)


def save_profile(data_dir: str | Path, name: str, profile: dict) -> dict:
    name = _identifier(name, "profile name")
    catalog = load_catalog(data_dir)
    normalized = normalize_catalog({"version": CATALOG_VERSION, "profiles": {name: profile}})["profiles"][name]
    catalog["profiles"][name] = normalized
    return save_catalog(data_dir, catalog)


def delete_profile(data_dir: str | Path, name: str) -> dict:
    name = _identifier(name, "profile name")
    catalog = load_catalog(data_dir)
    catalog["profiles"].pop(name, None)
    return save_catalog(data_dir, catalog)


def plan_hash(operation: str, targets: list[dict], options: dict | None = None) -> str:
    payload = {
        "operation": operation,
        "targets": sorted(
            [
                {
                    "name": item.get("name"),
                    "scope": item.get("scope"),
                    "physical_path": item.get("physical_path") or item.get("path"),
                }
                for item in targets
            ],
            key=lambda item: (str(item["scope"]), str(item["name"]), str(item["physical_path"])),
        ),
        "options": options or {},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def profile_preview(profile: dict, records: list[dict]) -> dict:
    targets = set(profile.get("targets", []))
    members: list[dict] = []
    for name in profile.get("skills", []):
        candidates = [row for row in records if row.get("name") == name]
        if targets:
            candidates = [
                row for row in candidates
                if row.get("scope") in targets or row.get("consumer") in targets
            ]
        hashes = {row.get("content_hash") for row in candidates if row.get("content_hash")}
        if not candidates:
            state = "missing"
        elif len(hashes) > 1:
            state = "divergent"
        elif all(row.get("disabled") for row in candidates):
            state = "disabled"
        else:
            state = "observed"
        members.append({
            "name": name,
            "state": state,
            "instances": [
                {"scope": row.get("scope"), "scope_label": row.get("scope_label"), "path": row.get("path")}
                for row in candidates
            ],
        })
    summary = {state: sum(1 for member in members if member["state"] == state) for state in ("observed", "disabled", "divergent", "missing")}
    return {"description": profile.get("description", ""), "targets": profile.get("targets", []), "members": members, "summary": summary}
