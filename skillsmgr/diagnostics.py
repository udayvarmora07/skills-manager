"""Internal diagnostics for recoverable fallback, cleanup, and repair actions.

Diagnostics are deliberately stderr-only so public return values, REST schemas,
and CLI output contracts remain unchanged.  Callers use this for failures that
would otherwise make a recovery or optional enrichment incomplete silently, and
for repairs that changed the user's data (e.g. ``resync`` clearing abandoned
transaction artifacts) so the action is traceable somewhere.
"""

from __future__ import annotations

import sys


def diagnose(context: str, error: BaseException | None = None) -> None:
    """Emit a concise, non-sensitive diagnostic without changing control flow.

    ``error`` is optional so a repair that *succeeded* is still recorded
    instead of touching the user's data with no trace at all.
    """
    if error is None:
        print(f"skillsmgr diagnostic: {context}", file=sys.stderr)
        return
    print(f"skillsmgr diagnostic: {context}: {error!r}", file=sys.stderr)
