"""Race Reports page — UI layer, no ORM imports (FR-130)."""

from __future__ import annotations

import streamlit as st

from src.schemas.race_schema import RaceStatus
from src.services import ensure_database_initialized
from src.services.race_service import RaceService
from src.services.reporting_service import ReportingService


def _get_services() -> tuple[RaceService, ReportingService]:
    if "race_service" not in st.session_state:
        ensure_database_initialized()
        st.session_state["race_service"] = RaceService()
    if "reporting_service" not in st.session_state:
        st.session_state["reporting_service"] = ReportingService(
            race_service=st.session_state["race_service"]
        )
    return st.session_state["race_service"], st.session_state["reporting_service"]


def _render() -> None:
    st.title("Race Reports")
    svc, reporting = _get_services()
    races = svc.list_races(limit=200)
    finished = [
        r for r in races if r.status in {RaceStatus.FINISHED, RaceStatus.CANCELLED}
    ]
    if not finished:
        st.info("No finished or cancelled races yet.")
        return
    options = {f"{r.name} (id={r.id}, {r.status.value})": r for r in finished}
    label = st.selectbox("Race", options=list(options.keys()))
    race = options[label]
    summary = reporting.race_summary(race.id)
    st.markdown(f"### {race.name}")
    if summary.duration_ms is not None:
        st.metric("Duration (ms)", summary.duration_ms)
    if summary.standings:
        st.subheader("Standings")
        st.table([row.model_dump() for row in summary.standings])
    if summary.drivers:
        st.subheader("Per-driver stats")
        st.table([d.model_dump() for d in summary.drivers])

    col_a, col_b = st.columns(2)
    col_a.download_button(
        "Download Summary CSV",
        data=reporting.export_summary_csv(race.id),
        file_name=f"race_{race.id}_summary.csv",
        mime="text/csv",
    )
    col_b.download_button(
        "Download Laps CSV",
        data=reporting.export_laps_csv(race.id),
        file_name=f"race_{race.id}_laps.csv",
        mime="text/csv",
    )

    st.subheader("Saved reports")
    report_type = st.text_input("Report type", value="race_summary")
    if st.button("Save Report Snapshot"):
        reporting.save_report(race.id, report_type, summary.model_dump(mode="json"))
        st.success("Report saved")
        st.rerun()
    for row in reporting.list_reports(race.id):
        st.caption(
            f"id={row.id} · type={row.report_type} · created_at={row.created_at}"
        )


_render()
