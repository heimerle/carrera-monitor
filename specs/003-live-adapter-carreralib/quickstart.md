# Quickstart: Live Continuity Hardening

**Feature**: 003-live-adapter-carreralib  
**Date**: 2026-05-16  
**Goal**: Verify auto car detection (max 6), reconnect persistence, and probe-driven stability behavior.

## Prerequisites

- Python 3.11 or 3.12 virtual environment
- Carrera Control Unit reachable via AppConnect
- Database initialized (`data/carrera_dashboard.sqlite3`)

## 1. Run focused tests for the hardening slice

```bash
.venv/bin/python -m pytest \
  tests/test_live_translation.py \
  tests/test_live_ble_stability.py \
  tests/test_live_idle_watchdog.py \
  tests/test_race_service_ingest.py \
  tests/test_race_runner.py \
  tests/test_main_adapter_selection.py \
  tests/test_state_manager.py \
  tests/test_live_continuity.py -q
```

Expected: all tests green.

## 2. Validate auto car-count detection

1. Start app in live mode.
2. Put only one car on the track and trigger telemetry (throttle/lap).
3. Verify snapshot/dashboard reports exactly one active car.
4. Add a second car and verify active count updates.
5. Confirm active count never exceeds 6, even if raw slots outside canonical range are observed.

## 3. Validate reconnect continuity (no race data loss)

1. Start a race and complete several laps.
2. Force a transient disconnect (power-cycle AppConnect briefly or block BLE).
3. Wait for reconnect.
4. Verify:
   - lap totals continue from prior values (no reset to zero)
   - no duplicate lap insertion errors for replayed crossings
   - race summary and standings still include pre-disconnect laps

## 4. Validate restart continuity

1. While race is running, stop the process.
2. Restart the process with recovery enabled.
3. Verify checkpoint restore path resumes continuity and race context remains active.

## 5. Validate link-health policy

1. Simulate stale/no-frame conditions.
2. Verify transition sequence:
   - healthy -> degraded -> stalled -> reconnecting -> healthy
3. Confirm no periodic forced reconnect occurs during active running race unless explicitly configured.

## 6. Suggested config for staging verification

```yaml
bluetooth:
  reconnect_interval_seconds: 2
  max_reconnect_interval_seconds: 20
  idle_timeout_seconds: 15
  idle_warning_seconds: 5
  periodic_forced_reconnect_seconds: 0
  periodic_reconnect_only_when_not_running: true
race_management:
  recover_running_race: true
```

## 7. Troubleshooting checks

- If active cars show phantom IDs: inspect slot mapping diagnostics and confirm canonical cap is enforced.
- If laps disappear after reconnect: inspect checkpoint restore logs and idempotency key collisions.
- If reconnect loops forever: inspect timeout streak logs and BLE environment (interference, concurrent BLE clients).
