# Implementation Plan: Robust Bluetooth Connection Supervisor

**Branch**: `005-bluetooth-connection-supervisor` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-bluetooth-connection-supervisor/spec.md`

## Summary

Implement a runtime-owned Bluetooth lifecycle supervisor that is independent from Streamlit rerender cycles, converges to explicit desired connection intent, recovers from transient disconnects and stale telemetry with bounded retry behavior, and preserves strict simulator-mode independence. The approach uses persisted runtime settings as process-safe command IPC, normalized additive lifecycle telemetry, and enriched connection snapshots for dashboard visibility.

## Technical Context

**Language/Version**: Python 3.11 / 3.12  
**Primary Dependencies**: asyncio, streamlit, pydantic, carreralib (optional live runtime dependency), SQLAlchemy (existing stack)  
**Storage**: `data/runtime_settings.json`, `logs/state.json`, JSONL telemetry logs  
**Testing**: pytest, ruff, mypy  
**Target Platform**: macOS and Linux hosts with optional BLE hardware  
**Project Type**: Single Python application (`src/`, `tests/`)  
**Performance Goals**: reconnect delay remains bounded by configured cap; dashboard reflects lifecycle metadata changes within 1 second; no process restart required for transient recovery  
**Constraints**: preserve backward compatibility for existing `connection_state` consumers; keep simulator/Bluetooth control paths independent; avoid introducing required new runtime dependencies  
**Scale/Scope**: one runtime process supervising one active Bluetooth session, one dashboard process issuing lifecycle commands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is an unratified placeholder template with no enforceable normative principles. Gate result: PASS (vacuous).

Repository guardrails remain enforceable and satisfied:

- Keep changes minimal: PASS
- Preserve backward compatibility: PASS
- Add tests for behavior changes: PASS

## Project Structure

### Documentation (this feature)

```text
specs/005-bluetooth-connection-supervisor/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── bluetooth-supervisor-lifecycle.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── config.py
├── dashboard.py
├── event_model.py
├── main.py
├── pages/
│   └── settings.py
├── schemas/
│   └── bluetooth_schema.py
├── services/
│   ├── bluetooth_connection_supervisor.py
│   ├── bluetooth_service.py
│   └── runtime_settings.py
├── state/
│   └── bluetooth_state.py
└── state_manager.py

tests/
├── test_bluetooth_connection_supervisor.py
├── test_bluetooth_service.py
├── test_event_model.py
└── test_state_manager.py
```

**Structure Decision**: Continue with the existing single-project Python layout and add feature-specific modules/tests inside current `src/` and `tests/` boundaries.

## Phase 0: Outline and Research

All technical context unknowns are resolved. Research decisions are documented in [research.md](./research.md):

- Runtime supervisor owns lifecycle independently from UI reruns
- Runtime settings provide command IPC with sequence-based consumption
- Bounded reconnect and stale-detection policy governs recovery
- Simulator-mode independence is explicitly enforced
- Additive telemetry and snapshot compatibility preserve downstream consumers

## Phase 1: Design and Contracts

### Data Model

Entity model and state transitions are documented in [data-model.md](./data-model.md).

### Interface Contracts

Runtime/UI/lifecycle contracts are documented in [contracts/bluetooth-supervisor-lifecycle.md](./contracts/bluetooth-supervisor-lifecycle.md).

### Quickstart

Manual validation flow and quality gates are documented in [quickstart.md](./quickstart.md).

### Agent Context Update

Plan reference between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` in `.github/copilot-instructions.md` points to `specs/005-bluetooth-connection-supervisor/plan.md`.

## Constitution Check (Post-Design)

Post-design re-check result: PASS (constitution template remains non-normative).

Repository guardrails remain satisfied:

- Minimal change footprint: PASS
- Backward compatibility preserved: PASS
- Tests planned for behavior changes: PASS

## Complexity Tracking

No constitution violations require justification.
