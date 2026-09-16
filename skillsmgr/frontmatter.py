"""Minimal, dependency-free YAML frontmatter parser and dumper.

Handles the YAML subset that appears in SKILL.md frontmatter (and the
vast majority of real-world frontmatter):

  * block mappings with string keys (``key: value``)
  * block lists (``- item``) including lists of mappings and nested lists
  * nested mappings by indentation
  * flow collections (``[a, b]``, ``{k: v}``)
  * block scalars ``|`` and ``>`` with ``-``/``+`` chomping and an
    optional indentation indicator (``|2-``)
  * single- and double-quoted scalars with escapes
  * inline comments

Coercion policy (string-oriented, round-trip friendly):
  * true/false/yes/no/on/off -> bool
  * null/~ -> None
  * everything else, including numbers, stays a string

The dumper quotes or switches to block scalars whenever a plain scalar
would change meaning, so ``parse_frontmatter(dump_frontmatter(data))``
returns an equivalent structure.
"""

from __future__ import annotations

import re

__all__ = ["FrontmatterError", "parse_frontmatter", "dump_frontmatter"]

_DOC_MARKER = re.compile(r"^---(?:\s+#.*)?$")
# ``key:`` optionally followed by a block-scalar header (``|``/``>`` plus
# optional indentation/chomping indicators) and an optional trailing comment.
_BLOCK_SCALAR_KEY = re.compile(r"^[^#]*:[ \t]+[|>][0-9+-]*[ \t]*(?:#.*)?$")
#: A '#' that the parser reads as the start of an inline comment (FM-8).
_INLINE_COMMENT_RE = re.compile(r"(?:^|[ \t])#")
#: A ':' that the parser reads as a mapping-key separator -- followed by
#: whitespace or end of line (see ``_split_key``).  The dumper used to quote
#: only for ": ", so a value containing ":\t" was re-parsed as a mapping.
_KEY_SEPARATOR_RE = re.compile(r":(?:[ \t]|$)")

MAX_DOCUMENT_CHARS = 512 * 1024
MAX_KEYS = 200
MAX_COLLECTION_ITEMS = 200
MAX_SCALAR_LENGTH = 16 * 1024
MAX_NESTING_DEPTH = 64


class FrontmatterError(ValueError):
    """Raised when frontmatter text cannot be parsed."""


def _fold_separator(previous: str, current: str) -> str:
    """Return the YAML folded-scalar separator for adjacent content lines."""
    if previous.startswith((" ", "\t")) or current.startswith((" ", "\t")):
        return "\n"
    return " "


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

_TRUE_WORDS = {"true", "yes", "on"}
_FALSE_WORDS = {"false", "no", "off"}
_NULL_WORDS = {"null", "~"}


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _block_scalar_content_indent(header: str, parent_indent: int) -> int:
    """Indentation of a block scalar's content, per its header.

    YAML resolves an explicit indentation indicator relative to the parent
    node; without one the content indent is not known until the first
    non-blank content line is seen (signalled by ``-1``).
    """
    info = header[1:].strip()
    if info and info[0] in "123456789":
        return parent_indent + int(info[0])
    return -1


def _find_closing_marker(lines: list[str]) -> int | None:
    """Return the index of the frontmatter block's closing ``---`` marker.

    The split happens *before* YAML parsing, so the scan has to know about
    block scalars: a line like ``---`` inside a ``|``/``>`` value is content,
    not a document marker.  Treating it as a marker truncates the value
    silently *and* promotes the rest of the value into the document body --
    which every write path then persists.  A bare ``---`` at column zero
    still closes the block, which is what the emitted documents rely on.
    """
    i = 1
    n = len(lines)
    while i < n:
        raw = lines[i]
        indent = _indent_of(raw)
        if _DOC_MARKER.match(raw.strip()):
            if indent == 0:
                return i
            i += 1
            continue
        if _BLOCK_SCALAR_KEY.match(raw.rstrip()):
            content_indent = _block_scalar_content_indent(
                raw.strip().split(":", 1)[1].lstrip(), indent
            )
            i += 1
            while i < n:
                body = lines[i]
                if body.strip() == "":
                    i += 1
                    continue
                body_indent = _indent_of(body)
                if body_indent <= indent:
                    break
                if content_indent < 0:
                    content_indent = body_indent
                if body_indent < content_indent:
                    break
                i += 1
            continue
        i += 1
    return None


def _normalize_crlf(text: str) -> str:
    """Normalize a document that uses CRLF line endings throughout.

    FM-7: the old code did ``rstrip("\\r")`` on every line, which cannot tell a
    CRLF terminator from a CR that is genuine *content* -- so a value holding
    ``line1\\r\\nline2`` lost its CR on the next round trip.  Only a document
    whose every line terminator is CRLF is treated as a CRLF document; a lone
    CR inside a line (or a mixed file) is left alone as content.
    """
    lines = text.split("\n")
    body = lines[:-1] if lines and lines[-1] == "" else lines
    if body and all(line.endswith("\r") for line in body):
        return text.replace("\r\n", "\n")
    return text


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split *text* into ``(frontmatter_dict, body)``.

    When the document has no leading ``---`` marker, ``({}, text)`` is
    returned.  When a marker exists but no closing marker is found, a
    ``FrontmatterError`` is raised.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    text = _normalize_crlf(text)
    if len(text) > MAX_DOCUMENT_CHARS:
        raise FrontmatterError(
            f"frontmatter document is too large (max {MAX_DOCUMENT_CHARS} characters)"
        )
    lines = text.split("\n")
    if not lines or not _DOC_MARKER.match(lines[0].strip()):
        return {}, text
    end = _find_closing_marker(lines)
    if end is None:
        raise FrontmatterError(
            "frontmatter block is missing its closing '---' marker"
        )
    yaml_lines = lines[1:end]
    if sum(len(line) + 1 for line in yaml_lines) > MAX_DOCUMENT_CHARS:
        raise FrontmatterError(
            f"frontmatter block is too large (max {MAX_DOCUMENT_CHARS} characters)"
        )
    body = "\n".join(lines[end + 1 :])
    data = _Parser(yaml_lines).parse_document()
    return data, body


class _Parser:
    """Line-based recursive descent parser for the YAML subset."""

    def __init__(self, lines: list[str]):
        self.lines = lines
        self.n = len(lines)
        self.keys_seen = 0
        self.collection_items = 0

    def _check_depth(self, depth: int) -> None:
        if depth > MAX_NESTING_DEPTH:
            raise FrontmatterError(
                f"frontmatter nesting is too deep (max {MAX_NESTING_DEPTH} levels)"
            )

    def _check_key(self) -> None:
        self.keys_seen += 1
        if self.keys_seen > MAX_KEYS:
            raise FrontmatterError(f"frontmatter has too many keys (max {MAX_KEYS})")

    def _check_item(self) -> None:
        self.collection_items += 1
        if self.collection_items > MAX_COLLECTION_ITEMS:
            raise FrontmatterError(
                f"frontmatter has too many collection items (max {MAX_COLLECTION_ITEMS})"
            )

    @staticmethod
    def _check_scalar(value: str) -> str:
        if len(value) > MAX_SCALAR_LENGTH:
            raise FrontmatterError(
                f"frontmatter scalar is too long (max {MAX_SCALAR_LENGTH} characters)"
            )
        _reject_surrogates(value)
        return value

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    @staticmethod
    def _is_blank(line: str) -> bool:
        return line.strip() == ""

    @staticmethod
    def _is_comment(line: str) -> bool:
        return line.lstrip().startswith("#")

    @staticmethod
    def _is_list_marker(stripped: str) -> bool:
        return stripped == "-" or stripped.startswith("- ")

    def _skip_noise(self, idx: int) -> int:
        """Advance past blank and comment-only lines."""
        while idx < self.n:
            line = self.lines[idx]
            if self._is_blank(line) or self._is_comment(line):
                idx += 1
            else:
                break
        return idx

    # -- document entry point ---------------------------------------------

    def parse_document(self) -> dict:
        idx = self._skip_noise(0)
        if idx >= self.n:
            return {}
        stripped = self.lines[idx].strip()
        if self._is_list_marker(stripped):
            # FM-2: this parser's contract is ``-> dict``.  Returning the list
            # made every consumer die with a raw AttributeError (``.get`` on a
            # list) from doctor/resync/db_rebuild/validate/scan.  A document
            # whose frontmatter root is a sequence is malformed here.
            raise FrontmatterError(
                "frontmatter root must be a mapping of keys, not a sequence"
            )
        data, _ = self._parse_mapping(idx, 0, 0)
        return data

    # -- mappings ----------------------------------------------------------

    def _parse_mapping(self, idx: int, indent: int, depth: int) -> tuple[dict, int]:
        self._check_depth(depth)
        data: dict = {}
        while True:
            idx = self._skip_noise(idx)
            if idx >= self.n:
                break
            line = self.lines[idx]
            ind = self._indent(line)
            if ind < indent:
                break
            if ind > indent:
                raise FrontmatterError(
                    f"line {idx + 1}: unexpected indentation: {line!r}"
                )
            stripped = line.strip()
            if self._is_list_marker(stripped):
                raise FrontmatterError(
                    f"line {idx + 1}: expected mapping key, found list item: {line!r}"
                )
            key, rest, ok = self._split_key(stripped)
            if not ok:
                raise FrontmatterError(
                    f"line {idx + 1}: malformed mapping line (expected 'key: value'): {line!r}"
                )
            idx += 1
            self._check_key()
            value, idx = self._parse_value(idx, indent, rest, depth)
            _store_mapping_value(data, key, value, idx)
        return data, idx

    def _parse_inline_mapping(
        self, idx: int, indent: int, first_rest: str, depth: int
    ) -> tuple[dict, int]:
        """Parse a mapping whose first key sits after ``- `` on one line.

        Continuation keys are expected at *indent* (the logical indentation
        of the first key, conventionally dash-indent + 2).
        """
        data: dict = {}
        key, rest, ok = self._split_key(first_rest)
        if not ok:
            raise FrontmatterError(
                f"line {idx + 1}: malformed list-item mapping: {first_rest!r}"
            )
        self._check_depth(depth)
        self._check_key()
        value, idx = self._parse_value(idx, indent, rest, depth)
        _store_mapping_value(data, key, value, idx)
        while True:
            idx = self._skip_noise(idx)
            if idx >= self.n:
                break
            line = self.lines[idx]
            ind = self._indent(line)
            if ind < indent:
                break
            if ind > indent:
                raise FrontmatterError(
                    f"line {idx + 1}: unexpected indentation: {line!r}"
                )
            stripped = line.strip()
            if self._is_list_marker(stripped):
                raise FrontmatterError(
                    f"line {idx + 1}: expected mapping key, found list item: {line!r}"
                )
            key, rest, ok = self._split_key(stripped)
            if not ok:
                raise FrontmatterError(
                    f"line {idx + 1}: malformed mapping line: {line!r}"
                )
            idx += 1
            self._check_key()
            value, idx = self._parse_value(idx, indent, rest, depth)
            _store_mapping_value(data, key, value, idx)
        return data, idx

    # -- block lists -------------------------------------------------------

    def _parse_block_list(self, idx: int, indent: int, depth: int = 0) -> tuple[list, int]:
        self._check_depth(depth)
        items = []
        while True:
            idx = self._skip_noise(idx)
            if idx >= self.n:
                break
            line = self.lines[idx]
            ind = self._indent(line)
            if ind < indent:
                break
            if ind > indent:
                raise FrontmatterError(
                    f"line {idx + 1}: unexpected indentation: {line!r}"
                )
            stripped = line.strip()
            if not self._is_list_marker(stripped):
                break
            rest = stripped[1:].lstrip()
            idx += 1
            self._check_item()
            item, idx = self._parse_list_item(idx, indent, rest, depth)
            items.append(item)
        return items, idx

    def _parse_list_item(
        self, idx: int, indent: int, rest: str, depth: int
    ) -> tuple[object, int]:
        """Parse the value of one ``- `` sequence element."""
        if rest == "":
            return self._parse_nested(idx, indent, depth + 1)
        if rest[0] in "|>":
            # A block scalar as a bare sequence element (``- |``): without this
            # the marker was read as the plain scalar "|" and the scalar's own
            # lines then tripped the indentation guard, so a value the dumper
            # emitted could not be read back at all.
            return self._parse_block_scalar(
                idx, indent, self._strip_inline_comment(rest)
            )
        if self._looks_like_key(rest):
            return self._parse_inline_mapping(idx, indent + 2, rest, depth + 1)
        return self._parse_inline(rest), idx

    # -- values ------------------------------------------------------------

    def _parse_value(
        self, idx: int, parent_indent: int, rest: str, depth: int
    ) -> tuple[object, int]:
        if rest == "":
            nested = self._skip_noise(idx)
            if nested < self.n and self._indent(self.lines[nested]) > parent_indent:
                return self._parse_nested(nested, parent_indent, depth + 1)
            return None, idx
        if rest[0] in "|>":
            header = self._strip_inline_comment(rest)
            value, idx = self._parse_block_scalar(idx, parent_indent, header)
            return value, idx
        return self._parse_inline(rest), idx

    def _parse_nested(self, idx: int, parent_indent: int, depth: int) -> tuple[object, int]:
        self._check_depth(depth)
        line = self.lines[idx]
        ind = self._indent(line)
        if ind <= parent_indent:
            return None, idx
        if self._is_list_marker(line.strip()):
            return self._parse_block_list(idx, ind, depth)
        return self._parse_mapping(idx, ind, depth)

    # -- block scalars -----------------------------------------------------

    def _parse_block_scalar(
        self, idx: int, parent_indent: int, header: str
    ) -> tuple[str, int]:
        style = header[0]
        info = header[1:].strip()
        chomp = "clip"
        explicit_indent: int | None = None
        if info:
            m = re.match(r"^([1-9])(.*)$", info)
            if m:
                explicit_indent = int(m.group(1))
                info = m.group(2)
            if info:
                first = info[0]
                if first == "-":
                    chomp = "strip"
                elif first == "+":
                    chomp = "keep"

        raw: list[str] = []
        i = idx
        while i < self.n:
            line = self.lines[i]
            if self._is_blank(line):
                # FM-6: a whitespace-only line is content, not a blank line --
                # collapsing it to "" silently ate the whitespace.  Only a
                # genuinely empty line becomes the empty string.
                raw.append("" if line == "" else line)
                i += 1
                continue
            if self._indent(line) <= parent_indent:
                break
            raw.append(line)
            i += 1

        if explicit_indent is not None:
            # FM-14: an indentation indicator is *parent-relative*, not absolute.
            content_indent = parent_indent + explicit_indent
        else:
            non_blank = [self._indent(l) for l in raw if l.strip() != ""]
            content_indent = min(non_blank) if non_blank else parent_indent + 1

        parts = []
        for line in raw:
            if line == "":
                parts.append("")
            else:
                parts.append(line[content_indent:] if len(line) >= content_indent else "")

        if style == "|":
            result = "\n".join(parts)
        else:  # folded ">"
            result = self._fold(parts)

        # FM-12: chomping follows YAML.  ``joined`` has no trailing newline of
        # its own, so the number of trailing empty lines is exactly the number
        # of trailing newlines the content carries beyond the final line's
        # terminator.  The old code added a newline only when one was missing,
        # so clip kept too many trailing blank lines and keep dropped one.
        if chomp == "strip":
            result = result.rstrip("\n")
        elif chomp == "clip":
            stripped = result.rstrip("\n")
            result = stripped + "\n" if stripped else ""
        else:  # keep
            result = result + "\n" if raw else ""
        return self._check_scalar(result), i

    @staticmethod
    def _fold(parts: list[str]) -> str:
        """Apply YAML folding while preserving more-indented lines.

        A newline between ordinary content lines folds to a space. A line
        that retains leading whitespace after the common block indentation is
        more-indented content, so YAML keeps the line break around it.
        """
        result = ""
        for index, part in enumerate(parts):
            if part == "":
                result += "\n"
                continue
            if index > 0 and parts[index - 1] != "":
                result += _fold_separator(parts[index - 1], part)
            result += part
        return result
    # -- inline scalars ----------------------------------------------------

    def _parse_inline(self, s: str) -> object:
        s = self._strip_inline_comment(s).strip()
        if s == "":
            return None
        if s[0] == "'":
            return self._parse_single_quoted(s)
        if s[0] == '"':
            return self._parse_double_quoted(s)
        if s[0] == "[":
            self._check_flow_depth(s)
            return self._parse_flow_list(s)
        if s[0] == "{":
            self._check_flow_depth(s)
            return self._parse_flow_map(s)
        return self._coerce(s)

    @staticmethod
    def _check_flow_depth(s: str) -> None:
        depth = 0
        maximum = 0
        for char in s:
            if char in "[{":
                depth += 1
                maximum = max(maximum, depth)
            elif char in "]}":
                depth -= 1
        if maximum > MAX_NESTING_DEPTH:
            raise FrontmatterError(
                f"frontmatter nesting is too deep (max {MAX_NESTING_DEPTH} levels)"
            )

    def _coerce(self, s: str) -> object:
        low = s.lower()
        if low in _TRUE_WORDS:
            return True
        if low in _FALSE_WORDS:
            return False
        if low in _NULL_WORDS:
            return None
        return self._check_scalar(s)

    # -- flow collections --------------------------------------------------

    def _find_flow_end(self, s: str, i: int, close_ch: str) -> int:
        depth = 1
        quote = None
        n = len(s)
        while i < n:
            c = s[i]
            if quote:
                if quote == "'":
                    if c == "'":
                        if i + 1 < n and s[i + 1] == "'":
                            i += 2
                            continue
                        quote = None
                else:
                    if c == "\\":
                        i += 2
                        continue
                    if c == '"':
                        quote = None
            else:
                if c in "'\"":
                    quote = c
                elif c in "[{":
                    depth += 1
                elif c in "]}":
                    depth -= 1
                    if depth == 0:
                        return i
            i += 1
        raise FrontmatterError(f"unterminated flow collection: {s!r}")

    def _split_flow(self, inner: str) -> list[str]:
        parts = []
        quote = None
        depth = 0
        current: list[str] = []
        i = 0
        n = len(inner)
        while i < n:
            c = inner[i]
            if quote:
                current.append(c)
                if quote == "'":
                    if c == "'":
                        if i + 1 < n and inner[i + 1] == "'":
                            current.append(inner[i + 1])
                            i += 2
                            continue
                        quote = None
                else:
                    if c == "\\":
                        if i + 1 < n:
                            current.append(inner[i + 1])
                            i += 2
                            continue
                    if c == '"':
                        quote = None
            else:
                if c in "'\"":
                    quote = c
                    current.append(c)
                elif c in "[{":
                    depth += 1
                    current.append(c)
                elif c in "]}":
                    depth -= 1
                    current.append(c)
                elif c == "," and depth == 0:
                    parts.append("".join(current))
                    current = []
                else:
                    current.append(c)
            i += 1
        if quote:
            raise FrontmatterError("unterminated quote in flow collection")
        parts.append("".join(current))
        return parts

    def _parse_flow_list(self, s: str) -> list:
        end = self._find_flow_end(s, 1, "]")
        trailing = s[end + 1 :].strip()
        if trailing:
            raise FrontmatterError(
                f"unexpected content after ']': {s!r}"
            )
        out = []
        for part in self._split_flow(s[1:end]):
            p = part.strip()
            if p:
                self._check_item()
                out.append(self._parse_inline(p))
        return out

    def _parse_flow_map(self, s: str) -> dict:
        end = self._find_flow_end(s, 1, "}")
        trailing = s[end + 1 :].strip()
        if trailing:
            raise FrontmatterError(f"unexpected content after '}}': {s!r}")
        data: dict = {}
        for part in self._split_flow(s[1:end]):
            p = part.strip()
            if not p:
                continue
            key, rest, ok = self._split_key(p)
            if not ok:
                raise FrontmatterError(f"malformed flow mapping entry: {p!r}")
            self._check_key()
            _store_flow_value(data, key, rest, self._parse_inline)
        return data

    # -- quoted scalars ----------------------------------------------------

    def _parse_single_quoted(self, s: str) -> str:
        result = []
        i = 1
        n = len(s)
        while i < n:
            c = s[i]
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    result.append("'")
                    i += 2
                    continue
                trailing = s[i + 1 :].strip()
                if trailing:
                    raise FrontmatterError(
                        f"unexpected content after quoted string: {s!r}"
                    )
                return self._check_scalar("".join(result))
            result.append(c)
            i += 1
        raise FrontmatterError(f"unterminated single-quoted string: {s!r}")

    _ESCAPES = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        "0": "\0",
        "a": "\a",
        "b": "\b",
        "f": "\f",
        "v": "\v",
        "e": "\x1b",
        '"': '"',
        "\\": "\\",
        "/": "/",
        " ": " ",
        "N": "\u0085",
        "_": "\u00a0",
        "L": "\u2028",
        "P": "\u2029",
    }

    def _parse_double_quoted(self, s: str) -> str:
        result = []
        i = 1
        n = len(s)
        while i < n:
            c = s[i]
            if c == "\\":
                if i + 1 >= n:
                    raise FrontmatterError(
                        f"trailing backslash in double-quoted string: {s!r}"
                    )
                e = s[i + 1]
                if e in "xUu" and i + 2 < n:
                    if e == "x":
                        width, digits = 2, s[i + 2 : i + 4]
                    elif e == "u":
                        width, digits = 4, s[i + 2 : i + 6]
                    else:
                        width, digits = 8, s[i + 2 : i + 10]
                    if len(digits) == width and _is_hex(digits):
                        result.append(_decode_escape(digits))
                        i += 2 + width
                        continue
                if e in self._ESCAPES:
                    result.append(self._ESCAPES[e])
                    i += 2
                else:
                    result.append(e)
                    i += 2
            elif c == '"':
                trailing = s[i + 1 :].strip()
                if trailing:
                    raise FrontmatterError(
                        f"unexpected content after quoted string: {s!r}"
                    )
                return self._check_scalar("".join(result))
            else:
                result.append(c)
                i += 1
        raise FrontmatterError(f"unterminated double-quoted string: {s!r}")

    # -- keys and comments -------------------------------------------------

    def _split_key(self, s: str) -> tuple[str | None, str, bool]:
        """Split ``key: rest`` at the first top-level colon followed by
        whitespace or end of line."""
        quote = None
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if quote:
                if quote == "'":
                    if c == "'":
                        if i + 1 < n and s[i + 1] == "'":
                            i += 2
                            continue
                        quote = None
                else:
                    if c == "\\":
                        i += 2
                        continue
                    if c == '"':
                        quote = None
            else:
                if c in "'\"":
                    quote = c
                elif c == ":":
                    if i + 1 >= n or s[i + 1] in " \t":
                        return self._clean_key(s[:i]), s[i + 1 :].lstrip(), True
            i += 1
        return None, None, False

    def _looks_like_key(self, s: str) -> bool:
        _, _, ok = self._split_key(s)
        return ok

    def _clean_key(self, key: str) -> str:
        key = key.strip()
        if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
            try:
                if key[0] == "'":
                    return self._parse_single_quoted(key)
                return self._parse_double_quoted(key)
            except FrontmatterError:
                return key[1:-1]
        return key

    @staticmethod
    def _strip_inline_comment(s: str) -> str:
        """Remove a trailing ``#`` comment, respecting quotes."""
        out = []
        quote = None
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if quote:
                out.append(c)
                if quote == "'":
                    if c == "'":
                        if i + 1 < n and s[i + 1] == "'":
                            out.append(s[i + 1])
                            i += 1
                        else:
                            quote = None
                else:
                    if c == "\\":
                        if i + 1 < n:
                            out.append(s[i + 1])
                            i += 1
                    elif c == '"':
                        quote = None
            else:
                if c in "'\"":
                    quote = c
                    out.append(c)
                elif c == "#" and (i == 0 or s[i - 1] in " \t"):
                    break
                else:
                    out.append(c)
            i += 1
        return "".join(out)


def _store_mapping_value(data: dict, key, value, idx: int) -> None:
    """Store one block-mapping entry, rejecting duplicate keys loudly."""
    if key in data:
        raise FrontmatterError(
            f"line {idx + 1}: duplicate frontmatter key: {key!r}"
        )
    data[key] = value


def _store_flow_value(data: dict, key, rest: str, parse_inline) -> None:
    """Store one flow-map entry parsed from its inline text."""
    if key in data:
        raise FrontmatterError(f"duplicate frontmatter key: {key!r}")
    data[key] = parse_inline(rest) if rest != "" else None

def _is_hex(s: str) -> bool:
    return all(c in "0123456789abcdefABCDEF" for c in s)


def _reject_surrogates(value: str) -> None:
    """Reject lone surrogates that only fail later, at write time.

    FM-4: `\\uD800` parsed cleanly and passed validation, and then *every*
    write path died with a raw UnicodeEncodeError.  The value is not
    representable in UTF-8, so it has to be refused where it enters.
    """
    for char in value:
        if 0xD800 <= ord(char) <= 0xDFFF:
            raise FrontmatterError(
                f"frontmatter contains an unpaired surrogate (U+{ord(char):04X}), "
                "which cannot be written as UTF-8"
            )


def _decode_escape(digits: str) -> str:
    """Decode one ``\\x``/``\\u``/``\\U`` escape, rejecting invalid ranges.

    FM-3: ``chr()`` raised a raw ValueError for out-of-range values and
    ``\\uD800`` produced a string every write path then failed to encode.
    Both bypassed every FrontmatterError guard, so they are translated here.
    """
    code = int(digits, 16)
    if 0xD800 <= code <= 0xDFFF:
        raise FrontmatterError(
            f"escape U+{code:04X} is an unpaired surrogate and cannot be written "
            "as UTF-8"
        )
    if code > 0x10FFFF:
        raise FrontmatterError(
            f"escape U+{code:04X} is outside the Unicode range (max U+10FFFF)"
        )
    return chr(code)


# --------------------------------------------------------------------------
# Dumping
# --------------------------------------------------------------------------

_KEYWORD_LIKE = {
    "true", "false", "yes", "no", "on", "off", "null", "~",
}


def dump_frontmatter(data: dict, /, *, key_order: list[str] | None = None) -> str:
    """Serialize *data* to a full frontmatter block including markers.

    *key_order* (optional) controls the ordering of top-level keys; keys
    not listed are appended afterwards in their original order.
    """
    if not isinstance(data, dict):
        raise TypeError("frontmatter must be a mapping")
    _check_dump_nesting(data)

    keys = list(data.keys())
    if key_order is not None:
        order = {k: i for i, k in enumerate(key_order)}
        known = [k for k in keys if k in order]
        known.sort(key=lambda k: order[k])
        keys = known + [k for k in keys if k not in order]

    _check_serialized_key_collisions(keys)
    lines = ["---"]
    for k in keys:
        _dump_kv(lines, k, data[k], 0)
    lines.append("---")
    return "\n".join(lines) + "\n"


def _check_dump_nesting(data: dict) -> None:
    """Reject container graphs deeper than the parser can represent.

    Programmatic callers can construct structures that could never be read
    from frontmatter text.  Validate those structures iteratively so the
    dumper reports its bounded public error before its recursive renderers
    approach Python's recursion limit.
    """
    stack = [(data, 0, False)]
    active: set[int] = set()
    while stack:
        value, depth, leaving = stack.pop()
        if not isinstance(value, (dict, list)):
            continue
        identity = id(value)
        if leaving:
            active.remove(identity)
            continue
        if depth > MAX_NESTING_DEPTH:
            raise TypeError(
                "frontmatter nesting is too deep "
                f"(max {MAX_NESTING_DEPTH} levels)"
            )
        if identity in active:
            raise TypeError("frontmatter contains a cyclic mapping or list")
        active.add(identity)
        stack.append((value, depth, True))
        children = list(value.values()) if isinstance(value, dict) else value
        stack.extend((child, depth + 1, False) for child in reversed(children))


def _dump_kv(lines: list[str], key, value, indent: int) -> None:
    prefix = " " * indent
    key_str = _format_key(key)
    if isinstance(value, dict):
        _dump_mapping_tail(lines, prefix, key_str, value, indent)
    elif isinstance(value, list):
        _dump_sequence_tail(lines, prefix, key_str, value, indent)
    else:
        lines.append(f"{prefix}{key_str}: {_dump_scalar(value, indent)}")


def _dump_mapping_tail(lines: list[str], prefix: str, key_str: str, value: dict, indent: int) -> None:
    """Append the body after ``key:`` for one mapping value."""
    if not value:
        lines.append(f"{prefix}{key_str}: {{}}")
        return
    _check_serialized_key_collisions(value.keys())
    lines.append(f"{prefix}{key_str}:")
    for key, item in value.items():
        _dump_kv(lines, key, item, indent + 2)


def _dump_sequence_tail(lines: list[str], prefix: str, key_str: str, value: list, indent: int) -> None:
    """Append the body after ``key:`` for one list value."""
    if not value or _all_scalars_and_scalar_lists(value):
        lines.append(f"{prefix}{key_str}: {_format_flow_list(value)}")
        return
    lines.append(f"{prefix}{key_str}:")
    for item in value:
        _dump_list_item(lines, item, indent + 2)


def _dump_sequence_element_value(item, indent: int) -> list[str]:
    """Render one block sequence element as lines (no ``- `` marker)."""
    if not isinstance(item, dict):
        raise TypeError("scalar sequence elements are handled by _dump_sequence_element")
    if not item:
        return ["{}"]
    parts: list[str] = []
    items = list(item.items())
    _check_serialized_key_collisions(key for key, _ in items)
    first_key, first_value = items[0]
    parts.append(f"{_format_key(first_key)}: {_dump_scalar_value_nested(first_value, indent + 2)}")
    for key, value in items[1:]:
        inner: list[str] = []
        _dump_kv(inner, key, value, indent + 2)
        parts.extend(line[indent + 2 :] for line in inner)
    return parts


def _dump_scalar_value_nested(value, indent: int) -> str:
    """Render the first value of a ``- key: value`` block item.

    Scalars stay on the dash line; mappings and lists drop to nested block
    lines joined by the caller. *indent* is the item indent; nested children
    are re-emitted with a fresh key render so continuation lines line up.
    Empty collections stay inline (``{}``/``[]``) so they parse back to the
    same empty value instead of ``None``.
    """
    if isinstance(value, dict):
        if not value:
            return "{}"
        pad = " " * (indent + 2)
        sub: list[str] = []
        for key, item in value.items():
            _dump_kv(sub, key, item, indent + 2)
        return "\n" + "\n".join(pad + line[(indent + 2) :] for line in sub)
    if isinstance(value, list):
        if not value:
            return "[]"
        pad = " " * (indent + 2)
        sub = []
        for item in value:
            _dump_list_item(sub, item, indent + 2)
        return "\n" + "\n".join(pad + line[(indent + 2) :] for line in sub)
    return _dump_scalar(value, indent)


def _dump_list_item(lines: list[str], item, indent: int) -> None:
    """Append one block sequence item; the marker starts on the ``- `` line."""
    _dump_sequence_element(lines, "- ", item, indent)


def _dump_sequence_element(lines: list[str], marker: str, item, indent: int) -> None:
    prefix = " " * indent
    if isinstance(item, dict):
        parts = _dump_sequence_element_value(item, indent)
        lines.append(f"{prefix}{marker}{parts[0]}")
        lines.extend(f"{prefix}  {part}" for part in parts[1:])
        return
    if isinstance(item, list):
        if not item or _all_scalars(item):
            lines.append(f"{prefix}{marker}{_format_flow_list(item)}")
            return
        # Non-scalar elements (nested lists, or mappings which flow brackets
        # cannot hold) recurse as a nested block sequence.
        lines.append(f"{prefix}{marker.rstrip()}")
        for sub in item:
            _dump_sequence_element(lines, "- ", sub, indent + 2)
        return
    lines.append(f"{prefix}{marker}{_dump_scalar(item, indent)}")


def _all_scalars(items: list) -> bool:
    return all(not isinstance(i, (dict, list)) for i in items)


def _all_scalars_and_scalar_lists(items: list) -> bool:
    """Flow-renderable lists: every element is a scalar or a scalar list."""

    def flowable(item) -> bool:
        if isinstance(item, dict):
            return False
        if isinstance(item, list):
            return all(flowable(i) for i in item)
        return True

    return all(flowable(i) for i in items)


def _dump_scalar(value, indent: int) -> str:
    """Render one scalar wherever a block value belongs (never in flow)."""
    return _render_block_scalar(value, indent)


def _render_block_scalar(value, indent: int) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        raise TypeError(
            "cannot inline a mapping or list as a block scalar; "
            "emit it as a nested block instead"
        )
    s = str(value)
    if "\n" in s:
        if s.strip() == "":
            # FM-6/FM-10: a value made only of whitespace and newlines cannot
            # survive a block scalar -- the dumper's pad and the parser's
            # indent detection both erase it (``"\\n"`` re-parsed as ``""`` and
            # ``" \\n "`` as ``""``).  A quoted scalar round-trips it exactly.
            return _double_quote(s)
        return _block_scalar(s, indent)
    return _quote_if_needed(s)


def _dump_flow_scalar(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return _quote_flow_text(str(value))


_FLOW_QUOTE_CHARS = (",", "[", "]", "{", "}", "'", '"', "#")


def _quote_flow_text(s: str) -> str:
    """Quote text so it survives inside one flow (bracket) list element.

    Bare commas/brackets/braces/quotes delimit or comment items; leaving them
    bare would make the emitted text unparseable.
    """
    if "\n" in s:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    quoted = _quote_if_needed(s)
    if quoted == s and any(c in s for c in _FLOW_QUOTE_CHARS):
        return _single_quote(s)
    return quoted


def _format_flow_list(items: list) -> str:
    return "[" + ", ".join(_format_flow_item(i, 1) for i in items) + "]"


def _format_flow_item(item, depth: int) -> str:
    """Serialize one flow element: scalars or nested lists.

    Mappings cannot be expressed in this parser's flow grammar: the bracket
    splitter cannot pair braces reliably across the outer list boundary, so
    fail loudly (block sequences carry mappings instead -- see
    _dump_sequence_element).
    """
    if isinstance(item, dict):
        raise TypeError(
            "cannot serialize a mapping inside a flow (bracket) list: "
            f"{item!r} (mappings are emitted as block sequence items instead)"
        )
    if isinstance(item, list):
        if depth >= MAX_NESTING_DEPTH:
            raise TypeError(
                f"flow list nesting exceeds the parser limit ({MAX_NESTING_DEPTH})"
            )
        return "[" + ", ".join(_format_flow_item(i, depth + 1) for i in item) + "]"
    return _dump_flow_scalar(item)


def _needs_indent_indicator(lines: list[str]) -> bool:
    """True when the parser's min-indent heuristic would eat real indentation.

    FM-5: the padded content of a value whose every line already begins with
    whitespace has a *higher* minimum indentation than the pad, so the parser's
    ``min(non-blank indents)`` strips the value's own indentation.  An explicit
    indentation indicator removes the guesswork.
    """
    content = [line for line in lines if line.strip() != ""]
    return bool(content) and all(line[:1] in (" ", "\t") for line in content)


def _block_scalar_header(s: str) -> tuple[str, str]:
    """Return ``(style, chomp)`` for *s* under YAML chomping rules."""
    if not s.endswith("\n"):
        return "|", "-"
    if s == s.rstrip("\n") + "\n":
        return "|", ""
    return "|", "+"


def _block_scalar_lines(s: str, chomp: str) -> list[str]:
    """Return the content lines a block scalar needs to reproduce *s*.

    A trailing newline is carried by a trailing empty line, because that is
    what a line terminator is inside a block scalar.
    """
    content = s.rstrip("\n") if chomp else s
    lines = content.split("\n") if content != "" else []
    if chomp == "+":
        lines += [""] * (len(s) - len(s.rstrip("\n")) - 1)
    return lines


def _block_scalar(s: str, indent: int) -> str:
    """Return a block-scalar representation that re-parses to exactly *s*.

    Header choice follows YAML chomping (FM-12): ``|-`` for a value with no
    trailing newline, ``|`` for exactly one, and ``|+`` for more.
    """
    pad = " " * (indent + 2)
    style, chomp = _block_scalar_header(s)
    lines = _block_scalar_lines(s, chomp)
    # The indentation indicator precedes the chomping indicator (``|2-``): the
    # parser reads the digit first.  It is parent-relative and the content is
    # always padded exactly two columns past the key, so it is always 2.
    indicator = "2" if _needs_indent_indicator(lines) else ""
    header = f"{style}{indicator}{chomp}"
    # An empty content line stays genuinely empty: padding it would turn it
    # into a whitespace-only line, which the parser preserves as content
    # (FM-6) and would then round-trip as spaces.
    body = "\n".join((pad + line) if line != "" else "" for line in lines)
    return f"{header}\n{body}"


_DOUBLE_QUOTE_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\x85": "\\N",
    "\xa0": "\\_",
    "\u2028": "\\L",
    "\u2029": "\\P",
}


def _double_quote(s: str) -> str:
    """Render *s* as a double-quoted scalar with escapes.

    Used for values a block scalar cannot express -- a value that is nothing
    but whitespace and newlines (FM-6, FM-10), where the dumper's own
    indentation and chomping rules would destroy it.
    """
    out = ['"']
    for char in s:
        escaped = _DOUBLE_QUOTE_ESCAPES.get(char)
        if escaped is not None:
            out.append(escaped)
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\x{ord(char):02x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _quote_if_needed(s: str) -> str:
    if s == "":
        return "''"
    if s.lower() in _KEYWORD_LIKE:
        return _single_quote(s)
    if s != s.strip():
        return _single_quote(s)
    if _KEY_SEPARATOR_RE.search(s):
        return _single_quote(s)
    # FM-8: the parser starts an inline comment at '#' preceded by a space *or
    # a tab*, so quoting only for " #" truncated any value containing "a\t#b"
    # to "a" with nothing reporting it.
    if _INLINE_COMMENT_RE.search(s):
        return _single_quote(s)
    if s.startswith(("#", "-", "?", "!", "&", "*", "[", "]", "{", "}",
                     ",", "`", "%", "@", "'", '"', "|", ">", ": ", ":",
                     "~", "=")):
        return _single_quote(s)
    return s


# Keys containing these characters must be single-quoted: the parser treats a
# bare quote or an inline-flow indicator mid-key as the start of a quoted
# token and rejects the line.
_QUOTE_KEY_CHARS = ("'", '"', "[", "]", "{", "}", "(", ")")


def _reject_unwritable_key(k: str) -> None:
    """Reject a mapping key this parser could never read back (FM-9).

    Escaped double-quoted keys can represent the control characters that the
    line-based parser accepts in quoted input.  Unicode surrogate code points
    are the exception: they cannot be encoded as UTF-8, even when escaped, so
    reject them before the writer can leak a raw encoding failure.
    """
    if any(0xD800 <= ord(char) <= 0xDFFF for char in k):
        raise ValueError(
            f"frontmatter key {k!r} contains a surrogate and cannot be "
            "written as a mapping key"
        )


def _format_key(key) -> str:
    k = str(key)
    _reject_unwritable_key(k)
    return _format_key_text(k)


def _format_key_text(k: str) -> str:
    """Choose an escaped, quoted, or bare representation for a key."""
    if (any(ord(char) < 0x20 or ord(char) == 0x7F for char in k)
            or any(char in "\u0085\u00a0\u2028\u2029" for char in k)):
        # FM-9: the parser already decodes escaped double-quoted keys.  Keep
        # the physical mapping entry on one line while preserving newlines,
        # tabs, and other representable control characters in the key value.
        return _double_quote(k)
    needs_quotes = (
        k == ""
        or k != k.strip()
        or k.startswith("-")
        or any(marker in k for marker in (":", "#", *_QUOTE_KEY_CHARS))
    )
    return _single_quote(k) if needs_quotes else k


def _check_serialized_key_collisions(keys) -> None:
    """Reject distinct mapping keys that would render to the same key text."""
    rendered: dict[str, object] = {}
    for key in keys:
        key_text = _format_key(key)
        if key_text in rendered:
            raise ValueError(
                "duplicate frontmatter key after serialization: "
                f"{rendered[key_text]!r} and {key!r} both render as {key_text!r}"
            )
        rendered[key_text] = key


def _single_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"
