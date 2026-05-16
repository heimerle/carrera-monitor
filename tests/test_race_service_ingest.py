"""Lap/event ingest tests (T027)."""

from __future__ import annotations

from datetime import UTC, datetime

from src.config import RaceManagementConfig
from src.database import SessionLocal
from src.event_model import EventType, TelemetryEvent
from src.models import RaceEvent, RaceLap
from src.race_context import ActiveRaceContext
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
    RaceStatus,
)
from src.services.race_service import RaceService


def _payload(name="R", lap_target=10):
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=lap_target,
        driver_count=2,
        drivers=[
            DriverAssignment(car_id=1, driver_name="A"),
            DriverAssignment(car_id=2, driver_name="B"),
        ],
    )


def _lap(
    car_id: int,
    lap_number: int,
    lap_time_ms: int = 8000,
    *,
    cu_timestamp_ms: int | None = None,
) -> TelemetryEvent:
    payload = {"lap_number": lap_number, "lap_time_ms": lap_time_ms}
    if cu_timestamp_ms is not None:
        payload["cu_timestamp_ms"] = cu_timestamp_ms
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=lap_number * 1000,
        source="mock",
        event_type=EventType.LAP,
        car_id=car_id,
        payload=payload,
    )


def test_record_lap_persists(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.record_lap(_lap(1, 1))
    svc.record_lap(_lap(2, 1))
    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 2


def test_record_lap_replayed_crossing_is_idempotent(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)

    svc.record_lap(_lap(1, 1, cu_timestamp_ms=10_000))
    svc.record_lap(_lap(1, 1, cu_timestamp_ms=10_000))

    with SessionLocal() as s:
        rows = (
            s.query(RaceLap)
            .filter(RaceLap.race_id == r.id, RaceLap.car_id == 1)
            .order_by(RaceLap.lap_number)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].lap_number == 1


def test_record_lap_dropped_when_paused(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.pause_race(r.id)
    svc.record_lap(_lap(1, 1))
    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 0


def test_record_lap_ignored_when_no_active_race(engine):
    svc = RaceService()
    assert ActiveRaceContext.get() is None
    # Should not raise.
    svc.record_lap(_lap(1, 1))
    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 0


def test_record_lap_unknown_car_dropped(engine, caplog):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.record_lap(_lap(5, 1))  # car_id 5 not in race
    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 0


def test_auto_finish_on_leader_lap_target(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=3))
    svc.start_race(r.id)
    for n in range(1, 3):
        svc.record_lap(_lap(1, n))
    assert svc.get_race(r.id).status is RaceStatus.RUNNING
    svc.record_lap(_lap(1, 3))  # leader hits target → auto-finish
    assert svc.get_race(r.id).status is RaceStatus.FINISHED


def test_record_event_persists_when_enabled(engine):
    svc = RaceService(config=RaceManagementConfig(persist_all_events=True))
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    ev = TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=10,
        source="mock",
        event_type=EventType.FUEL,
        car_id=1,
        payload={"level_percent": 75.0},
    )
    before = _count_fuel_events()
    svc.record_event(ev)
    assert _count_fuel_events() == before + 1


def _count_fuel_events() -> int:
    with SessionLocal() as s:
        return (
            s.query(RaceEvent).filter(RaceEvent.event_type == "fuel").count()
        )


def test_record_event_dropped_when_disabled(engine):
    svc = RaceService(config=RaceManagementConfig(persist_all_events=False))
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    ev = TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=10,
        source="mock",
        event_type=EventType.FUEL,
        car_id=1,
        payload={"level_percent": 75.0},
    )
    svc.record_event(ev)
    with SessionLocal() as s:
        assert s.query(RaceEvent).filter(RaceEvent.event_type == "fuel").count() == 0
