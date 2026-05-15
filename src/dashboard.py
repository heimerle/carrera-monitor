"""Streamlit dashboard. Reads `logs/state.json` only — never imports BLE."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import streamlit as st

# Lazy import to avoid pulling pydantic-heavy modules unnecessarily.
try:
    from streamlit_autorefresh import st_autorefresh  # type: ignore
except Exception:  # pragma: no cover - optional dep
    st_autorefresh = None  # type: ignore

from src.config import load_config


def _load_state(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


def render() -> None:
    st.set_page_config(page_title="Carrera Monitor", layout="wide")

    # Config (just to discover the log dir + refresh interval).
    cfg_path = Path("config.yaml")
    cfg = load_config(cfg_path if cfg_path.exists() else None)
    log_dir = Path(cfg.logging.directory)
    state_file = log_dir / "state.json"
    refresh_ms = cfg.dashboard.refresh_interval_ms

    # Auto-refresh.
    if st_autorefresh is not None:
        st_autorefresh(interval=refresh_ms, key="carrera_refresh")
    else:
        # Fallback: tell Streamlit to rerun via a sleep + meta-refresh hint.
        st.markdown(
            f'<meta http-equiv="refresh" content="{max(1, refresh_ms // 1000)}">',
            unsafe_allow_html=True,
        )

    st.title("🏁 Carrera Monitor")

    state = _load_state(state_file)
    if state is None:
        st.warning(f"Initializing… (waiting for `{state_file}`)")
        return

    # Stale-data banner (mtime older than 5× refresh interval).
    try:
        mtime = state_file.stat().st_mtime
        age_ms = (time.time() - mtime) * 1000
        if age_ms > 5 * refresh_ms:
            st.error(f"⚠️ Stale data: snapshot is {int(age_ms)} ms old.")
    except OSError:
        pass

    # Connection + race state header.
    conn = state.get("connection", {})
    race = state.get("race", "idle")
    c1, c2, c3 = st.columns(3)
    c1.metric("Connection", conn.get("state", "?"))
    c2.metric("Race state", race)
    if conn.get("last_error"):
        c3.metric("Last error", conn["last_error"])

    # Per-car cards.
    cars = state.get("cars", [])
    if not cars:
        st.info("No cars reporting yet.")
    else:
        cols = st.columns(min(len(cars), 3))
        for i, car in enumerate(cars):
            col = cols[i % len(cols)]
            with col:
                pit_badge = "🅿️ in pit" if car.get("in_pit") else ""
                st.subheader(f"Car {car['car_id']}  {pit_badge}")
                st.metric("Lap count", car.get("lap_count", 0))
                latest = car.get("latest_lap_ms")
                best = car.get("best_lap_ms")
                st.metric("Latest lap (ms)", latest if latest is not None else "—")
                st.metric("Best lap (ms)", best if best is not None else "—")
                fuel = car.get("fuel_percent")
                if fuel is not None:
                    st.progress(min(1.0, max(0.0, fuel / 100.0)), text=f"Fuel: {fuel:.1f}%")
                speed = car.get("last_speed_kmh")
                if speed is not None:
                    st.caption(f"Speed: {speed:.1f} km/h")

    # Recent events panel.
    with st.expander("Recent events", expanded=False):
        recent = state.get("recent_events", [])
        if not recent:
            st.caption("(no events yet)")
        else:
            rows: list[dict[str, Any]] = []
            for ev in recent[:50]:
                rows.append(
                    {
                        "ts_ms": ev.get("timestamp_monotonic_ms"),
                        "type": ev.get("event_type"),
                        "car": ev.get("car_id"),
                        "payload": ev.get("payload"),
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render()
