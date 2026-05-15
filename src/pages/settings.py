"""Settings stub — extended in a later iteration."""

from __future__ import annotations

import streamlit as st


def _render() -> None:
    st.title("Settings")
    st.caption("Read-only view of the current configuration.")
    st.info(
        "Edit `config.yaml` (or pass `--config` to `carrera-monitor`) and "
        "restart the app to apply changes. Live configuration editing will "
        "land in a future iteration."
    )


_render()
