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
* ``description`` (required): non-empty, at most 1024 chars; warnings when
  it lacks use-context ("Use ... when ...") or contains vague filler.
* ``compatibility`` (optional): at most 500 chars.
* ``metadata`` (optional): a mapping of string to string.
* ``allowed-tools`` (optional): space-separated tool names.

Body warnings cover: empty body, >500 lines, >5000 tokens (progressive
disclosure), missing ``scripts/``/``references/``/``assets/`` files the
body mentions, and relative links that escape or miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from . import frontmatter
from .tokens import count_tokens

__all__ = [
    "Issue",
    "ValidationResult",
    "NAME_RE",
    "MAX_NAME",
    "MAX_DESCRIPTION",
    "MAX_COMPATIBILITY",
    "MAX_BODY_LINES",
    "MAX_BODY_TOKENS",
    "validate_skill_name",
    "description_score",
    "validate_text",
    "validate_skill",
]

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500
MAX_BODY_LINES = 500
MAX_BODY_TOKENS = 5000

_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_LAYOUT_DIRS = ("scripts", "references", "assets")
_MENTION_RE = re.compile(r"(?:scripts|references|assets)/[^\s)`\"']*")
_REFERENCE_TRAILING_PUNCTUATION = ".,;:!?"
_USE_CONTEXT_RE = re.compile(
    r"(?i)\buse[sd]?\b.{0,80}\bwhen\b|\bwhen you\b|^\s*use\b|^\s*when\b"
)
_FILLER_RE = re.compile(
    r"(?i)\b(various|miscellaneous|etc\.|stuff|things|"
    r"best practices|appropriately|generally)\b"
)


def validate_skill_name(name: str) -> str:
    """Validate and return a canonical skill name.

    Every caller that turns a user-controlled skill name into a filesystem
    path must use this primitive first.  Keeping the rule beside ``NAME_RE``
    prevents Store, scope, CLI, and REST entry points from drifting apart.
    """
    if not isinstance(name, str):
        raise ValueError("skill name must be a string")
    if not NAME_RE.fullmatch(name) or len(name) > MAX_NAME:
        raise ValueError(
            f"invalid skill name {name!r}: must match {NAME_RE.pattern} "
            f"(1-{MAX_NAME} chars)"
        )
    if name.casefold() in {
        "con",
        "nul",
        "aux",
        "prn",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }:
        raise ValueError(f"invalid skill name {name!r}: reserved Windows device name")
    return name


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
            if not NAME_RE.fullmatch(name):
                result.add(
                    "error",
                    "name must match lowercase pattern "
                    "'word1-word2' (letters, digits, hyphens)",
                    "name",
                )

    _check_scalar(result, data, "name", required=True, max_len=MAX_NAME)
    frontmatter_name = data.get("name")
    if (
        isinstance(frontmatter_name, str)
        and frontmatter_name
        and not NAME_RE.fullmatch(frontmatter_name)
    ):
        result.add(
            "error",
            "name must match lowercase pattern "
            "'word1-word2' (letters, digits, hyphens)",
            "name",
        )
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
    if isinstance(description, str) and description.strip():
        score = description_score(description)
        if not score["has_use_context"]:
            result.add(
                "warning",
                "description has no use-context "
                "('Use ... when ...'); agents may not trigger this skill",
                "description",
            )
        for hit in score["filler_hits"]:
            result.add(
                "warning",
                f"description contains vague filler {hit!r}; "
                "name the concrete tool, format, or condition instead",
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
    if body.strip():
        body_tokens, _method = count_tokens(body)
        if body_tokens > MAX_BODY_TOKENS:
            result.add(
                "warning",
                f"body is ~{body_tokens} tokens (over {MAX_BODY_TOKENS}); "
                "move reference material to references/ with "
                "when-to-load guidance (progressive disclosure)",
                "body",
            )

    if body and _heading_re(body) is False and len(body.splitlines()) < 5:
        pass  # short body with prose is fine

    if skill_dir is not None:
        _check_links(result, body, skill_dir)
        _check_layout(result, body, skill_dir)

    return result


def _heading_re(body: str) -> bool:
    return any(_HEADING_RE.match(ln) for ln in body.splitlines())


def description_score(description: str) -> dict:
    """Score a skill description for trigger quality (agentskills.io guide).

    Returns ``{"has_use_context": bool, "filler_hits": [...],
    "word_count": int}``. ``has_use_context`` is True when the text names
    when the agent should reach for the skill ("Use ... when ...").
    """
    text = description or ""
    return {
        "has_use_context": bool(_USE_CONTEXT_RE.search(text)),
        "filler_hits": sorted(set(_FILLER_RE.findall(text))),
        "word_count": len(text.split()),
    }


def _check_layout(result: ValidationResult, body: str, skill_dir: Path) -> None:
    """Warn when the body mentions scripts/references/assets files that miss.

    Progressive disclosure only works if the referenced file exists;
    dangling mentions waste a load attempt or confuse the agent.
    """
    try:
        root = skill_dir.resolve()
    except (OSError, RuntimeError, ValueError):
        return
    for mention in sorted(set(_MENTION_RE.findall(body))):
        if mention.split("/", 1)[0] not in _LAYOUT_DIRS:
            continue
        candidates = _reference_candidates(mention)
        if not candidates:
            continue
        exists = False
        suppress_missing = False
        for candidate in candidates:
            try:
                target = (root / candidate).resolve()
                try:
                    inside = target.is_relative_to(root)
                except AttributeError:
                    inside = str(target).startswith(str(root) + "/")
            except (OSError, RuntimeError, ValueError):
                if candidate == candidates[0]:
                    result.add(
                        "warning",
                        f"layout mention {mention!r} cannot be resolved",
                        "body",
                    )
                    suppress_missing = True
                    break
                continue
            if not inside:
                if candidate == candidates[0]:
                    suppress_missing = True
                    break  # _check_links already flags escapes
                continue
            try:
                if target.exists():
                    exists = True
                    break
            except OSError:
                pass
        if not exists and not suppress_missing:
            result.add(
                "warning",
                f"body mentions {mention!r} but it does not exist",
                "body",
            )


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
    root: Path | None = None
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
        candidates = _reference_candidates(target)
        if not candidates:
            continue
        if root is None:
            try:
                root = skill_dir.resolve()
            except (OSError, RuntimeError, ValueError):
                result.add("warning", "link targets cannot be resolved", "body")
                return
        exists = False
        suppress_missing = False
        for candidate in candidates:
            try:
                target_path = (root / candidate).resolve()
                try:
                    inside = target_path.is_relative_to(root)
                except AttributeError:
                    inside = str(target_path).startswith(str(root) + "/")
            except (OSError, RuntimeError, ValueError):
                if candidate == candidates[0]:
                    result.add(
                        "warning",
                        f"link target {target!r} cannot be resolved",
                        "body",
                    )
                    suppress_missing = True
                    break
                continue
            if not inside:
                if candidate == candidates[0]:
                    result.add(
                        "warning",
                        f"link target {target!r} escapes the skill directory",
                        "body",
                    )
                    suppress_missing = True
                    break
                continue
            try:
                if target_path.exists():
                    exists = True
                    break
            except OSError:
                pass
        if not exists and not suppress_missing:
            result.add(
                "warning",
                f"link target {target!r} does not exist in the skill directory",
                "body",
            )


def _reference_candidates(reference: str) -> tuple[str, ...]:
    """Return filesystem candidates for a Markdown/layout reference.

    URL query and fragment components are not part of the target path. Decode
    the remaining URL path before containment checks so encoded traversal is
    still rejected. A second candidate without sentence punctuation handles
    prose mentions such as ``scripts/run.py.`` without masking a real file
    whose name includes that punctuation.
    """
    path = reference.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return ()
    decoded = unquote(path)
    candidates = [decoded]
    stripped = decoded.rstrip(_REFERENCE_TRAILING_PUNCTUATION)
    if stripped and stripped != decoded:
        candidates.append(stripped)
    return tuple(candidates)


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
        from .loader import read_skill_text

        text, decode_error = read_skill_text(skill_file)
    except OSError as exc:
        result.add("error", f"cannot read SKILL.md: {exc}")
        return result
    if decode_error is not None:
        # Same message the loader marks rows with (issue #13): name the file,
        # the offending byte, and the recovery step instead of a bare codec
        # error.
        result.add("error", decode_error)
        return result

    result = validate_text(text, name=name, skill_dir=skill_dir)

    fm_name = result.data.get("name")
    # Use the physical basename so symlinked scope roots/skill aliases do not
    # create a false frontmatter mismatch.  A malformed symlink can make
    # ``resolve()`` raise instead of returning a basename; report that through
    # the validator contract rather than leaking the filesystem exception.
    try:
        directory_name = skill_dir.resolve().name
    except (OSError, RuntimeError, ValueError) as exc:
        result.add("error", f"cannot resolve skill directory: {exc}", "name")
        return result
    if isinstance(fm_name, str) and fm_name and fm_name != directory_name:
        result.add(
            "error",
            f"frontmatter name {fm_name!r} does not match directory name "
            f"{directory_name!r}",
            "name",
        )
    return result
