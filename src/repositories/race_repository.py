"""CRUD layer for the race-management ORM models.

Each method takes an explicit ``session: Session`` so the caller controls
transaction boundaries. The repository never commits; that's the
service layer's job.

Mirrors the API described in ``specs/001-race-management/tasks.md`` (T013).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .._time import utcnow_naive
from ..models import Race, RaceDriver, RaceEvent, RaceLap, RaceReport
from ..schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
    RaceRead,
    RaceStatus,
    RaceUpdate,
)


class RaceRepository:
    """Thin, stateless DB accessor. Pass an explicit session to every method."""

    # -- Reads ----------------------------------------------------------

    def get_race(self, session: Session, race_id: int) -> Race | None:
        stmt = (
            select(Race)
            .where(Race.id == race_id)
            .options(selectinload(Race.drivers))
        )
        return session.execute(stmt).scalar_one_or_none()

    def list_races(
        self,
        session: Session,
        *,
        status: RaceStatus | str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Race]:
        stmt = select(Race).options(selectinload(Race.drivers))
        if status is not None:
            stmt = stmt.where(Race.status == str(status))
        stmt = stmt.order_by(Race.created_at.desc(), Race.id.desc()).limit(limit).offset(offset)
        return session.execute(stmt).scalars().all()

    def get_drivers(self, session: Session, race_id: int) -> Sequence[RaceDriver]:
        stmt = (
            select(RaceDriver)
            .where(RaceDriver.race_id == race_id)
            .order_by(RaceDriver.car_id)
        )
        return session.execute(stmt).scalars().all()

    def get_laps(self, session: Session, race_id: int) -> Sequence[RaceLap]:
        stmt = (
            select(RaceLap)
            .where(RaceLap.race_id == race_id)
            .order_by(RaceLap.car_id, RaceLap.lap_number)
        )
        return session.execute(stmt).scalars().all()

    # -- Writes ---------------------------------------------------------

    def create_race(
        self,
        session: Session,
        payload: RaceCreate,
        *,
        status: str = "draft",
        source_race_id: int | None = None,
    ) -> Race:
        race = Race(
            name=payload.name,
            mode=str(payload.mode),
            lap_target=payload.lap_target if payload.mode is RaceMode.FIXED_LAPS else None,
            duration_seconds=(
                payload.duration_seconds if payload.mode is RaceMode.FIXED_DURATION else None
            ),
            driver_count=payload.driver_count,
            status=status,
            notes=payload.notes,
            source_race_id=source_race_id,
        )
        for d in payload.drivers:
            race.drivers.append(RaceDriver(car_id=d.car_id, driver_name=d.driver_name))
        session.add(race)
        session.flush()
        return race

    def update_race(self, session: Session, race: Race, payload: RaceUpdate) -> Race:
        race.name = payload.name
        race.mode = str(payload.mode)
        race.lap_target = (
            payload.lap_target if payload.mode is RaceMode.FIXED_LAPS else None
        )
        race.duration_seconds = (
            payload.duration_seconds if payload.mode is RaceMode.FIXED_DURATION else None
        )
        race.driver_count = payload.driver_count
        race.notes = payload.notes
        race.updated_at = utcnow_naive()

        # Replace driver assignments wholesale (allowed only while race is editable).
        race.drivers.clear()
        session.flush()
        for d in payload.drivers:
            race.drivers.append(RaceDriver(car_id=d.car_id, driver_name=d.driver_name))
        session.flush()
        return race

    def delete_race(self, session: Session, race: Race) -> None:
        session.delete(race)
        session.flush()

    def set_status(self, session: Session, race: Race, status: str) -> Race:
        race.status = status
        race.updated_at = utcnow_naive()
        session.flush()
        return race

    def set_timestamps(
        self,
        session: Session,
        race: Race,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> Race:
        if started_at is not None:
            race.started_at = started_at
        if finished_at is not None:
            race.finished_at = finished_at
        race.updated_at = utcnow_naive()
        session.flush()
        return race

    def add_lap(
        self,
        session: Session,
        *,
        race_id: int,
        car_id: int,
        driver_name: str,
        lap_number: int,
        lap_time_ms: int,
        timestamp_iso: datetime,
    ) -> RaceLap:
        row = RaceLap(
            race_id=race_id,
            car_id=car_id,
            driver_name=driver_name,
            lap_number=lap_number,
            lap_time_ms=lap_time_ms,
            timestamp_iso=timestamp_iso,
        )
        session.add(row)
        session.flush()
        return row

    def add_event(
        self,
        session: Session,
        *,
        race_id: int,
        timestamp_iso: datetime,
        event_type: str,
        car_id: int | None,
        payload: dict[str, Any],
        raw_data: dict[str, Any] | None = None,
    ) -> RaceEvent:
        row = RaceEvent(
            race_id=race_id,
            timestamp_iso=timestamp_iso,
            event_type=event_type,
            car_id=car_id,
            payload_json=json.dumps(payload, default=str, sort_keys=True),
            raw_data_json=(
                json.dumps(raw_data, default=str, sort_keys=True) if raw_data else None
            ),
        )
        session.add(row)
        session.flush()
        return row

    def add_report(
        self,
        session: Session,
        *,
        race_id: int,
        report_type: str,
        payload: dict[str, Any],
    ) -> RaceReport:
        row = RaceReport(
            race_id=race_id,
            report_type=report_type,
            payload_json=json.dumps(payload, default=str, sort_keys=True),
        )
        session.add(row)
        session.flush()
        return row

    def list_reports(self, session: Session, race_id: int) -> Sequence[RaceReport]:
        stmt = (
            select(RaceReport)
            .where(RaceReport.race_id == race_id)
            .order_by(RaceReport.created_at.desc(), RaceReport.id.desc())
        )
        return session.execute(stmt).scalars().all()

    def lap_count_by_car(self, session: Session, race_id: int) -> dict[int, int]:
        """Return ``{car_id: COUNT(*)}`` for a race's lap table."""
        from sqlalchemy import func

        stmt = (
            select(RaceLap.car_id, func.count(RaceLap.id))
            .where(RaceLap.race_id == race_id)
            .group_by(RaceLap.car_id)
        )
        rows = session.execute(stmt).all()
        return {int(car_id): int(count) for car_id, count in rows}

    def latest_event_type(
        self,
        session: Session,
        race_id: int,
        event_types: Sequence[str],
    ) -> str | None:
        """Return the ``event_type`` of the most recent matching event for a
        race, or ``None`` if no event with one of the given types exists.

        Used by services to reconcile ephemeral in-memory caches from the
        authoritative event log (e.g. safety-car flag after a process
        restart). Ordering is ``(timestamp_iso DESC, id DESC)`` so ties on
        the timestamp prefer the row inserted last.
        """
        if not event_types:
            return None
        stmt = (
            select(RaceEvent.event_type)
            .where(
                RaceEvent.race_id == race_id,
                RaceEvent.event_type.in_(list(event_types)),
            )
            .order_by(RaceEvent.timestamp_iso.desc(), RaceEvent.id.desc())
            .limit(1)
        )
        row = session.execute(stmt).scalar_one_or_none()
        return row

    # -- DTO helpers ----------------------------------------------------

    @staticmethod
    def to_read(_session: Session, race: Race) -> RaceRead:
        return RaceRead(
            id=race.id,
            name=race.name,
            mode=RaceMode(race.mode),
            lap_target=race.lap_target,
            duration_seconds=race.duration_seconds,
            driver_count=race.driver_count,
            status=RaceStatus(race.status),
            notes=race.notes,
            source_race_id=race.source_race_id,
            created_at=race.created_at,
            updated_at=race.updated_at,
            started_at=race.started_at,
            finished_at=race.finished_at,
            drivers=[
                DriverAssignment(car_id=d.car_id, driver_name=d.driver_name)
                for d in sorted(race.drivers, key=lambda x: x.car_id)
            ],
        )


__all__ = ["RaceRepository"]
