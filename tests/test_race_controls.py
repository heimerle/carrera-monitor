"""Tests for the new race controls (T-controls).

Covers:
- ``RaceService.finish_race_by_user`` — explicit user-triggered finish,
  validation against invalid statuses, and the ``triggered_by='user'``
  marker on the persisted ``race_finished`` event.
- ``RaceService.set_safety_car`` / ``is_safety_car_active`` —
  toggle semantics, idempotency, ``race_events`` persistence, and the
  ``running|paused`` status guard.
- ``RuntimeSettings.get_mock_mode`` / ``set_mock_mode`` — round-trip
  persistence to ``data/runtime_settings.json``.
"""

from __future__ import annotations

import json

import pytest

from src.race_context import ActiveRaceContext
from src.repositories.race_repository import RaceRepository
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
    RaceStatus,
)
from src.services import InvalidRaceStateError
from src.services.race_service import RaceService
from src.services.runtime_settings import RuntimeSettings


def _payload(name: str = "R") -> RaceCreate:
    return RaceCreate(
        name=name,
        mode=RaceMode.FIXED_LAPS,
        lap_target=10,
        driver_count=1,
        drivers=[DriverAssignment(car_id=1, driver_name="A")],
    )


@pytest.fixture(autouse=True)
def _reset_active(engine):
    yield
    ActiveRaceContext.clear()


# ---------------------------------------------------------- finish_race_by_user


def test_finish_race_by_user_from_running(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)

    result = svc.finish_race_by_user(race.id)

    assert result.status is RaceStatus.FINISHED
    assert result.finished_at is not None
    assert ActiveRaceContext.get() is None


def test_finish_race_by_user_from_paused(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.pause_race(race.id)

    result = svc.finish_race_by_user(race.id)
    assert result.status is RaceStatus.FINISHED


@pytest.mark.parametrize("bad_status_setup", ["draft", "ready", "finished", "cancelled"])
def test_finish_race_by_user_rejects_invalid_statuses(engine, bad_status_setup):
    svc = RaceService()
    race = svc.create_race(_payload())
    if bad_status_setup == "ready":
        svc.mark_ready(race.id)
    elif bad_status_setup == "finished":
        svc.start_race(race.id)
        svc.finish_race_by_user(race.id)
    elif bad_status_setup == "cancelled":
        svc.cancel_race(race.id)
    # draft: no transition needed

    with pytest.raises(InvalidRaceStateError) as exc:
        svc.finish_race_by_user(race.id)
    assert bad_status_setup in str(exc.value)


def test_finish_race_by_user_persists_triggered_by_marker(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.finish_race_by_user(race.id)

    repo = RaceRepository()
    from src.database import SessionLocal

    with SessionLocal() as session:
        events = repo.list_events(session, race.id) if hasattr(
            repo, "list_events"
        ) else None
        if events is None:
            # Fallback: query directly.
            from sqlalchemy import select

            from src.models import RaceEvent

            events = list(
                session.execute(
                    select(RaceEvent).where(RaceEvent.race_id == race.id)
                ).scalars()
            )
    finish_events = [
        e
        for e in events
        if getattr(e, "event_type", None) == "race_finished"
    ]
    assert finish_events, "expected at least one race_finished event"
    payloads = [json.loads(e.payload_json) for e in finish_events]
    assert any(p.get("triggered_by") == "user" for p in payloads), payloads


def test_finish_race_by_user_creates_summary_report(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.finish_race_by_user(race.id)

    from sqlalchemy import select

    from src.database import SessionLocal
    from src.models import RaceReport

    with SessionLocal() as session:
        reports = list(
            session.execute(
                select(RaceReport).where(RaceReport.race_id == race.id)
            ).scalars()
        )
    assert any(r.report_type == "race_summary" for r in reports)


# ------------------------------------------------------------------- safety_car


def test_set_safety_car_on_running_race(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    assert svc.is_safety_car_active(race.id) is False

    assert svc.set_safety_car(race.id, True) is True
    assert svc.is_safety_car_active(race.id) is True

    assert svc.set_safety_car(race.id, False) is False
    assert svc.is_safety_car_active(race.id) is False


def test_set_safety_car_on_paused_race(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.pause_race(race.id)
    assert svc.set_safety_car(race.id, True) is True


def test_set_safety_car_idempotent(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.set_safety_car(race.id, True)
    # Second call with same value persists no extra event.
    svc.set_safety_car(race.id, True)

    from sqlalchemy import select

    from src.database import SessionLocal
    from src.models import RaceEvent

    with SessionLocal() as session:
        events = list(
            session.execute(
                select(RaceEvent).where(
                    RaceEvent.race_id == race.id,
                    RaceEvent.event_type == "safety_car_started",
                )
            ).scalars()
        )
    assert len(events) == 1


def test_set_safety_car_persists_events(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.set_safety_car(race.id, True)
    svc.set_safety_car(race.id, False)

    from sqlalchemy import select

    from src.database import SessionLocal
    from src.models import RaceEvent

    with SessionLocal() as session:
        kinds = [
            e.event_type
            for e in session.execute(
                select(RaceEvent)
                .where(RaceEvent.race_id == race.id)
                .order_by(RaceEvent.id)
            ).scalars()
        ]
    assert "safety_car_started" in kinds
    assert "safety_car_ended" in kinds
    assert kinds.index("safety_car_started") < kinds.index("safety_car_ended")


@pytest.mark.parametrize("status", ["draft", "ready", "finished", "cancelled"])
def test_set_safety_car_rejects_invalid_statuses(engine, status):
    svc = RaceService()
    race = svc.create_race(_payload())
    if status == "ready":
        svc.mark_ready(race.id)
    elif status == "finished":
        svc.start_race(race.id)
        svc.finish_race_by_user(race.id)
    elif status == "cancelled":
        svc.cancel_race(race.id)

    with pytest.raises(InvalidRaceStateError):
        svc.set_safety_car(race.id, True)


def test_safety_car_cleared_on_finish(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.set_safety_car(race.id, True)
    svc.finish_race_by_user(race.id)
    assert svc.is_safety_car_active(race.id) is False


def test_safety_car_cleared_on_cancel(engine):
    svc = RaceService()
    race = svc.create_race(_payload())
    svc.start_race(race.id)
    svc.set_safety_car(race.id, True)
    svc.cancel_race(race.id)
    assert svc.is_safety_car_active(race.id) is False


# --------------------------------------------------------------- runtime mock


def test_runtime_settings_round_trip(tmp_path):
    path = tmp_path / "runtime_settings.json"
    rs = RuntimeSettings(path=path)
    assert rs.get_mock_mode() is False

    rs.set_mock_mode(True)
    assert rs.get_mock_mode() is True
    # File on disk holds the value
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mock_mode"] is True

    # New instance reads from disk
    rs2 = RuntimeSettings(path=path)
    assert rs2.get_mock_mode() is True

    rs2.set_mock_mode(False)
    assert RuntimeSettings(path=path).get_mock_mode() is False


def test_runtime_settings_missing_file_returns_defaults(tmp_path):
    path = tmp_path / "nope.json"
    assert RuntimeSettings(path=path).get_mock_mode() is False


def test_runtime_settings_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not-json{{", encoding="utf-8")
    assert RuntimeSettings(path=path).get_mock_mode() is False
