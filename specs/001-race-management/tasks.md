# Tasks: Race Management Module

**Feature Branch**: `001-race-management` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Input**: Design documents in `specs/001-race-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Test tasks are included because the spec explicitly requires preserving the existing 52 tests (FR-134) and adding tests for each new layer (FR-132, "Add unit tests for race service, repository, lifecycle, repeat-race semantics").

**Organization**: Tasks are grouped by user story to enable independent implementation, testing, and incremental delivery.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on other in-progress tasks)
- **[Story]**: Story tag for user-story phases (US1, US2, US3); omitted in Setup / Foundational / Polish
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project-wide preparation for the new module.

- [X] T001 Add `SQLAlchemy>=2.0,<3` to [requirements.txt](requirements.txt) and (if present) [pyproject.toml](pyproject.toml) dependencies; verify install with `pip install -e ".[dev]"`
- [X] T002 Create the runtime data directory: add [data/.gitkeep](data/.gitkeep) and append `data/*.sqlite3` and `data/*.sqlite3-*` to [.gitignore](.gitignore) while keeping `!data/.gitkeep`
- [X] T003 [P] Extend [config.example.yaml](config.example.yaml) with the new top-level `database:` and `race_management:` sections per [data-model.md §5](specs/001-race-management/data-model.md)
- [X] T004 [P] Add `DatabaseConfig` and `RaceManagementConfig` Pydantic submodels plus the `database` and `race_management` fields to `AppConfig` in [src/config.py](src/config.py); ensure backward compatibility (default factories) so existing 52 tests still load configs with no DB section

**Checkpoint**: dependencies installed; config supports new sections; `data/` exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database engine, ORM models, schemas, and the active-race singleton. These MUST be complete before any user-story phase begins because every story imports from them.

**⚠️ CRITICAL**: No user-story work may start until this phase is checkpointed.

- [X] T005 Create [src/database.py](src/database.py): expose `Base = declarative_base()`, `engine = create_engine(config.database.url, connect_args={"check_same_thread": False, "timeout": 5.0}, echo=config.database.echo)`, `SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)`, an `@event.listens_for(engine, "connect")` hook that issues the WAL/synchronous/foreign_keys pragmas (see [contracts/database-schema.md](specs/001-race-management/contracts/database-schema.md)), and an `init_db()` function that creates the parent directory if missing and calls `Base.metadata.create_all(engine)`
- [X] T006 Create [src/models.py](src/models.py) with SQLAlchemy 2.x `Mapped[]` declarative models for `Race`, `RaceDriver`, `RaceLap`, `RaceEvent`, `RaceReport` exactly per [data-model.md §2](specs/001-race-management/data-model.md) and [contracts/database-schema.md](specs/001-race-management/contracts/database-schema.md) (columns, types, CHECK constraints, UNIQUE constraints, FK cascades, indices, relationships)
- [X] T007 [P] Create [src/schemas/__init__.py](src/schemas/__init__.py) and [src/schemas/race_schema.py](src/schemas/race_schema.py) with Pydantic v2 DTOs (`RaceMode`, `DurationUnit`, `RaceStatus`, `DriverAssignment`, `RaceCreate`, `RaceUpdate`, `RaceRead`, `DriverStats`, `StandingsRow`, `RaceSummary`, `ReportRead`) per [data-model.md §3](specs/001-race-management/data-model.md); include the cross-field `model_validator` on `RaceCreate` (mode/lap_target/duration consistency, unique car_ids, `len(drivers) == driver_count`)
- [X] T008 [P] Create [src/race_context.py](src/race_context.py) implementing the `ActiveRaceContext` singleton with `threading.RLock`, `get()`, `set(race_id)`, and `clear()` methods per [data-model.md §6](specs/001-race-management/data-model.md)
- [X] T009 [P] Define typed exception hierarchy in [src/services/__init__.py](src/services/__init__.py): `RaceServiceError`, `RaceNotFoundError`, `RaceValidationError`, `InvalidRaceStateError`, `RaceAlreadyRunningError`, `RaceNotEditableError` per [contracts/race-service.md](specs/001-race-management/contracts/race-service.md)
- [X] T010 Extend [tests/conftest.py](tests/conftest.py) with new fixtures: `engine` (in-memory SQLite with `StaticPool` and `check_same_thread=False`), `db_session` (yielding a fresh `Session` per test), `session_factory`, and a `race_factory` helper that creates a draft race + drivers; ensure these fixtures do NOT load when not requested so the 52 existing tests are unaffected
- [X] T011 [P] Add a smoke test [tests/test_database_init.py](tests/test_database_init.py) that calls `init_db()` against the in-memory engine and asserts all five tables + key indices/UNIQUE constraints exist (introspect via `sqlalchemy.inspect`)
- [X] T012 [P] Add [tests/test_race_schema.py](tests/test_race_schema.py) covering `RaceCreate` validators: rejects `mode=fixed_laps` without `lap_target`, rejects `mode=fixed_duration` without `duration_value`, rejects duplicate `car_id`, rejects `len(drivers) != driver_count`, rejects empty driver names, accepts a valid 2-driver 10-lap race

**Checkpoint**: ORM, schemas, context, and exception types exist; foundational tests pass; the user-story phases can now proceed in parallel.

---

## Phase 3: User Story 1 — Create, Run, and Persist a Race (Priority: P1) 🎯 MVP

**Goal**: A user can create a race with drivers in the UI, start it, the running telemetry pipeline records each lap into the database in real time, the user can pause/resume/finish/cancel, and on finish the race is stored with its complete lap log.

**Independent Test**: In mock mode, create a 2-driver fixed-laps=10 race, click Start, let the mock pipeline run for ~30 seconds, click Finish; then inspect the SQLite DB and confirm `races` has one `finished` row with `started_at`/`finished_at` set, `race_drivers` has 2 rows, and `race_laps` has exactly as many rows as the mock emitted lap events for cars 1 and 2.

### Repository + Service (US1)

- [X] T013 [P] [US1] Create [src/repositories/__init__.py](src/repositories/__init__.py) and [src/repositories/race_repository.py](src/repositories/race_repository.py) with CRUD queries: `create_race`, `get_race`, `list_races`, `update_race`, `delete_race`, `set_status`, `set_timestamps`, `add_lap`, `add_event`, `get_drivers`, `get_laps`; each method takes an explicit `session: Session` argument
- [X] T014 [US1] Create [src/services/race_service.py](src/services/race_service.py) `RaceService` class with CRUD methods (`create_race`, `get_race`, `list_races`, `update_race`, `delete_race`) and the validation contract from [contracts/race-service.md](specs/001-race-management/contracts/race-service.md); each method opens its own `with SessionLocal() as session:` context and converts ORM rows to `RaceRead` DTOs
- [X] T015 [US1] Add lifecycle methods (`mark_ready`, `start_race`, `pause_race`, `resume_race`, `finish_race`, `cancel_race`) to [src/services/race_service.py](src/services/race_service.py) — enforce the state-machine table from [data-model.md §4](specs/001-race-management/data-model.md); use the `ActiveRaceContext._lock` to serialize transitions; auto-pause any other running race on `start_race`/`resume_race`; write a `RaceEvent` row of type `race_started`/`race_paused`/etc. when `race_management.persist_all_events=True`
- [X] T016 [US1] Add `record_lap(event: TelemetryEvent)` and `record_event(event: TelemetryEvent)` ingest methods to [src/services/race_service.py](src/services/race_service.py); drop laps when active race is paused (Edge Case #3) or when `car_id` is not in the race's driver set (Edge Case #2) with a structured log warning; catch `SQLAlchemyError`, log structurally, and do NOT re-raise (FR-121); after each lap insert in `fixed_laps` mode, evaluate auto-finish using the **leader's** lap count (FR-109(a))
- [X] T017 [US1] Add `recover_on_startup()` to [src/services/race_service.py](src/services/race_service.py): find any `status='running'` race, auto-pause it (default) or re-attach to `ActiveRaceContext` when `race_management.recover_running_race=True`

### Telemetry runner (US1)

- [X] T018 [US1] Create [src/race_runner.py](src/race_runner.py) `RaceTelemetryRunner` class: subscribes to `EventBus`, on every `lap` event with `ActiveRaceContext.get() is not None` calls `await asyncio.to_thread(race_service.record_lap, event)`; on every other event type calls `record_event` when `persist_all_events=True`; never blocks the bus
- [X] T019 [US1] Add `_fixed_duration_ticker()` async task to [src/race_runner.py](src/race_runner.py): once per second, when an active race is `running` and `mode='fixed_duration'`, check `started_at + duration_seconds < now()` and call `race_service.finish_race()` if so (R-108)

### Wiring (US1)

- [X] T020 [US1] Wire the new components in [src/main.py](src/main.py): import and call `init_db()` at startup; instantiate `RaceService` (singleton-style, module-level); call `race_service.recover_on_startup()`; create and `await` `RaceTelemetryRunner(event_bus, race_service).start()` alongside the existing `StateManager`/`JsonlEventWriter` subscribers; ensure no existing test breaks (these calls must be no-ops if config disables them or if no race is active)

### Streamlit UI (US1)

- [X] T021 [US1] Create [src/app.py](src/app.py) as the new Streamlit entry point: builds `st.navigation([st.Page(... "Dashboard"), st.Page(... "Race Management"), st.Page(... "Race Reports"), st.Page(... "Settings")])` per [research.md R-105](specs/001-race-management/research.md); the Dashboard page re-uses `src.dashboard.render()` unchanged
- [X] T022 [P] [US1] Create [src/pages/__init__.py](src/pages/__init__.py) and [src/pages/race_management.py](src/pages/race_management.py) implementing FR-127/FR-128: list view (table of races with status badges), "New Race" form (name, mode, lap target or duration, driver count, per-car driver names), edit form (disabled when status ∉ {draft, ready} unless `allow_edit_running_race`), action buttons (Start/Pause/Resume/Finish/Cancel/Delete/Repeat) calling `RaceService`; NO direct SQLAlchemy imports (FR-130)
- [X] T022a [US1] Add a **race-running view** to [src/pages/race_management.py](src/pages/race_management.py) per FR-129: when a selected race has `status ∈ {running, paused}`, show race name + status badge, mode, a progress widget (`st.progress` for laps-vs-target on `fixed_laps`, elapsed-vs-duration on `fixed_duration`), and a live driver table (car_id, driver_name, lap_count, last_lap_ms, best_lap_ms, position) sorted per FR-124; data flows via `RaceService` + `ReportingService.final_standings()` only (no ORM imports)
- [X] T023 [US1] Add a "Race Reports" stub [src/pages/race_reports.py](src/pages/race_reports.py) and a "Settings" stub [src/pages/settings.py](src/pages/settings.py) — both registered in `st.navigation` (full Reports implementation lands in US3, but the page must exist so US1 navigation is complete)

### Tests (US1)

- [X] T024 [P] [US1] Create [tests/test_race_repository.py](tests/test_race_repository.py): CRUD round-trip, list ordering, unique-`(race_id, car_id)` enforcement, cascade-delete of drivers/laps/events/reports
- [X] T025 [P] [US1] Create [tests/test_race_service_crud.py](tests/test_race_service_crud.py): create/get/list/update/delete via the service; rejects update on a running race when `allow_edit_running_race=False`
- [X] T026 [P] [US1] Create [tests/test_race_service_lifecycle.py](tests/test_race_service_lifecycle.py): every valid transition + every invalid transition (asserts `InvalidRaceStateError`); auto-pause behavior on second `start_race`; `ActiveRaceContext` set/cleared correctly
- [X] T027 [P] [US1] Create [tests/test_race_service_ingest.py](tests/test_race_service_ingest.py): `record_lap` inserts a row with correct `driver_name` join; drops lap when race is paused; drops lap on unknown `car_id` with warning; swallows `SQLAlchemyError` without raising; `fixed_laps` auto-finish triggers when leader reaches `lap_target`
- [X] T028 [P] [US1] Create [tests/test_race_runner.py](tests/test_race_runner.py): publish a synthetic `lap` event through a real `EventBus`, assert the runner calls `record_lap` exactly once; assert non-lap events go to `record_event` when `persist_all_events=True`; assert the ticker calls `finish_race` when `now() > started_at + duration_seconds`
- [X] T029 [US1] Run the full suite (`pytest`) and assert zero regressions: the original 52 tests must still pass alongside the new ones (FR-134)

**Checkpoint**: a user can create, start, run, pause/resume, finish, and cancel a race end-to-end in mock mode, with persistence verified by tests. **This is the shippable MVP.**

---

## Phase 4: User Story 2 — Repeat a Past Race (Priority: P2)

**Goal**: A user can click "Repeat" on any past race and instantly get a new draft race with the same configuration and drivers but zero historical data.

**Independent Test**: After running through US1 once, click "Repeat" on the finished race; a new race appears in the list named `<original> (copy)` (or user-supplied name) with status `draft`, identical mode/lap_target/duration/driver_count, identical driver names per car_id, `source_race_id = <original.id>`, and zero rows in `race_laps`/`race_events`/`race_reports`. Start it and verify it runs as a fresh race.

- [X] T030 [US2] Add `repeat_race(source_race_id: int, new_name: str | None = None) -> RaceRead` to [src/services/race_service.py](src/services/race_service.py) per [contracts/race-service.md §Repeat](specs/001-race-management/contracts/race-service.md) and [research.md R-106](specs/001-race-management/research.md); copies only the columns listed there; sets `source_race_id`; status from `race_management.default_race_status_after_create`
- [X] T031 [US2] Add a "Repeat" action button per race row in [src/pages/race_management.py](src/pages/race_management.py) with an optional rename input; on click calls `RaceService.repeat_race()` and re-runs the page so the new race appears in the list
- [X] T032 [P] [US2] Create [tests/test_repeat_race.py](tests/test_repeat_race.py): repeat copies name/mode/lap_target/duration_seconds/driver_count/notes and all drivers (same car_ids/names), assigns a new `id`, sets `source_race_id` correctly, and creates zero child rows in `race_laps`/`race_events`/`race_reports`; repeating a draft race also works (Edge Case #9); custom `new_name` is honored
- [X] T033 [US2] Run `pytest` — confirm new tests pass and existing pass count is preserved

**Checkpoint**: race repetition works end-to-end in UI and tests.

---

## Phase 5: User Story 3 — Generate, View, Save, and Export Race Reports (Priority: P3)

**Goal**: For any finished race the user can view standings + per-driver stats + total race duration in the UI, save a report snapshot, and download a CSV.

**Independent Test**: For the US1 finished race, open Race Reports → race name; verify standings (sorted, with gap-to-leader and laps-behind), per-driver stats (total laps, best/avg/last lap, total race time), and race duration; click "Save Report" → row appears in `race_reports`; click "Download CSV" → bytes returned, parse and check header + N data rows match standings order; assert the report renders in <500 ms for a race with 1000 laps (SC-105).

- [X] T034 [P] [US3] Create [src/services/reporting_service.py](src/services/reporting_service.py) implementing `driver_stats`, `final_standings` (sort `(lap_count desc, total_race_time_ms asc, best_lap_ms asc, car_id asc)` per FR-124), `race_summary`, `save_report`, `list_reports`, `export_summary_csv` (per-driver, FR-126(b)), and `export_laps_csv` (per-lap, FR-126(a) + US3 AS#3) per [contracts/reporting-service.md](specs/001-race-management/contracts/reporting-service.md); both aggregates done in one SQL query each then joined in Python
- [X] T035 [US3] Hook auto-snapshot into [src/services/race_service.py](src/services/race_service.py): `finish_race()` (and `cancel_race()` when at least one lap exists) calls `ReportingService.save_report(race_id, "race_summary", RaceSummary(...).model_dump(mode="json"))`
- [X] T036 [US3] Implement the full UI in [src/pages/race_reports.py](src/pages/race_reports.py) (replacing the US1 stub): race selector (only finished/cancelled races), standings table, driver-stats table, race duration, "Save Report" button (free-form report-type input), saved-reports list, **two** `st.download_button`s — "Download Summary CSV" wired to `export_summary_csv(race_id)` and "Download Laps CSV" wired to `export_laps_csv(race_id)` (FR-126); NO direct SQLAlchemy imports (FR-130)
- [X] T037 [P] [US3] Create [tests/test_reporting_service.py](tests/test_reporting_service.py): seeds a race with deterministic laps for 2 drivers; asserts `driver_stats` totals/min/avg/last, `final_standings` ordering per FR-124 `(lap_count desc, total_race_time_ms asc, best_lap_ms asc, car_id asc)`, `race_summary.duration_ms`, `save_report` round-trip, `list_reports` ordering, `export_summary_csv` header + row content, `export_laps_csv` header + row content + `(car_id asc, lap_number asc)` ordering, and a 1000-lap performance assert <500 ms (`time.perf_counter()`-based; mark with `@pytest.mark.slow` if needed)
- [X] T038 [P] [US3] Create [tests/test_reporting_auto_snapshot.py](tests/test_reporting_auto_snapshot.py): `RaceService.finish_race()` writes one `race_summary` row to `race_reports`; `cancel_race()` writes one only when laps exist
- [X] T039 [US3] Run `pytest` and confirm full green; spot-check the report renders in the live Streamlit app (mock mode)

**Checkpoint**: full race-management feature is shippable — create, run, repeat, report.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, regression-proofing, and the explicit hardware-TODO markers from FR-135.

- [X] T040 [P] Update [README.md](README.md) with a "Race Management" section: link to [specs/001-race-management/quickstart.md](specs/001-race-management/quickstart.md), document the new `streamlit run src/app.py` entry point, document the schema-reset policy (delete `data/carrera_dashboard.sqlite3` on breaking changes — Alembic deferred per R-103)
- [X] T041 [P] Update the launch command and any docs that reference `streamlit run src/dashboard.py` to use `streamlit run src/app.py` instead; keep `src/dashboard.py` importable so the Dashboard page still works
- [X] T042 [P] Audit [src/pages/race_management.py](src/pages/race_management.py) and [src/pages/race_reports.py](src/pages/race_reports.py) for any SQLAlchemy import — must be zero (FR-130 lint-style check); add a comment at the top of each file stating "UI layer — no ORM imports"
- [X] T043 [P] Add explicit `# TODO(hardware): verify lap event payload mapping against real Carrera DIGITAL traffic` markers at the top of [src/race_runner.py](src/race_runner.py) and `RaceService.record_lap` per FR-135 (consistent with the existing R-001 marker convention)
- [X] T043a [P] Add [tests/test_storage_perf_with_race.py](tests/test_storage_perf_with_race.py) per SC-106: rerun the existing storage benchmark (or its equivalent ingest path) with a `running` race active and `race_management.persist_all_events=true`, assert p95 ingest-to-disk remains <50 ms over a 60 events/s burst (FR-022 of the MVP spec); mark `@pytest.mark.slow`
- [X] T044 Run the full suite one final time (`pytest -q`) and capture the count; commit + push; verify the GitHub Actions CI run for `main` (after PR merge) is green per the user's standing workflow rule

---

## Dependencies

```text
Phase 1 (Setup)          ──►  Phase 2 (Foundational)  ──►  Phase 3 (US1, MVP)
                                                       ├──►  Phase 4 (US2)
                                                       └──►  Phase 5 (US3)
                                                              │
                                                              ▼
                                                       Phase 6 (Polish)
```

- Phases 4 and 5 both depend on Phase 3 only via the existing `RaceService`/`RaceTelemetryRunner` from US1; once US1 is checkpointed, US2 and US3 can proceed **in parallel** (different files, different tests).
- Phase 6 depends on Phases 3, 4, and 5 being complete.
- Within Phase 2: T005 must complete before T006 (models depend on `Base`); T007/T008/T009/T011/T012 are [P] and can proceed concurrently; T010 depends on T005+T006.
- Within Phase 3: T013 → T014 → T015 → T016 → T017 is sequential (same file); T018/T019 depend on T016; T020 depends on T017+T018+T019; T021/T023 depend on nothing in US1 beyond Phase 2 and can land early; T022 depends on T015 (calls lifecycle methods); T024–T028 are [P] across files; T029 is last.
- Within Phase 5: T034 → T035 (auto-snapshot depends on the service) → T036 (UI uses the service); tests T037/T038 are [P].

---

## Parallel-execution examples

**Phase 2 — kick off four independent files at once** (after T005+T006):

```text
T007 [P]  src/schemas/race_schema.py
T008 [P]  src/race_context.py
T009 [P]  src/services/__init__.py        (exception types)
T011 [P]  tests/test_database_init.py
T012 [P]  tests/test_race_schema.py
```

**Phase 3 — fan out the US1 tests** (after T013–T020 land):

```text
T024 [P]  tests/test_race_repository.py
T025 [P]  tests/test_race_service_crud.py
T026 [P]  tests/test_race_service_lifecycle.py
T027 [P]  tests/test_race_service_ingest.py
T028 [P]  tests/test_race_runner.py
```

**Phases 4 + 5 — once US1 is shipped, run both stories' implementers concurrently**:

```text
Developer A:   T030, T031, T032 (US2 — repeat-race)
Developer B:   T034, T035, T036, T037, T038 (US3 — reports)
```

---

## Implementation strategy

1. **Ship MVP first**: Phases 1 + 2 + 3 — at this point the feature is usable end-to-end (create / run / persist / finish), all 52 existing tests still pass, and the dashboard is unaffected when no race is running. This is the smallest demoable slice.
2. **Add Repeat**: Phase 4 — single small service method + one UI button + one test file. Independent and shippable on its own.
3. **Add Reports**: Phase 5 — pure-read service + new page + auto-snapshot hook. Independent and shippable on its own.
4. **Polish**: Phase 6 — docs, hardware-TODO markers, final regression run.

Each phase ends with `pytest -q` green and a commit on `001-race-management`. The branch stays mergeable to `main` after every phase.

---

## Format validation

- [x] Every task starts with `- [ ]`
- [x] Every task has a sequential T-ID
- [x] User-story-phase tasks carry a [US1] / [US2] / [US3] tag
- [x] Setup, Foundational, and Polish tasks carry NO story tag
- [x] [P] is set only where the task touches a unique file with no in-flight dependency
- [x] Every task includes an exact file path

**Summary**:
- **Total tasks**: 46
- **Per story**: Setup 4, Foundational 8, US1 18, US2 4, US3 6, Polish 6
- **Parallel opportunities**: 21 tasks marked [P]
- **Suggested MVP scope**: Phases 1+2+3 (30 tasks) — covers all P1 acceptance scenarios for US1
- **Independent test criteria**: documented at the head of each user-story phase
