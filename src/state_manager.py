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
from .services.live_continuity import ActiveCarDetector
from .telemetry_processor import clamp_fuel, clamp_unit, update_best_lap

logger = logging.getLogger(__name__)

_RECENT_EVENTS_MAX = 100
_CANONICAL_MIN_CAR_ID = 1
_CANONICAL_MAX_CAR_ID = 6


@dataclass
class CarState:
    car_id: int
    lap_count: int = 0
    lap_samples: int = 0
    lap_total_ms: int = 0
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
        active_car_window_ms: int = 3000,
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
        self._active_detector = ActiveCarDetector(window_ms=active_car_window_ms)
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last_write_ms: int = 0
        self._processed_lap_events: int = 0
        self._dropped_lap_events: int = 0
        self._last_lap_payload: dict[str, Any] | None = None
        self._last_telemetry_at_iso: str | None = None
        self._last_state_update_at_iso: str | None = None

    # ----- Public API -----------------------------------------------------

    def apply(self, event: TelemetryEvent) -> None:
        """Apply one event to the in-memory state. Safe to call directly from tests."""
        self._last_telemetry_at_iso = event.timestamp_iso.isoformat()
        self._last_state_update_at_iso = utils.now_iso().isoformat()
        self._recent.appendleft(event)
        canonical_car_id = (
            event.car_id
            if isinstance(event.car_id, int)
            and self._is_canonical_car_id(event.car_id)
            else None
        )

        if canonical_car_id is not None and event.event_type in {
            EventType.LAP,
            EventType.FUEL,
            EventType.PITLANE,
            EventType.SPEED,
            EventType.CONTROLLER_INPUT,
        }:
            self._active_detector.observe(canonical_car_id, event.timestamp_monotonic_ms)

        if event.event_type is EventType.LAP:
            self._processed_lap_events += 1
            self._last_lap_payload = dict(event.payload)
            if canonical_car_id is None:
                self._dropped_lap_events += 1
                return
            lap_number_raw = event.payload.get("lap_number")
            lap_time_ms_raw = event.payload.get("lap_time_ms")
            if lap_number_raw is None or lap_time_ms_raw is None:
                self._dropped_lap_events += 1
                return
            try:
                lap_number = int(lap_number_raw)
                lap_time_ms = int(lap_time_ms_raw)
            except (TypeError, ValueError):
                self._dropped_lap_events += 1
                return
            if lap_number < 1 or lap_time_ms < 0:
                self._dropped_lap_events += 1
                return
            car = self._car(canonical_car_id)
            car.lap_count = max(car.lap_count, lap_number)
            car.latest_lap_ms = lap_time_ms
            car.best_lap_ms = update_best_lap(car.best_lap_ms, lap_time_ms)
            car.lap_samples += 1
            car.lap_total_ms += lap_time_ms
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.FUEL and canonical_car_id is not None:
            car = self._car(canonical_car_id)
            car.fuel_percent = clamp_fuel(float(event.payload["level_percent"]))
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.PITLANE and canonical_car_id is not None:
            car = self._car(canonical_car_id)
            car.in_pit = bool(event.payload["in_pit"])
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.SPEED and canonical_car_id is not None:
            car = self._car(canonical_car_id)
            car.last_speed_kmh = max(0.0, float(event.payload["speed_kmh"]))
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.CONTROLLER_INPUT and canonical_car_id is not None:
            car = self._car(canonical_car_id)
            # Sanitize via clamp helpers (no field stored, but invariant doc).
            _ = clamp_unit(float(event.payload["throttle"]))
            _ = clamp_unit(float(event.payload["brake"]))
            car.last_event_at_ms = event.timestamp_monotonic_ms
        elif event.event_type is EventType.RACE_STATE:
            self._race_state = RaceState(event.payload["state"])
        elif event.event_type is EventType.CONNECTION_STATE:
            new_conn_state = ConnectionState(event.payload["state"])
            err = event.payload.get("error")
            reason = event.payload.get("reason")
            timeout_streak = event.payload.get("timeout_streak")
            desired_connected = event.payload.get("desired_connected")
            reconnect_attempts = event.payload.get("reconnect_attempts")
            last_rx_ms = event.payload.get("last_rx_monotonic_ms")
            raw_rssi = event.payload.get("rssi")
            if (
                new_conn_state is not self._connection.state
                or err != self._connection.last_error
                or reason != self._connection.reason
                or timeout_streak != self._connection.timeout_streak
                or desired_connected != self._connection.desired_connected
                or reconnect_attempts != self._connection.reconnect_attempts
                or last_rx_ms != self._connection.last_rx_monotonic_ms
            ):
                self._connection = ConnectionStateRecord(
                    state=new_conn_state,
                    since_ms=event.timestamp_monotonic_ms,
                    last_error=err,
                    event=(
                        event.payload.get("event")
                        if isinstance(event.payload.get("event"), str)
                        else None
                    ),
                    reason=reason if isinstance(reason, str) else None,
                    timeout_streak=(
                        timeout_streak if isinstance(timeout_streak, int) else None
                    ),
                    desired_connected=(
                        desired_connected if isinstance(desired_connected, bool) else False
                    ),
                    device_id=(
                        event.payload.get("device_id")
                        if isinstance(event.payload.get("device_id"), str)
                        else None
                    ),
                    device_name=(
                        event.payload.get("device_name")
                        if isinstance(event.payload.get("device_name"), str)
                        else None
                    ),
                    mac_address=(
                        event.payload.get("mac_address")
                        if isinstance(event.payload.get("mac_address"), str)
                        else None
                    ),
                    rssi=raw_rssi if isinstance(raw_rssi, int) else None,
                    connected_at=(
                        event.payload.get("connected_at")
                        if isinstance(event.payload.get("connected_at"), str)
                        else None
                    ),
                    disconnected_at=(
                        event.payload.get("disconnected_at")
                        if isinstance(event.payload.get("disconnected_at"), str)
                        else None
                    ),
                    last_seen_at=(
                        event.payload.get("last_seen_at")
                        if isinstance(event.payload.get("last_seen_at"), str)
                        else None
                    ),
                    last_rx_monotonic_ms=last_rx_ms if isinstance(last_rx_ms, int) else None,
                    reconnect_attempts=(
                        reconnect_attempts if isinstance(reconnect_attempts, int) else 0
                    ),
                )

    def snapshot(self) -> dict[str, Any]:
        """JSON-serializable dict written to `state.json`."""
        active = self._active_detector.snapshot(self._mono())
        cars = [self._car_to_dict(c) for c in sorted(self._cars.values(), key=lambda c: c.car_id)]
        race_metrics = self._build_race_metrics(cars)
        return {
            "taken_at_iso": utils.now_iso().isoformat(),
            "taken_at_monotonic_ms": self._mono(),
            "connection": {
                "state": self._connection.state.value,
                "since_ms": self._connection.since_ms,
                "last_error": self._connection.last_error,
                "event": self._connection.event,
                "reason": self._connection.reason,
                "timeout_streak": self._connection.timeout_streak,
                "desired_connected": self._connection.desired_connected,
                "device_id": self._connection.device_id,
                "device_name": self._connection.device_name,
                "mac_address": self._connection.mac_address,
                "rssi": self._connection.rssi,
                "connected_at": self._connection.connected_at,
                "disconnected_at": self._connection.disconnected_at,
                "last_seen_at": self._connection.last_seen_at,
                "last_rx_monotonic_ms": self._connection.last_rx_monotonic_ms,
                "reconnect_attempts": self._connection.reconnect_attempts,
            },
            "race": self._race_state.value,
            "race_metrics": race_metrics,
            "active_car_ids": active["active_car_ids"],
            "active_car_count": active["active_car_count"],
            "active_car_window_ms": active["window_ms"],
            "cars": cars,
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
    def _is_canonical_car_id(car_id: int) -> bool:
        return _CANONICAL_MIN_CAR_ID <= car_id <= _CANONICAL_MAX_CAR_ID

    @staticmethod
    def _car_to_dict(car: CarState) -> dict[str, Any]:
        average_lap_ms: float | None = None
        if car.lap_samples > 0:
            average_lap_ms = float(car.lap_total_ms) / float(car.lap_samples)
        out = asdict(car)
        out["average_lap_ms"] = average_lap_ms
        out["pit_active"] = bool(car.in_pit)
        out["speed_kmh"] = car.last_speed_kmh
        out["driver_name"] = None
        out["position"] = None
        return out

    def _build_race_metrics(self, cars: list[dict[str, Any]]) -> dict[str, Any]:
        def _car_sort_key(car: dict[str, Any]) -> tuple[int, int, int]:
            best_lap = car.get("best_lap_ms")
            best_lap_key = int(best_lap) if isinstance(best_lap, (int, float)) else 10**12
            return (
                -int(car.get("lap_count", 0) or 0),
                best_lap_key,
                int(car.get("car_id", 0) or 0),
            )

        ranked = sorted(
            cars,
            key=_car_sort_key,
        )
        for idx, car in enumerate(ranked, start=1):
            car["position"] = idx

        best_values: list[int] = []
        for car in ranked:
            best_lap = car.get("best_lap_ms")
            if isinstance(best_lap, (int, float)):
                best_values.append(int(best_lap))
        leader_car_id = ranked[0]["car_id"] if ranked else None

        return {
            "race": {
                "id": None,
                "name": None,
                "status": self._race_state.value,
                "mode": None,
                "elapsed_ms": None,
                "progress_percent": None,
                "leader_car_id": leader_car_id,
                "fastest_lap_ms": min(best_values) if best_values else None,
                "total_laps": int(sum(int(c.get("lap_count", 0) or 0) for c in ranked)),
                "safety_car_active": None,
            },
            "cars": ranked,
            "diagnostics": {
                "last_telemetry_at_iso": self._last_telemetry_at_iso,
                "last_state_update_at_iso": self._last_state_update_at_iso,
                "active_race_id": None,
                "processed_lap_events": self._processed_lap_events,
                "cars_in_snapshot": [int(c["car_id"]) for c in ranked],
                "last_lap_payload": self._last_lap_payload,
                "dropped_lap_events": self._dropped_lap_events,
            },
        }

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
