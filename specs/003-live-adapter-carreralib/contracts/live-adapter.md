# Contract: Live Adapter & `--scan` CLI

**Feature**: 003-live-adapter-carreralib
**Date**: 2026-05-16
**Status**: Retroactive — describes the contract honored by the shipped code in [src/carrera_client.py](../../../src/carrera_client.py) and [src/main.py](../../../src/main.py).

This document captures two contracts owned by this slice:

1. The Python-level **adapter contract** that `LiveCarreraAdapter` honors and that the rest of the runtime relies on.
2. The **`--scan` CLI contract** (a sub-contract of the project's top-level CLI defined in [specs/main/contracts/cli.md](../../main/contracts/cli.md)).

## 1. Adapter Contract (`TelemetryAdapter` shape)

`LiveCarreraAdapter` is a `TelemetryAdapter` (the shared protocol exercised
by [tests/test_adapter_contract.py](../../../tests/test_adapter_contract.py)).
The contract this slice owns specifically:

### Method: `async def connect(self) -> None`

- **Pre-conditions**: Adapter is not currently connected.
- **Post-conditions on success**: A carreralib `ControlUnit` is open; a background reader task is running and pumping events into the internal queue.
- **`cu.reset()` gating**:
  - If `self._reset_on_connect is True` (default for a fresh adapter): MAY call `cu.reset()`. Logs `"live: initial connect — resetting CU clock"`.
  - If `self._reset_on_connect is False` (runner-set on reconnect): MUST NOT call `cu.reset()`. Logs `"live: reconnect — preserving CU clock (skipping cu.reset)"`.
- **Errors**:
  - `carreralib.TimeoutError`: caught by the runner, not the adapter (routed through reconnect path).
  - Other exceptions: propagate to the runner, which records them and enters backoff.

### Method: `async def events(self) -> AsyncIterator[TelemetryEvent]`

- **Yields**: One `TelemetryEvent` per drained `Status` / `Timer` frame, in arrival order.
- **Termination**:
  - On clean close (`close()` called and reader task ended without exception): exits cleanly (`StopAsyncIteration`).
  - On reader-task exception: drains any buffered events, then **re-raises** the stored exception so the runner observes the failure.
  - MUST NOT hang on an empty queue when the reader task has finished. This is the precise behavior fixed in PR #14.

### Method: `async def close(self) -> None`

- **Post-conditions**: `_read_task` cancelled and awaited; carreralib `ControlUnit` closed; `_connected == False`.
- **Idempotent**: Calling `close()` on an already-closed adapter is a no-op.

### Constructor: `LiveCarreraAdapter(..., reset_on_connect: bool = True, ...)`

- Zero-arg construction must remain valid for the test-fake factory pattern; new kwargs are keyword-only with defaults.
- Stores `reset_on_connect` as `self._reset_on_connect`.
- Existing zero-arg `FlakyAdapter`-style fakes in tests are unaffected.

### Runner Contract: `CarreraClientRunner`

The runner owns the lifecycle and the reconnect policy:

- Constructor accepts `max_reconnect_interval_seconds: int = 30`; stored as `_reconnect_max_s`, clamped to be ≥ `_reconnect_initial_s`.
- On `attempt > 0` and **only if** `hasattr(adapter, "_reset_on_connect")`: sets `adapter._reset_on_connect = False` before calling `adapter.connect()`.
- Backoff sequence: `backoff_s` starts at `_reconnect_initial_s`; on each failure, `backoff_s = min(backoff_s * 2, _reconnect_max_s)`. On successful connect, resets to `_reconnect_initial_s`.
- Sleep is `await asyncio.sleep(backoff_s)`; cancellable by the runner's stop signal.

## 2. `--scan` CLI Contract

Sub-contract of [specs/main/contracts/cli.md](../../main/contracts/cli.md).

### Invocation

```text
python -m src.main --scan [--config PATH] [--log-level LEVEL]
```

### Side-effect contract

`--scan` MUST be **side-effect-free** except for stdout and structured logs:

| Side effect | Allowed in `--scan` mode? |
|---|---|
| Print one `<MAC>\t<name>` line per discovered CU to stdout | ✅ Required |
| Write structured log lines to the configured log sink (stderr / file) | ✅ Allowed |
| Open a BLE/serial scan session via carreralib | ✅ Required |
| Create a SQLite race row | ❌ Forbidden |
| Open a telemetry log file (`./logs/*.jsonl`) | ❌ Forbidden |
| Launch the Streamlit dashboard | ❌ Forbidden |
| Start `CarreraClientRunner` / a telemetry pipeline | ❌ Forbidden |

### Output format

- Per discovered device, exactly one line: `<MAC><TAB><name>\n`.
- `MAC` is the device's Bluetooth address in colon-separated uppercase hex (e.g. `AA:BB:CC:DD:EE:FF`).
- `name` is the device's advertised name (UTF-8; may contain spaces; MUST NOT contain a tab or newline).
- Empty scan → zero lines (no header, no footer).

### Exit codes

- `0` — Scan completed (with any number of devices, including zero).
- `1` — Configuration error (invalid YAML / log level / etc.); no scan attempted.
- `3` — Unrecoverable runtime error during scan (e.g. Bluetooth stack unavailable AND `carreralib.scan()` raised). Implementation note: on hosts with no Bluetooth, the canonical behavior is empty scan + exit 0; exit 3 is reserved for genuinely unexpected exceptions.

### Interaction with other flags

- `--scan` + `--mock`: scan still runs against the real BLE stack (operator's explicit discovery intent wins). The mock adapter is not used in scan mode.
- `--scan` + `--mac`: `--mac` is ignored in scan mode (you're discovering MACs, not connecting to one).
- `--scan` + `--no-dashboard`: redundant but harmless (scan mode never launches the dashboard anyway).
- `--scan` + `--log-dir`, `--debug-raw`: the flags are accepted but have no effect because no telemetry session runs.

### Tested by

- [tests/test_main_adapter_selection.py](../../../tests/test_main_adapter_selection.py) — `--scan` exit path; no pipeline started.
