"""Race Management page — UI layer, no ORM imports (FR-130).

Calls only into ``src.services.race_service.RaceService`` and
``src.services.reporting_service.ReportingService``. Implements FR-127
(list view), FR-128 (create/edit/delete), FR-129 (running view), and the
US2 Repeat button.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial
from pathlib import Path

import streamlit as st

from src.config import load_config
from src.schemas.race_schema import (
    DriverAssignment,
    DurationUnit,
    RaceCreate,
    RaceMode,
    RaceRead,
    RaceStatus,
)
from src.services import (
    InvalidRaceStateError,
    RaceNotEditableError,
    RaceNotFoundError,
    RaceValidationError,
    ensure_database_initialized,
)
from src.services.race_service import RaceService
from src.services.reporting_service import ReportingService


def _load_live_snapshot() -> dict[str, object] | None:
    cfg_path = Path("config.yaml")
    cfg = load_config(cfg_path if cfg_path.exists() else None)
    state_path = Path(cfg.logging.directory) / "state.json"
    try:
        with open(state_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _get_service() -> RaceService:
    if "race_service" not in st.session_state:
        ensure_database_initialized()
        st.session_state["race_service"] = RaceService()
    svc: RaceService = st.session_state["race_service"]
    return svc


def _get_reporting() -> ReportingService:
    if "reporting_service" not in st.session_state:
        st.session_state["reporting_service"] = ReportingService(
            race_service=_get_service()
        )
    rep: ReportingService = st.session_state["reporting_service"]
    return rep


def _status_badge(status: RaceStatus) -> str:
    colors = {
        RaceStatus.DRAFT: "⚪",
        RaceStatus.READY: "🟡",
        RaceStatus.RUNNING: "🟢",
        RaceStatus.PAUSED: "🟠",
        RaceStatus.FINISHED: "🔵",
        RaceStatus.CANCELLED: "⚫",
    }
    return f"{colors.get(status, '⚪')} {status.value}"


def _render_create_form() -> None:
    st.subheader("Create new race")
    with st.form("new_race"):
        name = st.text_input("Race name", value="New Race")
        mode = st.selectbox("Mode", options=[m.value for m in RaceMode])
        col_a, col_b = st.columns(2)
        lap_target = col_a.number_input(
            "Lap target", min_value=1, value=10, step=1, disabled=(mode != "fixed_laps")
        )
        duration_value = col_b.number_input(
            "Duration",
            min_value=1,
            value=10,
            step=1,
            disabled=(mode != "fixed_duration"),
        )
        duration_unit = col_b.selectbox(
            "Unit",
            options=[u.value for u in DurationUnit],
            disabled=(mode != "fixed_duration"),
        )
        driver_count = st.number_input(
            "Driver count", min_value=1, max_value=6, value=2, step=1
        )
        drivers: list[DriverAssignment] = []
        for i in range(int(driver_count)):
            cols = st.columns([1, 3])
            car_id = cols[0].number_input(
                f"car_id #{i + 1}",
                min_value=1,
                max_value=6,
                value=i + 1,
                key=f"car_id_{i}",
            )
            driver_name = cols[1].text_input(
                f"driver name #{i + 1}",
                value=f"Driver {i + 1}",
                key=f"driver_name_{i}",
            )
            drivers.append(
                DriverAssignment(car_id=int(car_id), driver_name=driver_name)
            )
        notes = st.text_area("Notes", value="")
        submitted = st.form_submit_button("Create")
        if submitted:
            try:
                payload = RaceCreate(
                    name=name,
                    mode=RaceMode(mode),
                    lap_target=int(lap_target) if mode == "fixed_laps" else None,
                    duration_value=int(duration_value)
                    if mode == "fixed_duration"
                    else None,
                    duration_unit=DurationUnit(duration_unit)
                    if mode == "fixed_duration"
                    else None,
                    driver_count=int(driver_count),
                    drivers=drivers,
                    notes=notes or None,
                )
                race = _get_service().create_race(payload)
                st.success(f"Created race id={race.id}: {race.name}")
                st.rerun()
            except (RaceValidationError, ValueError) as exc:
                st.error(str(exc))


def _render_list() -> None:
    st.subheader("Races")
    races = _get_service().list_races(limit=200)
    if not races:
        st.info("No races yet. Create one above.")
        return
    for race in races:
        with st.container(border=True):
            cols = st.columns([3, 2, 1, 1, 1, 1, 1, 1])
            cols[0].markdown(f"**{race.name}** (id={race.id})")
            cols[1].markdown(_status_badge(race.status))
            cols[2].caption(race.mode.value)
            race_id = race.id
            svc = _get_service()
            if race.status in {RaceStatus.DRAFT, RaceStatus.READY}:
                if cols[3].button("Start", key=f"start_{race_id}"):
                    _safe(partial(svc.start_race, race_id))
            elif race.status is RaceStatus.RUNNING:
                if cols[3].button("Pause", key=f"pause_{race_id}"):
                    _safe(partial(svc.pause_race, race_id))
            elif race.status is RaceStatus.PAUSED and cols[3].button(
                "Resume", key=f"resume_{race_id}"
            ):
                _safe(partial(svc.resume_race, race_id))
            if race.status in {RaceStatus.RUNNING, RaceStatus.PAUSED} and cols[4].button(
                "Finish", key=f"finish_{race_id}"
            ):
                _safe(partial(svc.finish_race, race_id))
            if race.status not in {RaceStatus.FINISHED, RaceStatus.CANCELLED} and cols[
                5
            ].button("Cancel", key=f"cancel_{race_id}"):
                _safe(partial(svc.cancel_race, race_id))
            if cols[6].button("Repeat", key=f"repeat_{race_id}"):
                _safe(partial(svc.repeat_race, race_id))
            if race.status != RaceStatus.RUNNING and cols[7].button(
                "Delete", key=f"delete_{race_id}"
            ):
                _safe(partial(svc.delete_race, race_id))


def _safe(callable_: Callable[[], object]) -> None:
    try:
        callable_()
        callable_()
        st.rerun()
    except (
        RaceNotFoundError,
        RaceValidationError,
        RaceNotEditableError,
        InvalidRaceStateError,
        ValueError,
    ) as exc:
        st.error(str(exc))


def _render_race_controls(race: RaceRead) -> None:
    """Prominent race-control bar shown above the active race standings.

    - "Finish Race" calls :meth:`RaceService.finish_race_by_user` (visible only
      for ``running`` / ``paused`` races, per the new requirement).
    - "Safety Car ON/OFF" toggles a safety-car phase via
      :meth:`RaceService.set_safety_car`.
    """
    svc = _get_service()
    sc_active = svc.is_safety_car_active(race.id)
    if sc_active:
        st.warning("🟡 Safety car phase is currently ACTIVE.", icon="🟡")
    cols = st.columns([1, 1, 4])
    finish_clicked = cols[0].button(
        "🏁 Finish Race",
        key=f"finish_race_user_{race.id}",
        type="primary",
        help="Mark this race as finished, save the final report, and stop "
        "assigning new laps to it.",
    )
    sc_label = "🟢 End Safety Car" if sc_active else "🟡 Safety Car"
    sc_clicked = cols[1].button(
        sc_label,
        key=f"safety_car_{race.id}",
        help="Toggle a safety-car phase. Persists a race_events row and "
        "broadcasts the state to the dashboard.",
    )
    if finish_clicked:
        try:
            svc.finish_race_by_user(race.id)
            st.success(f"Race id={race.id} finished.")
            st.rerun()
        except (
            RaceNotFoundError,
            InvalidRaceStateError,
            RaceValidationError,
        ) as exc:
            st.error(str(exc))
    if sc_clicked:
        try:
            new_state = svc.set_safety_car(race.id, not sc_active)
            st.toast(
                f"Safety car {'ON' if new_state else 'OFF'} for race id={race.id}",
                icon="🟡" if new_state else "🟢",
            )
            st.rerun()
        except (
            RaceNotFoundError,
            InvalidRaceStateError,
            RaceValidationError,
        ) as exc:
            st.error(str(exc))


def _render_running_view() -> None:
    """FR-129 — live race view for status ∈ {running, paused}."""
    races = _get_service().list_races(limit=50)
    active = [r for r in races if r.status in {RaceStatus.RUNNING, RaceStatus.PAUSED}]
    if not active:
        return
    st.subheader("Active race")
    options = {f"{r.name} (id={r.id})": r for r in active}
    label = st.selectbox("Select race", options=list(options.keys()))
    race = options[label]
    st.markdown(f"**{race.name}** — {_status_badge(race.status)} · mode `{race.mode.value}`")

    snapshot = _load_live_snapshot()
    if snapshot is not None:
        active_raw = snapshot.get("active_car_count")
        active_count = int(active_raw) if isinstance(active_raw, (int, float, str)) else 0
        conn = snapshot.get("connection") if isinstance(snapshot.get("connection"), dict) else {}
        reason = conn.get("reason") if isinstance(conn, dict) else None
        details = f"Auto-detected active cars: {active_count}"
        if isinstance(reason, str) and reason:
            details += f" · link reason: {reason}"
        st.caption(details)

    _render_race_controls(race)

    reporting = _get_reporting()
    if race.mode is RaceMode.FIXED_LAPS and race.lap_target:
        standings = reporting.final_standings(race.id)
        leader_laps = max((row.lap_count for row in standings), default=0)
        progress = min(1.0, leader_laps / race.lap_target) if race.lap_target else 0.0
        st.progress(progress, text=f"{leader_laps}/{race.lap_target} laps")
    elif race.mode is RaceMode.FIXED_DURATION and race.duration_seconds and race.started_at:
        from .._time import utcnow_naive

        elapsed = (utcnow_naive() - race.started_at).total_seconds()
        progress = min(1.0, elapsed / race.duration_seconds)
        st.progress(progress, text=f"{int(elapsed)}/{race.duration_seconds} s")
    rows = reporting.final_standings(race.id)
    if rows:
        st.table(
            [
                {
                    "pos": r.position,
                    "car_id": r.car_id,
                    "driver": r.driver_name,
                    "laps": r.lap_count,
                    "best (ms)": r.best_lap_ms or "",
                    "total (ms)": r.total_race_time_ms or "",
                    "gap (ms)": r.gap_to_leader_ms or "",
                }
                for r in rows
            ]
        )
    else:
        st.caption("No laps recorded yet.")


def _render_page() -> None:
    st.title("Race Management")
    _render_running_view()
    _render_create_form()
    _render_list()


_render_page()
