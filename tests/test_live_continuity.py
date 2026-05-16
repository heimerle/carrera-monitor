"""Reconnect/startup continuity regression coverage for hardening tasks."""

from __future__ import annotations

from datetime import UTC, datetime

from src.database import SessionLocal
from src.event_model import EventType, TelemetryEvent
from src.models import RaceLap, RaceLapCheckpoint
from src.race_context import ActiveRaceContext
from src.schemas.race_schema import DriverAssignment, RaceCreate, RaceMode
from src.services.race_service import RaceService


def _payload(name="R"):
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=10,
        driver_count=1,
        drivers=[DriverAssignment(car_id=1, driver_name="A")],
    )


def _lap(cu_timestamp_ms: int, lap_time_ms: int = 8000) -> TelemetryEvent:
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=cu_timestamp_ms,
        source="mock",
        event_type=EventType.LAP,
        car_id=1,
        payload={
            "lap_number": 1,
            "lap_time_ms": lap_time_ms,
            "cu_timestamp_ms": cu_timestamp_ms,
        },
    )


def test_continuity_harness_checkpoint_seed_and_update(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)

    svc.record_lap(_lap(10_000, lap_time_ms=7_900))

    with SessionLocal() as s:
        checkpoint = (
            s.query(RaceLapCheckpoint)
            .filter(RaceLapCheckpoint.race_id == race.id, RaceLapCheckpoint.car_id == 1)
            .one()
        )
        assert checkpoint.lap_count == 1
        assert checkpoint.last_cu_timestamp_ms == 10_000


def test_reconnect_lap_continuity_regression(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)

    # First crossing is stored.
    svc.record_lap(_lap(20_000, lap_time_ms=8_100))

    # Simulate reconnect replay: same crossing arrives again.
    svc.record_lap(_lap(20_000, lap_time_ms=8_100))

    # New crossing after reconnect continues lap numbering.
    svc.record_lap(_lap(28_200, lap_time_ms=8_200))

    with SessionLocal() as s:
        laps = (
            s.query(RaceLap)
            .filter(RaceLap.race_id == race.id, RaceLap.car_id == 1)
            .order_by(RaceLap.lap_number)
            .all()
        )
        assert [row.lap_number for row in laps] == [1, 2]

        checkpoint = (
            s.query(RaceLapCheckpoint)
            .filter(RaceLapCheckpoint.race_id == race.id, RaceLapCheckpoint.car_id == 1)
            .one()
        )
        assert checkpoint.lap_count == 2
        assert checkpoint.last_cu_timestamp_ms == 28_200

    ActiveRaceContext.clear()
