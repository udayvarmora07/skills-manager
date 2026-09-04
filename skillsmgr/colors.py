"""ANSI color helpers with automatic terminal detection.

Colors are enabled only when stdout is a TTY, unless overridden via the
``NO_COLOR`` / ``FORCE_COLOR`` environment variables or explicit CLI flags.
"""

from __future__ import annotations

import os
import sys

__all__ = ["Colors", "COLORS"]


def _default_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    force = os.environ.get("FORCE_COLOR")
    if force is not None and force != "" and force != "0":
        return True
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


class Colors:
    """A minimal ANSI palette that no-ops when disabled."""

    def __init__(self, enabled: bool | None = None):
        self.enabled = _default_enabled() if enabled is None else enabled

    def paint(self, code: int, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def bold(self, text: str) -> str:
        return self.paint(1, text)

    def dim(self, text: str) -> str:
        return self.paint(2, text)

    def red(self, text: str) -> str:
        return self.paint(31, text)

    def green(self, text: str) -> str:
        return self.paint(32, text)

    def yellow(self, text: str) -> str:
        return self.paint(33, text)

    def cyan(self, text: str) -> str:
        return self.paint(36, text)

    def gray(self, text: str) -> str:
        return self.paint(90, text)


COLORS = Colors()
