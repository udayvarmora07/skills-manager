"""UTC timestamps for records, reviews and filesystem artifact names."""

from __future__ import annotations

from datetime import datetime, timezone

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
#: The filename-safe form used in trash names, snapshot ids and backups.
STAMP_FORMAT = "%Y-%m-%d_%H-%M-%SZ"


def iso(moment: datetime | float | None = None) -> str:
    """UTC ``YYYY-MM-DDTHH:MM:SSZ`` for a datetime, a POSIX timestamp, or now."""
    if moment is None:
        moment = datetime.now(timezone.utc)
    elif not isinstance(moment, datetime):
        moment = datetime.fromtimestamp(moment, timezone.utc)
    return moment.strftime(ISO_FORMAT)


def now_iso() -> str:
    """The current UTC time in :data:`ISO_FORMAT`."""
    return iso()


def stamp() -> str:
    """The current UTC time in the filename-safe :data:`STAMP_FORMAT`."""
    return datetime.now(timezone.utc).strftime(STAMP_FORMAT)
