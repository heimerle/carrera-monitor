# Feature Specification: Bluetooth Connect Button (Dashboard Kebab Menu)

**Feature Branch**: `004-bluetooth-connect-menu`
**Created**: 2026-05-16
**Status**: Draft
**Input**: User description: "neues feature, ich möchte im '3-Punkte' Menü einen button für Bluetooth Verbindung herstellen haben"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Connect to the Carrera AppConnect from the Dashboard (Priority: P1) 🎯 MVP

The user opens the Streamlit dashboard, clicks the **⋮** kebab menu in the header, and clicks **🔌 Bluetooth verbinden**. The dashboard runs a BLE scan, lists discovered Control Units, and lets the user pick one. Selecting a device persists its MAC into `data/runtime_settings.json::bluetooth_mac` and shows a "Restart erforderlich" notice. On the next `carrera-monitor` boot the live adapter connects directly to that MAC instead of scanning.

**Why this priority**: Today the only way to bind to a specific Control Unit is to memorize the MAC and pass it as `--mac` on the CLI, or to let the pipeline scan on every start. A one-click UI flow eliminates both pain points and is the smallest possible incremental UX win.

**Independent Test**: With `carreralib` installed and an AppConnect powered on, open the dashboard, click **⋮ → 🔌 Bluetooth verbinden**. Assert: (a) one or more devices appear with MAC + name; (b) clicking **Auswählen** writes the MAC to `data/runtime_settings.json`; (c) the page shows a "Restart erforderlich" `st.warning`; (d) on the next `python -m src.main` start (no `--mac` on the CLI), the live adapter connects to that MAC.

**Acceptance Scenarios**:

1. **Given** `carreralib` is installed and an AppConnect is reachable, **When** the user clicks **⋮ → 🔌 Bluetooth verbinden**, **Then** a BLE scan runs and one device list row per Control Unit is rendered, each with **Auswählen**.
2. **Given** the scan returns zero devices, **When** the user clicks **🔌 Bluetooth verbinden**, **Then** the popover shows a helpful empty-state message ("Keine Geräte gefunden — ist die AppConnect eingeschaltet?").
3. **Given** the user clicks **Auswählen** on a row, **When** the page reruns, **Then** `data/runtime_settings.json::bluetooth_mac` equals the selected MAC and a `st.success("Gespeichert. Restart erforderlich.")` notice is rendered above the device list.
4. **Given** `carreralib` is not installed, **When** the user clicks **🔌 Bluetooth verbinden**, **Then** the popover shows `st.error("carreralib nicht installiert. Bitte mit 'pip install carreralib' nachinstallieren.")` and the dashboard does not crash.
5. **Given** a `bluetooth_mac` is already persisted, **When** the user opens the kebab menu, **Then** the popover shows the currently-bound MAC plus a **Zurücksetzen** button that clears `bluetooth_mac` back to `None` and shows the same "Restart erforderlich" notice.

### Edge Cases

- BLE scan raises a non-ImportError exception (permission denied on macOS, hardware missing) → popover shows `st.error(str(exc))` and offers a retry button; no crash.
- User clicks **Auswählen** while the runtime-settings file directory is read-only → catch `OSError`, surface via `st.error`, do not corrupt state.
- A `--mac` CLI argument is present at next boot → CLI wins; the persisted `bluetooth_mac` is ignored (precedence already established by 002/FR-225 for `mock_mode`; this slice extends it to `bluetooth_mac`).
- Two concurrent Streamlit sessions click **Auswählen** with different MACs → last writer wins (file is replaced atomically per `RuntimeSettings._save`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `RuntimeSettings` MUST expose a new persisted key `bluetooth_mac: str | None` (default `None`) with `get_bluetooth_mac()` / `set_bluetooth_mac(value: str | None) -> str | None` accessors and matching module-level helpers, mirroring the existing `mock_mode` pattern.
- **FR-002**: A new helper module `src/services/bluetooth_scanner.py` MUST expose a synchronous `scan_for_devices() -> list[tuple[str, str]]` that wraps `carreralib.connection.scan()` and returns `(mac, name)` pairs. A missing `carreralib` MUST raise `ScannerUnavailableError`; other failures MUST raise `ScannerError(str(exc))`.
- **FR-003**: The dashboard MUST render a **⋮** kebab popover (`st.popover` with `use_container_width=False`) in the header row. The popover MUST contain a **🔌 Bluetooth verbinden** button, the currently persisted MAC (if any), and \u2014 after a scan \u2014 a list of discovered devices each with an **Auswählen** button.
- **FR-004**: Clicking **Auswählen** MUST call `set_bluetooth_mac(mac)` and render `st.success("Gespeichert. Restart erforderlich.")`. Clicking **Zurücksetzen** MUST call `set_bluetooth_mac(None)` and render the same notice.
- **FR-005**: `ScannerUnavailableError` MUST be surfaced via `st.error` with the actionable install hint; `ScannerError` MUST be surfaced via `st.error(str(exc))`. The dashboard MUST NOT crash on either path.
- **FR-006**: `src/main.py::_apply_overrides` MUST extend its precedence chain so that when `args.mac is None` AND `cfg.bluetooth.mac_address is None`, the value of `RuntimeSettings.get_bluetooth_mac()` is used as the fallback `cfg.bluetooth.mac_address`. CLI `--mac` and `config.yaml::bluetooth.mac_address` both still win over the persisted UI choice.
- **FR-007**: No new dependency. `carreralib` is already optional; this slice does not add it as a hard requirement.
- **FR-008**: `data/runtime_settings.json` is already gitignored (002/FR-226); no new gitignore entry is required.

### Key Entities *(data)*

- **`RuntimeSettings.bluetooth_mac` (new persisted key)** — `str | None`, default `None`. Empty string is normalized to `None`. MAC is stored verbatim in the upper/lower case the scan returned; comparison is case-sensitive (carreralib's scan is canonical).

## Success Criteria *(mandatory)*

- **SC-001**: A user with `carreralib` installed and an AppConnect powered on can bind a specific Control Unit to the next pipeline boot in ≤ 3 clicks from the dashboard (open kebab → Bluetooth verbinden → Auswählen). Verified manually against the quickstart; not pinned by an automated harness.
- **SC-002**: With `bluetooth_mac` persisted and no CLI override, `python -m src.main` skips the BLE scan and connects directly to the persisted MAC (verified by a unit test on `_apply_overrides`).
- **SC-003**: A missing `carreralib` package does not crash the Streamlit page; the user sees an actionable install hint.
- **SC-004**: All pre-feature tests remain green; new tests cover (a) `RuntimeSettings.bluetooth_mac` round-trip, (b) `scan_for_devices` error mapping (`ImportError` → `ScannerUnavailableError`, generic exception → `ScannerError`), (c) `_apply_overrides` honors the persisted MAC as a fallback. `ruff` + `mypy --strict` remain clean on the CI matrix (Python 3.11 + 3.12 × ubuntu/macos).

## Assumptions

- The hot-swap variant (start/stop the live `CarreraClientRunner` from inside the Streamlit process without a pipeline restart) is **out of scope** for v1. The persist-and-restart pattern from 002/FR-225 is reused as-is.
- The 3-dot menu lives in the **Dashboard page header only** (not globally). Other pages keep their existing layout. A global header is a future polish slice.
- BLE scanning is invoked synchronously inside the Streamlit script run. The default `carreralib` scan window is short (≈ 3 s); longer scans are out of scope for v1.
- Multi-CU rigs are supported (the device list lets the user pick any of the discovered units); a future slice may add per-driver MAC tagging.
