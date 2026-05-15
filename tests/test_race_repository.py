"""Repository tests — CRUD round-trip + cascade + unique constraints."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src._time import utcnow_naive
from src.database import SessionLocal
from src.models import RaceDriver, RaceEvent, RaceLap, RaceReport
from src.repositories.race_repository import RaceRepository
from src.schemas.race_schema import DriverAssignment, RaceCreate, RaceMode


@pytest.fixture
def repo():
    return RaceRepository()


def _make_payload(name="R"):
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=5,
        driver_count=2,
        drivers=[
            DriverAssignment(car_id=1, driver_name="A"),
            DriverAssignment(car_id=2, driver_name="B"),
        ],
    )


def test_create_and_get(engine, repo):
    with SessionLocal() as s:
        race = repo.create_race(s, _make_payload())
        s.commit()
        rid = race.id
    with SessionLocal() as s:
        fetched = repo.get_race(s, rid)
        assert fetched is not None
        assert fetched.name == "R"
        assert len(fetched.drivers) == 2


def test_list_orders_by_created_desc(engine, repo):
    with SessionLocal() as s:
        a = repo.create_race(s, _make_payload("A"))
        s.commit()
        b = repo.create_race(s, _make_payload("B"))
        s.commit()
    with SessionLocal() as s:
        races = repo.list_races(s)
        # Latest (b) first.
        assert [r.id for r in races[:2]] == [b.id, a.id]


def test_unique_race_car_constraint(engine, repo):
    with SessionLocal() as s:
        race = repo.create_race(s, _make_payload())
        s.commit()
        s.add(RaceDriver(race_id=race.id, car_id=1, driver_name="dup"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_cascade_delete_children(engine, repo):
    with SessionLocal() as s:
        race = repo.create_race(s, _make_payload())
        s.commit()
        rid = race.id
        repo.add_lap(
            s,
            race_id=rid,
            car_id=1,
            driver_name="A",
            lap_number=1,
            lap_time_ms=8000,
            timestamp_iso=utcnow_naive(),
        )
        repo.add_event(
            s,
            race_id=rid,
            timestamp_iso=utcnow_naive(),
            event_type="lap",
            car_id=1,
            payload={"x": 1},
        )
        repo.add_report(s, race_id=rid, report_type="race_summary", payload={"y": 2})
        s.commit()
    with SessionLocal() as s:
        race = repo.get_race(s, rid)
        repo.delete_race(s, race)
        s.commit()
    with SessionLocal() as s:
        assert s.query(RaceLap).count() == 0
        assert s.query(RaceEvent).count() == 0
        assert s.query(RaceReport).count() == 0
        assert s.query(RaceDriver).count() == 0


def test_set_status_and_timestamps(engine, repo):
    with SessionLocal() as s:
        race = repo.create_race(s, _make_payload())
        s.commit()
        rid = race.id
    now = utcnow_naive()
    with SessionLocal() as s:
        race = repo.get_race(s, rid)
        repo.set_status(s, race, "running")
        repo.set_timestamps(s, race, started_at=now)
        s.commit()
    with SessionLocal() as s:
        race = repo.get_race(s, rid)
        assert race.status == "running"
        assert race.started_at is not None


def test_lap_count_by_car(engine, repo):
    with SessionLocal() as s:
        race = repo.create_race(s, _make_payload())
        s.commit()
        rid = race.id
        for i in range(3):
            repo.add_lap(
                s,
                race_id=rid,
                car_id=1,
                driver_name="A",
                lap_number=i + 1,
                lap_time_ms=8000 + i,
                timestamp_iso=utcnow_naive(),
            )
        repo.add_lap(
            s,
            race_id=rid,
            car_id=2,
            driver_name="B",
            lap_number=1,
            lap_time_ms=9000,
            timestamp_iso=utcnow_naive(),
        )
        s.commit()
    with SessionLocal() as s:
        counts = repo.lap_count_by_car(s, rid)
        assert counts == {1: 3, 2: 1}
