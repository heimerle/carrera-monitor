# Data Model: Robust Bluetooth Connection Supervisor

## Entity: BluetoothState

- Purpose: Canonical lifecycle state vocabulary for runtime status and UI rendering.
- Values:
  - `disconnected`
  - `manually_disconnected`
  - `scanning`
  - `connecting`
  - `connected`
  - `subscribing`
  - `ready`
  - `stale`
  - `reconnecting`
  - `error`
- Notes:
  - `manually_disconnected` is distinct from `disconnected` to suppress automatic reconnect.
  - `ready` indicates transport is connected and telemetry pipeline is actively receiving.

## Entity: BluetoothConnectionStatus

- Purpose: Normalized status snapshot exposed to dashboard and lifecycle event payloads.
- Core fields:
  - `state: BluetoothState`
  - `desired_connected: bool`
  - `device_id: str | None`
  - `device_name: str | None`
  - `mac_address: str | None`
  - `rssi: int | None`
  - `connected_at: datetime | None`
  - `disconnected_at: datetime | None`
  - `last_seen_at: datetime | None`
  - `last_rx_monotonic_ms: int | None`
  - `reconnect_attempts: int`
  - `last_error: str | None`
  - `updated_at: datetime`
- Validation rules:
  - datetime fields are timezone-aware when present.
  - monotonic/retry counters are non-negative.

## Entity: BluetoothControlRequest

- Purpose: Persisted runtime intent written by dashboard and consumed by supervisor.
- Fields (runtime settings storage):
  - `bluetooth_desired_connected: bool`
  - `bluetooth_selected_device_id: str | None`
  - `bluetooth_command_seq: int`
  - `bluetooth_pending_command: "connect" | "disconnect" | "scan" | "retry" | None`
  - `bluetooth_pending_command_device_id: str | None`
- Validation rules:
  - command must be one of the allowed values.
  - sequence is strictly monotonic increasing for each written command.

## Entity: BluetoothDevice

- Purpose: Normalized discovered device identity for selection and display.
- Fields:
  - `device_id: str`
  - `device_name: str | None`
  - `mac_address: str | None`
  - `rssi: int | None`
- Validation rules:
  - `device_id` is required and stable within a scan cycle.

## Entity: BluetoothLifecycleEvent

- Purpose: Additive lifecycle telemetry emitted as `connection_state` payload.
- Fields:
  - `event: str`
  - `state: BluetoothState`
  - `desired_connected: bool`
  - `reason: str | None`
  - `error: str | None`
  - device and reconnect metadata mirrored from `BluetoothConnectionStatus`
- Relationships:
  - Emitted by supervisor.
  - Validated by event model.
  - Aggregated into state snapshots.

## Entity Relationships

- `BluetoothControlRequest` drives supervisor actions and desired-state reconciliation.
- Supervisor updates `BluetoothConnectionStatus` and emits `BluetoothLifecycleEvent`.
- `StateManager` ingests lifecycle events and publishes latest status into `state.json`.
- Dashboard reads `BluetoothConnectionStatus` snapshot and exposes control actions via `BluetoothControlRequest`.

## State Transitions

Primary transition patterns:

- `disconnected -> connecting -> connected -> subscribing -> ready`
- `ready -> stale` on telemetry timeout
- `stale -> reconnecting -> connecting` when reconnect-on-stale is enabled
- `ready/connected -> reconnecting` on unexpected disconnect/read failure
- `ready/connected/reconnecting -> manually_disconnected` on explicit user disconnect
- `error -> reconnecting/connecting` on user retry when desired state is connected
- Any active state -> `disconnected` during shutdown
