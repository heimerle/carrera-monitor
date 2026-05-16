"""Smoke test: ``init_db()`` against in-memory engine creates all 5 tables + indices."""

from __future__ import annotations

from sqlalchemy import inspect


def test_init_db_creates_all_tables(engine):
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {
        "races",
        "race_drivers",
        "race_laps",
        "race_events",
        "race_reports",
        "race_lap_checkpoints",
        "race_lap_ingest_identities",
    } <= tables


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


def test_continuity_tables_have_uniqueness_constraints(engine):
    insp = inspect(engine)
    checkpoint_uqs = insp.get_unique_constraints("race_lap_checkpoints")
    checkpoint_cols = [tuple(u["column_names"]) for u in checkpoint_uqs]
    assert ("race_id", "car_id") in checkpoint_cols

    identity_uqs = insp.get_unique_constraints("race_lap_ingest_identities")
    identity_cols = [tuple(u["column_names"]) for u in identity_uqs]
    assert ("race_id", "car_id", "cu_timestamp_ms") in identity_cols
