"""Archive inspection, safe extraction, and staged skill commit helpers."""

from __future__ import annotations

import re
import shutil
import tarfile
import zipfile
import zlib
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
    # Reject Windows separators on every host so a tar authored on Windows
    # cannot smuggle a nested path past the "/" split below (tar member
    # names are "/"-separated per POSIX; "\" must never become a separator).
    if name.startswith(("/", "\\")) or "\\" in name:
        raise ArchiveError(f"unsafe archive member: {name!r}")
    # Reject drive-letter prefixes ("C:...", including slash variants) on
    # every host so extraction stays inside the managed root on Windows too;
    # pathlib treats "C:..." as relative on POSIX while Windows resolves it
    # against the current drive.
    if re.fullmatch(r"[A-Za-z]:.*", name):
        raise ArchiveError(f"unsafe archive member: {name!r}")
    normalized = name.rstrip("/")
    parts = normalized.split("/") if normalized else []
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ArchiveError(f"unsafe archive member: {name!r}")
    return "/".join(parts)


def _validate_archive_limits(
    name: str,
    file_size: int,
    compressed_size: int,
    seen: set[str],
    expanded_size: int,
    ratio_compressed_size: int | None = None,
) -> tuple[str, int]:
    if len(name) > MAX_ARCHIVE_PATH_LENGTH:
        raise ArchiveError(f"archive member path is too long: {name!r}")
    normalized = normalize_member_name(name)
    if len(normalized.split("/")) > MAX_ARCHIVE_NESTING:
        raise ArchiveError(f"archive member path is nested too deeply: {name!r}")
    if normalized in seen:
        raise ArchiveError(f"duplicate archive member: {normalized!r}")
    seen.add(normalized)
    if len(seen) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveError(f"archive has too many members (max {MAX_ARCHIVE_MEMBERS})")
    if file_size > MAX_ARCHIVE_MEMBER_BYTES:
        raise ArchiveError(f"archive member exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes: {normalized!r}")
    expanded_size += file_size
    if expanded_size > MAX_ARCHIVE_EXPANDED_BYTES:
        raise ArchiveError(f"archive expanded size exceeds {MAX_ARCHIVE_EXPANDED_BYTES} bytes")
    ratio_size = compressed_size if ratio_compressed_size is None else ratio_compressed_size
    if expanded_size > max(ratio_size, 1) * MAX_ARCHIVE_COMPRESSION_RATIO:
        raise ArchiveError(f"archive compression ratio exceeds {MAX_ARCHIVE_COMPRESSION_RATIO}:1")
    return normalized, expanded_size


def _zip_member_is_dir(member: zipfile.ZipInfo) -> bool:
    """Use the trailing slash as the portable directory marker.

    ZIP writers vary widely in ``external_attr`` defaults.  A missing DOS/Unix
    directory bit is therefore tolerated for a slash-terminated name, while a
    positive directory bit on a non-directory name is rejected as contradictory.
    Special Unix types are rejected by the caller.
    """
    dos_dir = bool(member.external_attr & 0x10)
    name_dir = member.filename.endswith("/")
    mode = (member.external_attr >> 16) & 0o170000
    unix_dir = mode == 0o040000
    if not name_dir and (dos_dir or unix_dir):
        raise ArchiveError(f"inconsistent ZIP directory metadata: {member.filename!r}")
    return name_dir


def _validate_archive_layout(normalized: str, is_dir: bool, is_file: bool) -> None:
    if normalized == "manifest.json":
        if not is_file:
            raise ArchiveError("manifest.json must be a regular file")
        return
    parts = normalized.split("/")
    if parts[0] in {"skills", "trash"}:
        if len(parts) == 1:
            if not is_dir:
                raise ArchiveError(f"archive root entry must be a directory: {normalized!r}")
        elif len(parts) == 2 and not is_dir:
            label = "skill" if parts[0] == "skills" else "trash"
            raise ArchiveError(f"{label} archive entry must be a directory: {normalized!r}")
    elif parts[0] == "templates" and len(parts) == 2 and parts[1].endswith(".md"):
        if not is_file:
            raise ArchiveError(f"template archive entry must be a regular file: {normalized!r}")
    else:
        raise ArchiveError(f"unexpected archive layout: {normalized!r}")


def validate_members(tar: tarfile.TarFile, compressed_size: int) -> list[tuple[tarfile.TarInfo, str]]:
    if compressed_size > MAX_ARCHIVE_COMPRESSED_BYTES:
        raise ArchiveError(f"archive compressed size exceeds {MAX_ARCHIVE_COMPRESSED_BYTES} bytes")
    members: list[tuple[tarfile.TarInfo, str]] = []
    seen: set[str] = set()
    expanded_size = 0
    manifest_count = 0
    for member in tar.getmembers():
        if not (member.isdir() or member.isreg()):
            raise ArchiveError(f"unsupported archive member type: {member.name!r}")
        normalized, expanded_size = _validate_archive_limits(
            member.name, member.size if member.isreg() else 0, compressed_size, seen, expanded_size
        )
        _validate_archive_layout(normalized, member.isdir(), member.isreg())
        if normalized == "manifest.json":
            manifest_count += 1
        members.append((member, normalized))
    if manifest_count != 1:
        raise ArchiveError("archive must contain exactly one manifest.json")
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
    full_flag = manifest.get("full")
    if full_flag is not None and not isinstance(full_flag, bool):
        raise ArchiveError("invalid archive manifest: full must be a boolean")
    for field in ("trash", "templates"):
        value = manifest.get(field)
        if value is None:
            continue
        if not isinstance(value, list):
            raise ArchiveError(f"invalid archive manifest: {field} must be a list")
        for item in value:
            if (
                not isinstance(item, str)
                or not item
                or item.startswith(".")
                or "\\" in item
                or Path(item).name != item
            ):
                raise ArchiveError(f"invalid archive manifest: {field} entry is not a plain name: {item!r}")
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


def validate_zip_members(
    archive: zipfile.ZipFile, compressed_size: int
) -> list[tuple[zipfile.ZipInfo, str]]:
    """Validate ZIP members without trusting ``extractall`` path handling."""
    if compressed_size > MAX_ARCHIVE_COMPRESSED_BYTES:
        raise ArchiveError(f"archive compressed size exceeds {MAX_ARCHIVE_COMPRESSED_BYTES} bytes")
    members: list[tuple[zipfile.ZipInfo, str]] = []
    seen: set[str] = set()
    members_info = archive.infolist()
    if any(member.compress_size < 0 or member.file_size < 0 for member in members_info):
        raise ArchiveError("invalid ZIP member size")
    compressed_total = sum(member.compress_size for member in members_info if not member.is_dir())
    expanded_size = 0
    manifest_count = 0
    for member in members_info:
        mode = (member.external_attr >> 16) & 0o170000
        is_dir = _zip_member_is_dir(member)
        if mode == 0o120000 or (mode not in (0, 0o040000, 0o100000) and not is_dir):
            raise ArchiveError(f"unsupported archive member type: {member.filename!r}")
        # A per-member ratio keeps a stored, incompressible member from
        # masking a later bomb; the cumulative total is checked below too.
        if not is_dir and member.file_size > max(member.compress_size, 1) * MAX_ARCHIVE_COMPRESSION_RATIO:
            raise ArchiveError(f"archive compression ratio exceeds {MAX_ARCHIVE_COMPRESSION_RATIO}:1")
        normalized, expanded_size = _validate_archive_limits(
            member.filename,
            member.file_size if not is_dir else 0,
            compressed_total,
            seen,
            expanded_size,
        )
        _validate_archive_layout(normalized, is_dir, not is_dir)
        if normalized == "manifest.json":
            manifest_count += 1
        members.append((member, normalized))
    if manifest_count != 1:
        raise ArchiveError("archive must contain exactly one manifest.json")
    if expanded_size > max(compressed_total, 1) * MAX_ARCHIVE_COMPRESSION_RATIO:
        raise ArchiveError(f"archive compression ratio exceeds {MAX_ARCHIVE_COMPRESSION_RATIO}:1")
    return members


def extract_zip_members(
    archive: zipfile.ZipFile,
    dest: Path,
    members: list[tuple[zipfile.ZipInfo, str]],
) -> None:
    """Extract validated ZIP regular files into a private destination."""
    expanded_written = 0
    for member, normalized in members:
        target = paths.contained_path(dest, *normalized.split("/"))
        if _zip_member_is_dir(member):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with archive.open(member, "r") as source, target.open("wb") as output:
                while True:
                    chunk = source.read(min(1024 * 1024, MAX_ARCHIVE_MEMBER_BYTES - written + 1))
                    if not chunk:
                        break
                    written += len(chunk)
                    expanded_written += len(chunk)
                    if written > MAX_ARCHIVE_MEMBER_BYTES:
                        raise ArchiveError(f"archive member exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes: {normalized!r}")
                    if expanded_written > MAX_ARCHIVE_EXPANDED_BYTES:
                        raise ArchiveError(f"archive expanded size exceeds {MAX_ARCHIVE_EXPANDED_BYTES} bytes")
                    output.write(chunk)
            if written != member.file_size:
                raise ArchiveError(f"ZIP member size mismatch: {normalized!r}")
        except ArchiveError:
            raise
        except (OSError, RuntimeError, zipfile.BadZipFile, zlib.error, NotImplementedError, UnicodeError) as exc:
            raise ArchiveError(f"invalid archive extraction: {exc}") from exc


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
    dest_existed = dest.exists()
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
            # No original was moved aside: either staging failed before the
            # original was ever touched (dest_existed -> it is still the user's
            # skill and must survive) or the destination is one we created, in
            # which case a partial commit must be removed.
            if not dest_existed:
                rmtree(dest, ignore_errors=True)
            rmtree(staged, ignore_errors=True)
            return False, str(exc)
        rmtree(staged, ignore_errors=True)
        return False, str(exc)


def _rollback_full_install(installed: list[tuple[Path, Path | None]], staged: list[Path], *, move, rmtree) -> None:
    """Undo every payload installed by a failed full-import transaction."""
    for dest, previous in reversed(installed):
        rmtree(dest, ignore_errors=True)
        if previous is not None and previous.exists():
            try:
                move(str(previous), str(dest))
            except OSError:
                pass
    for stage in staged:
        rmtree(stage, ignore_errors=True)


def restore_full_payload(
    entries: list[tuple[str, str, Path, Path]],
    *,
    replace: bool,
    move=None,
    rmtree=None,
    copytree=None,
    copyfile=None,
) -> tuple[list[str], list[str], list[str]]:
    """Install validated full-import payloads as one all-or-nothing transaction.

    ``entries`` are ``(kind, label, source, dest)`` tuples that were validated
    before any mutation. Each payload is staged on the destination filesystem,
    the previous entry is moved aside, and the staged copy is moved into place;
    any failure rolls back every entry installed by this call and raises
    :class:`ArchiveError`, so a full import never leaves mixed old/new trash or
    templates behind.
    """
    move = move or shutil.move
    rmtree = rmtree or shutil.rmtree
    copytree = copytree or shutil.copytree
    copyfile = copyfile or shutil.copyfile
    restored: dict[str, list[str]] = {"trash": [], "templates": []}
    skipped: list[str] = []
    installed: list[tuple[Path, Path | None]] = []
    staged: list[Path] = []
    try:
        for kind, label, source, dest in entries:
            if (dest.exists() or dest.is_symlink()) and not replace:
                skipped.append(f"{kind}/{label}")
                continue
            stage = dest.parent / f".{dest.name}.skillsmgr-stage"
            backup = dest.parent / f".{dest.name}.skillsmgr-backup"
            dest.parent.mkdir(parents=True, exist_ok=True)
            rmtree(stage, ignore_errors=True)
            staged.append(stage)
            if source.is_dir():
                copytree(source, stage)
            else:
                copyfile(source, stage)
            previous = None
            if dest.exists() or dest.is_symlink():
                move(str(dest), str(backup))
                previous = backup
            move(str(stage), str(dest))
            installed.append((dest, previous))
            restored[kind].append(label)
    except (OSError, shutil.Error) as exc:
        _rollback_full_install(installed, staged, move=move, rmtree=rmtree)
        raise ArchiveError(f"could not restore full archive payload: {exc}") from exc
    rmtree_previous = [previous for _, previous in installed if previous is not None]
    for previous in rmtree_previous:
        rmtree(previous, ignore_errors=True)
    return restored["trash"], restored["templates"], skipped
