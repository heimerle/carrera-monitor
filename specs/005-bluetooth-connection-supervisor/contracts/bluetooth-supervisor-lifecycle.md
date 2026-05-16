# Contract: Bluetooth Supervisor Lifecycle

## Scope

Defines runtime, dashboard, and telemetry contracts for robust Bluetooth lifecycle supervision.

## Runtime Control Contract

### Storage channel

Runtime command bridge uses `data/runtime_settings.json` keys:

- `bluetooth_desired_connected` (bool)
- `bluetooth_selected_device_id` (string or null)
- `bluetooth_command_seq` (int)
- `bluetooth_pending_command` (`connect` | `disconnect` | `scan` | `retry` | null)
- `bluetooth_pending_command_device_id` (string or null)

### Write semantics

- Dashboard writes one command at a time.
- Every command increments `bluetooth_command_seq`.
- `connect` and `retry` force desired connected true.
- `disconnect` forces desired connected false.

### Consume semantics

- Supervisor consumes only commands with sequence greater than last applied sequence.
- Duplicate or stale command sequences are ignored.

## Lifecycle Status Contract

### Status shape

`BluetoothConnectionStatus` exposes at minimum:

- `state`
- `desired_connected`
- `device_id`, `device_name`, `mac_address`
- `reconnect_attempts`
- `last_seen_at`
- `last_error`
- `updated_at`

### Snapshot publication

- Runtime publishes status in `logs/state.json` under `connection`.
- Fields are additive and backward-compatible for existing consumers.

## Lifecycle Event Contract

### Event type

Supervisor emits lifecycle transitions through telemetry events:

- `event_type: connection_state`
- `source: system`

### Required payload fields

- `state`
- `desired_connected`
- `event` (lifecycle event name)

### Optional payload fields

- `reason`
- `error`
- `device_id`, `device_name`, `mac_address`, `rssi`
- `connected_at`, `disconnected_at`, `last_seen_at`
- `last_rx_monotonic_ms`
- `reconnect_attempts`

## UI Control Contract

Dashboard-facing controls:

- Connect
- Disconnect
- Scan Devices
- Retry Now

Rules:

- Manual disconnect suppresses auto-reconnect until explicit reconnect intent.
- Busy states disable conflicting controls.
- Retry is enabled only when desired state is connected and state is recoverable (`error`, `stale`, `disconnected`).
- Simulator mode remains independent from Bluetooth lifecycle state.

## Error Handling Contract

- Connect/scan failures update status to `error` with actionable `last_error` text.
- Stale telemetry transitions to `stale` and optionally reconnects based on config.
- Shutdown always releases active adapter connection and terminates supervisor loop.
