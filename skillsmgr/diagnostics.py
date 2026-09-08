"""Internal diagnostics for recoverable fallback and cleanup failures.

Diagnostics are deliberately stderr-only so public return values, REST schemas,
and CLI output contracts remain unchanged.  Callers use this for failures that
would otherwise make a recovery or optional enrichment incomplete silently.
"""

from __future__ import annotations

import sys


def diagnose(context: str, error: BaseException) -> None:
    """Emit a concise, non-sensitive diagnostic without changing control flow."""
    print(f"skillsmgr diagnostic: {context}: {error!r}", file=sys.stderr)
