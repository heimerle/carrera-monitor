"""Auto-snapshot of race_summary on finish/cancel (T038)."""

from __future__ import annotations

from datetime import UTC, datetime

from src.event_model import EventType, TelemetryEvent
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
)
from src.services.race_service import RaceService
from src.services.reporting_service import ReportingService


def _payload(name="R"):
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=10,
        driver_count=1,
        drivers=[DriverAssignment(car_id=1, driver_name="A")],
    )


def _lap(n: int) -> TelemetryEvent:
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=n * 1000,
        source="mock",
        event_type=EventType.LAP,
        car_id=1,
        payload={"lap_number": n, "lap_time_ms": 8000},
    )


def test_finish_creates_summary_snapshot(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.record_lap(_lap(1))
    svc.finish_race(r.id)
    rep = ReportingService(race_service=svc)
    reports = rep.list_reports(r.id)
    assert any(rr.report_type == "race_summary" for rr in reports)


def test_cancel_with_laps_creates_snapshot(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.record_lap(_lap(1))
    svc.cancel_race(r.id)
    rep = ReportingService(race_service=svc)
    reports = rep.list_reports(r.id)
    assert any(rr.report_type == "race_summary" for rr in reports)


def test_cancel_without_laps_no_snapshot(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.cancel_race(r.id)
    rep = ReportingService(race_service=svc)
    assert rep.list_reports(r.id) == []
