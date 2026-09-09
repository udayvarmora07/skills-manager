"""Archive inspection, safe extraction, and staged skill commit helpers."""

from __future__ import annotations

import re
import shutil
import tarfile
from pathlib import Path

from . import paths, __version__
from .atomic_io import tree_content_hash
from .frontmatter import FrontmatterError, parse_frontmatter
from .validator import validate_skill_name


class ArchiveError(Exception):
    """Raised for archive validation or extraction failures."""


MAX_ARCHIVE_COMPRESSED_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_EXPANDED_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 200
MAX_ARCHIVE_PATH_LENGTH = 512
MAX_ARCHIVE_NESTING = 16
MAX_ARCHIVE_COMPRESSION_RATIO = 1000


def normalize_member_name(name: str) -> str:
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ArchiveError(f"unsafe archive member: {name!r}")
    if name.startswith(("/", "\\")) or "\\" in name:
        raise ArchiveError(f"unsafe archive member: {name!r}")
    normalized = name.rstrip("/")
    parts = normalized.split("/") if normalized else []
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ArchiveError(f"unsafe archive member: {name!r}")
    return "/".join(parts)


def validate_members(tar: tarfile.TarFile, compressed_size: int) -> list[tuple[tarfile.TarInfo, str]]:
    members: list[tuple[tarfile.TarInfo, str]] = []
    seen: set[str] = set()
    expanded_size = 0
    manifest_count = 0
    for member in tar.getmembers():
        if len(member.name) > MAX_ARCHIVE_PATH_LENGTH:
            raise ArchiveError(f"archive member path is too long: {member.name!r}")
        normalized = normalize_member_name(member.name)
        if len(normalized.split("/")) > MAX_ARCHIVE_NESTING:
            raise ArchiveError(f"archive member path is nested too deeply: {member.name!r}")
        if normalized in seen:
            raise ArchiveError(f"duplicate archive member: {normalized!r}")
        seen.add(normalized)
        if len(seen) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveError(f"archive has too many members (max {MAX_ARCHIVE_MEMBERS})")
        if normalized == "manifest.json":
            manifest_count += 1
            if not member.isreg():
                raise ArchiveError("manifest.json must be a regular file")
        else:
            parts = normalized.split("/")
            if parts[0] == "skills" and len(parts) >= 2:
                if len(parts) == 2 and not member.isdir():
                    raise ArchiveError(f"skill archive entry must be a directory: {member.name!r}")
            elif parts[0] == "trash" and len(parts) >= 2:
                if len(parts) == 2 and not member.isdir():
                    raise ArchiveError(f"trash archive entry must be a directory: {member.name!r}")
            elif parts[0] == "templates" and len(parts) == 2 and parts[1].endswith(".md"):
                if not member.isreg():
                    raise ArchiveError(f"template archive entry must be a regular file: {member.name!r}")
            else:
                raise ArchiveError(f"unexpected archive layout: {member.name!r}")
        if not (member.isdir() or member.isreg()):
            raise ArchiveError(f"unsupported archive member type: {member.name!r}")
        if member.isreg():
            if member.size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ArchiveError(f"archive member exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes: {normalized!r}")
            expanded_size += member.size
            if expanded_size > MAX_ARCHIVE_EXPANDED_BYTES:
                raise ArchiveError(f"archive expanded size exceeds {MAX_ARCHIVE_EXPANDED_BYTES} bytes")
        members.append((member, normalized))
    if manifest_count != 1:
        raise ArchiveError("archive must contain exactly one manifest.json")
    if expanded_size > max(compressed_size, 1) * MAX_ARCHIVE_COMPRESSION_RATIO:
        raise ArchiveError(f"archive compression ratio exceeds {MAX_ARCHIVE_COMPRESSION_RATIO}:1")
    return members


def validate_manifest(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict):
        raise ArchiveError("invalid archive manifest: expected an object")
    if manifest.get("app") != "skills-mgr":
        raise ArchiveError("invalid archive manifest: unsupported app")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ArchiveError("invalid archive manifest: version must be semantic")
    if version.split(".", 1)[0] != __version__.split(".", 1)[0]:
        raise ArchiveError(f"unsupported archive manifest major version: {version}")
    created = manifest.get("created")
    if not isinstance(created, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created):
        raise ArchiveError("invalid archive manifest: created timestamp")
    skills = manifest.get("skills")
    if not isinstance(skills, list):
        raise ArchiveError("invalid archive manifest: skills must be a list")
    validated: list[dict] = []
    names: set[str] = set()
    for entry in skills:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ArchiveError("invalid archive manifest: each skill needs a name")
        try:
            name = validate_skill_name(entry["name"])
        except ValueError as exc:
            raise ArchiveError(f"invalid archive manifest skill name: {entry['name']!r}") from exc
        if name in names:
            raise ArchiveError(f"duplicate skill in archive manifest: {name!r}")
        names.add(name)
        validated.append(dict(entry, name=name))
    return validated


def extract_members(tar: tarfile.TarFile, dest: Path, members: list[tuple[tarfile.TarInfo, str]]) -> None:
    tar_members = [member for member, _ in members]
    data_filter = getattr(tarfile, "data_filter", None)
    if callable(data_filter):
        try:
            tar.extractall(dest, members=tar_members, filter=data_filter)
        except (OSError, tarfile.TarError, ValueError) as exc:
            raise ArchiveError(f"invalid archive extraction: {exc}") from exc
        return
    for member, normalized in members:
        target = paths.contained_path(dest, *normalized.split("/"))
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        source = tar.extractfile(member)
        if source is None:
            raise ArchiveError(f"archive member has no readable payload: {normalized!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
        except OSError as exc:
            raise ArchiveError(f"invalid archive extraction: {exc}") from exc


def has_skill_document(source: Path) -> bool:
    enabled = (source / "SKILL.md").is_file()
    disabled = (source / "SKILL.md.disabled").is_file()
    if enabled and disabled:
        raise ArchiveError(f"skill directory contains both enabled and disabled documents: {source.name!r}")
    return enabled or disabled


def validate_imported_skill(source: Path, name: str) -> None:
    document = source / ("SKILL.md" if (source / "SKILL.md").is_file() else "SKILL.md.disabled")
    try:
        data, _ = parse_frontmatter(document.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, FrontmatterError) as exc:
        raise ArchiveError(f"invalid skill document for {name!r}: {exc}") from exc
    if data.get("name") is not None and data.get("name") != name:
        raise ArchiveError(f"skill document name {data.get('name')!r} does not match manifest name {name!r}")


def commit_staged_skill(
    source: Path,
    dest: Path,
    stage_root: Path,
    expected_hash: str | None,
    *,
    upsert,
    copytree=None,
    move=None,
    rmtree=None,
) -> tuple[bool, str | None]:
    """Commit one staged skill and restore the prior destination on failure."""
    copytree = copytree or shutil.copytree
    move = move or shutil.move
    rmtree = rmtree or shutil.rmtree
    staged = stage_root / dest.name
    backup = stage_root / f"{dest.name}.backup"
    moved_original = False
    try:
        copytree(source, staged)
        if expected_hash and tree_content_hash(staged) != expected_hash:
            raise ArchiveError(f"content hash mismatch for '{dest.name}'")
        if dest.exists():
            move(str(dest), str(backup))
            moved_original = True
        move(str(staged), str(dest))
        if expected_hash and tree_content_hash(dest) != expected_hash:
            raise ArchiveError(f"committed content hash mismatch for '{dest.name}'")
        upsert(dest.name)
        if backup.exists():
            rmtree(backup)
        return True, None
    except Exception as exc:
        if moved_original:
            # dest now holds (at most) the staged copy we moved in; the user's
            # original lives in backup, so any partial dest may be discarded
            # before the original is moved back into place.
            rmtree(dest, ignore_errors=True)
            if backup.exists():
                try:
                    move(str(backup), str(dest))
                except Exception as restore_exc:
                    rmtree(staged, ignore_errors=True)
                    raise restore_exc from exc
        else:
            # dest was never touched by us: it is still the user's original
            # directory (e.g. the initial backup move failed), so it must be
            # preserved untouched.
            rmtree(staged, ignore_errors=True)
            return False, str(exc)
        rmtree(staged, ignore_errors=True)
        return False, str(exc)