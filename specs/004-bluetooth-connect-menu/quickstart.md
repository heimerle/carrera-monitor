# Quickstart: Manual Bluetooth Connection via Overflow Menu

## Prerequisites

1. Python environment set up for this repository.
2. Optional BLE dependencies installed (`carreralib` live extras where required).
3. Carrera AppConnect device powered on and nearby.

## Run Dashboard

1. Start the app:
   - `streamlit run src/app.py --server.headless true`
2. Open dashboard page in browser.

## Verify Overflow Menu

1. Confirm the header shows the overflow icon `⋮`.
2. Open menu and verify these entries:
   - `Connect Bluetooth`
   - `Disconnect Bluetooth`
   - `Scan Bluetooth Devices`
   - `Bluetooth Status`

## Connect Flow

1. Click `Connect Bluetooth`.
2. If MAC is configured, observe `CONNECTING` then `CONNECTED` or `ERROR`.
3. If MAC is not configured, run scan, select a device, then connect.

## Disconnect Flow

1. While connected, click `Disconnect Bluetooth`.
2. Verify state returns to `DISCONNECTED`.

## Scan Flow

1. Click `Scan Bluetooth Devices`.
2. Verify `SCANNING` state then `scan_complete` output.
3. If no devices are found, verify empty-state messaging.
4. If scan fails, verify `ERROR` state and actionable message.

## Status + Retry

1. Click `Bluetooth Status` and verify current lifecycle state and active MAC.
2. Trigger a failure scenario and verify `ERROR` state.
3. Retry from menu and verify transition `ERROR -> CONNECTING` or `ERROR -> SCANNING`.

## Simulator Coexistence

1. Enable simulator/mock mode and perform Bluetooth actions.
2. Verify simulator/mock mode remains unchanged.
3. Verify telemetry architecture behavior is unaffected.
