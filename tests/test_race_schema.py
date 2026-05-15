"""Cross-field validation tests for `RaceCreate` (T012)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.race_schema import (
    DriverAssignment,
    DurationUnit,
    RaceCreate,
    RaceMode,
)


def _drivers(*pairs):
    return [DriverAssignment(car_id=c, driver_name=n) for c, n in pairs]


def test_valid_two_driver_fixed_laps():
    payload = RaceCreate(
        name="R1",
        mode=RaceMode.FIXED_LAPS,
        lap_target=10,
        driver_count=2,
        drivers=_drivers((1, "A"), (2, "B")),
    )
    assert payload.lap_target == 10
    assert payload.duration_seconds is None


def test_fixed_laps_without_lap_target_rejected():
    with pytest.raises(ValidationError, match="lap_target is required"):
        RaceCreate(
            name="R", mode=RaceMode.FIXED_LAPS, driver_count=1,
            drivers=_drivers((1, "A")),
        )


def test_fixed_duration_without_duration_rejected():
    with pytest.raises(ValidationError, match="duration_value and duration_unit"):
        RaceCreate(
            name="R", mode=RaceMode.FIXED_DURATION, driver_count=1,
            drivers=_drivers((1, "A")),
        )


def test_fixed_duration_seconds_minutes():
    payload = RaceCreate(
        name="R",
        mode=RaceMode.FIXED_DURATION,
        duration_value=15,
        duration_unit=DurationUnit.MINUTES,
        driver_count=1,
        drivers=_drivers((1, "A")),
    )
    assert payload.duration_seconds == 15 * 60


def test_fixed_duration_seconds_hours():
    payload = RaceCreate(
        name="R",
        mode=RaceMode.FIXED_DURATION,
        duration_value=2,
        duration_unit=DurationUnit.HOURS,
        driver_count=1,
        drivers=_drivers((1, "A")),
    )
    assert payload.duration_seconds == 7200


def test_duplicate_car_ids_rejected():
    with pytest.raises(ValidationError, match="duplicate car_id"):
        RaceCreate(
            name="R", mode=RaceMode.FIXED_LAPS, lap_target=5, driver_count=2,
            drivers=_drivers((1, "A"), (1, "B")),
        )


def test_driver_count_mismatch_rejected():
    with pytest.raises(ValidationError, match="drivers length"):
        RaceCreate(
            name="R", mode=RaceMode.FIXED_LAPS, lap_target=5, driver_count=3,
            drivers=_drivers((1, "A"), (2, "B")),
        )


def test_empty_driver_name_rejected():
    with pytest.raises(ValidationError):
        RaceCreate(
            name="R", mode=RaceMode.FIXED_LAPS, lap_target=5, driver_count=1,
            drivers=[DriverAssignment(car_id=1, driver_name="")],
        )


def test_lap_target_with_fixed_duration_rejected():
    with pytest.raises(ValidationError, match="lap_target must be null"):
        RaceCreate(
            name="R",
            mode=RaceMode.FIXED_DURATION,
            duration_value=10,
            duration_unit=DurationUnit.MINUTES,
            lap_target=5,
            driver_count=1,
            drivers=_drivers((1, "A")),
        )
