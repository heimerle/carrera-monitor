"""Pydantic v2 DTOs for the race-management API surface.

Mirrors ``specs/001-race-management/data-model.md §3`` exactly. These
schemas are the boundary between the Streamlit UI / async pipeline and
the SQLAlchemy ORM in ``src.models``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RaceMode(StrEnum):
    FIXED_LAPS = "fixed_laps"
    FIXED_DURATION = "fixed_duration"


class DurationUnit(StrEnum):
    MINUTES = "minutes"
    HOURS = "hours"


class RaceStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class DriverAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    car_id: int = Field(ge=1, le=6)
    driver_name: str = Field(min_length=1, max_length=80)


class _RaceCommon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    mode: RaceMode
    lap_target: int | None = Field(default=None, ge=1)
    duration_value: int | None = Field(default=None, ge=1)
    duration_unit: DurationUnit | None = None
    driver_count: int = Field(ge=1, le=6)
    drivers: list[DriverAssignment]
    notes: str | None = None

    @model_validator(mode="after")
    def _consistency(self) -> _RaceCommon:
        # Mode <-> target/duration consistency.
        if self.mode is RaceMode.FIXED_LAPS:
            if self.lap_target is None:
                raise ValueError("lap_target is required when mode='fixed_laps'")
            if self.duration_value is not None:
                raise ValueError(
                    "duration_value must be null when mode='fixed_laps'"
                )
        elif self.mode is RaceMode.FIXED_DURATION:
            if self.duration_value is None or self.duration_unit is None:
                raise ValueError(
                    "duration_value and duration_unit are required when "
                    "mode='fixed_duration'"
                )
            if self.lap_target is not None:
                raise ValueError(
                    "lap_target must be null when mode='fixed_duration'"
                )
        # Driver-count consistency.
        if len(self.drivers) != self.driver_count:
            raise ValueError(
                f"drivers length {len(self.drivers)} != driver_count {self.driver_count}"
            )
        # Unique car_ids.
        car_ids = [d.car_id for d in self.drivers]
        if len(set(car_ids)) != len(car_ids):
            raise ValueError(f"duplicate car_id in drivers: {car_ids}")
        return self

    @property
    def duration_seconds(self) -> int | None:
        if self.duration_value is None or self.duration_unit is None:
            return None
        if self.duration_unit is DurationUnit.MINUTES:
            return self.duration_value * 60
        return self.duration_value * 3600


class RaceCreate(_RaceCommon):
    """Payload for POST /races (and the Streamlit New Race form)."""


class RaceUpdate(_RaceCommon):
    """Same shape; all fields settable while race is in draft/ready."""


class RaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    name: str
    mode: RaceMode
    lap_target: int | None
    duration_seconds: int | None
    driver_count: int
    status: RaceStatus
    notes: str | None
    source_race_id: int | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    drivers: list[DriverAssignment]


# -----------------------------------------------------------------------
# Report payload DTOs
# -----------------------------------------------------------------------


class DriverStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    car_id: int
    driver_name: str
    total_laps: int
    best_lap_ms: int | None
    average_lap_ms: int | None
    last_lap_ms: int | None
    total_race_time_ms: int | None
    pit_count: int | None = None
    fuel_summary: dict[str, float] | None = None


class StandingsRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int
    car_id: int
    driver_name: str
    lap_count: int
    best_lap_ms: int | None
    total_race_time_ms: int | None
    gap_to_leader_ms: int | None
    laps_behind: int


class RaceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    race: RaceRead
    duration_ms: int | None
    drivers: list[DriverStats]
    standings: list[StandingsRow]


class ReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    race_id: int
    report_type: str
    payload_json: str
    created_at: datetime


__all__ = [
    "DriverAssignment",
    "DriverStats",
    "DurationUnit",
    "RaceCreate",
    "RaceMode",
    "RaceRead",
    "RaceStatus",
    "RaceSummary",
    "RaceUpdate",
    "ReportRead",
    "StandingsRow",
]
