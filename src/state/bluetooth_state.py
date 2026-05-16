"""Bluetooth connection supervisor state vocabulary."""

from __future__ import annotations

from enum import StrEnum


class BluetoothState(StrEnum):
    DISCONNECTED = "disconnected"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBING = "subscribing"
    READY = "ready"
    STALE = "stale"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    MANUALLY_DISCONNECTED = "manually_disconnected"


_CONNECTING_STATES = {
    BluetoothState.SCANNING,
    BluetoothState.CONNECTING,
    BluetoothState.SUBSCRIBING,
    BluetoothState.RECONNECTING,
}

_CONNECTED_STATES = {
    BluetoothState.CONNECTED,
    BluetoothState.SUBSCRIBING,
    BluetoothState.READY,
    BluetoothState.STALE,
}


def is_connecting_state(state: BluetoothState | str) -> bool:
    try:
        parsed = state if isinstance(state, BluetoothState) else BluetoothState(str(state))
    except ValueError:
        return False
    return parsed in _CONNECTING_STATES


def is_reconnect_state(state: BluetoothState | str) -> bool:
    try:
        parsed = state if isinstance(state, BluetoothState) else BluetoothState(str(state))
    except ValueError:
        return False
    return parsed is BluetoothState.RECONNECTING


def is_connected_state(state: BluetoothState | str) -> bool:
    try:
        parsed = state if isinstance(state, BluetoothState) else BluetoothState(str(state))
    except ValueError:
        return False
    return parsed in _CONNECTED_STATES


__all__ = [
    "BluetoothState",
    "is_connected_state",
    "is_connecting_state",
    "is_reconnect_state",
]
