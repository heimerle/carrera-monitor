"""Streamlit entry point: navigation across Dashboard / Race Management / Reports / Settings.

Launched by ``src/main.py`` (or directly with
``streamlit run src/app.py -- --mock``). The Dashboard page re-uses the
existing ``src.dashboard`` module unchanged so the live telemetry view is
preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

# When Streamlit runs this file directly (``streamlit run src/app.py``) it
# prepends the script's parent directory (``src/``) to ``sys.path`` instead of
# the project root, so ``from src import ...`` in this file and in the pages
# under ``src/pages/`` fails with ``ModuleNotFoundError: No module named 'src'``.
# Prepend the project root before any first-party imports happen.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402  (import after sys.path fix is intentional)


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
