# Data Model: live-adapter-carreralib

**Feature**: 003-live-adapter-carreralib
**Date**: 2026-05-16
**Status**: Retroactive — describes shipped entities in [src/carrera_client.py](../../src/carrera_client.py).

This slice does not introduce a persistent storage schema. The entities
below are runtime objects (Python classes / dataclasses) that participate
in the live-adapter pipeline.

## Entities

### `LiveCarreraAdapter`

Production telemetry adapter that wraps carreralib.

| Field / Attribute | Type | Description |
|---|---|---|
| `_cu` | `carreralib.ControlUnit \| None` | Underlying carreralib connection; `None` when disconnected. |
| `_read_task` | `asyncio.Task[None] \| None` | Background task pumping carreralib frames into `_queue`. |
| `_queue` | `asyncio.Queue[TelemetryEvent]` | Buffer between the reader task and `events()` consumers. |
| `_connected` | `bool` | True while a carreralib connection is open; flipped to `False` in `_read_loop`'s `finally`. |
| `_reset_on_connect` | `bool` (default `True`) | Gate for `cu.reset()`; runner clears it for `attempt > 0`. |
| `_idle_timeout_s` | `float` | Idle-frame watchdog window (PR #12). |
| `_last_frame_at` | `float` | Monotonic timestamp of the last `Status`/`Timer` event; used by the watchdog. |
| `_reader_error` | `BaseException \| None` | Exception stored by `_read_loop` for surfacing through `events()`. |

**Invariants**:

- After a successful `connect()`, exactly one `_read_task` is running.
- `_reset_on_connect` is the **only** flag controlling `cu.reset()`; the
  runner sets it via `hasattr(adapter, "_reset_on_connect")` to preserve the
  zero-arg adapter factory contract.
- `events()` MUST re-raise `_reader_error` once the queue is empty and the
  reader task is done.

**State transitions** (high-level):

```text
DISCONNECTED ──connect()──► CONNECTED (reader running, watchdog armed)
CONNECTED ──reader exception OR watchdog idle──► DISCONNECTED (with _reader_error set)
CONNECTED ──close()──► DISCONNECTED (clean; _reader_error = None)
```

### `CarreraClientRunner`

Async supervisor that drives the adapter lifecycle.

| Field / Attribute | Type | Description |
|---|---|---|
| `_adapter_factory` | `Callable[[], LiveCarreraAdapter]` | Zero-arg callable that produces a fresh adapter per run loop. |
| `_reconnect_initial_s` | `float` | Initial reconnect sleep (was `reconnect_interval_seconds`). |
| `_reconnect_max_s` | `float` | Cap on backoff sleep, clamped to be ≥ `_reconnect_initial_s`. Default `30`. |
| `_reconnect_s` | `float` | Back-compat alias preserved for callers; mirrors `_reconnect_initial_s`. |
| `_stop` | `asyncio.Event` | Set by external shutdown; checked between reconnect attempts. |

**Behavior**:

- On `attempt == 0`: connect and (if the adapter supports it) leave `_reset_on_connect` at its default `True`.
- On `attempt > 0`: set `adapter._reset_on_connect = False` via `hasattr` guard before calling `adapter.connect()`.
- On connect or read failure: `backoff_s = min(backoff_s * 2, _reconnect_max_s)`; sleep that long (cancellable); increment attempt.
- On successful connect: reset `backoff_s` to `_reconnect_initial_s` and reset `attempt = 0` for the next failure cycle.
- On `_stop` set during sleep: exit the loop cleanly without raising.

### `TelemetryEvent` (consumed, not defined here)

Existing project schema produced by the adapter. `TelemetryEvent.source` is set to the adapter's `source_name` — `"carrera_appconnect"` for the live adapter ([src/carrera_client.py](../../../src/carrera_client.py)) and `"mock"` for [src/mock_client.py](../../../src/mock_client.py). The live adapter translates
two carreralib payload types into this schema:

| carreralib source | Project event | Notes |
|---|---|---|
| `carreralib.Status` | `TelemetryEvent` of kind `status` | Race-state snapshot (lights, fuel, button states). |
| `carreralib.Timer` | `TelemetryEvent` of kind `timer` | Per-car lap timing record. |

Translation is exercised by [tests/test_live_translation.py](../../tests/test_live_translation.py).

### Scan result line (transient, stdout-only)

Not a Python entity; a single line of CLI output produced by `python -m src.main --scan`.

| Field | Format | Description |
|---|---|---|
| MAC | colon-separated 6-byte hex (uppercase) | Bluetooth address of the discovered CU. |
| `\t` | literal tab | Separator. |
| name | UTF-8 string | Advertised device name (e.g. `Control_Unit`). |
| `\n` | LF | Line terminator. |

One line per discovered device; zero lines on an empty scan; no JSON wrapper.

## Relationships

```text
CarreraClientRunner ──owns──► LiveCarreraAdapter ──wraps──► carreralib.ControlUnit
        │                              │
        │                              └──pumps──► asyncio.Queue ──drains──► events() ──► TelemetryEvent stream
        │
        └──forwards TelemetryEvents to the rest of the pipeline (out of scope for this slice)
```

## Validation Rules

- `max_reconnect_interval_seconds < reconnect_interval_seconds` → clamp max to initial (D-006).
- `_reset_on_connect` MUST be `False` whenever the runner is on attempt > 0 (FR-006, SC-003).
- `events()` MUST NOT swallow reader-task exceptions (FR-005).
- `--scan` MUST produce zero side effects beyond stdout (FR-008, SC-005).
