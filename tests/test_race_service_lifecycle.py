"""Lifecycle transitions: draft → ready → running → paused/resumed → finished/cancelled (T026)."""

from __future__ import annotations

import pytest

from src.race_context import ActiveRaceContext
from src.schemas.race_schema import (
    DriverAssignment,
    RaceCreate,
    RaceMode,
    RaceStatus,
)
from src.services import InvalidRaceStateError
from src.services.race_service import RaceService


def _payload(name="R"):
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


def test_full_happy_path(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.mark_ready(r.id)
    assert svc.get_race(r.id).status is RaceStatus.READY
    svc.start_race(r.id)
    running = svc.get_race(r.id)
    assert running.status is RaceStatus.RUNNING
    assert running.started_at is not None
    assert ActiveRaceContext.get() == r.id
    svc.pause_race(r.id)
    assert svc.get_race(r.id).status is RaceStatus.PAUSED
    svc.resume_race(r.id)
    assert svc.get_race(r.id).status is RaceStatus.RUNNING
    svc.finish_race(r.id)
    finished = svc.get_race(r.id)
    assert finished.status is RaceStatus.FINISHED
    assert finished.finished_at is not None
    assert ActiveRaceContext.get() is None


def test_start_from_draft_directly(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    assert svc.get_race(r.id).status is RaceStatus.RUNNING


def test_cancel_from_running(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    svc.start_race(r.id)
    svc.cancel_race(r.id)
    assert svc.get_race(r.id).status is RaceStatus.CANCELLED
    assert ActiveRaceContext.get() is None


def test_invalid_transition_raises(engine):
    svc = RaceService()
    r = svc.create_race(_payload())
    with pytest.raises(InvalidRaceStateError):
        svc.pause_race(r.id)  # draft → paused not allowed
    with pytest.raises(InvalidRaceStateError):
        svc.resume_race(r.id)


def test_starting_second_race_auto_pauses_first(engine):
    svc = RaceService()
    a = svc.create_race(_payload("A"))
    b = svc.create_race(_payload("B"))
    svc.start_race(a.id)
    svc.start_race(b.id)
    assert svc.get_race(a.id).status is RaceStatus.PAUSED
    assert svc.get_race(b.id).status is RaceStatus.RUNNING
    assert ActiveRaceContext.get() == b.id


def test_finish_clears_active_context_only_if_matches(engine):
    svc = RaceService()
    a = svc.create_race(_payload("A"))
    b = svc.create_race(_payload("B"))
    svc.start_race(a.id)
    svc.start_race(b.id)  # a paused, b running
    svc.finish_race(a.id)  # finish the paused race — ActiveRaceContext should stay on b
    assert ActiveRaceContext.get() == b.id
