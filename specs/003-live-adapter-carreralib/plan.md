# Implementation Plan: live-adapter-carreralib

**Branch**: `003-live-adapter-carreralib-plan` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-live-adapter-carreralib/spec.md`
**Status**: Retroactive plan — feature is **already implemented on `main`** via PRs #9, #10, #12, #14.

## Summary

Replace the placeholder BLE adapter with a production `LiveCarreraAdapter`
built on top of the third-party `carreralib` library, add a one-shot
`python -m src.main --scan` CLI mode for adapter discovery, and harden the
surrounding `CarreraClientRunner` so live races survive transient Bluetooth
disturbances without losing the CU's internal race clock.

Approach (as shipped):

- `LiveCarreraAdapter` (in [src/carrera_client.py](../../src/carrera_client.py)) owns the carreralib connection, a background reader task, an idle-frame watchdog, and a `_reset_on_connect` flag that gates `cu.reset()`.
- `CarreraClientRunner` drives connect → consume `events()` → reconnect-with-backoff, using exponential backoff capped at `max_reconnect_interval_seconds` (default 30s).
- `src/main.py` short-circuits to the scan path when `--scan` is set: it calls the carreralib scanner, prints `<MAC>\t<name>` lines to stdout, and exits `0` without touching DB / log files / dashboard.
- `carreralib.TimeoutError` is treated as a non-fatal "no event this tick" / "transient connect stall" and routed through the reconnect path.

## Technical Context

**Language/Version**: Python 3.11 and 3.12 (CI matrix on both)  
**Primary Dependencies**: `carreralib` (third-party BLE/serial wrapper for Carrera Control Units), `asyncio` standard library, existing project modules (`TelemetryEvent`, `CarreraClientRunner` supervisor)  
**Storage**: N/A for this slice (telemetry persistence lives in adjacent modules; this slice only produces `TelemetryEvent`s and a CLI side-effect-free scan)  
**Testing**: `pytest` with `pytest-asyncio` patterns already in use; ruff (lint) and mypy strict on `src/`  
**Target Platform**: macOS + Linux desktop hosts with BLE (Bluetooth Low Energy) or serial access to a Carrera Control Unit  
**Project Type**: Single-project CLI + library (no frontend / backend split)  
**Performance Goals**: Sustain the CU's native frame rate (≈ 1 frame / 100 ms during a race) without queue back-pressure; reconnect within `reconnect_interval_seconds + max_reconnect_interval_seconds` of a drop  
**Constraints**: Must not call `cu.reset()` on reconnect attempts (`attempt > 0`) so the CU clock survives transient drops; `--scan` must have **zero** side effects beyond stdout; shutdown requests must interrupt the backoff sleep  
**Scale/Scope**: Single CU per process; one host per race; the live adapter is the single producer of live `TelemetryEvent`s

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project's constitution at `.specify/memory/constitution.md` is the
unratified template (placeholder principles `[PRINCIPLE_1_NAME]` … `[PRINCIPLE_5_NAME]`
with no concrete MUST/SHOULD content). There are therefore no ratified
principles to check against; this gate passes vacuously.

If/when the constitution is ratified with concrete principles, this plan
should be re-evaluated. Notable properties of the shipped code that any
likely future principles would care about:

- **Tests**: Each user-visible behavior has a corresponding test (`tests/test_live_translation.py`, `tests/test_live_ble_stability.py`, `tests/test_live_idle_watchdog.py`, `tests/test_main_adapter_selection.py`, `tests/test_adapter_contract.py`).
- **CLI**: `python -m src.main --scan` honors stdin/args → stdout, errors → stderr, exit code 0 on success.
- **Simplicity**: No new abstractions beyond what carreralib + the existing adapter contract require; `_reset_on_connect` is a single bool flag rather than a strategy object.

**Result**: PASS (vacuous). Re-evaluated after Phase 1 design below — still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/003-live-adapter-carreralib/
├── spec.md              # Retroactive feature spec (already authored)
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output — retroactive decisions log
├── data-model.md        # Phase 1 output — entities (adapter, runner, events)
├── quickstart.md        # Phase 1 output — operator-facing scan + live walkthrough
├── contracts/
│   └── live-adapter.md  # Phase 1 output — adapter contract + --scan CLI contract
├── checklists/
│   └── requirements.md  # Authored by /speckit.specify (already present)
└── tasks.md             # Phase 2 output (/speckit.tasks — generated separately)
```

### Source Code (repository root, as shipped)

```text
src/
├── carrera_client.py            # LiveCarreraAdapter + CarreraClientRunner (PRs #9/#10/#12/#14)
├── main.py                      # CLI entry; --scan short-circuit (PR #9)
├── mock_client.py               # Mock adapter (unchanged by this slice)
├── event_model.py               # TelemetryEvent schema (consumed, not modified)
└── … (db, dashboard, race controls, etc.)

tests/
├── test_adapter_contract.py     # Shared adapter contract — LiveCarreraAdapter conforms
├── test_live_translation.py     # Status/Timer → TelemetryEvent translation
├── test_live_ble_stability.py   # Reader-task failure, cu.reset skip, exp backoff (PR #14)
├── test_live_idle_watchdog.py   # Idle watchdog forces reconnect (PR #12)
└── test_main_adapter_selection.py  # --scan path + mock-vs-live selection
```

**Structure Decision**: Single-project Python CLI/library layout (Option 1).
No frontend/backend split. All live-adapter code lives in
[src/carrera_client.py](../../src/carrera_client.py); all tests for this
slice live directly under [tests/](../../tests/).

## Complexity Tracking

No constitution violations to justify (the constitution is unratified).
The shipped implementation introduces no extra projects, no new persistence
layer, no new service boundary. The single non-obvious mechanism — skipping
`cu.reset()` on reconnect attempts > 0 — is justified directly by FR-006
(preserve CU clock across drops) and has dedicated tests.
