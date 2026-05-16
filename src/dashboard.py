"""Streamlit dashboard. Reads `logs/state.json` only — never imports BLE."""

from __future__ import annotations

import json
import time
from pathlib import Path
from textwrap import dedent
from typing import Any

import streamlit as st

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
        "stale": "#EF4444",
        "stalled": "#EF4444",
        "connecting": "#F59E0B",
        "scanning": "#F59E0B",
        "reconnecting": "#EF4444",
        "error": "#EF4444",
        "manually_disconnected": "#6B7280",
        "disconnected": "#6B7280",
    }.get(state, "#6B7280")


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


def _render_header(state: dict[str, Any]) -> None:
    conn = state.get("connection") or {}
    conn_state = str(conn.get("state", "?"))
    conn_reason = conn.get("reason")
    desired_connected = bool(conn.get("desired_connected", False))
    device_name = conn.get("device_name") if isinstance(conn.get("device_name"), str) else None
    mac_address = conn.get("mac_address") if isinstance(conn.get("mac_address"), str) else None
    last_seen = conn.get("last_seen_at") if isinstance(conn.get("last_seen_at"), str) else None
    reconnect_attempts_raw = conn.get("reconnect_attempts")
    reconnect_attempts = (
        int(reconnect_attempts_raw)
        if isinstance(reconnect_attempts_raw, (int, float, str))
        else 0
    )
    race_state = str(state.get("race", "idle"))
    active_raw = state.get("active_car_count")
    active_car_count = int(active_raw) if isinstance(active_raw, (int, float, str)) else 0
    last_err = conn.get("last_error")

    err_html = ""
    if last_err:
        err_html = (
            f'<span class="cm-badge" style="color:#fecaca;border-color:#7f1d1d;">'
            f"⚠ {last_err}</span>"
        )
    reason_html = ""
    if isinstance(conn_reason, str) and conn_reason:
        reason_html = (
            '<span class="cm-badge" style="color:#cbd5e1;border-color:#334155;">'
            f"REASON · {conn_reason}</span>"
        )

    stale_html = ""
    if conn_state == "stale":
        stale_html = (
            '<span class="cm-badge" style="color:#fecaca;border-color:#7f1d1d;">'
            "STALE TELEMETRY</span>"
        )

    device_html = ""
    if device_name or mac_address:
        label = device_name or "unknown"
        suffix = f" · {mac_address}" if mac_address else ""
        device_html = f'<span class="cm-badge">DEVICE · {label}{suffix}</span>'

    last_seen_html = ""
    if last_seen:
        last_seen_html = f'<span class="cm-badge">LAST SEEN · {last_seen}</span>'

    st.html(
        dedent(
            f"""\
            <div class="cm-header">
                <div class="cm-title"><span class="flag">🏁</span>CARRERA · LIVE TIMING</div>
                <div class="cm-badges">
                    {err_html}
                    {reason_html}
                    {stale_html}
                    {device_html}
                    {last_seen_html}
                    <span class="cm-badge">CARS · {active_car_count}</span>
                    <span class="cm-badge">DESIRED · {str(desired_connected).upper()}</span>
                    <span class="cm-badge">RETRIES · {reconnect_attempts}</span>
                    <span class="cm-badge">
                        <span class="dot" style="background:{_race_color(race_state)}"></span>
                        RACE · {race_state.upper()}
                    </span>
                    <span class="cm-badge">
                        <span class="dot" style="background:{_connection_color(conn_state)}"></span>
                        LINK · {conn_state.upper()}
                    </span>
                </div>
            </div>
            """
        )
    )


def _render_leaderboard(state: dict[str, Any]) -> None:
    cars: list[dict[str, Any]] = list(state.get("cars") or [])
    if not cars:
        st.info("Waiting for cars…")
        return

    def _sort_key(c: dict[str, Any]) -> tuple[int, int]:
        laps = -int(c.get("lap_count", 0) or 0)
        best = c.get("best_lap_ms")
        best_v = int(best) if isinstance(best, (int, float)) else 10**12
        return (laps, best_v)

    cars.sort(key=_sort_key)

    leader = cars[0]
    leader_laps = int(leader.get("lap_count", 0) or 0)
    leader_best = leader.get("best_lap_ms")

    rows_html: list[str] = []
    for idx, car in enumerate(cars):
        pos = idx + 1
        pos_class = {1: "p1", 2: "p2", 3: "p3"}.get(pos, "")
        car_id = int(car.get("car_id", 0) or 0)
        color = _car_color(car_id)
        laps = int(car.get("lap_count", 0) or 0)
        best_ms = car.get("best_lap_ms")
        latest_ms = car.get("latest_lap_ms")
        fuel_pct = car.get("fuel_percent")
        speed = car.get("last_speed_kmh")
        in_pit = bool(car.get("in_pit"))

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
            fuel_html = '<span class="cm-time dim">—</span>'

        if isinstance(speed, (int, float)):
            speed_html = (
                f'<span class="cm-speed">{float(speed):5.1f}<span class="unit"> km/h</span></span>'
            )
        else:
            speed_html = '<span class="cm-time dim">—</span>'

        rows_html.append(
            dedent(
                f"""\
                <tr>
                    <td class="cm-pos {pos_class}">P{pos}</td>
                    <td>
                        <span class="cm-car">
                            <span class="chip" style="background:{color}">#{car_id}</span>
                            Car {car_id}{pit_html}
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


def _render_recent(state: dict[str, Any]) -> None:
    with st.expander("Recent events", expanded=False):
        recent = state.get("recent_events") or []
        if not recent:
            st.caption("(no events yet)")
            return
        rows: list[dict[str, Any]] = []
        for ev in recent[:50]:
            payload = ev.get("payload") or {}
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

    _render_header(state)
    _render_leaderboard(state)
    _render_recent(state)

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
