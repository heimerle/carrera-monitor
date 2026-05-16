# Implementation Plan: Robust Bluetooth Connection Supervisor

**Branch**: `main` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-bluetooth-connection-supervisor/spec.md`

## Summary

Introduce a single runtime-owned Bluetooth lifecycle supervisor that keeps live telemetry stable across transient transport failures, exposes explicit desired-state controls for dashboard users, and preserves strict simulator/Bluetooth independence. The design uses persisted runtime control intent as process-to-process IPC, normalized lifecycle events, and enriched connection status snapshots.

## Technical Context

**Language/Version**: Python 3.11 / 3.12  
**Primary Dependencies**: asyncio, streamlit, pydantic, carreralib (optional), SQLAlchemy (existing project stack)  
**Storage**: `data/runtime_settings.json`, `logs/state.json`, JSONL telemetry logs  
**Testing**: pytest, ruff, mypy  
**Target Platform**: macOS and Linux hosts with optional BLE hardware
**Project Type**: Single Python application (`src/`, `tests/`)  
**Performance Goals**: reconnects remain bounded; status updates visible within ~1 second of lifecycle transitions; no process restart needed for transient disconnect recovery  
**Constraints**: preserve backward compatibility for existing event consumers; keep dashboard control path independent from simulator mode; avoid introducing required new dependencies  
**Scale/Scope**: one runtime process supervising one active Bluetooth session, one dashboard process issuing control intent

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is currently an unratified placeholder template with no enforceable principles. Gate result: PASS (vacuous).

Repository guardrails still apply and are satisfied:
- Minimal and incremental change footprint: PASS
- Backward compatibility for existing consumers: PASS
- Tests for behavior changes: PASS

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

**Structure Decision**: Keep the existing single-project Python structure and add narrowly scoped Bluetooth lifecycle modules and tests; no architectural split is required.

## Phase 0: Outline and Research

Research findings are captured in [research.md](./research.md), including:
- Lifecycle ownership strategy outside Streamlit reruns
- Runtime settings command IPC strategy between dashboard and runtime
- Reconnect/stale handling policy and bounded backoff decisions
- Event and snapshot compatibility approach for downstream consumers

## Phase 1: Design and Contracts

### Data Model

The feature entities, validation rules, and state transitions are documented in [data-model.md](./data-model.md).

### Interface Contracts

Internal runtime/dashboard/event contracts are documented in [contracts/bluetooth-supervisor-lifecycle.md](./contracts/bluetooth-supervisor-lifecycle.md).

### Quickstart

Manual verification steps are documented in [quickstart.md](./quickstart.md).

### Agent Context Update

Update the plan pointer in `.github/copilot-instructions.md` between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` to this plan path:
`specs/005-bluetooth-connection-supervisor/plan.md`.

## Constitution Check (Post-Design)

Re-evaluated after research and design artifacts: PASS (vacuous constitution template).

Repository guardrails remain satisfied:
- Minimal and incremental change footprint: PASS
- Backward compatibility: PASS
- Test coverage for behavior change: PASS

## Complexity Tracking

No constitution violations require justification.

## Phase 2: Task Planning Endpoint

Task decomposition is generated in `tasks.md` via `/speckit.tasks`.
