"""Streamlit entry point: navigation across Dashboard / Race Management / Reports / Settings.

Launched by ``src/main.py`` (or directly with
``streamlit run src/app.py -- --mock``). The Dashboard page re-uses the
existing ``src.dashboard`` module unchanged so the live telemetry view is
preserved.
"""

from __future__ import annotations

import streamlit as st


def _dashboard_page() -> None:
    from src import dashboard

    dashboard.render()


pg = st.navigation(
    [
        st.Page(_dashboard_page, title="Dashboard", icon="🏁"),
        st.Page("pages/race_management.py", title="Race Management", icon="🏎️"),
        st.Page("pages/race_reports.py", title="Race Reports", icon="📊"),
        st.Page("pages/settings.py", title="Settings", icon="⚙️"),
    ]
)
pg.run()
