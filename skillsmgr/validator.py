"""Validation of SKILL.md files against the agentskills.io specification.

Validation produces *issues* split into two levels:

* ``error``   - the skill violates a hard spec rule and should not be
                used/installed as-is (missing/invalid name, missing
                description, unparseable frontmatter, ...).
* ``warning`` - the skill is usable but deviates from best practice
                (very short description, empty body, links to files
                that do not exist, ...).

Hard rules implemented (from the spec):

* ``name`` (required): 1-64 chars, ``^[a-z0-9]+(-[a-z0-9]+)*$``, and it
  must match the directory that holds the skill.
* ``description`` (required): non-empty, at most 1024 chars.
* ``compatibility`` (optional): at most 500 chars.
* ``metadata`` (optional): a mapping of string to string.
* ``allowed-tools`` (optional): space-separated tool names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter

__all__ = [
    "Issue",
    "ValidationResult",
    "NAME_RE",
    "MAX_NAME",
    "MAX_DESCRIPTION",
    "MAX_COMPATIBILITY",
    "MAX_BODY_LINES",
    "validate_text",
    "validate_skill",
]

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500
MAX_BODY_LINES = 500

_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s")


@dataclass
class Issue:
    """A single validation finding."""

    level: str
    message: str
    key: str = ""

    def __str__(self) -> str:
        prefix = "ERROR" if self.level == "error" else "WARN "
        if self.key:
            return f"{prefix} [{self.key}] {self.message}"
        return f"{prefix} {self.message}"


@dataclass
class ValidationResult:
    """Outcome of validating one skill."""

    issues: list[Issue] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    body: str = ""
    frontmatter_ok: bool = True

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def valid(self) -> bool:
        """True when there are no error-level issues."""
        return not self.errors

    def add(self, level: str, message: str, key: str = "") -> None:
        self.issues.append(Issue(level, message, key))


def validate_text(
    text: str, name: str | None = None, skill_dir: Path | None = None
) -> ValidationResult:
    """Validate frontmatter text *text* for a skill called *name*.

    When *skill_dir* is given, relative links in the body are checked
    against the real filesystem and missing targets produce warnings.
    """
    result = ValidationResult()

    try:
        data, body = frontmatter.parse_frontmatter(text)
    except frontmatter.FrontmatterError as exc:
        result.frontmatter_ok = False
        result.add("error", f"frontmatter is malformed: {exc}")
        return result
    result.data = data
    result.body = body

    if name is not None:
        if not isinstance(name, str) or not name:
            result.add("error", "skill name is empty", "name")
        else:
            if len(name) > MAX_NAME:
                result.add(
                    "error",
                    f"name must be at most {MAX_NAME} characters",
                    "name",
                )
            if not NAME_RE.match(name):
                result.add(
                    "error",
                    "name must match lowercase pattern "
                    "'word1-word2' (letters, digits, hyphens)",
                    "name",
                )

    _check_scalar(result, data, "name", required=True, max_len=MAX_NAME)
    _check_scalar(
        result, data, "description", required=True, max_len=MAX_DESCRIPTION
    )
    _check_scalar(
        result, data, "compatibility", required=False, max_len=MAX_COMPATIBILITY
    )

    if "license" in data and not isinstance(data["license"], str):
        result.add("error", "license must be a string", "license")

    metadata = data.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        result.add("error", "metadata must be a mapping of string to string", "metadata")
    else:
        for key, value in metadata.items():
            if not isinstance(value, str):
                result.add(
                    "warning",
                    f"metadata[{key!r}] should be a string, got {type(value).__name__}",
                    "metadata",
                )

    allowed = data.get("allowed-tools")
    if allowed is not None and not isinstance(allowed, str):
        result.add("error", "allowed-tools must be a space-separated string", "allowed-tools")

    description = data.get("description", "")
    if isinstance(description, str) and len(description) < 20:
        result.add(
            "warning",
            "description is very short; expand it to a full sentence",
            "description",
        )

    if not body.strip():
        result.add("warning", "skill body is empty (no instructions)", "body")
    elif len(body.splitlines()) > MAX_BODY_LINES:
        result.add(
            "warning",
            f"body exceeds {MAX_BODY_LINES} lines; consider splitting the skill",
            "body",
        )

    if body and _heading_re(body) is False and len(body.splitlines()) < 5:
        pass  # short body with prose is fine

    if skill_dir is not None:
        _check_links(result, body, skill_dir)

    return result


def _heading_re(body: str) -> bool:
    return any(_HEADING_RE.match(ln) for ln in body.splitlines())


def _check_scalar(
    result: ValidationResult,
    data: dict,
    key: str,
    *,
    required: bool,
    max_len: int,
) -> None:
    value = data.get(key)
    if value is None:
        if required:
            result.add("error", f"{key!r} is required", key)
        return
    if not isinstance(value, str):
        result.add("error", f"{key!r} must be a string", key)
        return
    if not value.strip():
        if required:
            result.add("error", f"{key!r} must not be empty", key)
        return
    if len(value) > max_len:
        result.add(
            "error",
            f"{key!r} must be at most {max_len} characters "
            f"(found {len(value)})",
            key,
        )


def _check_links(result: ValidationResult, body: str, skill_dir: Path) -> None:
    """Warn about relative links whose target file does not exist."""
    seen: set[str] = set()
    for match in _LINK_RE.finditer(body):
        target = match.group(1).strip()
        if target in seen:
            continue
        seen.add(target)
        if (
            not target
            or target.startswith(("#", "http://", "https://", "mailto:"))
            or "://" in target
        ):
            continue
        if target.startswith("<") and target.endswith(">"):
            continue
        target_path = (skill_dir / target).resolve()
        try:
            inside = target_path.is_relative_to(skill_dir.resolve())
        except AttributeError:
            inside = str(target_path).startswith(str(skill_dir.resolve()) + "/")
        if not inside:
            result.add(
                "warning",
                f"link target {target!r} escapes the skill directory",
                "body",
            )
            continue
        try:
            exists = target_path.exists()
        except OSError:
            exists = False
        if not exists:
            result.add(
                "warning",
                f"link target {target!r} does not exist in the skill directory",
                "body",
            )


def validate_skill(name: str, skill_dir: Path) -> ValidationResult:
    """Validate the SKILL.md inside *skill_dir*.

    Adds filesystem-level checks on top of :func:`validate_text`:

    * the directory must contain a ``SKILL.md`` (error if missing),
    * the frontmatter ``name`` must equal the directory name (error).
    """
    result = ValidationResult()
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        disabled_file = skill_dir / "SKILL.md.disabled"
        if disabled_file.is_file():
            skill_file = disabled_file
        else:
            result.add("error", f"missing SKILL.md in {skill_dir}")
            return result

    try:
        text = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        result.add("error", f"cannot read SKILL.md: {exc}")
        return result

    result = validate_text(text, name=name, skill_dir=skill_dir)

    fm_name = result.data.get("name")
    if isinstance(fm_name, str) and fm_name and fm_name != name:
        result.add(
            "error",
            f"frontmatter name {fm_name!r} does not match directory name {name!r}",
            "name",
        )
    return result
