"""Streamlit dashboard. Reads `logs/state.json` only — never imports BLE."""

from __future__ import annotations

import json
import time
from pathlib import Path
from textwrap import dedent
from typing import Any

import streamlit as st

from src import utils
from src.config import load_config

# Optional auto-refresh dep (used when st.fragment is unavailable).
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover - optional dep
    st_autorefresh = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_state(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


def _format_lap_ms(ms: int | float | None) -> str:
    """Render a lap time as `S.mmm` or `M:SS.mmm`."""
    if ms is None:
        return "—"
    try:
        total_ms = int(ms)
    except (TypeError, ValueError):
        return "—"
    if total_ms < 0:
        return "—"
    minutes, rem_ms = divmod(total_ms, 60_000)
    seconds = rem_ms / 1000.0
    if minutes > 0:
        return f"{minutes}:{seconds:06.3f}"
    return f"{seconds:.3f}"


# Per-car livery accents.
_CAR_COLORS: dict[int, str] = {
    1: "#FF1801",
    2: "#00A19B",
    3: "#FF8000",
    4: "#3671C6",
    5: "#F5E300",
    6: "#B6BABD",
}


def _car_color(car_id: int) -> str:
    return _CAR_COLORS.get(car_id, "#FFFFFF")


def _connection_color(state: str) -> str:
    return {
        "connected": "#22C55E",
        "ready": "#22C55E",
        "healthy": "#22C55E",
        "subscribing": "#F59E0B",
        "degraded": "#F59E0B",
        "stale": "#F97316",
        "stalled": "#EF4444",
        "connecting": "#F59E0B",
        "scanning": "#F59E0B",
        "reconnecting": "#EF4444",
        "error": "#EF4444",
        "manually_disconnected": "#6B7280",
        "disconnected": "#6B7280",
    }.get(state, "#9CA3AF")


def _connection_icon(state: str) -> str:
    s = str(state or "").lower()
    if s in {"ready", "connected"}:
        return "🟢"
    if s in {"connecting", "scanning", "subscribing", "reconnecting"}:
        return "🟡"
    if s == "stale":
        return "🟠"
    if s == "error":
        return "🔴"
    if s in {"disconnected", "manually_disconnected"}:
        return "⚫"
    return "⚪"


def _race_color(state: str) -> str:
    return {
        "running": "#22C55E",
        "paused": "#F59E0B",
        "idle": "#6B7280",
        "finished": "#3B82F6",
    }.get(state, "#6B7280")


def _fuel_color(pct: float) -> str:
    if pct >= 50:
        return "#22C55E"
    if pct >= 20:
        return "#F59E0B"
    return "#EF4444"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int_keyed_dict(value: Any) -> dict[int, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[int, Any] = {}
    for key, item in value.items():
        if isinstance(key, int):
            normalized[key] = item
            continue
        if isinstance(key, str):
            try:
                normalized[int(key)] = item
            except ValueError:
                continue
    return normalized


def _normalize_car_metric(raw: dict[str, Any], car_id: int) -> dict[str, Any]:
    lap_samples = max(0, _as_int(raw.get("lap_samples"), 0))
    lap_total_ms = max(0, _as_int(raw.get("lap_total_ms"), 0))
    avg_ms = _as_float(raw.get("average_lap_ms"))
    if avg_ms is None and lap_samples > 0:
        avg_ms = float(lap_total_ms) / float(lap_samples)

    speed = _as_float(raw.get("speed_kmh"))
    if speed is None:
        speed = _as_float(raw.get("last_speed_kmh"))

    return {
        "car_id": car_id,
        "driver_name": raw.get("driver_name") if isinstance(raw.get("driver_name"), str) else None,
        "lap_count": max(0, _as_int(raw.get("lap_count"), 0)),
        "latest_lap_ms": _as_int(raw.get("latest_lap_ms"), 0) if raw.get("latest_lap_ms") is not None else None,
        "best_lap_ms": _as_int(raw.get("best_lap_ms"), 0) if raw.get("best_lap_ms") is not None else None,
        "average_lap_ms": avg_ms,
        "position": _as_int(raw.get("position"), 0) if raw.get("position") is not None else None,
        "fuel_percent": _as_float(raw.get("fuel_percent")),
        "pit_active": bool(raw.get("pit_active", raw.get("in_pit", False))),
        "speed_kmh": speed,
    }


def _load_active_race_metadata() -> dict[str, Any] | None:
    try:
        from src.schemas.race_schema import RaceStatus
        from src.services import ensure_database_initialized
        from src.services.race_service import RaceService
    except Exception:
        return None

    try:
        ensure_database_initialized()
        svc = RaceService()
        race = svc.get_active_race()
        if race is None:
            return None
        if race.status not in {RaceStatus.RUNNING, RaceStatus.PAUSED}:
            return None

        elapsed_ms = None
        if race.started_at is not None:
            elapsed_ms = max(
                0,
                int((utils.now_iso() - race.started_at).total_seconds() * 1000.0),
            )

        progress = None
        if race.mode.value == "fixed_duration" and race.duration_seconds and elapsed_ms is not None:
            duration_ms = race.duration_seconds * 1000
            if duration_ms > 0:
                progress = min(100.0, (elapsed_ms / float(duration_ms)) * 100.0)

        safety_car_active = None
        try:
            safety_car_active = bool(svc.is_safety_car_active(race.id))
        except Exception:
            safety_car_active = None

        return {
            "race": {
                "id": race.id,
                "name": race.name,
                "status": race.status.value,
                "mode": race.mode.value,
                "elapsed_ms": elapsed_ms,
                "progress_percent": progress,
                "safety_car_active": safety_car_active,
                "lap_target": race.lap_target,
                "duration_seconds": race.duration_seconds,
            },
            "drivers": {d.car_id: d.driver_name for d in race.drivers},
        }
    except Exception:
        return None


def _resolve_race_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    raw_metrics = _as_dict(state.get("race_metrics"))
    snapshot_race = _as_dict(raw_metrics.get("race"))
    snapshot_diag = _as_dict(raw_metrics.get("diagnostics"))
    snapshot_cars_raw = _as_list(raw_metrics.get("cars"))

    fallback_cars_raw = _as_list(state.get("cars"))
    fallback_map: dict[int, dict[str, Any]] = {}
    for car in fallback_cars_raw:
        if not isinstance(car, dict):
            continue
        car_id = _as_int(car.get("car_id"), 0)
        if 1 <= car_id <= 6:
            fallback_map[car_id] = _normalize_car_metric(car, car_id)

    snapshot_map: dict[int, dict[str, Any]] = {}
    for car in snapshot_cars_raw:
        if not isinstance(car, dict):
            continue
        car_id = _as_int(car.get("car_id"), 0)
        if 1 <= car_id <= 6:
            snapshot_map[car_id] = _normalize_car_metric(car, car_id)

    service_meta = _load_active_race_metadata() or {}
    service_race = _as_dict(service_meta.get("race"))
    service_drivers = _as_int_keyed_dict(service_meta.get("drivers"))

    ids = set(range(1, 7))
    ids.update(fallback_map.keys())
    ids.update(snapshot_map.keys())
    ids.update(int(k) for k in service_drivers if isinstance(k, int) and 1 <= k <= 6)

    cars: list[dict[str, Any]] = []
    for car_id in sorted(ids):
        car = {
            "car_id": car_id,
            "driver_name": None,
            "lap_count": 0,
            "latest_lap_ms": None,
            "best_lap_ms": None,
            "average_lap_ms": None,
            "position": None,
            "fuel_percent": None,
            "pit_active": False,
            "speed_kmh": None,
        }
        if car_id in fallback_map:
            car.update(fallback_map[car_id])
        if car_id in service_drivers and isinstance(service_drivers[car_id], str):
            car["driver_name"] = str(service_drivers[car_id])
        if car_id in snapshot_map:
            for key, value in snapshot_map[car_id].items():
                if value is not None:
                    car[key] = value
        cars.append(car)

    def _car_rank_key(car: dict[str, Any]) -> tuple[int, int, int]:
        best_lap = car.get("best_lap_ms")
        best_lap_key = int(best_lap) if isinstance(best_lap, (int, float)) else 10**12
        return (
            -int(car.get("lap_count", 0) or 0),
            best_lap_key,
            int(car.get("car_id", 0) or 0),
        )

    ranked = sorted(cars, key=_car_rank_key)
    for idx, car in enumerate(ranked, start=1):
        car["position"] = idx

    fastest_values: list[int] = []
    for car in ranked:
        best_lap = car.get("best_lap_ms")
        if isinstance(best_lap, (int, float)):
            fastest_values.append(int(best_lap))
    leader_lap_count = int(ranked[0].get("lap_count", 0) or 0) if ranked else 0
    total_laps = int(sum(int(c.get("lap_count", 0) or 0) for c in ranked))
    leader_car_id = ranked[0]["car_id"] if ranked else None

    race = {
        "id": None,
        "name": None,
        "status": str(state.get("race", "idle")),
        "mode": None,
        "elapsed_ms": None,
        "progress_percent": None,
        "leader_car_id": leader_car_id,
        "fastest_lap_ms": min(fastest_values) if fastest_values else None,
        "total_laps": total_laps,
        "safety_car_active": None,
    }

    for key in ("id", "name", "status", "mode", "elapsed_ms", "progress_percent", "safety_car_active"):
        if key in service_race and service_race[key] is not None:
            race[key] = service_race[key]
    for key in (
        "id",
        "name",
        "status",
        "mode",
        "elapsed_ms",
        "progress_percent",
        "leader_car_id",
        "fastest_lap_ms",
        "total_laps",
        "safety_car_active",
    ):
        if key in snapshot_race and snapshot_race[key] is not None:
            race[key] = snapshot_race[key]

    lap_target = _as_int(service_race.get("lap_target"), 0)
    if race.get("progress_percent") is None and lap_target > 0:
        race["progress_percent"] = min(
            100.0,
            (float(leader_lap_count) / float(lap_target)) * 100.0,
        )

    diagnostics = {
        "last_telemetry_at_iso": snapshot_diag.get("last_telemetry_at_iso"),
        "last_state_update_at_iso": snapshot_diag.get("last_state_update_at_iso"),
        "active_race_id": snapshot_diag.get("active_race_id", race.get("id")),
        "processed_lap_events": _as_int(snapshot_diag.get("processed_lap_events"), 0),
        "cars_in_snapshot": snapshot_diag.get("cars_in_snapshot", [c["car_id"] for c in ranked]),
        "last_lap_payload": snapshot_diag.get("last_lap_payload"),
        "dropped_lap_events": _as_int(snapshot_diag.get("dropped_lap_events"), 0),
    }

    return {
        "race": race,
        "cars": ranked,
        "diagnostics": diagnostics,
        "source_priority": {
            "state_snapshot": bool(raw_metrics),
            "repository_fallback": bool(service_meta),
            "in_memory_fallback": True,
        },
    }


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------


_GLOBAL_CSS = """
<style>
.stApp {
    background:
        radial-gradient(circle at 20% 0%, #1f2937 0%, transparent 40%),
        radial-gradient(circle at 80% 0%, #1e1b4b 0%, transparent 40%),
        #0b0f17;
    color: #f8fafc;
    font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
}
section[data-testid="stSidebar"] { background: #0b0f17; }
h1, h2, h3, h4 { letter-spacing: 0.02em; }

.cm-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 18px; border-radius: 14px;
    background: linear-gradient(90deg, #111827 0%, #1f2937 100%);
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: 0 6px 24px rgba(0,0,0,0.45);
    margin-bottom: 14px;
}
.cm-title { font-size: 28px; font-weight: 800; letter-spacing: 0.05em; }
.cm-title .flag { margin-right: 10px; }
.cm-badges { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.cm-badge {
    padding: 6px 14px; border-radius: 999px;
    font-weight: 700; font-size: 13px; letter-spacing: 0.08em;
    text-transform: uppercase;
    border: 1px solid rgba(255,255,255,0.08);
    background: #0b0f17;
}
.cm-badge .dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 8px; vertical-align: middle;
}

.cm-leaderboard {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: rgba(17,24,39,0.7); border-radius: 14px; overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: 0 10px 30px rgba(0,0,0,0.45);
}
.cm-leaderboard thead th {
    background: #0b0f17;
    color: #9ca3af;
    text-transform: uppercase; letter-spacing: 0.12em; font-size: 11px;
    padding: 12px 14px; text-align: left; font-weight: 700;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
.cm-leaderboard tbody td {
    padding: 14px; vertical-align: middle;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-variant-numeric: tabular-nums;
}
.cm-leaderboard tbody tr:last-child td { border-bottom: 0; }
.cm-leaderboard tbody tr:hover td { background: rgba(255,255,255,0.025); }

.cm-pos { font-weight: 900; font-size: 22px; width: 56px; }
.cm-pos.p1 { color: #FFD700; }
.cm-pos.p2 { color: #C0C0C0; }
.cm-pos.p3 { color: #CD7F32; }

.cm-car {
    display: inline-flex; align-items: center; gap: 10px;
    font-weight: 800; font-size: 16px;
}
.cm-car .chip {
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 10px;
    color: #0b0f17; font-weight: 900; font-size: 16px;
    box-shadow: inset 0 -3px 0 rgba(0,0,0,0.25);
}

.cm-time { font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; font-weight: 700; font-size: 18px; }
.cm-time.best { color: #A78BFA; }
.cm-time.dim  { color: #9ca3af; font-size: 15px; font-weight: 600; }

.cm-laps { font-size: 22px; font-weight: 900; }
.cm-gap  { color: #9ca3af; font-family: "JetBrains Mono", monospace; }
.cm-pit  {
    color: #0b0f17; background: #FBBF24; padding: 2px 8px; border-radius: 6px;
    font-size: 11px; font-weight: 800; letter-spacing: 0.08em; margin-left: 8px;
}

.cm-fuel-wrap { width: 140px; }
.cm-fuel-bar {
    width: 100%; height: 10px; background: #1f2937; border-radius: 999px; overflow: hidden;
    border: 1px solid rgba(255,255,255,0.05);
}
.cm-fuel-fill { height: 100%; border-radius: 999px; transition: width 200ms ease-out; }
.cm-fuel-num  { color: #9ca3af; font-size: 11px; margin-top: 4px; font-variant-numeric: tabular-nums; }

.cm-speed { font-family: "JetBrains Mono", monospace; font-weight: 800; font-size: 18px; color: #f8fafc; }
.cm-speed .unit { color: #6b7280; font-size: 12px; margin-left: 4px; }

.cm-footer-meta {
    color: #6b7280; font-size: 12px; margin-top: 10px; text-align: right;
    font-variant-numeric: tabular-nums;
}
</style>
"""


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _render_header(state: dict[str, Any], race_snapshot: dict[str, Any]) -> None:
    conn = _as_dict(state.get("connection"))
    conn_state = str(conn.get("state", "unknown")).lower()
    race = _as_dict(race_snapshot.get("race"))
    race_status = str(race.get("status", "idle")).upper()
    active_car_count = len(race_snapshot.get("cars") or [])

    st.html(
        dedent(
            f"""\
            <div class="cm-header">
                <div class="cm-title"><span class="flag">🏁</span>CARRERA · LIVE TIMING</div>
                <div class="cm-badges">
                    <span class="cm-badge">CARS · {active_car_count}</span>
                    <span class="cm-badge">
                        <span class="dot" style="background:{_race_color(str(race.get('status', 'idle')).lower())}"></span>
                        RACE · {race_status}
                    </span>
                    <span class="cm-badge" title="Connection status" style="font-size:18px;padding:4px 10px;">
                        {_connection_icon(conn_state)}
                    </span>
                </div>
            </div>
            """
        )
    )


def _render_race_metrics(race_snapshot: dict[str, Any]) -> None:
    race = _as_dict(race_snapshot.get("race"))
    cars: list[dict[str, Any]] = [c for c in _as_list(race_snapshot.get("cars")) if isinstance(c, dict)]

    race_name = race.get("name") if isinstance(race.get("name"), str) else "-"
    race_status = str(race.get("status") or "idle").upper()
    race_mode = str(race.get("mode") or "-").upper()
    elapsed_display = _format_lap_ms(race.get("elapsed_ms"))
    progress = _as_float(race.get("progress_percent"))
    progress_display = f"{progress:.1f}%" if progress is not None else "-"
    leader_display = f"#{race.get('leader_car_id')}" if race.get("leader_car_id") is not None else "-"
    total_laps = _as_int(race.get("total_laps"), 0)
    fastest_lap = _format_lap_ms(race.get("fastest_lap_ms"))
    safety_raw = race.get("safety_car_active")
    safety_display = "ON" if safety_raw is True else "OFF" if safety_raw is False else "-"

    st.subheader("Race Metrics")
    top = st.columns(6)
    top[0].metric("Race", race_name)
    top[1].metric("Status", race_status)
    top[2].metric("Mode", race_mode)
    top[3].metric("Elapsed", elapsed_display)
    top[4].metric("Progress", progress_display)
    top[5].metric("Leader", leader_display)

    global_cols = st.columns(3)
    global_cols[0].metric("Total Laps", str(total_laps))
    global_cols[1].metric("Fastest Lap", fastest_lap)
    global_cols[2].metric("Safety Car", safety_display)

    if not cars:
        cars = [
            {
                "car_id": car_id,
                "driver_name": None,
                "lap_count": 0,
                "latest_lap_ms": None,
                "best_lap_ms": None,
                "fuel_percent": None,
                "pit_active": False,
                "speed_kmh": None,
                "position": car_id,
            }
            for car_id in range(1, 7)
        ]

    leader = cars[0]
    leader_laps = int(leader.get("lap_count", 0) or 0)
    leader_best = leader.get("best_lap_ms")

    rows_html: list[str] = []
    for car in cars:
        pos = _as_int(car.get("position"), 0)
        if pos <= 0:
            pos = len(rows_html) + 1
        pos_class = {1: "p1", 2: "p2", 3: "p3"}.get(pos, "")
        car_id = _as_int(car.get("car_id"), 0)
        color = _car_color(car_id)
        driver = car.get("driver_name") if isinstance(car.get("driver_name"), str) else f"Car {car_id}"
        laps = _as_int(car.get("lap_count"), 0)
        best_ms = car.get("best_lap_ms")
        latest_ms = car.get("latest_lap_ms")
        fuel_pct = car.get("fuel_percent")
        speed = car.get("speed_kmh")
        in_pit = bool(car.get("pit_active"))

        if pos == 1:
            gap_str = "—"
        else:
            lap_diff = leader_laps - laps
            if lap_diff > 0:
                gap_str = f"+{lap_diff} L"
            elif isinstance(best_ms, (int, float)) and isinstance(leader_best, (int, float)):
                delta = float(best_ms) - float(leader_best)
                gap_str = f"+{delta / 1000:.3f}"
            else:
                gap_str = "—"

        pit_html = '<span class="cm-pit">PIT</span>' if in_pit else ""

        if isinstance(fuel_pct, (int, float)):
            f_val = max(0.0, min(100.0, float(fuel_pct)))
            fuel_html = (
                '<div class="cm-fuel-wrap">'
                '<div class="cm-fuel-bar"><div class="cm-fuel-fill" '
                f'style="width:{f_val:.1f}%;background:{_fuel_color(f_val)}"></div></div>'
                f'<div class="cm-fuel-num">{f_val:.1f}%</div>'
                "</div>"
            )
        else:
            fuel_html = '<span class="cm-time dim">-</span>'

        if isinstance(speed, (int, float)):
            speed_html = (
                f'<span class="cm-speed">{float(speed):5.1f}<span class="unit"> km/h</span></span>'
            )
        else:
            speed_html = '<span class="cm-time dim">-</span>'

        rows_html.append(
            dedent(
                f"""\
                <tr>
                    <td class="cm-pos {pos_class}">P{pos}</td>
                    <td>
                        <span class="cm-car">
                            <span class="chip" style="background:{color}">#{car_id}</span>
                            {driver}{pit_html}
                        </span>
                    </td>
                    <td class="cm-laps">{laps}</td>
                    <td class="cm-time best">{_format_lap_ms(best_ms)}</td>
                    <td class="cm-time">{_format_lap_ms(latest_ms)}</td>
                    <td class="cm-gap">{gap_str}</td>
                    <td>{fuel_html}</td>
                    <td>{speed_html}</td>
                </tr>
                """
            )
        )

    table_html = (
        '<table class="cm-leaderboard">'
        "<thead><tr>"
        "<th>POS</th><th>CAR</th><th>LAPS</th><th>BEST</th>"
        "<th>LAST</th><th>GAP</th><th>FUEL</th><th>SPEED</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )
    st.html(table_html)


def _render_diagnostics(state: dict[str, Any], race_snapshot: dict[str, Any]) -> None:
    conn = _as_dict(state.get("connection"))
    diagnostics = _as_dict(race_snapshot.get("diagnostics"))
    with st.expander("Diagnostics", expanded=False):
        st.write(
            {
                "connection": {
                    "state": conn.get("state"),
                    "device_name": conn.get("device_name"),
                    "mac_address": conn.get("mac_address"),
                    "last_seen_at": conn.get("last_seen_at"),
                    "reconnect_attempts": conn.get("reconnect_attempts"),
                    "last_error": conn.get("last_error"),
                    "reason": conn.get("reason"),
                },
                "race_metrics": diagnostics,
                "source_priority": race_snapshot.get("source_priority", {}),
            }
        )

        recent = _as_list(state.get("recent_events"))
        if not recent:
            st.caption("(no events yet)")
            return

        rows: list[dict[str, Any]] = []
        for ev in recent[:50]:
            if not isinstance(ev, dict):
                continue
            payload = _as_dict(ev.get("payload"))
            if ev.get("event_type") == "lap" and "lap_time_ms" in payload:
                payload = {
                    **payload,
                    "lap_time": _format_lap_ms(payload.get("lap_time_ms")),
                }
            rows.append(
                {
                    "ts_ms": ev.get("timestamp_monotonic_ms"),
                    "type": ev.get("event_type"),
                    "car": ev.get("car_id"),
                    "payload": payload,
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_body(state_file: Path, refresh_ms: int) -> None:
    state = _load_state(state_file)
    if state is None:
        st.warning(f"Initializing… (waiting for `{state_file}`)")
        return

    try:
        mtime = state_file.stat().st_mtime
        age_ms = (time.time() - mtime) * 1000
        if age_ms > 5 * refresh_ms:
            st.error(f"⚠ Stale data: snapshot is {int(age_ms)} ms old.")
    except OSError:
        pass

    race_snapshot = _resolve_race_snapshot(state)
    _render_header(state, race_snapshot)
    _render_race_metrics(race_snapshot)
    _render_diagnostics(state, race_snapshot)

    snap_iso = state.get("taken_at_iso")
    if snap_iso:
        st.html(
            f'<div class="cm-footer-meta">snapshot · {snap_iso} · refresh {refresh_ms} ms</div>'
        )


def render() -> None:
    st.set_page_config(
        page_title="Carrera · Live Timing",
        layout="wide",
        initial_sidebar_state="collapsed",
        page_icon="🏁",
    )
    st.html(_GLOBAL_CSS)

    cfg_path = Path("config.yaml")
    cfg = load_config(cfg_path if cfg_path.exists() else None)
    log_dir = Path(cfg.logging.directory)
    state_file = log_dir / "state.json"
    refresh_ms = cfg.dashboard.refresh_interval_ms

    # Prefer st.fragment for in-place re-renders (Streamlit ≥1.37); fall back
    # to st_autorefresh or a meta refresh.
    fragment_decorator = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    if fragment_decorator is not None:

        @fragment_decorator(run_every=refresh_ms / 1000.0)
        def _frag() -> None:
            _render_body(state_file, refresh_ms)

        _frag()
        return

    if st_autorefresh is not None:
        st_autorefresh(interval=refresh_ms, key="carrera_refresh")
    else:  # pragma: no cover - last-resort fallback
        st.html(
            f'<meta http-equiv="refresh" content="{max(1, refresh_ms // 1000)}">'
        )
    _render_body(state_file, refresh_ms)


if __name__ == "__main__":
    render()
