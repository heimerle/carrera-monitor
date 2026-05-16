# Quickstart: Robust Bluetooth Connection Supervisor

## Prerequisites

1. Python environment and project dependencies installed.
2. Optional live dependency installed for hardware mode (`carreralib`).
3. AppConnect powered on for live-device tests.

## Start the Runtime

1. Start the application:
   - `python -m src.main`
2. Open dashboard at:
   - `http://localhost:8501`

## Verify Lifecycle Control Flow

1. Open Settings page Bluetooth controls.
2. Click Connect Bluetooth.
3. Verify status transitions toward connected/ready state.
4. Click Disconnect Bluetooth.
5. Verify state becomes manually disconnected and stays disconnected until reconnect is requested.

## Verify Scan and Selection

1. Click Scan Devices.
2. Confirm either discovered devices are listed or a clear empty-state message appears.
3. Request connect with selected device identity.
4. Confirm desired state and device identity are reflected in status output.

## Verify Unexpected Disconnect Recovery

1. Establish a live connection.
2. Induce transport disruption (for example by temporarily disabling adapter availability).
3. Verify state transitions to reconnecting and retries follow bounded delay policy.
4. Restore adapter availability and verify status returns to ready/connected state.

## Verify Stale Detection Path

1. Keep transport connected while telemetry is silent longer than configured stale timeout.
2. Verify state transitions to stale.
3. If `reconnect_on_stale=true`, verify reconnect path is triggered.

## Verify Simulator Coexistence

1. Enable simulator mode in Settings.
2. Perform Bluetooth connect/disconnect/scan/retry actions.
3. Confirm simulator mode value is unchanged.

## Run Quality Gates

1. `ruff check src tests`
2. `mypy src`
3. `pytest -q`

All gates should pass before task decomposition and implementation handoff.
