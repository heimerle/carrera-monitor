"""RaceTelemetryRunner tests (T028)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from src.database import SessionLocal
from src.event_bus import EventBus
from src.event_model import EventType, TelemetryEvent
from src.models import RaceLap
from src.race_runner import RaceTelemetryRunner
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
    RaceStatus,
)
from src.services.race_service import RaceService


def _payload(name="R"):
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=5,
        driver_count=1,
        drivers=[DriverAssignment(car_id=1, driver_name="A")],
    )


def _lap_event(lap_number: int) -> TelemetryEvent:
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=lap_number * 1000,
        source="mock",
        event_type=EventType.LAP,
        car_id=1,
        payload={"lap_number": lap_number, "lap_time_ms": 8000},
    )


@pytest.mark.asyncio
async def test_runner_persists_laps(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)

    bus = EventBus()
    runner = RaceTelemetryRunner(bus, svc, persist_all_events=False)
    await runner.start()
    try:
        await bus.publish(_lap_event(1))
        await bus.publish(_lap_event(2))
        await asyncio.sleep(0.2)
    finally:
        await runner.stop()
        await bus.close()

    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 2


@pytest.mark.asyncio
async def test_runner_ignores_when_no_active_race(engine):
    svc = RaceService()
    bus = EventBus()
    runner = RaceTelemetryRunner(bus, svc, persist_all_events=False)
    await runner.start()
    try:
        await bus.publish(_lap_event(1))
        await asyncio.sleep(0.1)
    finally:
        await runner.stop()
        await bus.close()
    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 0


@pytest.mark.asyncio
async def test_fixed_duration_ticker_auto_finishes(engine):
    from datetime import timedelta

    from src.schemas.race_schema import DurationUnit

    svc = RaceService()
    r = svc.create_race(
        RaceCreate(
            name="dur",
            mode=RaceMode.FIXED_DURATION,
            duration_value=1,
            duration_unit=DurationUnit.MINUTES,
            driver_count=1,
            drivers=[DriverAssignment(car_id=1, driver_name="A")],
        )
    )
    svc.start_race(r.id)

    # Synthetic clock far in the future so the ticker fires immediately.
    started = svc.get_race(r.id).started_at
    assert started is not None
    future = started + timedelta(seconds=120)

    bus = EventBus()
    runner = RaceTelemetryRunner(
        bus,
        svc,
        persist_all_events=False,
        ticker_interval_s=0.05,
        clock=lambda: future,
    )
    await runner.start()
    try:
        await asyncio.sleep(0.3)
    finally:
        await runner.stop()
        await bus.close()

    assert svc.get_race(r.id).status is RaceStatus.FINISHED
