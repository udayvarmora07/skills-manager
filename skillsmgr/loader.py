"""Shared SKILL.md loader and directory scanner.

Single implementation used by Store (global DB) and scopes (external agent
dirs). Keeps FS parsing consistent; FS stays source of truth.
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import FrontmatterError, parse_frontmatter
from .observations import document_observations
from .paths import contained_path
from .store import SkillNotFound, StoreError
from .tokens import estimate as _estimate_tokens


def read_skill_text(path: Path) -> tuple[str, str | None]:
    """Read a skill document, tolerating invalid UTF-8 (issue #13).

    Returns ``(text, decode_error)``.  ``decode_error`` is ``None`` for a clean
    UTF-8 document; otherwise ``text`` keeps the document readable with U+FFFD
    replacement characters and the message names the file, the offending byte,
    and the fix.  Read/report paths mark the row ``malformed`` with that
    message; write paths must call :func:`read_skill_text_strict` instead, so
    lossy replacement characters can never be written back to disk.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return raw.decode("utf-8", errors="replace"), (
            f"{path} is not valid UTF-8 (byte 0x{raw[exc.start]:02x} at offset "
            f"{exc.start}); re-save it as UTF-8"
        )


def read_skill_text_strict(path: Path, *, subject: str) -> str:
    """Read a skill document that is about to be rewritten.

    Undecodable input fails closed as a clean :class:`StoreError` naming
    ``subject``; a caller must never rewrite a document it could only read
    lossily.
    """
    text, decode_error = read_skill_text(path)
    if decode_error is not None:
        raise StoreError(f"cannot safely rewrite {subject}: {decode_error}")
    return text


def _coerce_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def load_skill(skill_dir: Path) -> dict:
    """Load one skill directory (SKILL.md or SKILL.md.disabled).

    An undecodable document never raises: it is reported as a ``malformed``
    row carrying ``decode_error`` so callers can surface drift instead of
    failing with a raw ``UnicodeDecodeError`` (issue #13).
    """
    text = None
    disabled = 0
    decode_error = None
    if (skill_dir / "SKILL.md").is_file():
        text, decode_error = read_skill_text(skill_dir / "SKILL.md")
        disabled = 0
    elif (skill_dir / "SKILL.md.disabled").is_file():
        text, decode_error = read_skill_text(skill_dir / "SKILL.md.disabled")
        disabled = 1
    if text is None:
        raise SkillNotFound(f"skill '{skill_dir.name}' has no SKILL.md (or SKILL.md.disabled)")
    malformed = decode_error is not None
    try:
        data, body = parse_frontmatter(text)
    except FrontmatterError:
        data, body = {}, text
        malformed = True
    metadata = data.get("metadata")
    category = "uncategorized"
    if isinstance(metadata, dict) and isinstance(metadata.get("category"), str):
        category = metadata["category"] or "uncategorized"
    raw_text = text or ""
    tok = _estimate_tokens(raw_text)
    record = {
        "name": skill_dir.name,
        "disabled": disabled,
        "malformed": malformed,
        "decode_error": decode_error,
        "description": _coerce_str(data.get("description")),
        "body": body,
        "category": category,
        "license": data.get("license") if data.get("license") is not None else None,
        "version": _coerce_str(data.get("version")) if data.get("version") else None,
        "tokens": tok["tokens"],
        "tokens_method": tok["method"],
        "tokens_pct": tok["pct_window"],
        "chars": tok["chars"],
    }
    record.update(document_observations(skill_dir, raw_text, data))
    return record


def scan_dir(root: Path, *, recursive: bool = False) -> list[dict]:
    """Scan a skill root, optionally walking nested skill directories.

    Recursive discovery is opt-in because consumers differ: some treat a root
    as a flat directory while Cursor/OpenCode-style project roots can organize
    skills below category or nested project directories.

    A directory whose document is unreadable is *kept* and marked ``malformed``
    (issue #13): the filesystem is the source of truth, so a skill that exists
    on disk must stay visible to ``doctor``/``resync`` as drift rather than
    silently vanish from the scan.
    """
    entries: list[dict] = []
    if not root.is_dir():
        return entries
    if recursive:
        candidates = sorted(
            {path.parent for path in root.rglob("SKILL.md")}
            | {path.parent for path in root.rglob("SKILL.md.disabled")}
        )
    else:
        candidates = sorted(path for path in root.iterdir() if path.is_dir())
    for child in candidates:
        try:
            relative = child.relative_to(root)
            child = contained_path(root, *relative.parts)
        except (ValueError, OSError):
            continue
        try:
            entry = load_skill(child)
            if recursive:
                entry["path"] = str(child)
            entries.append(entry)
        except SkillNotFound:
            continue
    return sorted(entries, key=lambda item: (item["name"].lower(), item.get("path", "")))
