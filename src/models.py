"""SQLAlchemy 2.x ORM models for the race-management module.

Mirrors `specs/001-race-management/contracts/database-schema.md` exactly.
Authoritative DDL is produced by ``Base.metadata.create_all`` in
``src/database.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

if TYPE_CHECKING:
    pass


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_races_name_nonempty"),
        CheckConstraint("mode IN ('fixed_laps','fixed_duration')", name="ck_races_mode"),
        CheckConstraint(
            "lap_target IS NULL OR lap_target > 0", name="ck_races_lap_target_positive"
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="ck_races_duration_positive",
        ),
        CheckConstraint("driver_count BETWEEN 1 AND 6", name="ck_races_driver_count"),
        CheckConstraint(
            "status IN ('draft','ready','running','paused','finished','cancelled')",
            name="ck_races_status",
        ),
        Index("ix_races_status", "status"),
        Index("ix_races_created_at", "created_at"),
        Index("ix_races_source_race_id", "source_race_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    lap_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_race_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    drivers: Mapped[list[RaceDriver]] = relationship(
        back_populates="race",
        cascade="all, delete-orphan",
        order_by="RaceDriver.car_id",
        passive_deletes=True,
    )
    laps: Mapped[list[RaceLap]] = relationship(
        back_populates="race", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list[RaceEvent]] = relationship(
        back_populates="race", cascade="all, delete-orphan", passive_deletes=True
    )
    reports: Mapped[list[RaceReport]] = relationship(
        back_populates="race", cascade="all, delete-orphan", passive_deletes=True
    )


class RaceDriver(Base):
    __tablename__ = "race_drivers"
    __table_args__ = (
        CheckConstraint("car_id BETWEEN 1 AND 6", name="ck_race_drivers_car_id"),
        CheckConstraint(
            "length(trim(driver_name)) > 0", name="ck_race_drivers_driver_name_nonempty"
        ),
        UniqueConstraint("race_id", "car_id", name="uq_race_drivers_race_car"),
        Index("ix_race_drivers_race_id", "race_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False
    )
    car_id: Mapped[int] = mapped_column(Integer, nullable=False)
    driver_name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    race: Mapped[Race] = relationship(back_populates="drivers")


class RaceLap(Base):
    __tablename__ = "race_laps"
    __table_args__ = (
        CheckConstraint("car_id BETWEEN 1 AND 6", name="ck_race_laps_car_id"),
        CheckConstraint("lap_number > 0", name="ck_race_laps_lap_number"),
        CheckConstraint("lap_time_ms > 0", name="ck_race_laps_lap_time"),
        UniqueConstraint(
            "race_id", "car_id", "lap_number", name="uq_race_laps_race_car_lap"
        ),
        Index("ix_race_laps_race_car", "race_id", "car_id", "lap_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False
    )
    car_id: Mapped[int] = mapped_column(Integer, nullable=False)
    driver_name: Mapped[str] = mapped_column(String(80), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_iso: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    race: Mapped[Race] = relationship(back_populates="laps")


class RaceEvent(Base):
    __tablename__ = "race_events"
    __table_args__ = (
        CheckConstraint(
            "car_id IS NULL OR (car_id BETWEEN 1 AND 6)", name="ck_race_events_car_id"
        ),
        Index("ix_race_events_race_type", "race_id", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False
    )
    timestamp_iso: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    car_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    race: Mapped[Race] = relationship(back_populates="events")


class RaceReport(Base):
    __tablename__ = "race_reports"
    __table_args__ = (Index("ix_race_reports_race_type", "race_id", "report_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    race: Mapped[Race] = relationship(back_populates="reports")


__all__ = ["Race", "RaceDriver", "RaceEvent", "RaceLap", "RaceReport"]
