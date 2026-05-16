from __future__ import annotations

from typing import Any

from src import dashboard


class _DummyExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _MetricSink:
    def __init__(self, sink: list[tuple[str, Any]]):
        self._sink = sink

    def metric(self, label: str, value: Any) -> None:
        self._sink.append((label, value))


def _minimal_snapshot() -> dict[str, Any]:
    return {
        "race": {
            "id": None,
            "name": None,
            "status": "idle",
            "mode": None,
            "elapsed_ms": None,
            "progress_percent": None,
            "leader_car_id": None,
            "fastest_lap_ms": None,
            "total_laps": 0,
            "safety_car_active": None,
        },
        "cars": [],
        "diagnostics": {
            "last_telemetry_at_iso": None,
            "last_state_update_at_iso": None,
            "active_race_id": None,
            "processed_lap_events": 0,
            "cars_in_snapshot": [],
            "last_lap_payload": None,
            "dropped_lap_events": 0,
        },
        "source_priority": {
            "state_snapshot": False,
            "repository_fallback": False,
            "in_memory_fallback": True,
        },
    }


def test_connection_icon_mapping_all_required_states() -> None:
    assert dashboard._connection_icon("ready") == "🟢"
    assert dashboard._connection_icon("connected") == "🟢"
    assert dashboard._connection_icon("connecting") == "🟡"
    assert dashboard._connection_icon("scanning") == "🟡"
    assert dashboard._connection_icon("subscribing") == "🟡"
    assert dashboard._connection_icon("reconnecting") == "🟡"
    assert dashboard._connection_icon("stale") == "🟠"
    assert dashboard._connection_icon("error") == "🔴"
    assert dashboard._connection_icon("disconnected") == "⚫"
    assert dashboard._connection_icon("manually_disconnected") == "⚫"
    assert dashboard._connection_icon("unknown") == "⚪"
    assert dashboard._connection_icon("") == "⚪"


def test_header_renders_icon_only_without_verbose_link_text(monkeypatch) -> None:
    html_calls: list[str] = []
    monkeypatch.setattr(dashboard.st, "html", lambda content: html_calls.append(content))

    state = {
        "connection": {
            "state": "reconnecting",
            "desired_connected": True,
            "reconnect_attempts": 4,
            "last_error": "boom",
            "device_name": "Control_Unit",
        }
    }
    dashboard._render_header(state, _minimal_snapshot())

    assert html_calls, "header html should be emitted"
    header_html = html_calls[0]
    assert "🟡" in header_html
    assert "LINK ·" not in header_html
    assert "RETRIES ·" not in header_html
    assert "DEVICE ·" not in header_html


def test_resolve_race_snapshot_ignores_non_canonical_car_ids_and_keeps_placeholders() -> None:
    state = {
        "race": "running",
        "cars": [
            {"car_id": 1, "lap_count": 2, "best_lap_ms": 6000, "latest_lap_ms": 6100},
            {"car_id": 7, "lap_count": 9, "best_lap_ms": 5000, "latest_lap_ms": 5100},
        ],
    }
    snap = dashboard._resolve_race_snapshot(state)

    ids = [int(c["car_id"]) for c in snap["cars"]]
    assert 7 not in ids
    assert ids == [1, 2, 3, 4, 5, 6]
    assert snap["race"]["status"] == "running"


def test_render_race_metrics_always_outputs_table_rows_when_no_active_race(monkeypatch) -> None:
    html_calls: list[str] = []
    metrics: list[tuple[str, Any]] = []

    monkeypatch.setattr(dashboard.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        dashboard.st,
        "columns",
        lambda n: [_MetricSink(metrics) for _ in range(n)],
    )
    monkeypatch.setattr(dashboard.st, "html", lambda content: html_calls.append(content))

    dashboard._render_race_metrics(_minimal_snapshot())

    assert html_calls, "leaderboard table should still render"
    table_html = html_calls[-1]
    assert "#1" in table_html
    assert "#6" in table_html
    assert ("Race", "-") in metrics
    assert ("Progress", "-") in metrics


def test_render_diagnostics_is_collapsed_by_default_and_includes_connection_details(monkeypatch) -> None:
    expander_calls: list[tuple[str, bool]] = []
    writes: list[dict[str, Any]] = []

    def _fake_expander(label: str, expanded: bool = False):
        expander_calls.append((label, expanded))
        return _DummyExpander()

    monkeypatch.setattr(dashboard.st, "expander", _fake_expander)
    monkeypatch.setattr(dashboard.st, "write", lambda payload: writes.append(payload))
    monkeypatch.setattr(dashboard.st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(dashboard.st, "caption", lambda *_args, **_kwargs: None)

    state = {
        "connection": {
            "state": "ready",
            "device_name": "Control_Unit",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "last_seen_at": "2026-05-16T12:00:00+00:00",
            "reconnect_attempts": 1,
            "last_error": None,
            "reason": "subscriptions_ready",
        },
        "recent_events": [],
    }

    race_snapshot = _minimal_snapshot()
    race_snapshot["diagnostics"] = {
        "last_telemetry_at_iso": "2026-05-16T12:00:00+00:00",
        "last_state_update_at_iso": "2026-05-16T12:00:01+00:00",
        "active_race_id": 42,
        "processed_lap_events": 4,
        "cars_in_snapshot": [1, 2],
        "last_lap_payload": {"lap_number": 4, "lap_time_ms": 5555},
        "dropped_lap_events": 0,
    }

    dashboard._render_diagnostics(state, race_snapshot)

    assert expander_calls == [("Diagnostics", False)]
    assert writes, "diagnostic payload should be rendered"
    payload = writes[0]
    assert payload["connection"]["device_name"] == "Control_Unit"
    assert payload["connection"]["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert payload["race_metrics"]["processed_lap_events"] == 4


def test_resolve_race_snapshot_is_stable_across_refresh_calls() -> None:
    state = {
        "race": "running",
        "cars": [
            {
                "car_id": 2,
                "lap_count": 5,
                "best_lap_ms": 5500,
                "latest_lap_ms": 5600,
                "fuel_percent": 70.0,
                "pit_active": False,
                "speed_kmh": 95.0,
            },
            {
                "car_id": 1,
                "lap_count": 4,
                "best_lap_ms": 5700,
                "latest_lap_ms": 5800,
                "fuel_percent": 68.0,
                "pit_active": False,
                "speed_kmh": 91.0,
            },
        ],
    }

    first = dashboard._resolve_race_snapshot(state)
    second = dashboard._resolve_race_snapshot(state)

    first_ids = [c["car_id"] for c in first["cars"]]
    second_ids = [c["car_id"] for c in second["cars"]]
    assert first_ids == second_ids
    assert first["race"]["total_laps"] == second["race"]["total_laps"]
