"""Service-layer exceptions for the race-management module.

Re-exported from :mod:`src.services.race_service` and friends so callers
can ``from src.services import RaceServiceError, RaceNotFoundError``.
"""

from __future__ import annotations

from .live_continuity import (
    ActiveCarDetector,
    CarSlotMapping,
    LinkHealthState,
    LinkHealthTracker,
    LiveContinuityService,
)


class RaceServiceError(Exception):
    """Base class for all race-service errors."""


class RaceNotFoundError(RaceServiceError):
    """Requested race id does not exist."""


class RaceValidationError(RaceServiceError):
    """Domain-level validation failed (mode/lap_target/driver mismatch, etc.)."""


class InvalidRaceStateError(RaceServiceError):
    """Attempted state transition is not permitted by the state machine."""


class RaceAlreadyRunningError(RaceServiceError):
    """Internal: another race is currently running (handled via auto-pause)."""


class RaceNotEditableError(RaceServiceError):
    """Race is in a terminal/active state and may not be edited."""


def ensure_database_initialized() -> None:
    """UI-friendly façade for :func:`src.database.init_db`.

    Pages may call this without importing the SQLAlchemy module directly
    (FR-130 — UI layer remains ORM-free).
    """

    from ..database import init_db

    init_db()


__all__ = [
    "ActiveCarDetector",
    "CarSlotMapping",
    "InvalidRaceStateError",
    "LinkHealthState",
    "LinkHealthTracker",
    "LiveContinuityService",
    "RaceAlreadyRunningError",
    "RaceNotEditableError",
    "RaceNotFoundError",
    "RaceServiceError",
    "RaceValidationError",
    "ensure_database_initialized",
]
