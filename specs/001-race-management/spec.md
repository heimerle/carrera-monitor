# Feature Specification: Race Management Module

**Feature Branch**: `001-race-management`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "Add a race management module that allows users to create, configure, store, repeat, run, and report Carrera DIGITAL races, persisted in a local database, on top of the existing telemetry dashboard."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Create, Run & Persist a Race (Priority: P1) 🎯 MVP

A user opens the Streamlit app, creates a race (name, mode, lap target *or* duration, 1–6 drivers with names per car ID), starts it, drives a session with mock or live telemetry, and finishes it. The race configuration, lap rows, driver assignments, and timestamps are persisted to a local SQLite database.

**Why this priority**: Without persistence and a lifecycle, the dashboard cannot describe a "race" — only a continuous telemetry stream. This story stands up the database, the service layer, and the minimum UI to operate a race end-to-end. Reports and repeat-race are useless without it.

**Independent Test**: Launch the app, create a `fixed_laps=10`, 2-driver race, start it, let the mock pipeline run, finish it. Verify a `races` row exists with `status = "finished"`, `race_drivers` has 2 rows, the leader has exactly 10 `race_laps` rows (the trailing car may have ≤10), and `started_at` / `finished_at` are populated.

**Acceptance Scenarios**:

1. **Given** the user is on the Race Management page, **When** they submit a valid race form with mode `fixed_laps`, `lap_target = 10`, and 3 drivers, **Then** a new race is stored in SQLite with `status = "draft"` and exactly 3 `RaceDriver` rows are linked.
2. **Given** a draft race exists, **When** the user clicks "Start", **Then** `status` becomes `running`, `started_at` is set, and the race becomes the active race context for telemetry.
3. **Given** a running race and a `lap` telemetry event arrives for a configured `car_id`, **When** the event is dispatched on the bus, **Then** a `RaceLap` row is inserted with `race_id`, `car_id`, `driver_name`, `lap_number`, `lap_time_ms`, and ISO timestamp.
4. **Given** a running `fixed_laps` race, **When** the **leader** has completed `lap_target` laps **OR** the user clicks "Finish", **Then** `status` becomes `finished` and `finished_at` is set.
5. **Given** a non-running race, **When** lap telemetry arrives, **Then** no `RaceLap` rows are written (telemetry continues to render in the live dashboard regardless).

---

### User Story 2 — Repeat a Previous Race (Priority: P2)

A user picks a past race from the list and clicks "Repeat". A new race is created as a draft with the original configuration and driver-to-car assignments copied, but with a fresh ID, fresh timestamps, and **no** laps, events, or reports.

**Why this priority**: Repeating is the most-requested race-management quality-of-life feature once a single race works. It is independently demonstrable but only meaningful after US1 has produced at least one race.

**Independent Test**: After completing a race in US1, click "Repeat" on its row. Verify the new race has `status = "draft"`, `source_race_id` set to the source, identical `mode` / `lap_target` / `duration_seconds` / `driver_count` / `notes`, identical driver names per `car_id`, and **zero** `RaceLap` / `RaceEvent` / `RaceReport` rows.

**Acceptance Scenarios**:

1. **Given** a finished race `R1`, **When** the user clicks "Repeat" on `R1`, **Then** a new race `R2` is created with `status = "draft"`, `source_race_id = R1.id`, and the same configuration and driver names.
2. **Given** `R1` had 200 lap rows, **When** `R2` is created via Repeat, **Then** `R2` has zero rows in `race_laps`, `race_events`, and `race_reports`.
3. **Given** `R2` is started and finished, **When** the user inspects `R1`, **Then** `R1`'s laps and reports are unchanged.

---

### User Story 3 — Race Reports (Priority: P3)

A user opens the Race Reports page for a finished race and sees: race metadata, per-driver statistics (laps, best, average, last lap, race time, pit count, fuel summary), and final standings. The user can save the report (it is persisted to `race_reports` as JSON) and optionally export laps as CSV.

**Why this priority**: Reports are valuable but only after races can be created, run, and finished. Generation logic depends entirely on US1's persisted lap rows.

**Independent Test**: For a finished race with ≥3 cars and ≥5 laps each, click "Generate report". Verify the UI shows the three required tables (summary / driver stats / standings), and a `race_reports` row with `report_type = "race_summary"` and a JSON payload is created.

**Acceptance Scenarios**:

1. **Given** a finished race with persisted laps, **When** "Generate race summary" is invoked, **Then** the rendered report shows race name, mode, start/finish/duration, driver list, and final standings sorted by `(lap_count desc, total_race_time_ms asc, best_lap_ms asc)`.
2. **Given** a generated report, **When** the user clicks "Save report", **Then** a `RaceReport` row is created with the JSON payload and a `created_at` timestamp.
3. **Given** a finished race, **When** the user requests "Export laps CSV", **Then** a CSV with rows `car_id, driver_name, lap_number, lap_time_ms, timestamp_iso` is downloaded. The user MUST also be able to request "Export summary CSV" to download the per-driver final-standings CSV defined in FR-126(b).

---

### Edge Cases

- User selects mode `fixed_laps` and submits the form without a `lap_target` → form rejects with a validation error; nothing is written.
- User selects 4 drivers but leaves name for car 3 empty → form rejects; the only valid empty driver slot is for car IDs beyond `driver_count`.
- Two cars finish on the same lap with the same best lap time → standings sort uses `(lap_count desc, best_lap_ms asc, latest_lap_timestamp asc)` and is deterministic.
- A `lap` telemetry event arrives for a `car_id` not configured in the active race (e.g., `car_id = 5` when `driver_count = 3`) → event is logged at WARN level and **dropped**; not persisted to `race_laps`.
- A `lap` event arrives while race is `paused` → it is **not** persisted to `race_laps`, but is still surfaced on the live dashboard.
- User starts a new race while another race is `running` → the previous race is auto-paused with a structured warning; only one race is active at a time per process.
- SQLite file is missing or `data/` directory does not exist → the database layer creates them automatically on startup.
- User edits a race that is not in `draft` state → blocked at the service layer with a typed error (`RaceNotEditableError`), unless `race_management.allow_edit_running_race` is true.
- Database error during `record_lap()` → exception is logged structurally; the telemetry pipeline does not crash and the live dashboard continues to function.
- "Repeat" pressed on a `draft` race → allowed; produces a sibling draft with the same `source_race_id`.

## Requirements *(mandatory)*

### Functional Requirements

#### Race Configuration

- **FR-101**: System MUST allow creating a race with: `name`, `mode` (`fixed_laps` | `fixed_duration`), optional `lap_target`, optional `duration_seconds`, optional `duration_unit` (`minutes` | `hours`), `driver_count` in `1..6`, driver names per car ID `1..driver_count`, and optional `notes`.
- **FR-102**: System MUST reject a race where `mode = "fixed_laps"` and `lap_target` is not a positive integer.
- **FR-103**: System MUST reject a race where `mode = "fixed_duration"` and `duration_seconds` is not a positive integer (computed from `duration_value` × unit).
- **FR-104**: System MUST reject a race whose driver-name list does not have exactly `driver_count` non-empty names, each bound to a unique `car_id` in `1..6`.
- **FR-105**: System MUST reject a race whose `name` is empty / whitespace-only.

#### Race Lifecycle

- **FR-106**: System MUST support the race-status transitions `draft → ready → running → paused → running → finished` and the abort branch `* → cancelled` (where `*` is any non-terminal state).
- **FR-107**: System MUST allow editing a race only while in `draft` (or `ready`) status, unless `race_management.allow_edit_running_race` is true.
- **FR-108**: System MUST set `started_at` on first `start_race()` call and `finished_at` on `finish_race()` / `cancel_race()`.
- **FR-109**: System MUST auto-finish a `running` race when (a) `fixed_laps`: the configured `lap_target` is reached by the leader, or (b) `fixed_duration`: `started_at + duration_seconds` has elapsed.
- **FR-110**: System MUST allow at most one race in `running` state per process; starting a new race while another is `running` MUST auto-pause the previous one with a structured warning.

#### Repeat

- **FR-111**: System MUST provide a `repeat_race(race_id)` operation that creates a new race with `status = default_race_status_after_create`, `source_race_id = race_id`, and copies **only** `name`, `mode`, `lap_target`, `duration_seconds`, `driver_count`, `notes`, and the `RaceDriver` rows.
- **FR-112**: The repeated race MUST NOT carry over any rows from `race_laps`, `race_events`, or `race_reports`.

#### Persistence

- **FR-113**: System MUST persist races, drivers, laps, events, and reports to a relational store (SQLite by default at `./data/carrera_dashboard.sqlite3`).
- **FR-114**: System MUST expose configuration `database.url` for overriding the SQLAlchemy connection string.
- **FR-115**: System MUST create the database file and parent directory automatically on first run.
- **FR-116**: System MUST use relational columns for core race/driver/lap fields and JSON payload columns only for flexible event and report payloads.

#### Telemetry Integration

- **FR-117**: System MUST associate `lap` `TelemetryEvent`s with the currently active race (if any) and create one `RaceLap` row per accepted `lap` event.
- **FR-118**: System MUST optionally persist every normalized `TelemetryEvent` as a `RaceEvent` row when `race_management.persist_all_events = true`; otherwise only race-relevant types (`lap`, `race_state`, `pitlane`, `fuel`, `connection_state`) are persisted.
- **FR-119**: System MUST drop and structurally log lap events whose `car_id` is not in the active race's driver assignments.
- **FR-120**: System MUST NOT write to the database when no race is `running`.
- **FR-121**: Database write failures during ingest MUST be caught at the service boundary, logged structurally, and MUST NOT crash the telemetry pipeline (extends FR-018 / FR-033 from the MVP spec).

#### Reporting

- **FR-122**: System MUST provide a `generate_race_summary(race_id)` that returns race metadata, start / finish / duration, drivers, and final standings.
- **FR-123**: System MUST provide `generate_driver_stats(race_id)` that returns, per driver: total laps, best lap, average lap, last lap, total race time, optional pit count, optional fuel summary.
- **FR-124**: System MUST provide `generate_final_standings(race_id)` that returns drivers sorted by `(lap_count desc, total_race_time_ms asc, best_lap_ms asc)`. Ties beyond `best_lap_ms` are broken by `car_id asc` for determinism.
- **FR-125**: System MUST provide `save_report(race_id, report_type, payload)` that inserts a `RaceReport` row.
- **FR-126**: System MUST offer two CSV exports for a finished race: (a) a **per-lap** export of `race_laps` with columns `car_id, driver_name, lap_number, lap_time_ms, timestamp_iso`, and (b) a **per-driver summary** export of final standings with columns `position, car_id, driver_name, lap_count, best_lap_ms, gap_to_leader_ms, laps_behind, total_race_time_ms, average_lap_ms, pit_count`.

#### UI / Navigation

- **FR-127**: System MUST present four top-level Streamlit views: Dashboard, Race Management, Race Reports, Settings (sidebar or `st.navigation`).
- **FR-128**: Race Management page MUST support listing races, creating a race, editing a draft, viewing details, repeating, and triggering lifecycle actions (start / pause / resume / finish / cancel).
- **FR-129**: Race-running view MUST show name, status, mode, progress (laps-vs-target or elapsed-vs-duration), and a driver table (car ID, driver name, lap count, latest lap, best lap, position).
- **FR-130**: Streamlit pages MUST NOT import SQLAlchemy models directly; they MUST go through services / repositories.

#### Architecture

- **FR-131**: System MUST place SQLAlchemy session management in `src/database.py` and ORM models in `src/models.py`.
- **FR-132**: System MUST provide Pydantic DTOs for race configuration and report payloads in `src/schemas/race_schema.py`.
- **FR-133**: System MUST place repository code (queries) in `src/repositories/race_repository.py` and business logic in `src/services/race_service.py` and `src/services/reporting_service.py`.
- **FR-134**: System MUST NOT break or regress any existing test in `tests/` (52 passing as of MVP).
- **FR-135**: Carrera-telemetry event mappings that depend on real hardware MUST be marked with `# TODO(hardware): …` comments where they cross the live `carreralib` boundary (consistent with the existing R-001 rule).

### Key Entities *(data)*

- **Race**: A configured racing session. Holds name, mode, lap target *or* duration in seconds, driver count, status, optional notes, optional `source_race_id` pointer (Repeat), and lifecycle timestamps (created/updated/started/finished).
- **RaceDriver**: Assignment of a driver name to a `car_id` (1..6) within one race. Unique on `(race_id, car_id)`.
- **RaceLap**: One completed lap by one car in one race: `lap_number`, `lap_time_ms`, ISO timestamp. Append-only.
- **RaceEvent**: A normalized `TelemetryEvent` persisted under a race for replay/analytics, with flexible JSON payload.
- **RaceReport**: A generated report payload (JSON) attached to a race: `report_type`, `payload_json`, `created_at`.
- **ActiveRaceContext**: In-memory pointer (held by `RaceService` / `StateManager`) identifying which race, if any, is currently `running` and so eligible to receive lap writes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: A user can create a fixed-laps race with 3 drivers, run it through 10 simulated laps with mock telemetry, and finish it — end-to-end in under 3 minutes from a fresh checkout.
- **SC-102**: 100% of `lap` events emitted by `MockCarreraAdapter` while a race is `running` and whose `car_id` is within the active driver set produce exactly one `RaceLap` row (no duplicates, no drops).
- **SC-103**: A repeated race contains zero rows in `race_laps`, `race_events`, and `race_reports`, and the same configuration + driver names as its source (verified by a dedicated test).
- **SC-104**: Existing test suite (52 tests) remains green; new race-management tests (≥ the eight listed in §10 of the request) all pass on the same CI matrix.
- **SC-105**: Generating a race-summary report for a finished race takes < 500 ms wall time for sessions up to 1,000 lap rows.
- **SC-106**: Telemetry pipeline performance (FR-022 of MVP: ~60 events/s, <50 ms p95 ingest-to-disk) remains unaffected — measured by re-running the existing storage benchmark with race persistence enabled.
- **SC-107**: A database write error during `record_lap()` does not crash the pipeline; verified by a fault-injection test.

## Assumptions

- Default storage is SQLite on the local filesystem; multi-user / multi-host scenarios are out of scope for this feature.
- Alembic migrations are deferred — the MVP uses `Base.metadata.create_all()` against a versioned schema; a follow-up may introduce Alembic when schema changes are needed.
- "Position" in the driver table is computed live from `(lap_count desc, best_lap_ms asc)` — there is no sector-timing or actual track position available from `carreralib`.
- Pit count and fuel summary depend on `pitlane` / `fuel` events being emitted (already covered by the existing event model); both fields are nullable in the report payload.
- Race start does not auto-start the mock/live adapter — telemetry source is independent and may already be running.
- The existing four event types relevant to a race (`lap`, `pitlane`, `fuel`, `race_state`) are sufficient; deeper sector/checkpoint data is out of scope for v1.
- Only one race can be `running` per Python process; multi-process race control is out of scope.
- The existing dashboard view at `src/dashboard.py` is preserved as the "Dashboard" tab; new pages live in `src/pages/`.
