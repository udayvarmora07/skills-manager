"""The Store that ``global`` means for the current thread of work.

SCOPE-10: this is a ``ContextVar``, not a module global.  As a plain global the
last binding won for every caller in the process, so a second in-process
``WebAppServer`` silently redirected the first server's global reads *and* its
snapshot writes to another data dir.  The web server rebinds it from its own
``store`` at the start of every request thread, and the CLI binds the Store it
was asked for, so neither inherits a stale binding.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar

ACTIVE_STORE: ContextVar = ContextVar("skillsmgr_active_store", default=None)


def active_store():
    """The bound Store, or ``None`` when nothing has bound one."""
    return ACTIVE_STORE.get()


def set_active_store(store) -> None:
    """Bind ``store`` for this context (``None`` unbinds)."""
    ACTIVE_STORE.set(store)


@contextlib.contextmanager
def bound_store(store):
    """Bind ``store`` for the block, restoring the prior binding after."""
    token = ACTIVE_STORE.set(store)
    try:
        yield store
    finally:
        ACTIVE_STORE.reset(token)
