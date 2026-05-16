# Data Model: Manual Bluetooth Overflow Workflow

## Entity: BluetoothRuntimeSettings

- Purpose: Persist operator-selected Bluetooth target and scan behavior defaults.
- Fields:
  - `bluetooth_mac: str | None` - selected device MAC for next startup fallback.
  - `scan_timeout_seconds: int` - configurable scan timeout (bounded).
- Validation Rules:
  - Empty MAC string is normalized to `None`.
  - Timeout must be within configured bounds.
- Relationships:
  - Consumed by startup override resolution in `src/main.py`.

## Entity: BluetoothDevice

- Purpose: Normalized representation of a discovered BLE/AppConnect device.
- Fields:
  - `mac: str`
  - `name: str`
  - `rssi: int | None`
- Validation Rules:
  - `mac` must be non-empty.
  - `name` defaults to an implementation-defined placeholder when unavailable.
- Relationships:
  - Produced by scanner service and consumed by dashboard menu rendering.

## Entity: BluetoothConnectionState

- Purpose: Canonical state for connection lifecycle.
- Values:
  - `DISCONNECTED`
  - `SCANNING`
  - `CONNECTING`
  - `CONNECTED`
  - `RECONNECTING`
  - `ERROR`
- Relationships:
  - Published via EventBus transition events.
  - Rendered by dashboard status entry.

## Entity: BluetoothStatusSnapshot

- Purpose: Observable status payload for UI and logs.
- Fields:
  - `state: BluetoothConnectionState`
  - `active_mac: str | None`
  - `last_error: str | None`
  - `updated_at: datetime`
- Validation Rules:
  - `last_error` is required when `state == ERROR`.
- Relationships:
  - Produced by Bluetooth service/state manager.
  - Consumed by dashboard and telemetry status surfaces.

## Entity: BluetoothEvent

- Purpose: EventBus message for lifecycle transitions.
- Fields:
  - `event_type: str` (for example `bluetooth.state.changed`)
  - `from_state: BluetoothConnectionState`
  - `to_state: BluetoothConnectionState`
  - `reason: str | None`
  - `timestamp: datetime`
- Relationships:
  - Emitted by Bluetooth service.
  - Consumed by StateManager observers and UI update hooks.

## State Transitions

Allowed transitions for v1:

- `DISCONNECTED -> SCANNING`
- `SCANNING -> CONNECTING`
- `SCANNING -> ERROR`
- `CONNECTING -> CONNECTED`
- `CONNECTING -> ERROR`
- `CONNECTED -> DISCONNECTED`
- `CONNECTED -> RECONNECTING`
- `RECONNECTING -> CONNECTED`
- `RECONNECTING -> ERROR`
- `ERROR -> CONNECTING`
- `ERROR -> SCANNING`
- `ERROR -> DISCONNECTED`
