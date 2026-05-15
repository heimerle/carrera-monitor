"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src import utils
from src.event_model import EventType, TelemetryEvent


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, int]]:
    """Freeze `utils.now_iso` and `utils.now_monotonic_ms` to deterministic values.

    The returned dict can be mutated by tests to advance the clock:
        clock["mono_ms"] += 100
    """
    state = {"mono_ms": 0, "iso_epoch": 1_700_000_000}

    def fake_mono() -> int:
        return int(state["mono_ms"])

    def fake_iso() -> datetime:
        return datetime.fromtimestamp(state["iso_epoch"], tz=UTC)

    monkeypatch.setattr(utils, "now_monotonic_ms", fake_mono)
    monkeypatch.setattr(utils, "now_iso", fake_iso)
    yield state


@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def event_factory():
    """Build a valid `TelemetryEvent` with sensible defaults; override via kwargs."""

    def _make(
        event_type: EventType = EventType.LAP,
        car_id: int | None = 1,
        payload: dict[str, Any] | None = None,
        source: str = "mock",
        monotonic_ms: int = 0,
        iso: datetime | None = None,
        **extra: Any,
    ) -> TelemetryEvent:
        if payload is None:
            payload = _default_payload(event_type)
        return TelemetryEvent(
            timestamp_iso=iso or datetime.now(tz=UTC),
            timestamp_monotonic_ms=monotonic_ms,
            source=source,  # type: ignore[arg-type]
            event_type=event_type,
            car_id=car_id,
            payload=payload,
            **extra,
        )

    return _make


def _default_payload(event_type: EventType) -> dict[str, Any]:
    match event_type:
        case EventType.LAP:
            return {"lap_number": 1, "lap_time_ms": 8000}
        case EventType.RACE_STATE:
            return {"state": "running"}
        case EventType.FUEL:
            return {"level_percent": 50.0}
        case EventType.CONTROLLER_INPUT:
            return {"throttle": 0.5, "brake": 0.0}
        case EventType.SPEED:
            return {"speed_kmh": 42.0}
        case EventType.BRAKE:
            return {"brake": 0.3}
        case EventType.PITLANE:
            return {"in_pit": False, "reason": "manual"}
        case EventType.CONNECTION_STATE:
            return {"state": "connected", "error": None}
        case EventType.NOT_SUPPORTED:
            return {"reason": "test"}
        case EventType.RAW:
            return {}
    return {}


# ---------------------------------------------------------------------
# Race-management fixtures (opt-in: only loaded by tests that request them)
# ---------------------------------------------------------------------


@pytest.fixture
def engine():
    """In-memory SQLite engine shared across threads/connections."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool

    from src import database as db_mod

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn: Any, _record: Any) -> None:
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()

    # Register models on Base then create schema.
    from sqlalchemy.orm import sessionmaker

    from src import models  # noqa: F401

    db_mod.Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, expire_on_commit=False, future=True)

    # Patch module globals so SessionLocal()/get_engine() use our test engine.
    orig_engine = db_mod._engine
    orig_session = db_mod._SessionLocal
    db_mod._engine = eng
    db_mod._SessionLocal = sm
    try:
        yield eng
    finally:
        db_mod._engine = orig_engine
        db_mod._SessionLocal = orig_session
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    from src.database import get_sessionmaker

    return get_sessionmaker()


@pytest.fixture
def db_session(session_factory):
    sess = session_factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def race_factory(engine):
    """Build a draft race + drivers via the repository layer; return RaceRead."""
    from src.database import SessionLocal
    from src.repositories.race_repository import RaceRepository
    from src.schemas.race_schema import (
        DriverAssignment,
        RaceCreate,
        RaceMode,
    )

    def _make(
        *,
        name: str = "Test Race",
        mode: RaceMode = RaceMode.FIXED_LAPS,
        lap_target: int | None = 10,
        duration_value: int | None = None,
        duration_unit: Any = None,
        drivers: list[tuple[int, str]] | None = None,
    ):
        if drivers is None:
            drivers = [(1, "Alice"), (2, "Bob")]
        payload = RaceCreate(
            name=name,
            mode=mode,
            lap_target=lap_target,
            duration_value=duration_value,
            duration_unit=duration_unit,
            driver_count=len(drivers),
            drivers=[DriverAssignment(car_id=c, driver_name=n) for c, n in drivers],
        )
        repo = RaceRepository()
        with SessionLocal() as session:
            race = repo.create_race(session, payload)
            session.commit()
            return repo.to_read(session, race)

    return _make
