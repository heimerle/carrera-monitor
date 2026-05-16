"""Service-layer exceptions for the race-management module.

Re-exported from :mod:`src.services.race_service` and friends so callers
can ``from src.services import RaceServiceError, RaceNotFoundError``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .live_continuity import (
    ActiveCarDetector,
    CarSlotMapping,
    LinkHealthState,
    LinkHealthTracker,
    LiveContinuityService,
)

if TYPE_CHECKING:
    from .bluetooth_connection_supervisor import BluetoothConnectionSupervisor
    from .bluetooth_service import BluetoothService
    from .runtime_settings import RuntimeSettings


def __getattr__(name: str) -> Any:
    """Lazy bluetooth exports to avoid import cycles in core runtime modules."""

    if name == "BluetoothConnectionSupervisor":
        from .bluetooth_connection_supervisor import BluetoothConnectionSupervisor

        return BluetoothConnectionSupervisor
    if name == "BluetoothService":
        from .bluetooth_service import BluetoothService

        return BluetoothService
    if name == "RuntimeSettings":
        from .runtime_settings import RuntimeSettings

        return RuntimeSettings
    if name == "get_bluetooth_desired_connected":
        from .runtime_settings import get_bluetooth_desired_connected

        return get_bluetooth_desired_connected
    if name == "request_bluetooth_command":
        from .runtime_settings import request_bluetooth_command

        return request_bluetooth_command
    if name == "set_bluetooth_desired_connected":
        from .runtime_settings import set_bluetooth_desired_connected

        return set_bluetooth_desired_connected
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    "BluetoothConnectionSupervisor",
    "BluetoothService",
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
    "RuntimeSettings",
    "ensure_database_initialized",
    "get_bluetooth_desired_connected",
    "request_bluetooth_command",
    "set_bluetooth_desired_connected",
]
