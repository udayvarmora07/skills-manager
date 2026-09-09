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

MAX_DOCUMENT_CHARS = 512 * 1024
MAX_KEYS = 200
MAX_COLLECTION_ITEMS = 200
MAX_SCALAR_LENGTH = 16 * 1024
MAX_NESTING_DEPTH = 64


class FrontmatterError(ValueError):
    """Raised when frontmatter text cannot be parsed."""


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

_TRUE_WORDS = {"true", "yes", "on"}
_FALSE_WORDS = {"false", "no", "off"}
_NULL_WORDS = {"null", "~"}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split *text* into ``(frontmatter_dict, body)``.

    When the document has no leading ``---`` marker, ``({}, text)`` is
    returned.  When a marker exists but no closing marker is found, a
    ``FrontmatterError`` is raised.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    if len(text) > MAX_DOCUMENT_CHARS:
        raise FrontmatterError(
            f"frontmatter document is too large (max {MAX_DOCUMENT_CHARS} characters)"
        )
    lines = text.split("\n")
    if not lines or not _DOC_MARKER.match(lines[0].strip()):
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if _DOC_MARKER.match(lines[i].strip()):
            end = i
            break
    if end is None:
        raise FrontmatterError(
            "frontmatter block is missing its closing '---' marker"
        )
    yaml_lines = [ln.rstrip("\r") for ln in lines[1:end]]
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
            items, _ = self._parse_block_list(idx, self._indent(self.lines[idx]))
            return items
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
            if rest == "":
                item, idx = self._parse_nested(idx, indent, depth + 1)
            elif self._looks_like_key(rest):
                item, idx = self._parse_inline_mapping(idx, indent + 2, rest, depth + 1)
            else:
                item = self._parse_inline(rest)
            items.append(item)
        return items, idx

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
                raw.append("")
                i += 1
                continue
            if self._indent(line) <= parent_indent:
                break
            raw.append(line)
            i += 1

        if explicit_indent is not None:
            content_indent = explicit_indent
        else:
            non_blank = [self._indent(l) for l in raw if l != ""]
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

        if chomp == "strip":
            result = result.rstrip("\n")
        elif chomp == "clip":
            if result and not result.endswith("\n"):
                result += "\n"
        else:  # keep
            if result and not result.endswith("\n"):
                result += "\n"
        return self._check_scalar(result), i

    @staticmethod
    def _fold(parts: list[str]) -> str:
        """Apply YAML folding: single newlines become spaces, blank lines
        become newlines."""
        result = ""
        i = 0
        while i < len(parts):
            part = parts[i]
            if part == "":
                j = i
                while j < len(parts) and parts[j] == "":
                    j += 1
                result += "\n" * (j - i)
                i = j
            else:
                if result and not result.endswith("\n"):
                    result += " "
                result += part
                i += 1
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
                        result.append(chr(int(digits, 16)))
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

    keys = list(data.keys())
    if key_order is not None:
        order = {k: i for i, k in enumerate(key_order)}
        known = [k for k in keys if k in order]
        known.sort(key=lambda k: order[k])
        keys = known + [k for k in keys if k not in order]

    lines = ["---"]
    for k in keys:
        _dump_kv(lines, k, data[k], 0)
    lines.append("---")
    return "\n".join(lines) + "\n"


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


def _dump_scalar_value(value, indent: int) -> str:
    """Render one leaf scalar for a mapping value."""
    return _dump_scalar(value, indent)


def _dump_sequence_element_value(item, indent: int) -> list[str]:
    """Render one block sequence element as lines (no ``- `` marker)."""
    if not isinstance(item, dict):
        raise TypeError("scalar sequence elements are handled by _dump_sequence_element")
    if not item:
        return ["{}"]
    parts: list[str] = []
    items = list(item.items())
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
    prefix = " " * indent
    _dump_block_item(lines, item, indent, is_first=True)


def _dump_block_item(lines: list[str], item, indent: int, *, is_first: bool) -> None:
    """Append one block item; top-level items start on the ``- `` line."""
    marker = "- " if is_first else "- "
    _dump_sequence_element(lines, marker, item, indent)


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


def _block_scalar(s: str, indent: int) -> str:
    """Return a multi-line block-scalar representation for *s*."""
    pad = " " * (indent + 2)
    if s.endswith("\n"):
        stripped = s.rstrip("\n")
        if s == stripped + "\n":
            header = "|"
            content = stripped
        else:
            header = "|+"
            content = s
    else:
        header = "|-"
        content = s
    body = "\n".join(pad + line for line in content.split("\n"))
    return f"{header}\n{body}"


def _quote_if_needed(s: str) -> str:
    if s == "":
        return "''"
    if s.lower() in _KEYWORD_LIKE:
        return _single_quote(s)
    if s != s.strip():
        return _single_quote(s)
    if ": " in s or s.endswith(":"):
        return _single_quote(s)
    if " #" in s:
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


def _format_key(key) -> str:
    k = str(key)
    needs_quotes = (
        k == ""
        or k != k.strip()
        or k.startswith("-")
        or any(marker in k for marker in (":", "#", *_QUOTE_KEY_CHARS))
    )
    return _single_quote(k) if needs_quotes else k


def _single_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"
