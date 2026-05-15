# Implementation Plan: Carrera Digital Telemetry Dashboard MVP

**Branch**: `main` | **Date**: 2026-05-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/main/spec.md`

## Summary

Build a modular, async-first Python pipeline that ingests Carrera DIGITAL 124/132 telemetry via `carreralib` (or a fully equivalent mock generator), normalizes every signal into a single canonical Pydantic `TelemetryEvent`, fans it out over an in-process async event bus to (a) a state manager, (b) an append-only JSONL storage writer, and (c) a Streamlit dashboard that reads an atomic state snapshot file. The architecture is explicitly seamed so future consumers (replay, websockets, REST, analytics, OBS overlay) can attach without modifying core code. Mock mode is a first-class subsystem — the project must be fully usable without any BLE hardware.

## Technical Context

**Language/Version**: Python 3.11+ (asyncio-first; `from __future__ import annotations` everywhere)  
**Primary Dependencies**: `carreralib` (live mode only, lazy-imported), `streamlit`, `pydantic` v2, `pyyaml`; optional `rich`, `loguru`, `pandas`  
**Storage**: Filesystem only — append-only JSONL event log + atomic `state.json` snapshot + optional lap CSV; no database in MVP  
**Testing**: `pytest`, `pytest-asyncio`; coverage for event model, storage writer, mock generator, state manager, and adapter contract  
**Target Platform**: Single-user developer workstation (macOS / Linux / Windows), fully offline-capable  
**Project Type**: CLI + local dashboard (single-project Python package, two run-time processes: pipeline + Streamlit)  
**Performance Goals**: Sustain 6 cars × ~10 Hz telemetry (≈60 events/s) with <50 ms p95 ingest-to-disk latency on a modern laptop; dashboard refresh 1 Hz default (500–2000 ms configurable)  
**Constraints**: No network dependencies at runtime; no required cloud services; dashboard must not import `carreralib` or BLE code (FR-024); never silently swallow exceptions (FR-033)  
**Scale/Scope**: 1–6 cars, single-process pipeline, single-machine dashboard, hours-long sessions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution at `.specify/memory/constitution.md` is currently a template (placeholders not yet ratified). No principles are in force yet, so no constitutional violations can be raised. As a precaution, this plan self-imposes the principles explicitly called out by the feature spec, which a future ratified constitution is expected to formalize:

- **Modularity & seams**: every cross-component boundary is a Pydantic model or a Protocol; no direct `carreralib` references outside `src/carrera_client.py`. Enforced by R-001, R-008.
- **Observability**: structured JSON logs on stderr + JSONL event log on disk + atomic state snapshot. Enforced by FR-032, [contracts/event-log.md](./contracts/event-log.md), [contracts/state-snapshot.md](./contracts/state-snapshot.md).
- **Testability**: every non-trivial unit (event model, storage, mock, state manager, adapter contract) has dedicated pytest coverage. Enforced by FR-034 and the adapter-contract test obligation.
- **Simplicity / YAGNI**: no broker, no DB, no web server beyond Streamlit; replay, websockets, REST, sniffer, analytics are explicit *future* seams not implemented in MVP (R-009).
- **Fail loudly**: no bare `except`; every failure path is either typed-raised or logged with full context (FR-033).

**Re-check after Phase 1 design**: no new violations introduced; all extension points (R-008) are described in docs and require no speculative code in MVP. Gate passes.

> If `/speckit.constitution` is run later to ratify a real constitution that conflicts with the above, this gate must be re-evaluated and Complexity Tracking populated.

## Project Structure

### Documentation (this feature)

```text
specs/main/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   ├── cli.md
│   ├── event-log.md
│   ├── state-snapshot.md
│   └── carrera-adapter.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
carrera-monitor/
├── README.md
├── requirements.txt
├── pyproject.toml
├── config.example.yaml
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI entry, asyncio runtime, orchestration
│   ├── config.py               # Pydantic AppConfig + YAML loader
│   ├── event_model.py          # TelemetryEvent, EventType, RaceState, ConnectionState
│   ├── event_bus.py            # async pub/sub with bounded per-subscriber queues
│   ├── carrera_client.py       # CarreraAdapter Protocol + carreralib-backed impl + translation
│   ├── mock_client.py          # CarreraAdapter Protocol mock impl
│   ├── storage.py              # JSONL writer + optional CSV lap writer
│   ├── state_manager.py        # CarState/RaceState aggregation + StateSnapshot + atomic write
│   ├── telemetry_processor.py  # per-event derivations (e.g., best-lap helpers)
│   ├── dashboard.py            # Streamlit app (read-only consumer of state.json + JSONL tail)
│   └── utils.py                # time helpers, atomic-write helper, structured log setup
├── logs/                       # created at runtime; gitignored
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_event_model.py
│   ├── test_storage.py
│   ├── test_mock_client.py
│   ├── test_state_manager.py
│   └── test_adapter_contract.py  # shared contract test, runs against both mock and live adapter
├── docs/
│   ├── architecture.md         # diagram + extension seams (R-008)
│   └── troubleshooting.md
└── .github/                    # speckit + (optional) CI workflows; add to .gitignore for credential safety
```

**Structure Decision**: Single Python package under `src/` (Option 1 from the template, "Single project"). The dashboard is a Streamlit script inside the same package but is run as a separate process; the only cross-process coupling is the atomic state snapshot file documented in `contracts/state-snapshot.md`. `main.py` orchestrates the async pipeline and (unless `--no-dashboard`) launches Streamlit as a subprocess so the hobbyist sees a single command.

## Complexity Tracking

> No constitution violations (constitution not yet ratified). Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | _(n/a)_ | _(n/a)_ |
