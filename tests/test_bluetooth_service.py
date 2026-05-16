"""Tests for BluetoothService helpers and proxy behavior."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.schemas.bluetooth_schema import BluetoothConnectionStatus
from src.services.bluetooth_service import (
    BluetoothService,
    compute_button_disabled_state,
    simulator_warning_message,
)
from src.services.runtime_settings import RuntimeSettings
from src.state.bluetooth_state import BluetoothState


def _status(
    state: BluetoothState,
    *,
    desired_connected: bool = False,
) -> BluetoothConnectionStatus:
    return BluetoothConnectionStatus(
        state=state,
        desired_connected=desired_connected,
        updated_at=datetime.now(tz=UTC),
    )


def test_compute_button_disabled_state_for_busy_states() -> None:
    status = _status(BluetoothState.CONNECTING, desired_connected=True)
    disabled = compute_button_disabled_state(status)

    assert disabled["connect"] is True
    assert disabled["scan"] is True
    assert disabled["disconnect"] is False


def test_compute_button_disabled_state_retry_rules() -> None:
    disconnected = _status(BluetoothState.DISCONNECTED, desired_connected=True)
    stale = _status(BluetoothState.STALE, desired_connected=True)
    ready = _status(BluetoothState.READY, desired_connected=True)

    assert compute_button_disabled_state(disconnected)["retry"] is False
    assert compute_button_disabled_state(stale)["retry"] is False
    assert compute_button_disabled_state(ready)["retry"] is True


def test_simulator_warning_only_for_mock_and_active_bluetooth() -> None:
    warning = simulator_warning_message(
        mock_mode=True,
        bluetooth_status=_status(BluetoothState.READY, desired_connected=True),
    )
    none_for_live = simulator_warning_message(
        mock_mode=False,
        bluetooth_status=_status(BluetoothState.READY, desired_connected=True),
    )
    none_for_disconnected = simulator_warning_message(
        mock_mode=True,
        bluetooth_status=_status(BluetoothState.DISCONNECTED, desired_connected=False),
    )

    assert warning is not None
    assert none_for_live is None
    assert none_for_disconnected is None


def test_proxy_request_connect_updates_runtime_command(tmp_path: Path) -> None:
    runtime = RuntimeSettings(path=tmp_path / "runtime_settings.json")
    service = BluetoothService(runtime_settings=runtime, state_file=tmp_path / "state.json")

    status = service.request_connect("AA:BB:CC:DD:EE:FF")
    seq, command, device_id = runtime.consume_bluetooth_command(last_sequence=0)

    assert seq >= 1
    assert command == "connect"
    assert device_id == "AA:BB:CC:DD:EE:FF"
    assert status.desired_connected is True


def test_get_status_reads_connection_snapshot(tmp_path: Path) -> None:
    runtime = RuntimeSettings(path=tmp_path / "runtime_settings.json")
    state_file = tmp_path / "state.json"
    payload = {
        "taken_at_iso": "2026-01-01T12:00:00+00:00",
        "connection": {
            "state": "ready",
            "desired_connected": True,
            "device_id": "AA:BB:CC:DD:EE:FF",
            "device_name": "Control_Unit",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "rssi": -67,
            "connected_at": "2026-01-01T11:59:50+00:00",
            "disconnected_at": None,
            "last_seen_at": "2026-01-01T12:00:00+00:00",
            "last_rx_monotonic_ms": 123456,
            "reconnect_attempts": 2,
            "last_error": None,
        },
    }
    state_file.write_text(json.dumps(payload), encoding="utf-8")

    service = BluetoothService(runtime_settings=runtime, state_file=state_file)
    status = service.get_status()

    assert status.state is BluetoothState.READY
    assert status.desired_connected is True
    assert status.device_name == "Control_Unit"
    assert status.reconnect_attempts == 2
    assert status.last_rx_monotonic_ms == 123456
