# Implementation Plan: Calm Connection UI + Restore Race Metrics

**Branch**: `006-calm-connection-ui-restore-race-metrics` | **Date**: 2026-05-16 | **Spec**: `/specs/006-calm-connection-ui-restore-race-metrics/spec.md`
**Input**: Feature specification from `/specs/006-calm-connection-ui-restore-race-metrics/spec.md`

## Summary

This fix removes noisy connection text from the dashboard header in favor of a deterministic icon-only indicator, while restoring always-visible race metrics backed by a stable dashboard snapshot model. The technical approach is to keep rendering stable (never hide the metrics section), normalize mixed lap event payload variants into one pipeline, and surface deep diagnostics only in collapsed debug panels.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Streamlit, Pydantic, SQLAlchemy, asyncio runtime services  
**Storage**: Local SQLite (race data) plus JSON state snapshot file (`logs/state.json`)  
**Testing**: pytest, ruff, mypy  
**Target Platform**: macOS/Linux desktop runtime (local Streamlit dashboard)
**Project Type**: Single Python application (telemetry ingestion + Streamlit UI)  
**Performance Goals**: Dashboard remains responsive and updates race metrics within one refresh cycle after telemetry events  
**Constraints**: Backward compatible additive changes; no unrelated architecture refactor; robust against malformed/partial telemetry  
**Scale/Scope**: Up to 6 actively rendered cars per race dashboard, continuous live telemetry stream

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file at `.specify/memory/constitution.md` currently contains template placeholders without enforceable project-specific principles. For this plan, compliance gates are derived from repository instructions (`.github/copilot-instructions.md`) and current engineering constraints.

Pre-Phase 0 gate review:
- Gate A - Minimal Change Scope: PASS (fix is constrained to connection header UX plus race metric restoration path)
- Gate B - Backward Compatibility: PASS (additive snapshot/render normalization, no breaking API intent)
- Gate C - Test Coverage for Behavior Changes: PASS (explicit test additions required in spec)
- Gate D - Operational Safety: PASS (malformed telemetry must degrade gracefully, not crash dashboard)

Post-Phase 1 re-check:
- Research, data model, contracts, and quickstart artifacts keep all gates in PASS state.
- No gate violations require complexity exception handling.

## Project Structure

### Documentation (this feature)

```text
specs/006-calm-connection-ui-restore-race-metrics/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── dashboard-race-metrics-contract.md
```

### Source Code (repository root)

```text
src/
├── dashboard.py
├── state_manager.py
├── event_model.py
├── telemetry_processor.py
├── pages/
│   └── race_management.py
└── services/
    ├── bluetooth_connection_supervisor.py
    └── race_service.py

tests/
├── test_state_manager.py
├── test_live_translation.py
├── test_bluetooth_connection_supervisor.py
└── test_app_streamlit_launch.py
```

**Structure Decision**: Keep the existing single-project Python layout. Implement this feature via targeted updates to dashboard rendering (`src/dashboard.py`), snapshot/state assembly (`src/state_manager.py` and related models), telemetry normalization paths, and focused regression tests under `tests/`.

## Complexity Tracking

No constitution violations or complexity exceptions were identified for this feature plan.
