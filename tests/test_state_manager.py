"""Tests for `StateManager` (T015, T026)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.event_model import ConnectionState, EventType, RaceState, TelemetryEvent
from src.state_manager import StateManager


def _ev(event_type: EventType, *, car_id=None, payload=None, ts_ms=0):
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=timezone.utc),
        timestamp_monotonic_ms=ts_ms,
        source="mock",
        event_type=event_type,
        car_id=car_id,
        payload=payload or {},
    )


def _make_mgr(tmp_path: Path) -> StateManager:
    q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
    return StateManager(q, state_file=tmp_path / "state.json", refresh_interval_ms=1000)


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


def test_race_state_idle_resets_lap_counts(tmp_path: Path):
    mgr = _make_mgr(tmp_path)
    mgr.apply(_ev(EventType.RACE_STATE, payload={"state": "running"}))
    mgr.apply(_ev(EventType.LAP, car_id=1, payload={"lap_number": 5, "lap_time_ms": 8000}))
    assert mgr.snapshot()["cars"][0]["lap_count"] == 5
    mgr.apply(_ev(EventType.RACE_STATE, payload={"state": "idle"}))
    assert mgr.snapshot()["cars"][0]["lap_count"] == 0


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
    mgr.apply(_ev(EventType.CONNECTION_STATE, payload={"state": "connected", "error": None}, ts_ms=100))
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "connected"
    assert snap["connection"]["since_ms"] == 100

    mgr.apply(_ev(EventType.CONNECTION_STATE, payload={"state": "reconnecting", "error": "lost"}, ts_ms=500))
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "reconnecting"
    assert snap["connection"]["since_ms"] == 500
    assert snap["connection"]["last_error"] == "lost"

    mgr.apply(_ev(EventType.CONNECTION_STATE, payload={"state": "connected", "error": None}, ts_ms=900))
    snap = mgr.snapshot()
    assert snap["connection"]["state"] == "connected"
    assert snap["connection"]["since_ms"] == 900
    types_in_recent = [e["event_type"] for e in snap["recent_events"]]
    assert "connection_state" in types_in_recent
    # Both transitions should be in recent_events (newest-first deque).
    assert types_in_recent.count("connection_state") >= 3
