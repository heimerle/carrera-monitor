# Implementation Plan: Calm Connection UI + Restore Race Metrics

**Branch**: `006-calm-connection-ui-restore-race-metrics` | **Date**: 2026-05-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-calm-connection-ui-restore-race-metrics/spec.md`

## Summary

This feature removes noisy connection text from the dashboard header, restores always-visible race metrics, and keeps the dashboard stable under reconnect churn. The implementation keeps existing architecture intact by extending snapshot assembly and rendering paths. Clarification A is applied as a planning constraint: race-metric updates must become visible no later than 1 second after telemetry ingestion.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Streamlit, Pydantic, SQLAlchemy, asyncio runtime services  
**Storage**: Local SQLite for race metadata plus JSON state snapshot file (`logs/state.json`)  
**Testing**: pytest, ruff, mypy  
**Target Platform**: macOS/Linux desktop runtime  
**Project Type**: Single Python application (telemetry runtime + Streamlit UI)  
**Performance Goals**: Dashboard reflects telemetry-derived metric changes within 1 second of ingestion  
**Constraints**: Backward-compatible additive changes, no unrelated architecture refactor, robust behavior for malformed/partial telemetry  
**Scale/Scope**: Up to 6 rendered cars per race dashboard, continuous live telemetry stream

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file at `.specify/memory/constitution.md` still contains placeholders and therefore no enforceable project-specific principles. For this plan, gates are derived from repository governance (`.github/copilot-instructions.md`) and feature constraints.

Pre-Phase 0 gate review:
- Gate A - Minimal change scope: PASS (dashboard/state/normalization only)
- Gate B - Backward compatibility: PASS (additive snapshot and rendering behavior)
- Gate C - Test coverage for behavior changes: PASS (explicit FR-driven regression coverage)
- Gate D - Operational safety: PASS (malformed telemetry must degrade safely)

Post-Phase 1 gate review:
- Research, data model, contract, and quickstart remain consistent with all gates.
- No gate violations require complexity exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/006-calm-connection-ui-restore-race-metrics/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── dashboard-race-metrics-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── dashboard.py
├── state_manager.py
├── event_model.py
├── carrera_client.py
├── telemetry_processor.py
└── services/
    ├── race_service.py
    └── bluetooth_connection_supervisor.py

tests/
├── conftest.py
├── test_dashboard_metrics.py
├── test_state_manager.py
├── test_live_translation.py
├── test_event_model.py
└── fixtures/
    ├── dashboard_state_no_race.json
    └── dashboard_state_active_race.json
```

**Structure Decision**: Keep the current single-project Python layout. Implement via targeted changes in `src/dashboard.py`, `src/state_manager.py`, `src/event_model.py`, `src/carrera_client.py`, and `src/services/race_service.py` plus focused regression tests in `tests/`.

## Complexity Tracking

No constitution exceptions or complexity justifications are required for this feature.
