"""``RaceService`` — single source of truth for race lifecycle, CRUD, and ingest.

Contract: ``specs/001-race-management/contracts/race-service.md``.
All methods are synchronous and open their own ``SessionLocal()`` context.
Telemetry-ingest methods are called from the async pipeline via
``await asyncio.to_thread(...)``.

# TODO(hardware): verify lap event payload mapping against real Carrera
# DIGITAL traffic (see FR-135). The current ingest reads ``event.payload``
# keys ``lap_number`` and ``lap_time_ms`` exactly as produced by
# ``src.mock_client`` — the live adapter must produce the same shape.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError

from ..config import RaceManagementConfig
from ..database import SessionLocal
from ..event_model import EventType, TelemetryEvent
from ..race_context import ActiveRaceContext
from ..repositories.race_repository import RaceRepository
from ..schemas.race_schema import (
    RaceCreate,
    RaceRead,
    RaceStatus,
    RaceSummary,
    RaceUpdate,
)
from . import (
    InvalidRaceStateError,
    RaceNotEditableError,
    RaceNotFoundError,
    RaceValidationError,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ..models import Race

logger = logging.getLogger(__name__)


# State-machine table (see data-model.md §4).
_VALID_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "mark_ready": {"draft": {"ready"}, "ready": {"ready"}},
    "start_race": {"draft": {"running"}, "ready": {"running"}},
    "pause_race": {"running": {"paused"}},
    "resume_race": {"paused": {"running"}},
    "finish_race": {"running": {"finished"}, "paused": {"finished"}},
    "cancel_race": {
        "draft": {"cancelled"},
        "ready": {"cancelled"},
        "running": {"cancelled"},
        "paused": {"cancelled"},
    },
}


def _check_transition(method: str, current: str) -> None:
    allowed = _VALID_TRANSITIONS.get(method, {}).get(current)
    if not allowed:
        raise InvalidRaceStateError(
            f"cannot {method} a race in status={current!r}"
        )


def _race_event_payload(method: str) -> tuple[str, dict[str, str]]:
    """Map a lifecycle method name → (event_type, payload)."""
    mapping = {
        "start_race": "race_started",
        "pause_race": "race_paused",
        "resume_race": "race_resumed",
        "finish_race": "race_finished",
        "cancel_race": "race_cancelled",
    }
    return mapping.get(method, method), {"method": method}


class RaceService:
    """Synchronous facade over the repository + ORM."""

    def __init__(
        self,
        *,
        config: RaceManagementConfig | None = None,
        repository: RaceRepository | None = None,
    ) -> None:
        self._cfg = config or RaceManagementConfig()
        self._repo = repository or RaceRepository()

    # -------------------------------------------------------------- CRUD

    def create_race(self, payload: RaceCreate) -> RaceRead:
        try:
            initial_status = self._cfg.default_race_status_after_create
            RaceStatus(initial_status)  # validate
        except ValueError as exc:
            raise RaceValidationError(str(exc)) from exc
        with SessionLocal() as session:
            race = self._repo.create_race(session, payload, status=initial_status)
            session.commit()
            session.refresh(race)
            return self._repo.to_read(session, race)

    def get_race(self, race_id: int) -> RaceRead:
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            return self._repo.to_read(session, race)

    def list_races(
        self,
        status: RaceStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RaceRead]:
        with SessionLocal() as session:
            races = self._repo.list_races(
                session, status=status, limit=limit, offset=offset
            )
            return [self._repo.to_read(session, r) for r in races]

    def update_race(self, race_id: int, payload: RaceUpdate) -> RaceRead:
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            if race.status not in {"draft", "ready"} and not self._cfg.allow_edit_running_race:
                raise RaceNotEditableError(
                    f"race id={race_id} status={race.status!r} is not editable"
                )
            self._repo.update_race(session, race, payload)
            session.commit()
            session.refresh(race)
            return self._repo.to_read(session, race)

    def delete_race(self, race_id: int) -> None:
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            if race.status == "running":
                raise InvalidRaceStateError("cannot delete a running race")
            self._repo.delete_race(session, race)
            session.commit()
            if ActiveRaceContext.get() == race_id:
                ActiveRaceContext.clear()

    # ---------------------------------------------------------- Lifecycle

    def mark_ready(self, race_id: int) -> RaceRead:
        return self._transition(race_id, "mark_ready", "ready")

    def start_race(self, race_id: int) -> RaceRead:
        with ActiveRaceContext.lock():
            current_active = ActiveRaceContext.get()
            if current_active is not None and current_active != race_id:
                # Auto-pause the currently running race first.
                with contextlib.suppress(RaceNotFoundError, InvalidRaceStateError):
                    self._transition(current_active, "pause_race", "paused")
            result = self._transition(
                race_id, "start_race", "running", set_started_at=True
            )
            ActiveRaceContext.set(race_id)
            return result

    def pause_race(self, race_id: int) -> RaceRead:
        with ActiveRaceContext.lock():
            result = self._transition(race_id, "pause_race", "paused")
            if ActiveRaceContext.get() == race_id:
                ActiveRaceContext.clear()
            return result

    def resume_race(self, race_id: int) -> RaceRead:
        with ActiveRaceContext.lock():
            current_active = ActiveRaceContext.get()
            if current_active is not None and current_active != race_id:
                with contextlib.suppress(RaceNotFoundError, InvalidRaceStateError):
                    self._transition(current_active, "pause_race", "paused")
            result = self._transition(race_id, "resume_race", "running")
            ActiveRaceContext.set(race_id)
            return result

    def finish_race(self, race_id: int) -> RaceRead:
        with ActiveRaceContext.lock():
            result = self._transition(
                race_id, "finish_race", "finished", set_finished_at=True
            )
            if ActiveRaceContext.get() == race_id:
                ActiveRaceContext.clear()
            self._auto_snapshot(race_id, force=True)
            return result

    def cancel_race(self, race_id: int) -> RaceRead:
        with ActiveRaceContext.lock():
            had_laps = self._race_has_laps(race_id)
            result = self._transition(
                race_id, "cancel_race", "cancelled", set_finished_at=True
            )
            if ActiveRaceContext.get() == race_id:
                ActiveRaceContext.clear()
            if had_laps:
                self._auto_snapshot(race_id, force=True)
            return result

    def _transition(
        self,
        race_id: int,
        method: str,
        new_status: str,
        *,
        set_started_at: bool = False,
        set_finished_at: bool = False,
    ) -> RaceRead:
        with SessionLocal() as session:
            race = self._repo.get_race(session, race_id)
            if race is None:
                raise RaceNotFoundError(f"race id={race_id} not found")
            _check_transition(method, race.status)
            now = datetime.utcnow()
            if set_started_at and race.started_at is None:
                self._repo.set_timestamps(session, race, started_at=now)
            if set_finished_at and race.finished_at is None:
                self._repo.set_timestamps(session, race, finished_at=now)
            self._repo.set_status(session, race, new_status)
            if self._cfg.persist_all_events and method != "mark_ready":
                evt_type, payload = _race_event_payload(method)
                try:
                    self._repo.add_event(
                        session,
                        race_id=race.id,
                        timestamp_iso=now,
                        event_type=evt_type,
                        car_id=None,
                        payload=payload,
                    )
                except SQLAlchemyError:
                    logger.exception("race_service: failed to persist lifecycle event")
            session.commit()
            session.refresh(race)
            return self._repo.to_read(session, race)

    # -------------------------------------------------------- Ingest API

    def record_lap(self, event: TelemetryEvent) -> None:
        """Persist a lap event when one applies to the active race.

        # TODO(hardware): verify ``event.payload['lap_number']`` /
        # ``lap_time_ms`` semantics against real Carrera DIGITAL frames
        # (FR-135).
        """
        race_id = ActiveRaceContext.get()
        if race_id is None:
            return
        if event.event_type is not EventType.LAP or event.car_id is None:
            return
        try:
            with SessionLocal() as session:
                race = self._repo.get_race(session, race_id)
                if race is None:
                    ActiveRaceContext.clear()
                    return
                if race.status == "paused":
                    logger.debug(
                        "race_service: dropping lap for paused race id=%d", race_id
                    )
                    return
                if race.status != "running":
                    return
                driver = next(
                    (d for d in race.drivers if d.car_id == event.car_id), None
                )
                if driver is None:
                    logger.warning(
                        "race_service: lap event for unknown car_id=%d in race id=%d",
                        event.car_id,
                        race_id,
                        extra={"race_id": race_id, "car_id": event.car_id},
                    )
                    return
                try:
                    self._repo.add_lap(
                        session,
                        race_id=race.id,
                        car_id=event.car_id,
                        driver_name=driver.driver_name,
                        lap_number=int(event.payload["lap_number"]),
                        lap_time_ms=int(event.payload["lap_time_ms"]),
                        timestamp_iso=event.timestamp_iso,
                    )
                    session.commit()
                except SQLAlchemyError:
                    logger.exception(
                        "race_service: failed to persist lap (race=%d car=%d)",
                        race_id,
                        event.car_id,
                    )
                    session.rollback()
                    return
                if race.mode == "fixed_laps" and race.lap_target is not None:
                    self._maybe_auto_finish(session, race)
        except SQLAlchemyError:
            logger.exception("race_service: lap-ingest session failure")

    def record_event(self, event: TelemetryEvent) -> None:
        """Persist a non-lap event into ``race_events`` when an active race exists."""
        if not self._cfg.persist_all_events:
            return
        race_id = ActiveRaceContext.get()
        if race_id is None:
            return
        try:
            with SessionLocal() as session:
                race = self._repo.get_race(session, race_id)
                if race is None or race.status not in {"running", "paused"}:
                    return
                try:
                    self._repo.add_event(
                        session,
                        race_id=race.id,
                        timestamp_iso=event.timestamp_iso,
                        event_type=str(event.event_type),
                        car_id=event.car_id,
                        payload=dict(event.payload),
                        raw_data=event.raw_data,
                    )
                    session.commit()
                except SQLAlchemyError:
                    logger.exception(
                        "race_service: failed to persist event type=%s",
                        event.event_type,
                    )
                    session.rollback()
        except SQLAlchemyError:
            logger.exception("race_service: event-ingest session failure")

    def _maybe_auto_finish(self, session: Session, race: Race) -> None:
        """FR-109(a): finish when the LEADER reaches ``lap_target``."""
        counts = self._repo.lap_count_by_car(session, race.id)
        leader_laps = max(counts.values(), default=0)
        target = race.lap_target or 0
        if leader_laps >= target:
            logger.info(
                "race_service: auto-finish — leader reached lap_target (race id=%d, "
                "leader=%d, target=%d)",
                race.id,
                leader_laps,
                target,
            )
            # Close current session before triggering the lifecycle transition,
            # which opens its own session.
            session.commit()
            with contextlib.suppress(InvalidRaceStateError):
                self.finish_race(race.id)

    def _race_has_laps(self, race_id: int) -> bool:
        with SessionLocal() as session:
            counts = self._repo.lap_count_by_car(session, race_id)
            return any(c > 0 for c in counts.values())

    # ----------------------------------------------------------- Recover

    def recover_on_startup(self) -> None:
        """Handle a process that crashed while a race was ``running``."""
        with SessionLocal() as session:
            races = self._repo.list_races(session, status=RaceStatus.RUNNING)
        for race in races:
            if self._cfg.recover_running_race:
                ActiveRaceContext.set(race.id)
                logger.warning(
                    "race_service: recovered running race id=%d (reattached)", race.id
                )
            else:
                try:
                    self.pause_race(race.id)
                    logger.warning(
                        "race_service: auto-paused running race id=%d on startup", race.id
                    )
                except (RaceNotFoundError, InvalidRaceStateError):
                    pass

    # ---------------------------------------------------- Repeat (US2)

    def repeat_race(
        self, source_race_id: int, new_name: str | None = None
    ) -> RaceRead:
        """Create a fresh draft race that mirrors the configuration of an existing one.

        Copies only: name, mode, lap_target, duration_seconds, driver_count,
        notes, and all driver rows. Sets ``source_race_id``. Resets status to
        the configured default. **No** child rows in race_laps/race_events/
        race_reports are copied (see R-106).
        """
        from ..schemas.race_schema import DriverAssignment, RaceMode

        with SessionLocal() as session:
            src = self._repo.get_race(session, source_race_id)
            if src is None:
                raise RaceNotFoundError(f"race id={source_race_id} not found")
            # Build a synthetic RaceCreate payload from the source.
            drivers = [
                DriverAssignment(car_id=d.car_id, driver_name=d.driver_name)
                for d in sorted(src.drivers, key=lambda x: x.car_id)
            ]
            if src.mode == "fixed_duration":
                # Round duration back into value+minutes (minutes-resolution is fine
                # because we only ever stored value*60 / value*3600).
                duration_value = src.duration_seconds or 0
                from ..schemas.race_schema import DurationUnit

                payload = RaceCreate(
                    name=new_name or f"{src.name} (copy)",
                    mode=RaceMode(src.mode),
                    duration_value=duration_value,
                    duration_unit=DurationUnit.MINUTES if duration_value % 3600 != 0
                    else DurationUnit.HOURS,
                    driver_count=src.driver_count,
                    drivers=drivers,
                    notes=src.notes,
                )
                # Override the seconds calculation: store the exact source value.
                # We do this by constructing the ORM row directly below.
                new_race = self._repo.create_race(
                    session,
                    payload,
                    status=self._cfg.default_race_status_after_create,
                    source_race_id=src.id,
                )
                new_race.duration_seconds = src.duration_seconds
                session.flush()
            else:
                payload = RaceCreate(
                    name=new_name or f"{src.name} (copy)",
                    mode=RaceMode(src.mode),
                    lap_target=src.lap_target,
                    driver_count=src.driver_count,
                    drivers=drivers,
                    notes=src.notes,
                )
                new_race = self._repo.create_race(
                    session,
                    payload,
                    status=self._cfg.default_race_status_after_create,
                    source_race_id=src.id,
                )
            session.commit()
            session.refresh(new_race)
            return self._repo.to_read(session, new_race)

    # ----------------------------------------------------- Auto-snapshot

    def _auto_snapshot(self, race_id: int, *, force: bool = False) -> None:
        """Write a ``race_summary`` row to ``race_reports`` on finish/cancel."""
        # Lazy import to avoid an import cycle (reporting_service imports
        # RaceService.get_race).
        from .reporting_service import ReportingService

        try:
            reporting = ReportingService(race_service=self)
            summary: RaceSummary = reporting.race_summary(race_id)
            reporting.save_report(
                race_id, "race_summary", summary.model_dump(mode="json")
            )
        except Exception:
            logger.exception(
                "race_service: failed to save auto-snapshot for race id=%d", race_id
            )


__all__ = ["RaceService"]
