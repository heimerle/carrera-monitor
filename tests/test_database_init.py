"""Smoke test: ``init_db()`` against in-memory engine creates all 5 tables + indices."""

from __future__ import annotations

from sqlalchemy import inspect


def test_init_db_creates_all_tables(engine):
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {"races", "race_drivers", "race_laps", "race_events", "race_reports"} <= tables


def test_race_drivers_unique_constraint(engine):
    insp = inspect(engine)
    uqs = insp.get_unique_constraints("race_drivers")
    cols = [tuple(u["column_names"]) for u in uqs]
    assert ("race_id", "car_id") in cols


def test_race_laps_indices_present(engine):
    insp = inspect(engine)
    idx_names = {i["name"] for i in insp.get_indexes("race_laps")}
    assert "ix_race_laps_race_car" in idx_names


def test_foreign_keys_enabled(engine):
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
        assert result == 1
