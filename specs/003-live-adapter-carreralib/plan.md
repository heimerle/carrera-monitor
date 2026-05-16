# Implementation Plan: Live Adapter Continuity Hardening

**Branch**: `main` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Follow-up requirements for live reliability:
1. Auto-detect number of cars in race (maximum 6)
2. Preserve race data across reconnects
3. Stabilize Bluetooth connection (heartbeat/probe policy)

## Summary

Harden the existing live adapter pipeline to eliminate reconnect-related race discontinuities and phantom car slots. The plan introduces canonical car-slot normalization (cap 6), automatic active-car detection, durable lap checkpoint persistence across reconnect/restart, and a probe-driven reconnect strategy. The design keeps the existing event bus and race management architecture while adding targeted persistence and health-state layers.

## Technical Context

**Language/Version**: Python 3.11 / 3.12  
**Primary Dependencies**: `carreralib`, `asyncio`, `pydantic`, `sqlalchemy`, `streamlit`  
**Storage**: SQLite (`data/carrera_dashboard.sqlite3`), `logs/state.json`, JSONL telemetry logs  
**Testing**: `pytest` unit/integration tests for translation, reconnect continuity, ingest idempotency, and state behavior  
**Target Platform**: macOS and Linux hosts with optional BLE hardware  
**Project Type**: Single Python application (`src/`, `tests/`)  
**Performance Goals**:
- Reconnect recovery visible within configured window (initial backoff + watchdog)
- No lap continuity regression across reconnect in active race
- Active car count converges within a short event window and is capped at 6
**Constraints**:
- Physical race capacity remains max 6 cars
- Backward-compatible defaults for existing configs
- Do not force reconnects on a fixed timer while race is running
- No race data loss on reconnect/restart for active race
**Scale/Scope**: Single local operator process controlling one active live pipeline and one race database

## Constitution Check (Pre-Design)

`.specify/memory/constitution.md` is a placeholder template with no enforceable ratified principles. Gate result: PASS (vacuous).

Repository guardrails still apply and are enforced in this plan:
- Minimal changes to existing architecture: PASS (targeted modules only)
- Backward compatibility: PASS (new knobs default-safe)
- Tests for behavior changes: PASS (explicit new tests listed in quickstart/contract)

## Project Structure

### Documentation (this feature)

```text
specs/003-live-adapter-carreralib/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── live-adapter.md
│   └── live-reliability-hardening.md
└── tasks.md
```

### Source Code (planned impact)

```text
src/
├── carrera_client.py              # slot normalization, reconnect continuity hooks
├── race_runner.py                 # dispatch behavior for continuity events
├── services/
│   ├── race_service.py            # durable lap checkpoint + idempotent ingest
│   └── (new) live_continuity.py   # persistence + restore helpers
├── state_manager.py               # race state reset guard on reconnect noise
├── config.py                      # optional link-health knobs
├── models.py                      # checkpoint schema (migration-backed)
└── dashboard.py                   # show active car auto-detection and health hints

tests/
├── test_live_translation.py
├── test_live_ble_stability.py
├── test_race_service_ingest.py
├── test_state_manager.py
└── test_live_continuity.py        # new focused coverage
```

**Structure Decision**: Keep single-project structure; add one narrowly scoped service module for continuity persistence instead of broader architectural refactor.

## Phase 0: Outline & Research

Research outcomes are captured in [research.md](./research.md) and resolve the core unknowns:
- Canonical max-6 car identity under mixed hardware slot semantics
- Reconnect/restart lap continuity and race-state persistence
- Probe-driven link stabilization vs periodic forced reconnect

## Phase 1: Design & Contracts

### Data Model

Runtime and persistence entities are documented in [data-model.md](./data-model.md), including:
- `CarSlotMapping`
- `ActiveCarSet`
- `LiveLapCheckpoint`
- `LinkHealthState`

### Interface Contracts

Behavioral contract for normalization, persistence, reconnect policy, and config knobs is documented in [contracts/live-reliability-hardening.md](./contracts/live-reliability-hardening.md).

### Quickstart

Operator/developer verification flow is documented in [quickstart.md](./quickstart.md).

### Agent Context Update

Updated SPECKIT plan pointer in `.github/copilot-instructions.md` to this plan path:
`specs/003-live-adapter-carreralib/plan.md`.

## Constitution Check (Post-Design)

Re-evaluated after research + design artifacts: PASS.

- Minimal-change gate: PASS (incremental hardening, no architecture replacement)
- Backward-compat gate: PASS (new behavior constrained to live mode pathways)
- Test gate: PASS (new tests mandated before merge)

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Additional persistence entity for checkpoints | Needed to preserve lap continuity across reconnect/restart | In-memory-only state loses continuity on adapter recreation/process restart |

## Phase 2: Task Planning Endpoint

Planning stops at design artifacts by intent. Task decomposition follows in `tasks.md` (`speckit.tasks`).
