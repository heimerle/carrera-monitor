# Quickstart: live-adapter-carreralib

**Feature**: 003-live-adapter-carreralib
**Date**: 2026-05-16
**Status**: Retroactive — operator-facing walkthrough of behavior shipped on `main`.

This quickstart shows an operator how to (a) discover Carrera Control Units
on a fresh venue and (b) run a resilient live race that survives transient
Bluetooth drops.

## Prerequisites

- Python 3.11 or 3.12.
- The project installed in a virtualenv with `requirements.txt` resolved (carreralib + project deps).
- A Carrera Control Unit (CU) powered on within Bluetooth range, OR a serial-bridge cable.
- macOS Bluetooth permission granted to the terminal, or Linux `bluetoothd` running.

## 1. Discover Control Units (`--scan`)

Before starting the dashboard, find the MAC of the CU you want to use:

```bash
python -m src.main --scan
```

Expected output on stdout — one line per discovered device:

```text
AA:BB:CC:DD:EE:FF	Control_Unit
11:22:33:44:55:66	Control_Unit
```

If nothing is reachable, the command prints zero lines and exits `0`.
Either way, **no SQLite race row, telemetry log file, or dashboard server
is created**. The process is intentionally side-effect-free beyond stdout.

Pipe the output through standard Unix tools — for example, grab the first MAC:

```bash
MAC=$(python -m src.main --scan | head -n 1 | cut -f1)
echo "found CU at $MAC"
```

## 2. Start a live race against a known MAC

```bash
python -m src.main --mac AA:BB:CC:DD:EE:FF
```

The runner will:

1. Connect to the CU and call `cu.reset()` exactly once on the **initial** connect (zeros the CU's race clock to a known start state).
2. Stream `Status` / `Timer` frames into the dashboard and persistence layer.
3. If the BLE link drops, enter the reconnect loop:
   - Sleep with exponential backoff (1 s → 2 s → 4 s → … capped at `max_reconnect_interval_seconds`, default 30 s).
   - On every reconnect attempt (`attempt > 0`), **skip** `cu.reset()` so the CU's race clock keeps running across the drop.
   - A successful reconnect resets the backoff for the next failure cycle.
4. If AppConnect goes silent (link healthy, no frames), the BLE idle watchdog forces a reconnect through the same path.
5. If `carreralib.TimeoutError` fires during connect or poll (common before stewards press start), it is logged as a structured diagnostic and routed through reconnect — **never** crashes the runner.

Press `Ctrl+C` to stop; the runner exits cleanly even mid-backoff-sleep.

## 3. Validate the slice locally

```bash
# Unit tests for live-adapter behavior
pytest tests/test_live_translation.py tests/test_live_ble_stability.py \
       tests/test_live_idle_watchdog.py tests/test_main_adapter_selection.py \
       tests/test_adapter_contract.py -q

# Lint + types (project policy: strict on src/)
ruff check src/ tests/
mypy src/
```

All three commands should pass green; the full suite is run by CI on every push to `main`.

## 4. Operator troubleshooting

| Symptom | Likely cause | What the runner does |
|---|---|---|
| `--scan` prints nothing | No CU in range, or Bluetooth permission denied | Exits `0`; check OS Bluetooth permission, retry. |
| Dashboard freezes mid-race, no errors | AppConnect silently stopped forwarding | Idle watchdog forces reconnect within the configured window. |
| Logs show repeated `TimeoutError` before race start | CU is on but not yet broadcasting | Logged as diagnostic; runner stays alive in reconnect loop. |
| Logs show "reconnect — preserving CU clock (skipping cu.reset)" | A drop occurred and the runner is reconnecting | Expected; race clock is preserved. |

## 5. Configuration knobs

Set in `config.yaml` (all optional; defaults are sensible):

```yaml
live:
  reconnect_interval_seconds: 1        # Initial backoff sleep
  max_reconnect_interval_seconds: 30   # Cap on backoff sleep (clamped >= initial)
  idle_watchdog_seconds: <see code>    # Watchdog window for silent AppConnect stalls
```

CLI overrides (from [specs/main/contracts/cli.md](../../main/contracts/cli.md)) take precedence over `config.yaml`.
