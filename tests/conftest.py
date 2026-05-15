"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from src import utils
from src.event_model import EventType, TelemetryEvent


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, int]]:
    """Freeze `utils.now_iso` and `utils.now_monotonic_ms` to deterministic values.

    The returned dict can be mutated by tests to advance the clock:
        clock["mono_ms"] += 100
    """
    state = {"mono_ms": 0, "iso_epoch": 1_700_000_000}

    def fake_mono() -> int:
        return int(state["mono_ms"])

    def fake_iso() -> datetime:
        return datetime.fromtimestamp(state["iso_epoch"], tz=timezone.utc)

    monkeypatch.setattr(utils, "now_monotonic_ms", fake_mono)
    monkeypatch.setattr(utils, "now_iso", fake_iso)
    yield state


@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def event_factory():
    """Build a valid `TelemetryEvent` with sensible defaults; override via kwargs."""

    def _make(
        event_type: EventType = EventType.LAP,
        car_id: int | None = 1,
        payload: dict[str, Any] | None = None,
        source: str = "mock",
        monotonic_ms: int = 0,
        iso: datetime | None = None,
        **extra: Any,
    ) -> TelemetryEvent:
        if payload is None:
            payload = _default_payload(event_type)
        return TelemetryEvent(
            timestamp_iso=iso or datetime.now(tz=timezone.utc),
            timestamp_monotonic_ms=monotonic_ms,
            source=source,  # type: ignore[arg-type]
            event_type=event_type,
            car_id=car_id,
            payload=payload,
            **extra,
        )

    return _make


def _default_payload(event_type: EventType) -> dict[str, Any]:
    match event_type:
        case EventType.LAP:
            return {"lap_number": 1, "lap_time_ms": 8000}
        case EventType.RACE_STATE:
            return {"state": "running"}
        case EventType.FUEL:
            return {"level_percent": 50.0}
        case EventType.CONTROLLER_INPUT:
            return {"throttle": 0.5, "brake": 0.0}
        case EventType.SPEED:
            return {"speed_kmh": 42.0}
        case EventType.BRAKE:
            return {"brake": 0.3}
        case EventType.PITLANE:
            return {"in_pit": False, "reason": "manual"}
        case EventType.CONNECTION_STATE:
            return {"state": "connected", "error": None}
        case EventType.NOT_SUPPORTED:
            return {"reason": "test"}
        case EventType.RAW:
            return {}
    return {}
