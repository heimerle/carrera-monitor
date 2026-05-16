# Quickstart: Calm Connection UI + Restore Race Metrics

## Prerequisites

- Python environment available for this repository.
- Dependencies installed.
- Dashboard runnable via project start command.

## 1. Start Application

1. Launch the application runtime and dashboard.
2. Open the dashboard URL in browser.
3. Confirm main dashboard page renders.

## 2. Verify Connection Indicator (Icon-Only)

1. Observe the dashboard header while connection transitions occur.
2. Confirm the header shows only one icon for connection state (no verbose status text).
3. Validate mapping:
   - ready/connected -> `🟢`
   - connecting/scanning/subscribing/reconnecting -> `🟡`
   - stale -> `🟠`
   - error -> `🔴`
   - disconnected/manually_disconnected -> `⚫`
   - unknown/missing -> `⚪`
4. Open diagnostics panel and confirm full connection details are still available there.

## 3. Verify Race Metrics Section Always Visible

1. With no active race, load dashboard.
2. Confirm race metrics cards/table remain visible with placeholders (`-`) for unavailable values.
3. Start or simulate an active race.
4. Confirm race-level metrics update: name, status, mode, elapsed, progress.

## 4. Verify Per-Car Metrics and Lap Normalization

1. Feed telemetry lap updates for configured cars.
2. Confirm each car row updates `lap_count`, `latest_lap`, `best_lap`, `average_lap`.
3. Repeat with both event variants:
   - `lap.payload.lap_time_ms`
   - `lap_completed.payload.time_ms`
4. Confirm both variants update the same car metrics consistently.

## 5. Verify Resilience Edge Cases

1. Emit unknown car IDs and malformed lap payloads.
2. Confirm dashboard remains stable and continues rendering metrics section.
3. Confirm diagnostics indicates dropped/ignored lap events without UI breakage.

## 6. Run Quality Gates

Run project quality commands:
1. `ruff check .`
2. `mypy src`
3. `pytest`

Expected result:
- All checks pass.
- New/updated tests cover icon-only connection rendering, always-visible metrics section, lap normalization compatibility, and metric calculations.

Latest implementation run result:
- `ruff check .` -> `All checks passed!`
- `mypy src` -> `Success: no issues found in 36 source files`
- `pytest` -> `209 passed in 13.58s`
