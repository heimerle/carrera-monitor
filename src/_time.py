"""Internal time helper.

Python 3.12 deprecates ``datetime.utcnow()``. Existing SQLite columns store
naive datetimes, so we keep the same shape but build it from a timezone-aware
UTC instant.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow_naive() -> datetime:
    """Return the current UTC time as a naive ``datetime`` (no tzinfo)."""
    return datetime.now(UTC).replace(tzinfo=None)
