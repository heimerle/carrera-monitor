"""Settings page — runtime toggles + read-only config reference.

Currently exposes:

- **Race Simulator (Mock Mode)** — flips the persistent
  ``data/runtime_settings.json`` flag that ``src/main.py`` reads at
  startup to choose between the mock telemetry generator and the live
  Bluetooth adapter.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.config import load_config
from src.services.bluetooth_service import (
    BluetoothService,
    compute_button_disabled_state,
    simulator_warning_message,
)
from src.services.runtime_settings import (
    DEFAULT_PATH,
    RuntimeSettings,
    get_mock_mode,
    set_mock_mode,
)


def _get_bluetooth_service() -> BluetoothService:
    cfg_path = Path("config.yaml")
    cfg = load_config(cfg_path if cfg_path.exists() else None)
    state_file = Path(cfg.logging.directory) / "state.json"
    return BluetoothService(
        runtime_settings=RuntimeSettings(),
        state_file=state_file,
    )


def _render_mock_mode_toggle() -> None:
    st.subheader("Race Simulator")
    st.caption(
        "Switch the telemetry source between the in-process mock generator "
        "and the live Carrera AppConnect BLE adapter."
    )
    current = get_mock_mode()
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
            set_mock_mode(new_value)
            st.success(
                f"Mock mode {'ENABLED' if new_value else 'DISABLED'}. "
                "Restart the carrera-monitor process to apply."
            )
        except OSError as exc:
            st.error(f"Failed to persist setting: {exc}")
    state_label = "ON" if get_mock_mode() else "OFF"
    st.info(
        f"Current persistent setting: **{state_label}** "
        f"(file: `{DEFAULT_PATH}`). The running pipeline applies the value "
        "at process start; an explicit `--mock` or `--mac` CLI flag still "
        "overrides this setting."
    )


def _render_bluetooth_controls() -> None:
    service = _get_bluetooth_service()
    status = service.get_status()
    disabled = compute_button_disabled_state(status)

    st.subheader("Bluetooth Connection")
    st.caption(
        "Requests are forwarded to the long-running BluetoothConnectionSupervisor. "
        "This UI only sends commands and renders status."
    )

    warning = simulator_warning_message(
        mock_mode=get_mock_mode(),
        bluetooth_status=status,
    )
    if warning:
        st.warning(warning)

    c1, c2, c3 = st.columns(3)
    c1.metric("State", status.state.value.upper())
    c2.metric("Desired", "CONNECTED" if status.desired_connected else "DISCONNECTED")
    c3.metric("Reconnect Attempts", str(status.reconnect_attempts))

    details = {
        "device_name": status.device_name,
        "device_id": status.device_id,
        "mac_address": status.mac_address,
        "rssi": status.rssi,
        "connected_at": status.connected_at.isoformat() if status.connected_at else None,
        "disconnected_at": (
            status.disconnected_at.isoformat() if status.disconnected_at else None
        ),
        "last_seen_at": status.last_seen_at.isoformat() if status.last_seen_at else None,
        "last_rx_monotonic_ms": status.last_rx_monotonic_ms,
        "last_error": status.last_error,
        "updated_at": status.updated_at.isoformat(),
    }
    st.json(details)

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("Connect Bluetooth", disabled=disabled["connect"]):
        service.request_connect(status.device_id)
        st.success("Connect requested.")
        st.rerun()

    if b2.button("Disconnect Bluetooth", disabled=disabled["disconnect"]):
        service.request_disconnect()
        st.success("Disconnect requested.")
        st.rerun()

    if b3.button("Scan Devices", disabled=disabled["scan"]):
        service.request_scan()
        st.success("Scan requested.")
        st.rerun()

    retry_visible = (
        status.desired_connected
        and status.state.value in {"error", "stale", "disconnected"}
    )
    if retry_visible and b4.button("Retry Now", disabled=disabled["retry"]):
        service.request_retry()
        st.success("Immediate retry requested.")
        st.rerun()


def _render() -> None:
    st.title("Settings")
    _render_bluetooth_controls()
    st.divider()
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
