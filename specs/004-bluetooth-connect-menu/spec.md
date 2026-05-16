# Feature Specification: Manual Bluetooth Connection via Overflow Menu

**Feature Branch**: `004-bluetooth-connect-menu`
**Created**: 2026-05-16
**Status**: Draft
**Input**: User description: "neues feature, ich möchte im '3-Punkte' Menü einen button für Bluetooth Verbindung herstellen haben"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Manage Bluetooth Connection from the Dashboard (Priority: P1) 🎯 MVP

The user opens the Streamlit dashboard, clicks the **⋮** overflow menu in the header, and can run the full Bluetooth workflow: scan nearby AppConnect devices, connect either via configured MAC or selected scan result, inspect current Bluetooth status, disconnect explicitly, and retry after failures. Selecting a device persists its MAC into `data/runtime_settings.json::bluetooth_mac` and keeps simulator/mock mode independent from Bluetooth lifecycle changes. On the next `carrera-monitor` boot the live adapter connects directly to that MAC when no higher-priority override exists.

**Why this priority**: Today the only way to bind to a specific Control Unit is to memorize the MAC and pass it as `--mac` on the CLI, or to let the pipeline scan on every start. A one-click UI flow eliminates both pain points and is the smallest possible incremental UX win.

**Independent Test**: With `carreralib` installed and an AppConnect powered on, open the dashboard and use **⋮** menu actions. Assert: (a) scanning shows discovered devices or an explicit empty-state; (b) selecting a device writes the MAC to `data/runtime_settings.json`; (c) status reflects `CONNECTING -> CONNECTED` and disconnect returns `DISCONNECTED`; (d) after an induced failure, retry returns to `CONNECTING`/`SCANNING`; (e) on the next `python -m src.main` start (no `--mac` on the CLI and no config MAC), the live adapter connects to the persisted MAC.

**Acceptance Scenarios**:

1. **Given** `carreralib` is installed and an AppConnect is reachable, **When** the user clicks **⋮ → Scan Bluetooth Devices**, **Then** a BLE scan runs and one device list row per Control Unit is rendered, each with **Auswählen**.
2. **Given** the scan returns zero devices, **When** the user clicks **🔌 Bluetooth verbinden**, **Then** the popover shows a helpful empty-state message ("Keine Geräte gefunden — ist die AppConnect eingeschaltet?").
3. **Given** the user clicks **Auswählen** on a row, **When** the page reruns, **Then** `data/runtime_settings.json::bluetooth_mac` equals the selected MAC and a `st.success("Gespeichert. Restart erforderlich.")` notice is rendered above the device list.
4. **Given** `carreralib` is not installed, **When** the user clicks **🔌 Bluetooth verbinden**, **Then** the popover shows `st.error("carreralib nicht installiert. Bitte mit 'pip install carreralib' nachinstallieren.")` and the dashboard does not crash.
5. **Given** the user is connected, **When** the user clicks **Disconnect Bluetooth**, **Then** the UI state returns to `DISCONNECTED` and a status entry confirms no active Bluetooth link.
6. **Given** a previous connect/scan attempt failed, **When** the user clicks **Connect Bluetooth** again, **Then** the workflow retries and updates status from `ERROR` to `CONNECTING` or `SCANNING`.
7. **Given** simulator/mock mode is enabled, **When** the user performs Bluetooth scan/connect/disconnect actions, **Then** simulator/mock mode remains unchanged.

### Edge Cases

- BLE scan raises a non-ImportError exception (permission denied on macOS, hardware missing) → popover shows `st.error(str(exc))`. The user can simply click **🔌 Bluetooth verbinden** again to retry; no separate retry button is required.
- User clicks **Auswählen** while the runtime-settings file directory is read-only → catch `OSError`, surface via `st.error(str(exc))`, do not corrupt state.
- A `--mac` CLI argument is present at next boot → CLI wins; the persisted `bluetooth_mac` is ignored (precedence already established by 002/FR-225 for `mock_mode`; this slice extends it to `bluetooth_mac`).
- Two concurrent Streamlit sessions click **Auswählen** with different MACs → last writer wins (file is replaced atomically per `RuntimeSettings._save`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `RuntimeSettings` MUST expose a new persisted key `bluetooth_mac: str | None` (default `None`) with `get_bluetooth_mac()` / `set_bluetooth_mac(value: str | None) -> str | None` accessors and matching module-level helpers, mirroring the existing `mock_mode` pattern.
- **FR-002**: A helper module `src/services/bluetooth_scanner.py` MUST expose `scan_for_devices(timeout_seconds: int | None = None) -> list[BluetoothDevice]` that wraps `carreralib.connection.scan()` and returns normalized entries with `mac: str`, `name: str`, and optional `rssi: int | None`. A missing `carreralib` MUST raise `ScannerUnavailableError`; other failures MUST raise `ScannerError(str(exc))`.
- **FR-003**: `RuntimeSettings` MUST also expose `scan_timeout_seconds: int` with a bounded default used by scan actions when no explicit timeout is provided.
- **FR-004**: The dashboard MUST render a **⋮** overflow popover (`st.popover` with `use_container_width=False`) in the header row with entries: **Connect Bluetooth**, **Disconnect Bluetooth**, **Scan Bluetooth Devices**, and **Bluetooth Status**.
- **FR-005**: The popover MUST contain the currently persisted MAC (if any), and after a scan, a list of discovered devices each with an **Auswählen** button. When the scan returns zero devices, the popover MUST render the empty-state message `Keine Geräte gefunden — ist die AppConnect eingeschaltet?` (via `st.info`).
- **FR-006**: Clicking **Auswählen** MUST call `set_bluetooth_mac(mac)` and render `st.success("Gespeichert. Restart erforderlich.")`. Clicking **Zurücksetzen** MUST call `set_bluetooth_mac(None)` and render the same notice.
- **FR-007**: `ScannerUnavailableError` MUST be surfaced via `st.error` with the actionable install hint; `ScannerError` MUST be surfaced via `st.error(str(exc))`. The dashboard MUST NOT crash on either path.
- **FR-008**: A Bluetooth lifecycle state model MUST be used with states `DISCONNECTED`, `SCANNING`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, and `ERROR`. The dashboard status entry MUST reflect the current lifecycle state.
- **FR-009**: `Connect Bluetooth` MUST attempt direct connection when a configured MAC exists; otherwise it MUST scan and allow selecting a discovered device before connecting.
- **FR-010**: `Disconnect Bluetooth` MUST terminate the active connection and update status to `DISCONNECTED`.
- **FR-011**: Lifecycle transitions MUST emit an EventBus event `bluetooth.state.changed` containing `from_state`, `to_state`, and timestamp; reason/active_mac are optional metadata.
- **FR-012**: Retry after failures MUST be user-driven from the overflow menu and transition from `ERROR` to `CONNECTING` or `SCANNING`.
- **FR-013**: `src/main.py::_apply_overrides` MUST extend its precedence chain so that when `args.mac is None` AND `cfg.bluetooth.mac_address is None`, the value of `RuntimeSettings.get_bluetooth_mac()` is used as the fallback `cfg.bluetooth.mac_address`. CLI `--mac` and `config.yaml::bluetooth.mac_address` both still win over the persisted UI choice.
- **FR-014**: Bluetooth scan/connect/disconnect actions MUST NOT mutate simulator/mock mode. Simulator/mock controls MUST NOT force Bluetooth lifecycle changes.
- **FR-015**: No new dependency. `carreralib` is already optional; this slice does not add it as a hard requirement.
- **FR-016**: `data/runtime_settings.json` is already gitignored (002/FR-226); no new gitignore entry is required.

### Key Entities *(data)*

- **`RuntimeSettings.bluetooth_mac`** — `str | None`, default `None`. Empty string is normalized to `None`.
- **`RuntimeSettings.scan_timeout_seconds`** — `int`, bounded default used by BLE scans.
- **`BluetoothDevice`** — normalized discovery result with `mac`, `name`, and optional `rssi`.
- **`BluetoothStatusSnapshot`** — current lifecycle state, active MAC, and optional last error.

## Success Criteria *(mandatory)*

- **SC-001**: A user with `carreralib` installed and an AppConnect powered on can bind a specific Control Unit to the next pipeline boot in ≤ 3 clicks from the dashboard (open kebab → Bluetooth verbinden → Auswählen). Verified manually against the quickstart; not pinned by an automated harness.
- **SC-002**: With `bluetooth_mac` persisted and no CLI override, `python -m src.main` uses the persisted MAC as Bluetooth fallback (verified by a unit test on `_apply_overrides`).
- **SC-003**: A missing `carreralib` package does not crash the Streamlit page; the user sees an actionable install hint.
- **SC-004**: The dashboard status view reflects lifecycle transitions for scan/connect/disconnect/retry and returns to `DISCONNECTED` after disconnect.
- **SC-005**: All pre-feature tests remain green; new tests cover (a) `RuntimeSettings` keys (`bluetooth_mac`, `scan_timeout_seconds`), (b) scanner success/error mapping, (c) lifecycle state transitions and EventBus emission, (d) `_apply_overrides` fallback precedence, and (e) overflow workflow rendering. `ruff` + `mypy --strict` remain clean on the CI matrix (Python 3.11 + 3.12 × ubuntu/macos).

## Assumptions

- The hot-swap variant (start/stop the live `CarreraClientRunner` from inside the Streamlit process without a pipeline restart) is **out of scope** for v1. The persist-and-restart pattern from 002/FR-225 is reused as-is.
- The 3-dot menu lives in the **Dashboard page header only** (not globally). Other pages keep their existing layout. A global header is a future polish slice.
- BLE scanning is invoked synchronously inside the Streamlit script run. The default `carreralib` scan window is short (≈ 3 s); longer scans are out of scope for v1.
- Multi-CU rigs are supported (the device list lets the user pick any of the discovered units); a future slice may add per-driver MAC tagging.
