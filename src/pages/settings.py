"""Settings page — runtime toggles + read-only config reference.

Currently exposes:

- **Race Simulator (Mock Mode)** — flips the persistent
  ``data/runtime_settings.json`` flag that ``src/main.py`` reads at
  startup to choose between the mock telemetry generator and the live
  Bluetooth adapter.
"""

from __future__ import annotations

import streamlit as st

from src.services.runtime_settings import RuntimeSettings


def _get_settings() -> RuntimeSettings:
    if "runtime_settings" not in st.session_state:
        st.session_state["runtime_settings"] = RuntimeSettings()
    rs: RuntimeSettings = st.session_state["runtime_settings"]
    return rs


def _render_mock_mode_toggle() -> None:
    st.subheader("Race Simulator")
    st.caption(
        "Switch the telemetry source between the in-process mock generator "
        "and the live Carrera AppConnect BLE adapter."
    )
    rs = _get_settings()
    current = rs.get_mock_mode()
    new_value = st.toggle(
        "Mock mode (race simulator)",
        value=current,
        key="mock_mode_toggle",
        help="When ON, the next pipeline start uses the MockCarreraAdapter "
        "instead of the live BLE adapter. Setting is stored in "
        "data/runtime_settings.json.",
    )
    if new_value != current:
        try:
            rs.set_mock_mode(new_value)
            st.success(
                f"Mock mode {'ENABLED' if new_value else 'DISABLED'}. "
                "Restart the carrera-monitor process to apply."
            )
        except OSError as exc:
            st.error(f"Failed to persist setting: {exc}")
    state_label = "ON" if rs.get_mock_mode() else "OFF"
    st.info(
        f"Current persistent setting: **{state_label}** "
        f"(file: `{rs.path}`). The running pipeline applies the value at "
        "process start; an explicit `--mock` or `--mac` CLI flag still "
        "overrides this setting."
    )


def _render() -> None:
    st.title("Settings")
    _render_mock_mode_toggle()
    st.divider()
    st.subheader("Configuration")
    st.caption("Read-only view of the current configuration.")
    st.info(
        "Edit `config.yaml` (or pass `--config` to `carrera-monitor`) and "
        "restart the app to apply changes. Live configuration editing will "
        "land in a future iteration."
    )


_render()
