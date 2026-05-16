"""Bluetooth service facade for UI and runtime integration.

- In runtime mode, delegates to ``BluetoothConnectionSupervisor``.
- In UI proxy mode (Streamlit process), writes control requests to
  runtime-settings and reads current status from ``state.json``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..schemas.bluetooth_schema import BluetoothConnectionStatus, BluetoothDevice
from ..state.bluetooth_state import BluetoothState, is_connected_state
from .bluetooth_connection_supervisor import BluetoothConnectionSupervisor
from .runtime_settings import RuntimeSettings


def compute_button_disabled_state(status: BluetoothConnectionStatus) -> dict[str, bool]:
    state = status.state
    busy = state in {
        BluetoothState.SCANNING,
        BluetoothState.CONNECTING,
        BluetoothState.SUBSCRIBING,
        BluetoothState.RECONNECTING,
    }
    return {
        "connect": busy,
        "scan": busy or is_connected_state(state),
        "disconnect": state in {
            BluetoothState.DISCONNECTED,
            BluetoothState.MANUALLY_DISCONNECTED,
            BluetoothState.ERROR,
        },
        "retry": not (
            status.desired_connected
            and state in {
                BluetoothState.ERROR,
                BluetoothState.STALE,
                BluetoothState.DISCONNECTED,
            }
        ),
    }


def simulator_warning_message(
    *,
    mock_mode: bool,
    bluetooth_status: BluetoothConnectionStatus,
) -> str | None:
    if not mock_mode:
        return None
    if bluetooth_status.state in {
        BluetoothState.CONNECTING,
        BluetoothState.CONNECTED,
        BluetoothState.SUBSCRIBING,
        BluetoothState.READY,
        BluetoothState.RECONNECTING,
        BluetoothState.STALE,
    }:
        return (
            "Simulator is active. Real Carrera telemetry and simulated telemetry "
            "are separated by source."
        )
    return None


class BluetoothService:
    """High-level Bluetooth API for UI and process runtime."""

    def __init__(
        self,
        *,
        supervisor: BluetoothConnectionSupervisor | None = None,
        runtime_settings: RuntimeSettings | None = None,
        state_file: Path | None = None,
    ) -> None:
        self._supervisor = supervisor
        self._runtime = runtime_settings or RuntimeSettings()
        self._state_file = Path(state_file) if state_file is not None else Path("logs/state.json")

    async def scan_devices(self) -> list[BluetoothDevice]:
        if self._supervisor is not None:
            return await self._supervisor.scan_devices()
        self._runtime.request_bluetooth_command("scan")
        return []

    async def connect(self, device_id: str | None = None) -> BluetoothConnectionStatus:
        if self._supervisor is not None:
            return await self._supervisor.connect(device_id)
        self._runtime.set_bluetooth_desired_connected(True)
        self._runtime.request_bluetooth_command("connect", device_id=device_id)
        if device_id is not None:
            self._runtime.set_bluetooth_selected_device_id(device_id)
        return self.get_status()

    async def disconnect(self) -> BluetoothConnectionStatus:
        if self._supervisor is not None:
            return await self._supervisor.disconnect(manual=True)
        self._runtime.set_bluetooth_desired_connected(False)
        self._runtime.request_bluetooth_command("disconnect")
        return self.get_status()

    async def retry_now(self) -> BluetoothConnectionStatus:
        if self._supervisor is not None:
            return await self._supervisor.retry_now()
        self._runtime.set_bluetooth_desired_connected(True)
        self._runtime.request_bluetooth_command("retry")
        return self.get_status()

    def request_connect(self, device_id: str | None = None) -> BluetoothConnectionStatus:
        self._runtime.set_bluetooth_desired_connected(True)
        self._runtime.request_bluetooth_command("connect", device_id=device_id)
        if device_id is not None:
            self._runtime.set_bluetooth_selected_device_id(device_id)
        return self.get_status()

    def request_disconnect(self) -> BluetoothConnectionStatus:
        self._runtime.set_bluetooth_desired_connected(False)
        self._runtime.request_bluetooth_command("disconnect")
        return self.get_status()

    def request_scan(self) -> BluetoothConnectionStatus:
        self._runtime.request_bluetooth_command("scan")
        return self.get_status()

    def request_retry(self) -> BluetoothConnectionStatus:
        self._runtime.set_bluetooth_desired_connected(True)
        self._runtime.request_bluetooth_command("retry")
        return self.get_status()

    def get_status(self) -> BluetoothConnectionStatus:
        if self._supervisor is not None:
            return self._supervisor.get_status()

        desired = self._runtime.get_bluetooth_desired_connected()
        base = BluetoothConnectionStatus(
            state=BluetoothState.DISCONNECTED,
            desired_connected=desired,
            updated_at=datetime.now(tz=UTC),
        )
        try:
            with open(self._state_file, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return base
        if not isinstance(data, dict):
            return base
        conn = data.get("connection")
        if not isinstance(conn, dict):
            return base

        payload: dict[str, Any] = {
            "state": conn.get("state", BluetoothState.DISCONNECTED.value),
            "desired_connected": conn.get("desired_connected", desired),
            "device_id": conn.get("device_id"),
            "device_name": conn.get("device_name"),
            "mac_address": conn.get("mac_address"),
            "rssi": conn.get("rssi"),
            "connected_at": conn.get("connected_at"),
            "disconnected_at": conn.get("disconnected_at"),
            "last_seen_at": conn.get("last_seen_at"),
            "last_rx_monotonic_ms": conn.get("last_rx_monotonic_ms"),
            "reconnect_attempts": conn.get("reconnect_attempts", 0),
            "last_error": conn.get("last_error"),
            "updated_at": data.get("taken_at_iso", datetime.now(tz=UTC).isoformat()),
        }
        try:
            return BluetoothConnectionStatus.model_validate(payload)
        except Exception:
            return base

    def is_connected(self) -> bool:
        status = self.get_status()
        return is_connected_state(status.state)

    def is_ready(self) -> bool:
        return self.get_status().state is BluetoothState.READY


__all__ = [
    "BluetoothService",
    "compute_button_disabled_state",
    "simulator_warning_message",
]
