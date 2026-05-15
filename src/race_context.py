"""Process-singleton tracking which race (if any) is currently `running`.

Read by ``RaceTelemetryRunner`` on every event; written only by the
lifecycle methods of ``RaceService`` (``start_race``, ``resume_race``,
``pause_race``, ``finish_race``, ``cancel_race``).

A ``threading.RLock`` is used because the writers run on a background
thread spawned by ``asyncio.to_thread`` while the singleton is also
accessible from synchronous UI code paths.
"""

from __future__ import annotations

import threading


class ActiveRaceContext:
    """Class-level singleton — never instantiated."""

    _race_id: int | None = None
    _lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:  # pragma: no cover - intentional
        raise TypeError("ActiveRaceContext is a class-level singleton; do not instantiate")

    @classmethod
    def get(cls) -> int | None:
        with cls._lock:
            return cls._race_id

    @classmethod
    def set(cls, race_id: int | None) -> None:
        with cls._lock:
            cls._race_id = race_id

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._race_id = None

    @classmethod
    def lock(cls) -> threading.RLock:
        """Expose the RLock so services can serialize a multi-step transition."""
        return cls._lock


__all__ = ["ActiveRaceContext"]
