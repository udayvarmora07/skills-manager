"""Internal multipart and folder-upload helpers for the local web UI."""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import compat32 as _email_policy
from email.utils import collapse_rfc2231_value, unquote
from pathlib import Path, PurePosixPath
from typing import Callable

from .store import StoreError


MAX_UPLOAD_PARTS = 200
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _contained(target: Path, root: Path) -> bool:
    """Return whether the resolved *target* is inside the staging *root*."""

    return target.is_relative_to(root)


def _stage_path(tmp_root: Path, rel: str) -> Path:
    """Return the staging path for one uploaded part, refusing name conflicts.

    SEC-6: one upload may contain both ``a`` (a file) and ``a/b/SKILL.md``
    (which requires ``a`` to be a directory).  Either order used to escape as a
    raw ``IsADirectoryError``/``NotADirectoryError`` — an HTTP 500 that also
    printed the exception to the server log — so both are reported here as the
    same actionable conflict: one name is both a file and a directory.
    """

    if "\x00" in rel:
        raise StoreError(f"uploaded file name contains a NUL byte: {rel!r}")
    parts = PurePosixPath(rel).parts
    if not parts:
        raise StoreError(f"uploaded file name is empty: {rel!r}")
    current = tmp_root
    for index, part in enumerate(parts):
        current = current / part
        if index == len(parts) - 1:
            if current.is_dir():
                raise StoreError(f"a file and a directory share the name {part!r}")
            return current
        if current.is_file():
            raise StoreError(f"a file and a directory share the name {part!r}")
    return current  # unreachable: the loop returns or raises on the last part


def parse_multipart(raw: bytes, boundary: str) -> list[dict]:
    """Parse the limited multipart form used by webkitdirectory uploads.

    Returns dictionaries containing ``name``, ``filename`` and byte
    ``content``.  Relative paths in ``filename`` are retained for the folder
    staging helper; the helper validates containment before writing anything.

    SEC-11: framing follows RFC 2046 — a delimiter is CRLF + ``--`` + boundary —
    and exactly the one CRLF belonging to the delimiter is removed.  The previous
    parser split on the bare delimiter anywhere in the bytes and then
    ``rstrip``-ed every trailing newline, so an uploaded document was stored
    altered: trailing blank lines disappeared from every upload, and content was
    silently cut at a literal ``--boundary`` inside it.  Filenames now come from
    the email parser rather than a regex, so an RFC 2231/5987 encoded name
    (non-ASCII or quoted, which is what browsers send in that case) arrives
    decoded instead of missing or truncated.
    """

    marker = b"--" + boundary.encode()
    chunks = _split_multipart(raw, marker)
    # The first split is the opening delimiter.  A second split is the closing
    # delimiter (or the next part), so a two-chunk body is an unterminated
    # single-part upload and still carries its one framing CRLF.
    has_delimiter = len(chunks) > 2
    parts = []
    for index, chunk in enumerate(chunks):
        if chunk.startswith(b"--"):
            break
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        elif chunk.startswith(b"\n"):
            chunk = chunk[1:]
        header_blob, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        # With a real delimiter the CRLF immediately before it was consumed by
        # _split_multipart.  Only a malformed/unterminated body leaves that
        # framing CRLF in the final chunk, so remove exactly that one there.
        if not has_delimiter and index == len(chunks) - 1:
            if content.endswith(b"\r\n"):
                content = content[:-2]
            elif content.endswith(b"\n"):
                content = content[:-1]
        headers = BytesParser(policy=_email_policy).parsebytes(header_blob + b"\r\n")
        disposition = headers.get("Content-Disposition", "")
        name = headers.get_param("name", header="content-disposition") or ""
        filename = headers.get_param("filename", header="content-disposition")
        if isinstance(filename, tuple):
            filename = collapse_rfc2231_value(filename)
        elif filename is not None:
            filename = unquote(filename)
        parts.append(
            {
                "name": name,
                "filename": filename,
                "content": content,
            }
        )
    return parts


def _split_multipart(raw: bytes, marker: bytes) -> list[bytes]:
    """Split a multipart body on exact RFC 2046 delimiter lines.

    The primary framing is CRLF + ``--`` + boundary, and the boundary must be
    followed by CRLF, LF, ``--`` (closing), or end-of-body.  Checking the suffix
    matters: ``CRLF--boundary-not-the-boundary`` is file content, not a part
    delimiter.  A body framed with bare LF remains an accepted fallback for
    hand-rolled local clients.
    """
    for line_break in (b"\r\n", b"\n"):
        framed = line_break + raw
        prefix = line_break + marker
        chunks: list[bytes] = []
        cursor = 0
        search = 0
        while True:
            index = framed.find(prefix, search)
            if index < 0:
                chunks.append(framed[cursor:])
                break
            after = index + len(prefix)
            suffix = framed[after:after + 2]
            if suffix not in (b"\r\n", b"\n", b"--", b""):
                # It is content, not framing.  Advance only the search cursor;
                # the output chunk must retain every byte since the last real
                # delimiter.
                search = index + len(line_break)
                continue
            chunks.append(framed[cursor:index])
            cursor = after
            search = after
        if len(chunks) > 1:
            return chunks
    return [raw]


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
            target = _stage_path(tmp_root, rel).resolve()
            if not _contained(target, tmp_root):
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(part["content"])
            except (OSError, ValueError) as exc:
                # Never surface a raw Python exception as the client's error
                # message (SEC-6); the OS's own wording is the useful part.
                reason = getattr(exc, "strerror", None) or "unsupported file name"
                raise StoreError(f"cannot stage uploaded file {rel!r}: {reason}") from exc
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


@contextmanager
def staged_single_skill(
    file_parts: list[dict],
    *,
    max_parts: int = MAX_UPLOAD_PARTS,
    max_bytes: int = MAX_UPLOAD_BYTES,
):
    """Yield one bounded uploaded skill root for review-first operations.

    Unlike ``upload_folder`` this helper never installs anything. It accepts a
    single directory tree, requires exactly one primary skill document, and
    removes the temporary bytes when the caller has copied them into its own
    durable review artifact.
    """
    if len(file_parts) > max_parts:
        raise StoreError(f"too many upload parts (max {max_parts})")
    if sum(len(part.get("content") or b"") for part in file_parts) > max_bytes:
        raise StoreError("upload too large")
    names = [part.get("filename") for part in file_parts if part.get("filename")]
    primary = [name for name in names if PurePosixPath(name).name in {"SKILL.md", "SKILL.md.disabled"}]
    if len(primary) != 1:
        raise StoreError("upload must contain exactly one SKILL.md or SKILL.md.disabled")
    root_name = PurePosixPath(primary[0]).parent
    if str(root_name) in ("", "."):
        root_name = PurePosixPath(".")
    if any(PurePosixPath(name).parts[:len(root_name.parts)] != root_name.parts for name in names):
        raise StoreError("upload must contain exactly one skill root")
    tmp_root = Path(tempfile.mkdtemp(prefix="skillsmgr-update-"))
    try:
        for part in file_parts:
            rel = part.get("filename")
            if not rel or rel.startswith("/") or "\\" in rel or ".." in PurePosixPath(rel).parts:
                raise StoreError("uploaded file path is unsafe")
            target = _stage_path(tmp_root, rel).resolve()
            if not _contained(target, tmp_root):
                raise StoreError("uploaded file path escapes its staging root")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(part.get("content") or b"")
        yield tmp_root if str(root_name) == "." else tmp_root / root_name
    except (OSError, ValueError) as exc:
        reason = getattr(exc, "strerror", None) or "unsupported file name"
        raise StoreError(f"cannot stage uploaded file: {reason}") from exc
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
