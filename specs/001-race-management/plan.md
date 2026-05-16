# Implementation Plan: Race Management Module

**Branch**: `001-race-management` | **Date**: 2026-05-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-race-management/spec.md`

## Summary

Extend the existing Carrera telemetry pipeline with a relational race-management layer: SQLAlchemy 2.x + SQLite, Pydantic DTOs, a repository + service split (`RaceRepository`, `RaceService`, `ReportingService`), and three new Streamlit pages (`Race Management`, `Race Reports`, `Settings`) wired through `st.navigation`. A new `ActiveRaceContext` mediates between the existing `EventBus` and the database: when a race is `running`, `lap`-typed `TelemetryEvent`s are written to `race_laps`; optionally all events are mirrored to `race_events`. The existing live dashboard, event model, bus, and storage writers stay unchanged — race persistence is an **additional subscriber** to the same bus, not a rewrite. Repeat-race copies only configuration + drivers; lifecycle is a strict state machine; reports are pure functions over persisted rows.

## Technical Context

**Language/Version**: Python 3.11+ (asyncio-first; `from __future__ import annotations`).
**Primary Dependencies**: existing — `pydantic` v2, `streamlit` ≥1.30, `pyyaml`, `carreralib` (live mode); **new** — `SQLAlchemy` ≥2.0 (sync `Session` API, declarative), built-in `sqlite3`. Optional `alembic` deferred.
**Storage**: SQLite file at `./data/carrera_dashboard.sqlite3` (configurable via `database.url`); JSONL telemetry log (existing) untouched.
**Testing**: `pytest`, `pytest-asyncio` (existing). New unit tests use an in-memory SQLite (`sqlite:///:memory:`) with `StaticPool` so each test gets an isolated `Session`.
**Target Platform**: Single-user developer workstation (macOS / Linux / Windows). No daemon, no server, no cloud.
**Project Type**: CLI + local dashboard (unchanged); race management is a sub-module of the same single Python package.
**Performance Goals**: ≤500 ms wall time for race-summary report on ≤1,000 laps (SC-105); writes must not regress the existing 60 events/s / <50 ms p95 ingest-to-disk envelope (SC-106).
**Constraints**: No network at runtime; no SQLAlchemy imports inside `src/dashboard.py` or `src/pages/*` (only via services); telemetry pipeline must never crash on DB errors (FR-121); concurrent reads from Streamlit and writes from the telemetry task must use separate sessions and a connection pool that tolerates concurrency.
**Scale/Scope**: ≤6 cars per race; race sessions of up to ~2 hours / ~1,000 laps; up to a few thousand persisted races in the local DB before pruning becomes interesting.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution at `.specify/memory/constitution.md` is still an unratified template (placeholders only). No principles are in force, so no constitutional violation can be raised. As in the MVP plan, this plan self-imposes the principles the spec explicitly relies on:

- **Modularity & seams** — SQLAlchemy lives in `src/database.py` + `src/models.py` only; repositories own queries; services own business rules; Streamlit pages call services. No ORM in UI files (FR-130, FR-131, FR-133). The telemetry pipeline integrates via a new `EventBus` subscriber — no edits to `event_bus.py` / `event_model.py` semantics.
- **Observability** — every lifecycle transition (`start`, `pause`, `resume`, `finish`, `cancel`, `auto-finish`) emits a structured log + a `connection_state`-style event into `race_events` (when persistence enabled).
- **Testability** — each service method is independently unit-testable against an in-memory SQLite; lap-ingest is contract-tested with a stubbed telemetry stream.
- **Simplicity / YAGNI** — no Alembic in v1 (`Base.metadata.create_all()` suffices for an evolving local DB); no async ORM; no FastAPI / REST; no multi-user concerns.
- **Fail loudly** — every caught DB exception logs structurally and either re-raises a typed `RaceServiceError` to the caller or, at the ingest boundary, is logged-and-dropped (FR-121).

**Re-check after Phase 1 design**: no violations introduced; sync SQLAlchemy + a single bounded session-per-task is the simplest design that still tolerates Streamlit's threaded read pattern. Gate passes. No entry needed in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-race-management/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   ├── race-service.md
│   ├── reporting-service.md
│   └── database-schema.md
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created here)
```

### Source Code (repository root)

```text
carrera-monitor/
├── src/
│   ├── (existing: main.py, config.py, event_model.py, event_bus.py,
│   │    carrera_client.py, mock_client.py, storage.py, state_manager.py,
│   │    telemetry_processor.py, dashboard.py, utils.py)
│   ├── database.py                 # NEW — engine, SessionLocal, Base, init_db()
│   ├── models.py                   # NEW — ORM models (Race, RaceDriver, RaceLap, RaceEvent, RaceReport)
│   ├── race_context.py             # NEW — ActiveRaceContext (in-memory pointer + thread-safe accessors)
│   ├── race_runner.py              # NEW — EventBus subscriber that writes laps/events via RaceService
│   ├── schemas/
│   │   ├── __init__.py             # NEW
│   │   └── race_schema.py          # NEW — Pydantic DTOs (RaceCreate, RaceUpdate, RaceRead, ReportPayloads)
│   ├── repositories/
│   │   ├── __init__.py             # NEW
│   │   └── race_repository.py      # NEW — SQLAlchemy queries (CRUD + list + repeat-copy)
│   ├── services/
│   │   ├── __init__.py             # NEW
│   │   ├── race_service.py         # NEW — lifecycle, validation, telemetry ingest
│   │   └── reporting_service.py    # NEW — summary/driver-stats/standings/save_report/csv export
│   └── pages/
│       ├── __init__.py             # NEW
│       ├── race_management.py      # NEW — list/create/edit/repeat/lifecycle
│       └── race_reports.py         # NEW — render reports, save, CSV export
├── data/                           # NEW — gitignored except .gitkeep
│   └── .gitkeep
├── tests/
│   ├── (existing 52 tests)              # pre-001 baseline; total drifts as later slices land (see CI on `main`)
│   ├── test_race_repository.py     # NEW
│   ├── test_race_service.py        # NEW
│   ├── test_reporting_service.py   # NEW
│   ├── test_repeat_race.py         # NEW
│   ├── test_race_runner.py         # NEW — telemetry-ingest behavior
│   └── conftest.py                 # extend with `db_session`, `engine`, `race_factory` fixtures
├── config.example.yaml             # add database + race_management sections
└── README.md                       # extend with race-management quickstart
```

**Structure Decision**: Single project (existing layout). Race management is layered on top via four new top-level modules (`database`, `models`, `race_context`, `race_runner`), plus three subpackages (`schemas/`, `repositories/`, `services/`), plus a `pages/` subpackage for the new Streamlit views. The existing `src/dashboard.py` stays as the "Dashboard" tab content; a small router at the top of `dashboard.py` (or a new `src/app.py` entry point) wires `st.navigation` to the four pages.

## Phase 0 — Research

See [research.md](./research.md). Resolves: (1) SQLAlchemy 2.x session pattern for a mixed Streamlit-read / async-task-write workload, (2) SQLite concurrency settings (WAL mode + `check_same_thread=False`), (3) whether to use Alembic in v1, (4) how `MockCarreraAdapter`'s `lap` events expose `lap_time_ms` (already covered by `event_model.py`'s `lap` payload schema), (5) Streamlit multi-page navigation strategy on Streamlit ≥1.30, (6) repeat-race copy semantics (deep vs shallow on JSON columns — N/A since we copy zero JSON), (7) testing strategy for in-memory SQLite shared across two threads/tasks.

## Phase 1 — Design & Contracts

### Outputs

- [data-model.md](./data-model.md) — ER diagram, table-level schema (columns, types, constraints, indices), Pydantic DTOs, and state-machine table for `Race.status`.
- [contracts/race-service.md](./contracts/race-service.md) — full method signatures + pre/post-conditions for `RaceService`.
- [contracts/reporting-service.md](./contracts/reporting-service.md) — method signatures + report payload shapes.
- [contracts/database-schema.md](./contracts/database-schema.md) — exact `CREATE TABLE` shapes (informational; produced by `create_all()` at runtime).
- [quickstart.md](./quickstart.md) — copy-pasteable steps to install, run mock + new pages, create + run + repeat + report a race.

### Agent context update

The `<!-- SPECKIT START --><!-- SPECKIT END -->` block in [.github/copilot-instructions.md](../../.github/copilot-instructions.md) is repointed to this plan: `specs/001-race-management/plan.md`.

### Constitution Re-Check (post-design)

No new gates triggered. Sync SQLAlchemy + sync repositories accept events from an async pipeline by hopping through `loop.run_in_executor(None, …)` inside the subscriber task — the single concession to mixing sync ORM with asyncio. This is justified because (a) Streamlit itself is sync, so the ORM must be sync to share sessions with UI reads; (b) `aiosqlite` does not solve the Streamlit half. The blocking-window per write is sub-millisecond on SQLite WAL, well under the existing batch-flush budget of 250 ms.

## Phase 2 — Tasks (deferred)

`tasks.md` is generated by `/speckit.tasks` once this plan is reviewed. Phase 2 is intentionally NOT created here.

## Complexity Tracking

*(empty — no constitutional violations to justify; sync-ORM-with-async-pipeline is documented above as a one-line, well-bounded concession.)*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| — | — | — |
