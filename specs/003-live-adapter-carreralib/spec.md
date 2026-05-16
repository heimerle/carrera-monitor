# Feature Specification: live-adapter-carreralib

**Feature Branch**: `003-live-adapter-carreralib`  
**Created**: 2026-05-16  
**Status**: Implemented (retroactive specification)  
**Input**: Retroactive spec for the carreralib-based live adapter stack already merged on `main` via PRs #9, #10, #12, and #14.

## Overview

This slice replaces the original placeholder BLE adapter with a production
`LiveCarreraAdapter` built on top of the third-party `carreralib` library, and
hardens the surrounding runner so that real-world Carrera Control Unit (CU)
sessions survive transient Bluetooth disturbances without losing the CU's
internal race clock. It also adds a one-shot `--scan` CLI mode so operators
can discover nearby CUs before launching the full telemetry pipeline.

The feature is already implemented on `main`. This specification documents
the user-visible behavior retroactively so that downstream `tasks.md` can
be generated as a `[X]` checklist for traceability.

Primary implementation files:

- [src/carrera_client.py](../../src/carrera_client.py) — `LiveCarreraAdapter`, translation of `Status`/`Timer` payloads into `TelemetryEvent`, BLE idle watchdog, exponential reconnect backoff, conditional `cu.reset`.
- [src/main.py](../../src/main.py) — CLI entry point, `--scan` short-circuit, adapter wiring for the live runner.

Primary test files:

- [tests/test_live_translation.py](../../tests/test_live_translation.py) — `Status`/`Timer` → `TelemetryEvent` translation.
- [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) — reader-task exceptions surface, reconnect skips `cu.reset`, exponential backoff cap.
- [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) — idle-frame watchdog forces reconnect when AppConnect goes silent.
- [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) — `--scan` exit path and mock-vs-live adapter selection.
- [tests/test_adapter_contract.py](../../tests/test_adapter_contract.py) — shared telemetry-adapter contract honored by `LiveCarreraAdapter`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover Control Units before a race (Priority: P1)

A race operator setting up at a new venue needs to know which Carrera Control
Units are reachable from the host machine before committing to a full run.

**Why this priority**: Without a discovery step, the operator has to guess MAC
addresses or read them off the CU sticker; getting this wrong wastes the
warm-up window and erodes trust in the tool.

**Independent Test**: Run `python -m src.main --scan` on a host that has at
least one CU powered on within BLE range. The command MUST print one
`<MAC>\t<name>` line per discovered CU to stdout, exit with code 0, and MUST
NOT start the telemetry pipeline, the database writer, or the dashboard.

**Acceptance Scenarios**:

1. **Given** at least one Carrera CU is powered on within BLE range, **When** the operator runs `python -m src.main --scan`, **Then** the process prints discovered CUs as tab-separated `MAC<TAB>name` lines on stdout and exits with code 0.
2. **Given** no CUs are reachable, **When** the operator runs `python -m src.main --scan`, **Then** the process prints no device lines, exits with code 0, and does not start the dashboard, database, or runner.
3. **Given** the `--scan` flag is set, **When** the process starts, **Then** no SQLite race row, no telemetry log file, and no dashboard server is created.

---

### User Story 2 - Live race survives a transient BLE drop (Priority: P1)

During a live race, the BLE link between the host and the CU briefly drops
(e.g. someone walks between laptop and track). Stewards must not lose the
race: the CU's internal clock keeps running, and the host must reconnect and
resume ingest while preserving lap timing continuity.

**Why this priority**: A mid-race process crash or a clock reset on reconnect
invalidates the race result. This is the single most important reliability
property for the live adapter.

**Independent Test**: Simulate a drop by closing the underlying carreralib
connection mid-stream (covered by `test_live_ble_stability.py`). The runner
MUST observe the drop, sleep using exponential backoff capped at
`max_reconnect_interval_seconds`, reconnect, and on every reconnect attempt
(attempt index > 0) MUST NOT call `cu.reset()`. Only the very first connect
of a runner lifecycle is allowed to reset the CU clock.

**Acceptance Scenarios**:

1. **Given** a live adapter is connected and streaming, **When** the carreralib reader task raises an exception, **Then** `events()` surfaces the exception (does not hang on an empty queue) and the `CarreraClientRunner` enters its reconnect loop.
2. **Given** the runner is reconnecting after a drop, **When** `connect()` is invoked with `attempt > 0`, **Then** the adapter MUST skip `cu.reset()` and keep the CU's race clock intact.
3. **Given** repeated connect failures, **When** each retry fires, **Then** the sleep interval doubles starting from `reconnect_interval_seconds` and is capped at `max_reconnect_interval_seconds` (default 30s); a successful connect resets the backoff to the initial value.
4. **Given** the runner is shutting down, **When** stop is requested during a reconnect sleep, **Then** the runner exits cleanly without raising.

---

### User Story 3 - Silent AppConnect stalls auto-recover (Priority: P2)

The CU's BLE bridge ("AppConnect") sometimes stops forwarding `Status`/`Timer`
frames without dropping the BLE socket. From the host's perspective the
connection looks healthy but no telemetry arrives.

**Why this priority**: Silent stalls are harder to detect than hard drops and,
if undetected, leave the dashboard frozen for an entire race.

**Independent Test**: Drive the adapter with a fake source that delivers no
frames for longer than the configured idle window (covered by
`test_live_idle_watchdog.py`). The watchdog MUST trigger a forced reconnect.

**Acceptance Scenarios**:

1. **Given** the adapter has gone longer than the configured idle interval without any `Status` or `Timer` event, **When** the watchdog ticks, **Then** the adapter forces a reconnect through the same path used for hard drops.
2. **Given** a reconnect was triggered by the idle watchdog, **When** it succeeds, **Then** the CU clock is preserved (no `cu.reset` on attempt > 0) and ingest resumes.

---

### User Story 4 - Pre-race timeouts no longer kill the process (Priority: P2)

Before stewards press the green button, the CU may not yet be broadcasting
useful frames. The carreralib library raises `TimeoutError` from `recv()`
roughly every second when idle, and previously a `TimeoutError` during
connect or initial poll could crash the runner.

**Why this priority**: A crash during setup forces the operator to restart
the whole tool, often losing dashboard state and the partially configured
race row.

**Independent Test**: Inject a `carreralib.TimeoutError` during the connect
and poll paths. The runner MUST log a structured diagnostic and route the
condition through the reconnect path instead of propagating the exception.

**Acceptance Scenarios**:

1. **Given** the adapter is connecting, **When** carreralib raises `TimeoutError`, **Then** the runner catches it, emits a structured diagnostic event, and re-enters the reconnect loop instead of terminating.
2. **Given** the adapter is polling, **When** carreralib raises `TimeoutError`, **Then** the poll is treated as "no event this tick" rather than as a fatal error.

---

### Edge Cases

- `--scan` on a host without a working Bluetooth stack: the command prints no device lines and exits 0; it does not raise an unhandled exception.
- `--scan` combined with `--mock`: scan still takes precedence and runs against the real BLE stack (the operator's explicit discovery intent wins).
- Reconnect attempted while the user has already requested shutdown: backoff sleep is interruptible and the runner exits cleanly.
- `max_reconnect_interval_seconds` configured lower than `reconnect_interval_seconds`: the adapter clamps the maximum to be at least the initial value so backoff is well-defined.
- carreralib reader task raises an unexpected (non-`TimeoutError`) exception: it is surfaced through `events()` and routed through reconnect rather than swallowed.
- Idle watchdog fires while a reconnect is already in progress: the watchdog does not stack additional reconnect attempts.

## Requirements *(mandatory)*

### Functional Requirements

All requirements below are **already implemented on `main`** (status: `[X]`).

- **FR-001** `[X]`: System MUST provide a `LiveCarreraAdapter` in `src/carrera_client.py` that wraps `carreralib` and translates its `Status` and `Timer` payloads into the project's `TelemetryEvent` schema, conforming to the shared adapter contract exercised by `tests/test_adapter_contract.py` and `tests/test_live_translation.py`.
- **FR-002** `[X]`: System MUST expose a one-shot CLI mode `python -m src.main --scan` that discovers Carrera Control Units via BLE/serial, prints one `<MAC>\t<name>` line per device to stdout, exits with code 0, and does NOT start the telemetry pipeline, database writer, or dashboard.
- **FR-003** `[X]`: System MUST treat `carreralib.TimeoutError` raised during connect or poll as a non-fatal condition: log a structured diagnostic and route the situation through the existing reconnect path instead of terminating the runner.
- **FR-004** `[X]`: System MUST implement a BLE idle watchdog that, when no `Status` or `Timer` event has been observed for `live.idle_timeout_seconds` (default `15`, clamped to `>= 3`), forces a reconnect through the same path used for hard drops.
- **FR-005** `[X]`: `LiveCarreraAdapter.events()` MUST surface exceptions raised by the underlying carreralib reader task to its async consumer (instead of hanging on an empty queue), so `CarreraClientRunner` can observe connection drops and trigger reconnect.
- **FR-006** `[X]`: On reconnect attempts (attempt index > 0), the adapter MUST skip `cu.reset()` so the Control Unit's race clock is preserved across drops; only the very first connect of a runner lifecycle is allowed to perform `cu.reset()`.
- **FR-007** `[X]`: `CarreraClientRunner` MUST use exponential backoff between reconnect attempts, starting from `reconnect_interval_seconds` and capped at a configurable `max_reconnect_interval_seconds` (default `30`); a successful connect MUST reset the backoff to the initial value.
- **FR-008** `[X]`: System MUST allow the operator to combine `--scan` with other CLI flags without performing any side effects beyond device discovery and stdout printing (no database row, no log file, no dashboard server).
- **FR-009** `[X]`: Shutdown requests MUST be honored during reconnect sleeps; the runner MUST exit cleanly without propagating exceptions from the backoff loop.

### Key Entities

- **LiveCarreraAdapter**: Production telemetry adapter wrapping carreralib; owns the BLE/serial connection, the reader task, the idle watchdog timer, and the `_reset_on_connect` flag that gates `cu.reset()`.
- **CarreraClientRunner**: Async supervisor that drives the adapter lifecycle (connect → events → reconnect-with-backoff) and forwards translated `TelemetryEvent`s to the rest of the pipeline.
- **TelemetryEvent**: Existing project schema (defined elsewhere) into which carreralib `Status` and `Timer` frames are translated; the adapter is the only producer of these events in live mode.
- **Scan result line**: Single CLI output record of the form `MAC<TAB>name`, one per discovered Control Unit, emitted exclusively by the `--scan` path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full project test suite passes on the existing CI matrix (Python 3.11 and 3.12 × ubuntu-latest and macos-latest) on every push to `main`. The absolute test count is intentionally not pinned, per the policy shipped in PR #15; the success signal is "all matrix jobs green," not a specific number.
- **SC-002**: A simulated reader-task exception during a live session results in a reconnect attempt within at most `reconnect_interval_seconds + max_reconnect_interval_seconds` wall-clock seconds (verified by `tests/test_live_ble_stability.py`).
- **SC-003**: Across an arbitrary number of reconnects within a single runner lifecycle, `cu.reset()` is invoked at most once — on the very first successful connect (verified by `tests/test_live_ble_stability.py`).
- **SC-004**: When AppConnect stops forwarding frames for longer than the configured idle interval, a forced reconnect is triggered without operator intervention (verified by `tests/test_live_idle_watchdog.py`).
- **SC-005**: `python -m src.main --scan` exits with code 0 and produces zero side effects beyond stdout output on a host with no reachable CUs (verified by `tests/test_main_adapter_selection.py`).
- **SC-006**: A `TimeoutError` raised by carreralib during the connect or poll phase never propagates out of the runner; it is converted into a structured diagnostic and routed through reconnect (verified by the live-adapter test suite).

## Assumptions

- The third-party `carreralib` library is installed and importable in the runtime environment; its public API (`Status`, `Timer`, `TimeoutError`, `scan()`, `connect()`, `recv()`, `reset()`) is stable for the versions pinned in `requirements.txt`.
- Bluetooth/serial access is granted to the host process (e.g. macOS Bluetooth permission, Linux `bluetoothd` running); environments without BLE simply produce empty scan results rather than errors.
- The project's existing `TelemetryEvent` schema, `CarreraClientRunner` supervisor, and mock adapter pathway remain backward-compatible; this slice strictly replaces the placeholder live adapter and adds CLI + resilience features.
- The CI matrix defined in `.github/workflows/` on `main` is the canonical success gate; success is "matrix green" rather than any fixed test count, in line with the PR #15 policy.
- Operators run `--scan` interactively from a terminal; programmatic consumers parse the `MAC<TAB>name` line format directly from stdout.
