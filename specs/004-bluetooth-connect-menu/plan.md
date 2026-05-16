# Implementation Plan: Manual Bluetooth Connection via Overflow Menu

**Branch**: `004-bluetooth-connect-menu` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: User-provided feature specification for manual Bluetooth connect/disconnect, scan, status, and simulator coexistence

## Summary

Extend the existing dashboard kebab menu into a full manual Bluetooth workflow: scan devices, connect using configured MAC or selected scanned device, disconnect explicitly, visualize live connection state, and retry failures. The implementation remains incremental and preserves the existing telemetry pipeline, EventBus flow, and simulator/mock behavior. No hot-swap rewrite or architecture replacement is introduced.

## Technical Context

**Language/Version**: Python 3.11 / 3.12
**Primary Dependencies**: Streamlit >= 1.37 (`st.popover`), `carreralib` optional extra (`[live]`), internal EventBus and StateManager abstractions, `pydantic`, `pyyaml`
**Storage**: `data/runtime_settings.json` for persisted Bluetooth MAC fallback and existing runtime flags
**Testing**: pytest unit tests for scanner/service/state mapping/override precedence; targeted integration tests around EventBus state emissions; manual Streamlit smoke
**Target Platform**: macOS and Linux developer machines with optional BLE-capable hardware
**Project Type**: Single Python package application (`src/`)
**Performance Goals**: Non-blocking UI interactions with bounded scan/connect operations and user-visible progress states
**Constraints**:
- Preserve existing telemetry architecture and race-management behavior
- Keep simulator/mock mode independent from Bluetooth telemetry lifecycle
- Preserve CLI/config precedence over persisted runtime Bluetooth choice
- Keep changes backward-compatible with existing runtime settings files
**Scale/Scope**: Single local operator dashboard with one active telemetry pipeline process

## Constitution Check (Pre-Design)

`.specify/memory/constitution.md` is currently an unratified template with placeholders and no enforceable principles. Gate status: PASS (vacuous). Repo guardrails still apply: minimal change, backward compatibility, and tests for behavioral changes.

## Project Structure

### Documentation (this feature)

```
specs/004-bluetooth-connect-menu/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── bluetooth-overflow-menu.md
└── tasks.md
```

### Source Code (planned impact)

```
src/
├── dashboard.py                   # overflow menu actions, status rendering
├── main.py                        # runtime fallback and coexistence behavior
├── services/
│   ├── runtime_settings.py        # persisted bluetooth_mac helpers
│   └── bluetooth_scanner.py       # device discovery + error mapping
├── state/ or services/            # bluetooth connection state service (new or extended)
└── event_bus/ integration points  # state transition events for UI updates

tests/
├── test_bluetooth_scanner.py
├── test_main_overrides.py
├── test_dashboard_bluetooth_menu.py
└── test_bluetooth_state_service.py
```

## Phase 0: Outline & Research

Research outcomes are captured in [research.md](./research.md). All technical unknowns from this plan are resolved there, including async scan handling, EventBus integration boundaries, and retry/state semantics.

## Phase 1: Design & Contracts

### Data Model

Detailed entities and state transitions are documented in [data-model.md](./data-model.md), including the lifecycle:
`DISCONNECTED -> SCANNING -> CONNECTING -> CONNECTED -> RECONNECTING -> ERROR`.

### Interface Contracts

Behavioral contracts for menu actions, service calls, EventBus events, and error handling are specified in [contracts/bluetooth-overflow-menu.md](./contracts/bluetooth-overflow-menu.md).

### Quickstart

Manual verification flow is documented in [quickstart.md](./quickstart.md).

### Agent Context Update

The `<!-- SPECKIT START -->` pointer in `.github/copilot-instructions.md` already references this plan file (`specs/004-bluetooth-connect-menu/plan.md`), so no path update is required.

## Constitution Check (Post-Design)

Re-evaluated after research/design artifacts: PASS (vacuous constitution template). The design remains incremental, testable, and backward-compatible.

## Phase 2: Task Planning Endpoint

Planning stops here by design. Task decomposition is handled in `tasks.md` (or regenerated with `speckit.tasks` if scope changes are accepted into the feature spec).
