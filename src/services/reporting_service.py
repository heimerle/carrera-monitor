"""``ReportingService`` — read-only aggregations over race_laps / race_events.

Contract: ``specs/001-race-management/contracts/reporting-service.md``.

Performance budget: ≤500 ms for races with up to 1,000 laps (SC-105).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from ..database import SessionLocal
from ..models import RaceLap
from ..repositories.race_repository import RaceRepository
from ..schemas.race_schema import (
    DriverStats,
    RaceRead,
    RaceSummary,
    ReportRead,
    StandingsRow,
)
from . import RaceNotFoundError

if TYPE_CHECKING:
    from .race_service import RaceService

logger = logging.getLogger(__name__)


class ReportingService:
    def __init__(
        self,
        *,
        race_service: RaceService | None = None,
        repository: RaceRepository | None = None,
    ) -> None:
        self._race_service = race_service
        self._repo = repository or RaceRepository()

    # ------------------------------------------------------- driver_stats

    def driver_stats(self, race_id: int) -> list[DriverStats]:
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            # Aggregate per car_id in one query.
            stmt = (
                select(
                    RaceLap.car_id,
                    func.count(RaceLap.id),
                    func.min(RaceLap.lap_time_ms),
                    func.avg(RaceLap.lap_time_ms),
                    func.sum(RaceLap.lap_time_ms),
                    func.max(RaceLap.lap_number),
                )
                .where(RaceLap.race_id == race_id)
                .group_by(RaceLap.car_id)
            )
            agg = {
                car_id: (count, best, avg, total, max_lap)
                for car_id, count, best, avg, total, max_lap in session.execute(stmt).all()
            }
            # Look up last_lap_ms via a second small query (lap_time of MAX(lap_number)).
            last_lap_by_car: dict[int, int] = {}
            for car_id, (_count, _best, _avg, _total, max_lap) in agg.items():
                if max_lap is None:
                    continue
                stmt2 = select(RaceLap.lap_time_ms).where(
                    RaceLap.race_id == race_id,
                    RaceLap.car_id == car_id,
                    RaceLap.lap_number == max_lap,
                )
                last = session.execute(stmt2).scalar_one_or_none()
                if last is not None:
                    last_lap_by_car[car_id] = last

            stats: list[DriverStats] = []
            for driver in sorted(race.drivers, key=lambda d: d.car_id):
                count, best, avg, total, _max_lap = agg.get(
                    driver.car_id, (0, None, None, None, None)
                )
                stats.append(
                    DriverStats(
                        car_id=driver.car_id,
                        driver_name=driver.driver_name,
                        total_laps=int(count or 0),
                        best_lap_ms=int(best) if best is not None else None,
                        average_lap_ms=round(float(avg)) if avg is not None else None,
                        last_lap_ms=last_lap_by_car.get(driver.car_id),
                        total_race_time_ms=int(total) if total is not None else None,
                        pit_count=None,
                        fuel_summary=None,
                    )
                )
            return stats

    # ----------------------------------------------------- final_standings

    def final_standings(self, race_id: int) -> list[StandingsRow]:
        stats = self.driver_stats(race_id)
        # Filter out drivers with zero laps if no race has laps yet —> spec
        # says return [] when race has no laps yet. Otherwise include all
        # drivers (lap_count=0 sorts last).
        if all(s.total_laps == 0 for s in stats):
            return []
        ranked = sorted(
            stats,
            key=lambda s: (
                -s.total_laps,
                s.total_race_time_ms if s.total_race_time_ms is not None else 1 << 62,
                s.best_lap_ms if s.best_lap_ms is not None else 1 << 62,
                s.car_id,
            ),
        )
        leader = ranked[0]
        rows: list[StandingsRow] = []
        for pos, s in enumerate(ranked, start=1):
            laps_behind = leader.total_laps - s.total_laps
            gap: int | None
            if (
                laps_behind == 0
                and leader.total_race_time_ms is not None
                and s.total_race_time_ms is not None
            ):
                gap = s.total_race_time_ms - leader.total_race_time_ms
            else:
                gap = None
            rows.append(
                StandingsRow(
                    position=pos,
                    car_id=s.car_id,
                    driver_name=s.driver_name,
                    lap_count=s.total_laps,
                    best_lap_ms=s.best_lap_ms,
                    total_race_time_ms=s.total_race_time_ms,
                    gap_to_leader_ms=gap,
                    laps_behind=laps_behind,
                )
            )
        return rows

    # -------------------------------------------------------- race_summary

    def race_summary(self, race_id: int) -> RaceSummary:
        race_read = self._get_race_read(race_id)
        duration_ms: int | None = None
        if race_read.started_at is not None:
            end = race_read.finished_at or datetime.utcnow()
            duration_ms = int((end - race_read.started_at).total_seconds() * 1000)
        drivers = self.driver_stats(race_id)
        standings = self.final_standings(race_id)
        return RaceSummary(
            race=race_read,
            duration_ms=duration_ms,
            drivers=drivers,
            standings=standings,
        )

    def _get_race_read(self, race_id: int) -> RaceRead:
        if self._race_service is not None:
            return self._race_service.get_race(race_id)
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            return self._repo.to_read(session, race)

    # ------------------------------------------------------------ reports

    def save_report(
        self, race_id: int, report_type: str, payload: dict[str, Any]
    ) -> int:
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            row = self._repo.add_report(
                session, race_id=race.id, report_type=report_type, payload=payload
            )
            session.commit()
            return row.id

    def list_reports(self, race_id: int) -> list[ReportRead]:
        with SessionLocal() as session:
            rows = self._repo.list_reports(session, race_id)
            return [ReportRead.model_validate(r) for r in rows]

    # --------------------------------------------------------------- CSV

    def export_summary_csv(self, race_id: int) -> bytes:
        """Per-driver standings CSV (FR-126(b))."""
        standings = self.final_standings(race_id)
        stats = {s.car_id: s for s in self.driver_stats(race_id)}
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "position",
                "car_id",
                "driver_name",
                "lap_count",
                "best_lap_ms",
                "gap_to_leader_ms",
                "laps_behind",
                "total_race_time_ms",
                "average_lap_ms",
                "pit_count",
            ]
        )
        for row in standings:
            ds = stats.get(row.car_id)
            writer.writerow(
                [
                    row.position,
                    row.car_id,
                    row.driver_name,
                    row.lap_count,
                    "" if row.best_lap_ms is None else row.best_lap_ms,
                    "" if row.gap_to_leader_ms is None else row.gap_to_leader_ms,
                    row.laps_behind,
                    "" if row.total_race_time_ms is None else row.total_race_time_ms,
                    "" if ds is None or ds.average_lap_ms is None else ds.average_lap_ms,
                    "" if ds is None or ds.pit_count is None else ds.pit_count,
                ]
            )
        return buf.getvalue().encode("utf-8")

    def export_laps_csv(self, race_id: int) -> bytes:
        """Per-lap CSV (FR-126(a)). Ordered by ``(car_id ASC, lap_number ASC)``."""
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            laps = self._repo.get_laps(session, race_id)
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(
                ["car_id", "driver_name", "lap_number", "lap_time_ms", "timestamp_iso"]
            )
            for lap in laps:
                writer.writerow(
                    [
                        lap.car_id,
                        lap.driver_name,
                        lap.lap_number,
                        lap.lap_time_ms,
                        lap.timestamp_iso.isoformat(),
                    ]
                )
            return buf.getvalue().encode("utf-8")


__all__ = ["ReportingService"]
