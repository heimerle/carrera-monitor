# Contract: Dashboard Overflow Bluetooth Workflow

## Scope

Defines UI-service-event behavior for manual Bluetooth connect/disconnect/scan/status from the dashboard overflow menu.

## UI Contract

Menu icon:
- `⋮` in dashboard header top-right.

Menu entries:
- `Connect Bluetooth`
- `Disconnect Bluetooth`
- `Scan Bluetooth Devices`
- `Bluetooth Status`

Optional placeholders (non-functional in v1):
- `Settings`
- `Export Logs`

## Action Contracts

### Connect Bluetooth

Inputs:
- none

Behavior:
1. If configured MAC exists, attempt direct connect.
2. If no configured MAC exists, run scan and present selectable device list.
3. On selected device, connect and optionally persist MAC for startup fallback.

Outputs:
- Emits progress/state updates.
- Returns success or actionable error.

Error handling:
- Must surface error message in UI and set lifecycle state to `ERROR`.
- Must expose explicit retry path.

### Disconnect Bluetooth

Inputs:
- none

Behavior:
1. Request disconnect from active device/session.
2. Update status to `DISCONNECTED`.

Outputs:
- Emits `CONNECTED -> DISCONNECTED` transition event when applicable.

### Scan Bluetooth Devices

Inputs:
- `scan_timeout_seconds` (configured default with bounds)

Behavior:
1. Transition to `SCANNING`.
2. Return normalized device list.
3. Filter likely Carrera devices when detectable.

Outputs:
- Scan state transitions and device list payload.

Error handling:
- `scan_error` represented as state `ERROR` with details.

### Bluetooth Status

Outputs:
- Shows current state (`DISCONNECTED`, `SCANNING`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, `ERROR`).
- Shows active MAC when available.
- Shows last error when in `ERROR`.

## Service Contract

Scanner service returns normalized devices:

- `mac: str`
- `name: str`
- `rssi: int | None`

Connection service exposes:

- `connect(target_mac: str | None) -> None`
- `disconnect() -> None`
- `scan(timeout_seconds: int) -> list[BluetoothDevice]`
- `get_status() -> BluetoothStatusSnapshot`

## EventBus Contract

Required event topic:
- `bluetooth.state.changed`

Event payload fields:
- `from_state`
- `to_state`
- `reason` (optional)
- `active_mac` (optional)
- `timestamp`

## Coexistence Contract (Simulator)

- Bluetooth connect/disconnect/scan actions must not mutate simulator/mock mode.
- Simulator/mock controls must not force Bluetooth lifecycle changes.
- Telemetry pipeline architecture remains unchanged.
