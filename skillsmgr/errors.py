"""Exception hierarchy for the skill store.

This is a leaf module: it imports nothing from :mod:`skillsmgr`, so callers
that only need to catch or raise these errors do not have to import the whole
:mod:`skillsmgr.store` module (and importing it here cannot create a cycle).

``skillsmgr.store`` re-exports every class below for compatibility, so
``from skillsmgr.store import StoreError`` keeps working and both spellings
name the same object.
"""

from __future__ import annotations

__all__ = [
    "StoreError",
    "SkillNotFound",
    "LockTimeoutError",
    "StoreLayoutError",
]


class StoreError(Exception):
    """Raised for any store-level failure (validation, I/O, conflicts)."""


class SkillNotFound(StoreError):
    """Raised when an operation targets a skill that does not exist."""


class LockTimeoutError(StoreError):
    """Another process held a mutation lock past ``MUTATION_LOCK_TIMEOUT`` (R5).

    Routed as ``409`` by the web layer's existing ``status`` attribute: the
    request was valid, the library is busy, and a retry is the remedy.
    """

    status = 409


class StoreLayoutError(StoreError):
    """Raised when the managed data layout exists but cannot be used.

    A component of ``<data>`` -- usually ``skills`` -- is a regular file, or the
    index is present but unusable.  This is distinct from "nothing is
    installed": there is nothing to read *and* nothing the reader may create,
    so the message names the path and the repair rather than leaving a caller
    to discover it (docs/24 §D3-4).

    Every write path raises this too, via ``_ensure_store_dirs``' guard, so the
    condition has one name wherever a user meets it.
    """

    # The web layer already routes a ``StoreError`` through this attribute, so a
    # broken layout answers 404 -- the resource cannot be read, and nothing the
    # caller sent caused it -- instead of 400 with an internal path.
    status = 404
