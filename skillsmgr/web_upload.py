"""Internal multipart and folder-upload helpers for the local web UI."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from email.parser import BytesParser
from email.policy import default as _email_policy
from pathlib import Path
from typing import Callable

from .store import StoreError


MAX_UPLOAD_PARTS = 200
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def parse_multipart(raw: bytes, boundary: str) -> list[dict]:
    """Parse the limited multipart form used by webkitdirectory uploads.

    Returns dictionaries containing ``name``, ``filename`` and byte
    ``content``.  Relative paths in ``filename`` are retained for the folder
    staging helper; the helper validates containment before writing anything.
    """

    delimiter = b"--" + boundary.encode()
    parts = []
    for chunk in raw.split(delimiter):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        header_blob, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        content = content.rstrip(b"\r\n")
        if header_blob.endswith(b"--"):
            continue
        headers = BytesParser(policy=_email_policy).parsebytes(header_blob + b"\r\n")
        disposition = headers.get("Content-Disposition", "")
        name_match = re.search(r'name="([^"]*)"', disposition)
        file_match = re.search(r'filename="([^"]*)"', disposition)
        parts.append(
            {
                "name": name_match.group(1) if name_match else "",
                "filename": file_match.group(1) if file_match else None,
                "content": content,
            }
        )
    return parts


def upload_folder(
    file_parts: list[dict],
    add_skill: Callable[[Path], dict],
    *,
    max_parts: int = MAX_UPLOAD_PARTS,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> dict:
    """Stage a webkitdirectory upload, then add each discovered skill.

    ``add_skill`` is the Store adapter supplied by the handler.  Keeping the
    filesystem staging and per-skill result contract here makes this policy
    independently testable without exposing a new Store method or changing
    ``WebAppHandler``/``WebAppServer`` interfaces.
    """

    if len(file_parts) > max_parts:
        raise StoreError(f"too many upload parts (max {max_parts})")
    if sum(len(part.get("content") or b"") for part in file_parts) > max_bytes:
        raise StoreError("upload too large")
    skill_files = [
        part
        for part in file_parts
        if part["filename"] and part["filename"].endswith("SKILL.md")
    ]
    if not skill_files:
        raise StoreError("no SKILL.md files in upload")

    tmp_root = Path(tempfile.mkdtemp(prefix="skillsmgr-add-"))
    imported: list[str] = []
    skipped: list[str] = []
    try:
        for part in file_parts:
            rel = part["filename"]
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                continue
            target = (tmp_root / rel).resolve()
            try:
                inside = target.is_relative_to(tmp_root)
            except AttributeError:
                inside = str(target).startswith(str(tmp_root) + os.sep)
            if not inside:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(part["content"])
        for skill_file in sorted(tmp_root.rglob("SKILL.md")):
            source_dir = skill_file.parent
            try:
                result = add_skill(source_dir)
                imported.append(result["name"])
            except StoreError as exc:
                skipped.append(f"{source_dir.name}: {exc}")
        return {"imported": imported, "skipped": skipped}
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
