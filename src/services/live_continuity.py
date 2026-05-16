"""Runtime helpers for live continuity hardening.

This module centralizes three concerns used across the live pipeline:
- Canonical slot->car mapping (race-domain IDs must stay within 1..6)
- Active car detection over a bounded recency window
- Durable checkpoint + lap identity helpers used by RaceService
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from .._time import utcnow_naive
from ..models import RaceLapCheckpoint
from ..repositories.race_repository import RaceRepository

MappingMode = Literal["zero_based", "one_based", "explicit"]
LinkHealthStatus = Literal["healthy", "degraded", "stalled", "reconnecting"]


@dataclass
class CarSlotMapping:
    """Normalize raw slot/address values into canonical race car IDs (1..6)."""

    mapping_mode: MappingMode = "one_based"
    slot_to_car_id: dict[int, int] = field(default_factory=dict)
    locked: bool = False

    def normalize_slot(self, raw_slot: int | None) -> int | None:
        if raw_slot is None:
            return None
        slot = int(raw_slot)

        # Reuse an existing decision so mapping stays stable in-session.
        if slot in self.slot_to_car_id:
            car_id = self.slot_to_car_id[slot]
            return car_id if 1 <= car_id <= 6 else None

        if self.locked:
            return None

        if self.mapping_mode == "zero_based":
            candidate = slot + 1
        elif self.mapping_mode == "one_based":
            candidate = slot
        else:
            # explicit mode requires a precomputed map.
            return None

        if not 1 <= candidate <= 6:
            return None

        self.slot_to_car_id[slot] = candidate
        return candidate

    def normalize_car_id(self, raw_car_id: int | None) -> int | None:
        if raw_car_id is None:
            return None
        return self.normalize_slot(int(raw_car_id))


@dataclass
class ActiveCarDetector:
    """Track recently active canonical cars over a smoothing window."""

    window_ms: int = 3_000
    _last_seen_ms: dict[int, int] = field(default_factory=dict)

    def observe(self, car_id: int | None, timestamp_monotonic_ms: int) -> None:
        if car_id is None:
            return
        cid = int(car_id)
        if 1 <= cid <= 6:
            self._last_seen_ms[cid] = int(timestamp_monotonic_ms)

    def active_car_ids(self, now_monotonic_ms: int) -> list[int]:
        now_ms = int(now_monotonic_ms)
        horizon = max(100, int(self.window_ms))
        active = [
            cid
            for cid, last in self._last_seen_ms.items()
            if now_ms - last <= horizon
        ]
        return sorted(active)[:6]

    def snapshot(self, now_monotonic_ms: int) -> dict[str, object]:
        ids = self.active_car_ids(now_monotonic_ms)
        return {
            "active_car_ids": ids,
            "active_car_count": len(ids),
            "window_ms": int(self.window_ms),
        }


@dataclass
class LinkHealthState:
    state: LinkHealthStatus = "healthy"
    timeout_streak: int = 0
    last_frame_at_ms: int = 0
    reason: str | None = None


@dataclass
class LinkHealthTracker:
    """State machine for watchdog-driven link health diagnostics."""

    warning_threshold: int = 5
    hard_threshold: int = 15
    state: LinkHealthState = field(default_factory=LinkHealthState)

    def on_timeout(self) -> LinkHealthState:
        self.state.timeout_streak += 1
        if self.state.timeout_streak >= self.hard_threshold:
            self.state.state = "stalled"
            self.state.reason = "timeout_streak_hard"
        elif self.state.timeout_streak >= self.warning_threshold:
            self.state.state = "degraded"
            self.state.reason = "timeout_streak_warning"
        return self.state

    def on_frame(self, now_monotonic_ms: int) -> LinkHealthState:
        self.state.last_frame_at_ms = int(now_monotonic_ms)
        self.state.timeout_streak = 0
        self.state.state = "healthy"
        self.state.reason = "frame_received"
        return self.state

    def mark_reconnecting(self, reason: str) -> LinkHealthState:
        self.state.state = "reconnecting"
        self.state.reason = reason
        return self.state


class LiveContinuityService:
    """Persistence helpers used by RaceService during reconnect/restart continuity."""

    def __init__(self, repository: RaceRepository | None = None) -> None:
        self._repo = repository or RaceRepository()

    def load_checkpoint(
        self,
        session: Session,
        race_id: int,
        car_id: int,
    ) -> RaceLapCheckpoint | None:
        return self._repo.get_lap_checkpoint(session, race_id=race_id, car_id=car_id)

    def save_checkpoint(
        self,
        session: Session,
        *,
        race_id: int,
        car_id: int,
        last_cu_timestamp_ms: int,
        lap_count: int,
    ) -> RaceLapCheckpoint:
        return self._repo.upsert_lap_checkpoint(
            session,
            race_id=race_id,
            car_id=car_id,
            last_cu_timestamp_ms=last_cu_timestamp_ms,
            lap_count=lap_count,
            updated_at=utcnow_naive(),
        )

    def register_lap_identity(
        self,
        session: Session,
        *,
        race_id: int,
        car_id: int,
        cu_timestamp_ms: int,
    ) -> bool:
        return self._repo.insert_lap_identity_if_new(
            session,
            race_id=race_id,
            car_id=car_id,
            cu_timestamp_ms=cu_timestamp_ms,
        )

    def seed_from_existing_laps(
        self,
        session: Session,
        *,
        race_id: int,
        car_id: int,
    ) -> None:
        """Best-effort checkpoint seeding from existing lap rows for restart recovery."""
        lap_count = self._repo.count_laps_for_car(session, race_id=race_id, car_id=car_id)
        if lap_count < 0:
            lap_count = 0
        self._repo.upsert_lap_checkpoint(
            session,
            race_id=race_id,
            car_id=car_id,
            last_cu_timestamp_ms=0,
            lap_count=lap_count,
            updated_at=utcnow_naive(),
        )


__all__ = [
    "ActiveCarDetector",
    "CarSlotMapping",
    "LinkHealthState",
    "LinkHealthTracker",
    "LiveContinuityService",
    "MappingMode",
]
