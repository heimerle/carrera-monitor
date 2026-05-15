"""`StateManager` — in-memory aggregate fed by the bus, writer of `state.json`.

Subscribes to a queue from the event bus and updates per-car aggregates,
the global race state, and the connection state record. Periodically (or
on every change) writes an atomic snapshot to `logs/state.json` for the
Streamlit dashboard to read.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import utils
from .event_model import (
    ConnectionState,
    ConnectionStateRecord,
    EventType,
    RaceState,
    TelemetryEvent,
)
from .telemetry_processor import clamp_fuel, clamp_unit, update_best_lap

logger = logging.getLogger(__name__)

_RECENT_EVENTS_MAX = 100


@dataclass
class CarState:
    car_id: int
    lap_count: int = 0
    best_lap_ms: int | None = None
    latest_lap_ms: int | None = None
    fuel_percent: float | None = None
    in_pit: bool = False
    last_speed_kmh: float | None = None
    last_event_at_ms: int | None = None


class StateManager:
    """Aggregates the event stream and exposes a JSON-serializable snapshot."""

    def __init__(
        self,
        queue: asyncio.Queue[TelemetryEvent],
        state_file: Path,
        *,
        refresh_interval_ms: int = 1000,
        monotonic_clock: Callable[[], int] | None = None,
    ) -> None:
        self._queue = queue
        self._state_file = Path(state_file)
        self._refresh_ms = refresh_interval_ms
        self._mono = monotonic_clock or utils.now_monotonic_ms
        self._cars: dict[int, CarState] = {}
        self._race_state: RaceState = RaceState.IDLE
        self._connection: ConnectionStateRecord = ConnectionStateRecord(
            state=ConnectionState.DISCONNECTED,
            since_ms=self._mono(),
        )
        self._recent: deque[TelemetryEvent] = deque(maxlen=_RECENT_EVENTS_MAX)
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last_write_ms: int = 0

    # ----- Public API -----------------------------------------------------

    def apply(self, event: TelemetryEvent) -> None:
        """Apply one event to the in-memory state. Safe to call directly from tests."""
        self._recent.appendleft(event)

        if event.event_type is EventType.LAP and event.car_id is not None:
            car = self._car(event.car_id)
            lap_number = int(event.payload["lap_number"])
            lap_time_ms = int(event.payload["lap_time_ms"])
            car.lap_count = max(car.lap_count, lap_number)
            car.latest_lap_ms = lap_time_ms
            car.best_lap_ms = update_best_lap(car.best_lap_ms, lap_time_ms)
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.FUEL and event.car_id is not None:
            car = self._car(event.car_id)
            car.fuel_percent = clamp_fuel(float(event.payload["level_percent"]))
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.PITLANE and event.car_id is not None:
            car = self._car(event.car_id)
            car.in_pit = bool(event.payload["in_pit"])
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.SPEED and event.car_id is not None:
            car = self._car(event.car_id)
            car.last_speed_kmh = max(0.0, float(event.payload["speed_kmh"]))
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.CONTROLLER_INPUT and event.car_id is not None:
            car = self._car(event.car_id)
            # Sanitize via clamp helpers (no field stored, but invariant doc).
            _ = clamp_unit(float(event.payload["throttle"]))
            _ = clamp_unit(float(event.payload["brake"]))
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.RACE_STATE:
            new_race_state = RaceState(event.payload["state"])
            if new_race_state is RaceState.IDLE and self._race_state is not RaceState.IDLE:
                # Reset lap counts on transition to idle (data-model §3 invariant).
                for car in self._cars.values():
                    car.lap_count = 0
            self._race_state = new_race_state
        elif event.event_type is EventType.CONNECTION_STATE:
            new_conn_state = ConnectionState(event.payload["state"])
            err = event.payload.get("error")
            if new_conn_state is not self._connection.state:
                self._connection = ConnectionStateRecord(
                    state=new_conn_state,
                    since_ms=event.timestamp_monotonic_ms,
                    last_error=err,
                )

    def snapshot(self) -> dict[str, Any]:
        """JSON-serializable dict written to `state.json`."""
        return {
            "taken_at_iso": utils.now_iso().isoformat(),
            "taken_at_monotonic_ms": self._mono(),
            "connection": {
                "state": self._connection.state.value,
                "since_ms": self._connection.since_ms,
                "last_error": self._connection.last_error,
            },
            "race": self._race_state.value,
            "cars": [asdict(c) for c in sorted(self._cars.values(), key=lambda c: c.car_id)],
            "recent_events": [
                self._event_to_dict(ev) for ev in list(self._recent)[:_RECENT_EVENTS_MAX]
            ],
        }

    def write_snapshot(self) -> None:
        utils.atomic_write_json(self._state_file, self.snapshot())
        self._last_write_ms = self._mono()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="state-manager")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except TimeoutError:
                self._task.cancel()
            except Exception:
                logger.exception("state_manager: task raised on shutdown")
            self._task = None
        # Final snapshot so dashboard sees the last state.
        try:
            self.write_snapshot()
        except OSError:
            logger.exception("state_manager: final snapshot write failed")

    # ----- Internals ------------------------------------------------------

    def _car(self, car_id: int) -> CarState:
        if car_id not in self._cars:
            self._cars[car_id] = CarState(car_id=car_id)
        return self._cars[car_id]

    @staticmethod
    def _event_to_dict(ev: TelemetryEvent) -> dict[str, Any]:
        return {
            "timestamp_iso": ev.timestamp_iso.isoformat(),
            "timestamp_monotonic_ms": ev.timestamp_monotonic_ms,
            "source": ev.source,
            "event_type": ev.event_type.value,
            "car_id": ev.car_id,
            "controller_id": ev.controller_id,
            "payload": ev.payload,
            "metadata": ev.metadata,
        }

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    ev = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                except TimeoutError:
                    pass
                else:
                    self.apply(ev)
                now_ms = self._mono()
                if now_ms - self._last_write_ms >= self._refresh_ms:
                    try:
                        self.write_snapshot()
                    except OSError:
                        logger.exception("state_manager: snapshot write failed")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("state_manager: run loop crashed")


__all__ = ["CarState", "StateManager"]
