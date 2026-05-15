"""ReportingService tests + perf assertion (T037)."""

from __future__ import annotations

import csv
import io
import time
from datetime import UTC, datetime

from src.database import SessionLocal
from src.event_model import EventType, TelemetryEvent
from src.repositories.race_repository import RaceRepository
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
)
from src.services.race_service import RaceService
from src.services.reporting_service import ReportingService


def _payload(name="R", lap_target=1000):
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


def _lap(car_id: int, lap_number: int, ms: int) -> TelemetryEvent:
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=lap_number * 1000,
        source="mock",
        event_type=EventType.LAP,
        car_id=car_id,
        payload={"lap_number": lap_number, "lap_time_ms": ms},
    )


def test_driver_stats_basic(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=10))
    svc.start_race(r.id)
    for n in range(1, 4):
        svc.record_lap(_lap(1, n, 8000 + n))
    svc.record_lap(_lap(2, 1, 9000))
    rep = ReportingService(race_service=svc)
    stats = rep.driver_stats(r.id)
    by_car = {s.car_id: s for s in stats}
    assert by_car[1].total_laps == 3
    assert by_car[1].best_lap_ms == 8001
    assert by_car[1].average_lap_ms == 8002
    assert by_car[1].total_race_time_ms == 8001 + 8002 + 8003
    assert by_car[1].last_lap_ms == 8003
    assert by_car[2].total_laps == 1


def test_final_standings_sort_and_gap(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=10))
    svc.start_race(r.id)
    # Car 2 has more laps → leader.
    svc.record_lap(_lap(1, 1, 8000))
    svc.record_lap(_lap(2, 1, 7000))
    svc.record_lap(_lap(2, 2, 7500))
    rep = ReportingService(race_service=svc)
    rows = rep.final_standings(r.id)
    assert rows[0].car_id == 2
    assert rows[0].position == 1
    assert rows[0].laps_behind == 0
    assert rows[0].gap_to_leader_ms == 0
    assert rows[1].laps_behind == 1
    assert rows[1].gap_to_leader_ms is None  # laps_behind > 0


def test_final_standings_empty_when_no_laps(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=10))
    svc.start_race(r.id)
    rep = ReportingService(race_service=svc)
    assert rep.final_standings(r.id) == []


def test_race_summary_duration_ms(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=10))
    svc.start_race(r.id)
    svc.finish_race(r.id)
    rep = ReportingService(race_service=svc)
    summary = rep.race_summary(r.id)
    assert summary.duration_ms is not None
    assert summary.duration_ms >= 0


def test_csv_exports(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=10))
    svc.start_race(r.id)
    svc.record_lap(_lap(1, 1, 8000))
    svc.record_lap(_lap(2, 1, 9000))
    rep = ReportingService(race_service=svc)
    summary_csv = rep.export_summary_csv(r.id).decode("utf-8")
    rows = list(csv.reader(io.StringIO(summary_csv)))
    assert rows[0][:4] == ["position", "car_id", "driver_name", "lap_count"]
    assert len(rows) == 3  # header + 2 drivers

    laps_csv = rep.export_laps_csv(r.id).decode("utf-8")
    rows = list(csv.reader(io.StringIO(laps_csv)))
    assert rows[0] == [
        "car_id",
        "driver_name",
        "lap_number",
        "lap_time_ms",
        "timestamp_iso",
    ]
    assert len(rows) == 3


def test_save_and_list_reports(engine):
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=10))
    rep = ReportingService(race_service=svc)
    rep.save_report(r.id, "custom", {"x": 1})
    reports = rep.list_reports(r.id)
    assert any(rr.report_type == "custom" for rr in reports)


def test_reporting_perf_1000_laps(engine):
    """SC-105: report computation ≤500 ms for 1,000 laps."""
    svc = RaceService()
    r = svc.create_race(_payload(lap_target=2000))
    svc.start_race(r.id)
    repo = RaceRepository()
    now = datetime.now(tz=UTC)
    with SessionLocal() as s:
        for n in range(1, 501):
            repo.add_lap(
                s,
                race_id=r.id,
                car_id=1,
                driver_name="A",
                lap_number=n,
                lap_time_ms=8000 + (n % 50),
                timestamp_iso=now,
            )
            repo.add_lap(
                s,
                race_id=r.id,
                car_id=2,
                driver_name="B",
                lap_number=n,
                lap_time_ms=8500 + (n % 50),
                timestamp_iso=now,
            )
        s.commit()
    rep = ReportingService(race_service=svc)
    start = time.perf_counter()
    summary = rep.race_summary(r.id)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(summary.standings) == 2
    assert elapsed_ms < 500, f"race_summary took {elapsed_ms:.1f} ms (>500)"
