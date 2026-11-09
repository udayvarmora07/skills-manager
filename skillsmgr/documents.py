"""The on-disk shape of one skill: which document it holds and how it toggles.

A skill directory holds exactly one of ``SKILL.md`` (enabled) or
``SKILL.md.disabled`` (disabled).  Every module that reads, installs, toggles or
hashes a skill asks this module rather than spelling the two names itself, so
the layout and the one-document invariant have a single owner.
"""

from __future__ import annotations

from pathlib import Path

from .errors import SkillNotFound, StoreError

ACTIVE_DOCUMENT = "SKILL.md"
DISABLED_DOCUMENT = "SKILL.md.disabled"
DOCUMENT_NAMES = frozenset({ACTIVE_DOCUMENT, DISABLED_DOCUMENT})

__all__ = [
    "ACTIVE_DOCUMENT",
    "DISABLED_DOCUMENT",
    "DOCUMENT_NAMES",
    "conflicting_documents",
    "document_path",
    "document_text",
    "has_document",
    "read_skill_text",
    "read_skill_text_strict",
    "reject_conflicting_documents",
    "toggle_document",
]


def read_skill_text(path: Path) -> tuple[str, str | None]:
    """Read a skill document, tolerating invalid UTF-8 (issue #13).

    Returns ``(text, decode_error)``.  ``decode_error`` is ``None`` for a clean
    UTF-8 document; otherwise ``text`` keeps the document readable with U+FFFD
    replacement characters and the message names the file, the offending byte,
    and the fix.  Write paths must call :func:`read_skill_text_strict` instead,
    so lossy replacement characters can never be written back to disk.
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
    """Read a document that is about to be rewritten; undecodable fails closed."""
    text, decode_error = read_skill_text(path)
    if decode_error is not None:
        raise StoreError(f"cannot safely rewrite {subject}: {decode_error}")
    return text


def document_path(skill_dir: Path) -> Path | None:
    """The document a skill directory holds (enabled first), or ``None``."""
    for filename in (ACTIVE_DOCUMENT, DISABLED_DOCUMENT):
        candidate = skill_dir / filename
        if candidate.is_file():
            return candidate
    return None


def document_text(skill_dir: Path, *, lossy: bool = True) -> str:
    """The document's text, or ``""`` when absent or unreadable.

    Invalid UTF-8 is read with replacement characters, unless ``lossy`` is
    false, in which case such a document also reads as ``""``.
    """
    document = document_path(skill_dir)
    if document is None:
        return ""
    try:
        text, decode_error = read_skill_text(document)
    except OSError:
        return ""
    return "" if decode_error and not lossy else text


def has_document(skill_dir: Path) -> bool:
    """True when *skill_dir* holds either document."""
    return document_path(skill_dir) is not None


def conflicting_documents(skill_dir: Path) -> bool:
    """True when a skill directory holds *both* documents.

    With both present, exactly one is visible to reads while a toggle resolves
    the other as its source and renames it over the first, silently destroying
    one of the two -- with no snapshot taken.  Every entry point that toggles or
    installs a skill has to refuse this state instead of guessing.
    """
    return (skill_dir / ACTIVE_DOCUMENT).is_file() and (skill_dir / DISABLED_DOCUMENT).is_file()


def _where(scope_id: str | None) -> str:
    return f" in scope '{scope_id}'" if scope_id else ""


def reject_conflicting_documents(skill_dir: Path, name: str, *, scope_id: str | None = None) -> None:
    """Raise :class:`StoreError` unless *skill_dir* holds at most one document.

    ``scope_id`` names which agent root holds the ambiguous copy, since one
    skill name can exist in several.
    """
    if conflicting_documents(skill_dir):
        raise StoreError(
            f"skill '{name}' has both SKILL.md and SKILL.md.disabled{_where(scope_id)}; "
            "remove one of the two documents first"
        )


def toggle_document(skill_dir: Path, name: str, *, enable: bool, scope_id: str | None = None) -> None:
    """Rename the document between its enabled and disabled names.

    The caller holds the lock that makes the checks and the rename one step.
    """
    src = skill_dir / (DISABLED_DOCUMENT if enable else ACTIVE_DOCUMENT)
    dst = skill_dir / (ACTIVE_DOCUMENT if enable else DISABLED_DOCUMENT)
    where = _where(scope_id)
    if not src.is_file():
        if dst.is_file():
            raise StoreError(f"skill '{name}' is already {'enabled' if enable else 'disabled'}{where}")
        raise SkillNotFound(f"skill '{name}' is not installed{where}")
    reject_conflicting_documents(skill_dir, name, scope_id=scope_id)
    try:
        src.rename(dst)
    except FileNotFoundError:
        # STORE-11: the advisory lock excludes cooperating writers, but a change
        # made outside the tool can still move the document between the checks
        # and this rename.
        raise StoreError(
            f"skill '{name}' changed concurrently{where} (another process moved "
            f"{src.name}); retry the {'enable' if enable else 'disable'}"
        ) from None
