"""US2: repeat_race service method (T032)."""

from __future__ import annotations

from src.schemas.race_schema import (
    DriverAssignment,
    DurationUnit,
    RaceCreate,
    RaceMode,
    RaceStatus,
)
from src.services.race_service import RaceService


def test_repeat_fixed_laps(engine):
    svc = RaceService()
    source = svc.create_race(
        RaceCreate(
            name="Source",
            mode=RaceMode.FIXED_LAPS,
            lap_target=15,
            driver_count=2,
            drivers=[
                DriverAssignment(car_id=1, driver_name="Alpha"),
                DriverAssignment(car_id=2, driver_name="Beta"),
            ],
            notes="orig",
        )
    )
    svc.start_race(source.id)
    svc.finish_race(source.id)

    clone = svc.repeat_race(source.id, new_name="Clone")
    assert clone.id != source.id
    assert clone.name == "Clone"
    assert clone.source_race_id == source.id
    assert clone.lap_target == 15
    assert clone.driver_count == 2
    assert clone.status is RaceStatus.DRAFT
    assert {(d.car_id, d.driver_name) for d in clone.drivers} == {
        (1, "Alpha"),
        (2, "Beta"),
    }


def test_repeat_fixed_duration_preserves_seconds(engine):
    svc = RaceService()
    source = svc.create_race(
        RaceCreate(
            name="Source",
            mode=RaceMode.FIXED_DURATION,
            duration_value=2,
            duration_unit=DurationUnit.MINUTES,
            driver_count=1,
            drivers=[DriverAssignment(car_id=1, driver_name="A")],
        )
    )
    clone = svc.repeat_race(source.id)
    assert clone.duration_seconds == source.duration_seconds == 120
    assert clone.mode is RaceMode.FIXED_DURATION


def test_repeat_default_name(engine):
    svc = RaceService()
    source = svc.create_race(
        RaceCreate(
            name="Original",
            mode=RaceMode.FIXED_LAPS,
            lap_target=5,
            driver_count=1,
            drivers=[DriverAssignment(car_id=1, driver_name="A")],
        )
    )
    clone = svc.repeat_race(source.id)
    assert clone.name == "Original (copy)"
