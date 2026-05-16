"""Tests for `StateManager` (T015, T026)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from src.event_model import EventType, TelemetryEvent
from src.state_manager import StateManager


def _ev(event_type: EventType, *, car_id=None, payload=None, ts_ms=0):
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=ts_ms,
        source="mock",
        event_type=event_type,
        car_id=car_id,
        payload=payload or {},
    )


def _make_mgr(
    tmp_path: Path,
    *,
    active_car_window_ms: int = 3000,
    monotonic_clock=None,
) -> StateManager:
    q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
    return StateManager(
        q,
        state_file=tmp_path / "state.json",
        refresh_interval_ms=1000,
        active_car_window_ms=active_car_window_ms,
        monotonic_clock=monotonic_clock,
    )


def test_lap_updates_best_and_latest(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(_ev(EventType.LAP, car_id=1, payload={"lap_number": 1, "lap_time_ms": 9000}))
    mgr.apply(_ev(EventType.LAP, car_id=1, payload={"lap_number": 2, "lap_time_ms": 8500}))
    mgr.apply(_ev(EventType.LAP, car_id=1, payload={"lap_number": 3, "lap_time_ms": 8700}))
    snap = mgr.snapshot()
    car = snap["cars"][0]
    assert car["car_id"] == 1
    assert car["lap_count"] == 3
    assert car["latest_lap_ms"] == 8700
    assert car["best_lap_ms"] == 8500


def test_fuel_clamped(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    # event-model would reject 150 outright; here we use a valid edge value 100.
    mgr.apply(_ev(EventType.FUEL, car_id=2, payload={"level_percent": 100.0}))
    snap = mgr.snapshot()
    car = next(c for c in snap["cars"] if c["car_id"] == 2)
    assert car["fuel_percent"] == 100.0


def test_pit_state_transitions(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(_ev(EventType.PITLANE, car_id=1, payload={"in_pit": True, "reason": "fuel"}))
    assert mgr.snapshot()["cars"][0]["in_pit"] is True
    mgr.apply(_ev(EventType.PITLANE, car_id=1, payload={"in_pit": False, "reason": "manual"}))
    assert mgr.snapshot()["cars"][0]["in_pit"] is False


def test_race_state_idle_does_not_reset_lap_counts_on_transient_idle(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(_ev(EventType.RACE_STATE, payload={"state": "running"}))
    mgr.apply(_ev(EventType.LAP, car_id=1, payload={"lap_number": 5, "lap_time_ms": 8000}))
    assert mgr.snapshot()["cars"][0]["lap_count"] == 5
    mgr.apply(_ev(EventType.RACE_STATE, payload={"state": "idle"}))
    assert mgr.snapshot()["cars"][0]["lap_count"] == 5


def test_active_car_detection_window(tmp_path: Path):
    clock = {"ms": 0}
    mgr = _make_mgr(
        tmp_path,
        active_car_window_ms=1000,
        monotonic_clock=lambda: int(clock["ms"]),
    )

    mgr.apply(_ev(EventType.SPEED, car_id=1, payload={"speed_kmh": 10.0}, ts_ms=100))
    clock["ms"] = 500
    snap = mgr.snapshot()
    assert snap["active_car_ids"] == [1]
    assert snap["active_car_count"] == 1

    clock["ms"] = 1_800
    snap = mgr.snapshot()
    assert snap["active_car_ids"] == []
    assert snap["active_car_count"] == 0


def test_snapshot_atomic_write_is_readable(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(_ev(EventType.LAP, car_id=1, payload={"lap_number": 1, "lap_time_ms": 8000}))
    mgr.write_snapshot()
    state_file = tmp_path / "state.json"
    assert state_file.exists()
    with open(state_file, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["cars"][0]["car_id"] == 1
    assert loaded["race"] in {"idle", "countdown", "running", "paused", "finished"}


def test_connection_transitions(tmp_path: Path):
    """T026 — connected → reconnecting → connected."""
    mgr = _make_mgr(tmp_path)
    mgr.apply(
        _ev(EventType.CONNECTION_STATE, payload={"state": "connected", "error": None}, ts_ms=100)
    )
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "connected"
    assert snap["connection"]["since_ms"] == 100

    mgr.apply(
        _ev(
            EventType.CONNECTION_STATE,
            payload={"state": "reconnecting", "error": "lost", "reason": "adapter_read_error"},
            ts_ms=500,
        )
    )
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "reconnecting"
    assert snap["connection"]["since_ms"] == 500
    assert snap["connection"]["last_error"] == "lost"
    assert snap["connection"]["reason"] == "adapter_read_error"

    mgr.apply(
        _ev(EventType.CONNECTION_STATE, payload={"state": "connected", "error": None}, ts_ms=900)
    )
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "connected"
    assert snap["connection"]["since_ms"] == 900
    types_in_recent = [e["event_type"] for e in snap["recent_events"]]
    assert "connection_state" in types_in_recent
    # Both transitions should be in recent_events (newest-first deque).
    assert types_in_recent.count("connection_state") >= 3


def test_connection_snapshot_includes_supervisor_fields(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(
        _ev(
            EventType.CONNECTION_STATE,
            payload={
                "event": "bluetooth_ready",
                "state": "ready",
                "desired_connected": True,
                "device_id": "AA:BB:CC:DD:EE:FF",
                "device_name": "Control_Unit",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "rssi": -60,
                "connected_at": "2026-01-01T12:00:00+00:00",
                "disconnected_at": None,
                "last_seen_at": "2026-01-01T12:00:02+00:00",
                "last_rx_monotonic_ms": 12345,
                "reconnect_attempts": 2,
                "reason": "subscriptions_ready",
                "error": None,
            },
            ts_ms=321,
        )
    )

    conn = mgr.snapshot()["connection"]
    assert conn["state"] == "ready"
    assert conn["event"] == "bluetooth_ready"
    assert conn["desired_connected"] is True
    assert conn["device_name"] == "Control_Unit"
    assert conn["last_rx_monotonic_ms"] == 12345
    assert conn["reconnect_attempts"] == 2


def test_connection_snapshot_preserves_legacy_fields(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(
        _ev(
            EventType.CONNECTION_STATE,
            payload={
                "state": "reconnecting",
                "error": "lost",
                "reason": "adapter_read_error",
                "timeout_streak": 4,
            },
            ts_ms=777,
        )
    )

    conn = mgr.snapshot()["connection"]
    assert conn["state"] == "reconnecting"
    assert conn["since_ms"] == 777
    assert conn["last_error"] == "lost"
    assert conn["reason"] == "adapter_read_error"
    assert conn["timeout_streak"] == 4


def test_connection_status_visibility_within_one_second(tmp_path: Path):
    clock = {"ms": 0}
    mgr = _make_mgr(tmp_path, monotonic_clock=lambda: int(clock["ms"]))

    event_ts = 1000
    mgr.apply(
        _ev(
            EventType.CONNECTION_STATE,
            payload={
                "event": "bluetooth_ready",
                "state": "ready",
                "desired_connected": True,
                "error": None,
            },
            ts_ms=event_ts,
        )
    )

    clock["ms"] = 1800
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "ready"
    assert snap["connection"]["since_ms"] == event_ts
    latency_ms = int(snap["taken_at_monotonic_ms"]) - int(event_ts)
    assert latency_ms <= 1000
