"""CRUD via RaceService (T025)."""

from __future__ import annotations

import pytest

from src.config import RaceManagementConfig
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
    RaceStatus,
    RaceUpdate,
)
from src.services import (
    InvalidRaceStateError,
    RaceNotEditableError,
    RaceNotFoundError,
)
from src.services.race_service import RaceService


def _payload(name="R", drivers=None):
    if drivers is None:
        drivers = [DriverAssignment(car_id=1, driver_name="A")]
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=10,
        driver_count=len(drivers),
        drivers=drivers,
    )


def test_create_get_list(engine):
    svc = RaceService()
    race = svc.create_race(_payload("R1"))
    assert race.id > 0
    assert race.status is RaceStatus.DRAFT
    fetched = svc.get_race(race.id)
    assert fetched.name == "R1"
    assert any(r.id == race.id for r in svc.list_races())


def test_get_missing_race_raises(engine):
    svc = RaceService()
    with pytest.raises(RaceNotFoundError):
        svc.get_race(9999)


def test_delete_race(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.delete_race(r.id)
    with pytest.raises(RaceNotFoundError):
        svc.get_race(r.id)


def test_update_draft_race(engine):
    svc = RaceService()
    r = svc.create_race(_payload("R1"))
    upd = RaceUpdate(
        name="R1-renamed",
        mode=RaceMode.FIXED_LAPS,
        lap_target=20,
        driver_count=2,
        drivers=[
            DriverAssignment(car_id=1, driver_name="Alpha"),
            DriverAssignment(car_id=2, driver_name="Beta"),
        ],
    )
    updated = svc.update_race(r.id, upd)
    assert updated.name == "R1-renamed"
    assert updated.lap_target == 20
    assert len(updated.drivers) == 2


def test_update_running_race_blocked_by_default(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    with pytest.raises(RaceNotEditableError):
        svc.update_race(
            r.id,
            RaceUpdate(
                name="x",
                mode=RaceMode.FIXED_LAPS,
                lap_target=5,
                driver_count=1,
                drivers=[DriverAssignment(car_id=1, driver_name="X")],
            ),
        )


def test_update_running_race_allowed_via_config(engine):
    svc = RaceService(config=RaceManagementConfig(allow_edit_running_race=True))
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    updated = svc.update_race(
        r.id,
        RaceUpdate(
            name="renamed",
            mode=RaceMode.FIXED_LAPS,
            lap_target=10,
            driver_count=1,
            drivers=[DriverAssignment(car_id=1, driver_name="A")],
        ),
    )
    assert updated.name == "renamed"


def test_delete_running_race_blocked(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    with pytest.raises(InvalidRaceStateError):
        svc.delete_race(r.id)
