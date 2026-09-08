"""Private CLI output helpers.

The command handlers remain in :mod:`skillsmgr.cli`; this module owns the
small, reusable output policy so formatting changes have one tested seam.
"""

from __future__ import annotations

import json
import sys

from .colors import COLORS


def print_json(obj, stream=None) -> None:
    """Write an indented JSON value, preserving the CLI's historical format."""
    (stream or sys.stdout).write(json.dumps(obj, indent=2, default=str) + "\n")


def err(message: str, stream=None) -> None:
    """Write a consistently styled CLI error to stderr."""
    (stream or sys.stderr).write(f"{COLORS.red('error:')} {message}\n")


def truncate(text: str, limit: int) -> str:
    """Limit a display string without changing short values."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def render_table(rows: list[list[str]]) -> str:
    """Render rows with aligned columns and a bold first row."""
    if not rows:
        return ""
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
