"""Private CLI output helpers.

The command handlers remain in :mod:`skillsmgr.cli`; this module owns the
small, reusable output policy so formatting changes have one tested seam.
"""

from __future__ import annotations

import json
import sys
import unicodedata

from .colors import COLORS

#: C0 controls, DEL, and C1 controls -- the range a terminal interprets as
#: commands (ESC is 0x1B, so ``\x1b[2K\x1b[32m`` is covered by the C0 group).
#: ``\t`` and ``\n`` are not display characters here either: a table cell that
#: carries one would break the column layout, so both are replaced too.
_CONTROL_RANGES = ((0x00, 0x1F), (0x7F, 0x9F))
#: Unicode line/paragraph separators and the other separators a terminal or a
#: paste may treat as a line break.
_LINE_SEPARATORS = "\u2028\u2029\u0085"
_REPLACEMENT = "?"


def print_json(obj, stream=None) -> None:
    """Write an indented JSON value, preserving the CLI's historical format."""
    (stream or sys.stdout).write(json.dumps(obj, indent=2, default=str) + "\n")


def err(message: str, stream=None) -> None:
    """Write a consistently styled CLI error to stderr."""
    (stream or sys.stderr).write(f"{COLORS.red('error:')} {message}\n")


def sanitize_text(text: str) -> str:
    """Render untrusted text safe to print in a terminal (CLI-3).

    Skill descriptions and categories come from imported archives and from
    directories other tools wrote, so they are attacker-influenced.  A raw
    ``ESC`` payload spoofs ``list``/``view`` output (erase the real row, print a
    convincing "verified" one) and corrupts column widths, because the escapes
    count towards ``len()``.  Colors are emitted by this tool separately, so
    every character here is removed at the display seam instead.
    """
    if not isinstance(text, str):
        text = str(text)
    out = []
    for char in text:
        code = ord(char)
        if any(low <= code <= high for low, high in _CONTROL_RANGES):
            out.append(_REPLACEMENT)
        elif char in _LINE_SEPARATORS:
            out.append(_REPLACEMENT)
        elif unicodedata.category(char) in ("Cf", "Cs"):
            # Format characters (a bidi override can reorder a whole line) and
            # lone surrogates have no business in terminal output.
            out.append(_REPLACEMENT)
        else:
            out.append(char)
    return "".join(out)


def truncate(text: str, limit: int) -> str:
    """Limit a display string without changing short values."""
    text = sanitize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def render_table(rows: list[list[str]]) -> str:
    """Render rows with aligned columns and a bold first row."""
    if not rows:
        return ""
    rows = [[sanitize_text(cell) for cell in row] for row in rows]
    widths = [0] * len(rows[0])
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = []
    for index, row in enumerate(rows):
        cells = []
        for i, cell in enumerate(row):
            if i < len(row) - 1:
                cells.append(cell.ljust(widths[i]))
            else:
                cells.append(cell)
        line = "   ".join(cells)
        if index == 0:
            line = COLORS.bold(line)
        lines.append(line)
    return "\n".join(lines)
