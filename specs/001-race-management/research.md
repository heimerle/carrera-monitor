# Phase 0 — Research: Race Management Module

All open questions from the spec have been resolved or have a clearly chosen default. No `NEEDS CLARIFICATION` markers remain.

## R-101 SQLAlchemy 2.x session pattern for mixed Streamlit/async workload

**Decision**: Use **synchronous** SQLAlchemy 2.x with a single module-level `Engine` and a `sessionmaker(bind=engine, expire_on_commit=False)` factory exposed as `SessionLocal`. Every service method opens its own short-lived `Session` via a `with SessionLocal() as session: …` context manager — both from Streamlit pages and from the async telemetry subscriber. The async subscriber wraps blocking calls in `await asyncio.to_thread(...)` so the event loop is never blocked.

**Rationale**:
- Streamlit reruns are synchronous and per-request; the same sync ORM idiom can be reused.
- `aiosqlite` only helps the async side; it forces split engines and double the code.
- SQLite + WAL handles concurrent readers + a single writer trivially at our scale.

**Alternatives considered**: async SQLAlchemy + `aiosqlite` (more code, no measurable benefit at our throughput); `databases` library (dead/unmaintained).

## R-102 SQLite concurrency settings

**Decision**: At engine creation, run `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, `PRAGMA foreign_keys = ON;`, and pass `connect_args={"check_same_thread": False, "timeout": 5.0}`. Use a `StaticPool` only for in-memory test databases; default to SQLAlchemy's `NullPool` or `QueuePool` for file-backed DBs.

**Rationale**: WAL allows one writer + many readers without contention; `synchronous = NORMAL` is the canonical local-dev safe value; `check_same_thread = False` is required because the async task and Streamlit run on different threads.

**Alternatives considered**: default `journal_mode = DELETE` (blocks readers during writes — fails our concurrent-read use case); `synchronous = FULL` (slower, no durability gain in this app).

## R-103 Alembic in v1?

**Decision**: **No.** Use `Base.metadata.create_all(engine)` on first run. Document the migration policy in the README: when a schema change ships, users delete `data/carrera_dashboard.sqlite3` (a manual one-time step at this stage of the project).

**Rationale**: Alembic adds a non-trivial setup tax for a single-user local app. The user explicitly marked Alembic optional ("keep the first MVP simple"). When the first breaking schema change lands post-v1, we add Alembic in its own slice.

**Alternatives considered**: Alembic from day 1 (over-engineered); ad-hoc `ALTER TABLE` (fragile).

## R-104 Lap event payload — already canonical

**Decision**: Reuse the existing `lap` payload contract from `src/event_model.py`: `{"lap_number": int, "lap_time_ms": int}` plus `car_id` at the top-level event. No new payload keys required. The `RaceService.record_lap()` method consumes a `TelemetryEvent` and maps:
- `event.car_id` → `RaceLap.car_id`
- `event.payload["lap_number"]` → `RaceLap.lap_number`
- `event.payload["lap_time_ms"]` → `RaceLap.lap_time_ms`
- `event.timestamp_iso` → `RaceLap.timestamp_iso`
- driver_name resolved from the active `RaceDriver` row for `(race_id, car_id)`.

**Rationale**: Zero new shape to maintain; existing tests already verify the lap payload.

## R-105 Streamlit multi-page navigation

**Decision**: Use `st.navigation` + `st.Page` (Streamlit ≥1.30 native API). Single entry point `src/app.py` registers four pages:
- `Dashboard` → re-uses the existing `src/dashboard.py:render()` function (called inside a `st.Page` wrapper).
- `Race Management` → `src/pages/race_management.py:render()`.
- `Race Reports` → `src/pages/race_reports.py:render()`.
- `Settings` → minimal placeholder showing current config (full implementation can land later; not required by acceptance).

The existing `python -m src.main` subprocess command changes to launch `streamlit run src/app.py` instead of `src/dashboard.py`.

**Rationale**: `st.navigation` is the modern, supported way; the older "pages/" directory convention couples filenames to URL slugs and is harder to share state with. The existing dashboard module is reused verbatim as a tab.

**Alternatives considered**: legacy `pages/` directory (filename-based; ugly URLs); a single-page app with `st.tabs` (heavier reruns, less idiomatic).

## R-106 Repeat-race copy semantics

**Decision**: Copy only `name`, `mode`, `lap_target`, `duration_seconds`, `driver_count`, `notes`. New row gets fresh `id`, `created_at`, `updated_at`. `started_at` / `finished_at` are NULL. `source_race_id` is set to the source race id. `RaceDriver` rows are duplicated (new ids, new `created_at`, same `car_id`/`driver_name`). **Zero** rows in `race_laps`, `race_events`, `race_reports`. Status set from `race_management.default_race_status_after_create` (default `draft`).

**Rationale**: Matches FR-111/FR-112 word-for-word. JSON-blob deep-copy is N/A because we don't copy any JSON-bearing tables.

## R-107 Testing strategy for in-memory SQLite shared across two callers

**Decision**: For each test, build an isolated engine `create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)` so the **same** physical connection is reused across the test's threads and tasks. Yield a `SessionLocal` factory bound to that engine. Tests that need the async-ingest path use `pytest-asyncio` + a tiny `EventBus` instance + `to_thread`.

**Rationale**: `StaticPool` + `:memory:` is the documented SQLAlchemy idiom for sharing an in-memory DB across threads in tests. It avoids the disk and is fast (<5 ms per test).

**Alternatives considered**: per-test temp `tmp_path` SQLite file (slower, harder to clean up between tests in the same session); single shared session per test (breaks the "one session per service call" production pattern).

## R-108 Race auto-finish wiring

**Decision**: Auto-finish is evaluated inside `RaceService.record_lap()` after each lap is inserted (for `fixed_laps`) and inside a lightweight async ticker in `race_runner.py` once per second (for `fixed_duration`). The ticker checks `started_at + duration_seconds < now()` and calls `finish_race()` if so. No SQL trigger, no background daemon.

**Rationale**: Co-locating the check with the lap write avoids race conditions and is testable purely via service-level unit tests. The 1 Hz ticker is acceptable for hour-scale durations (worst-case finish lag = 1 second).

**Alternatives considered**: A separate `asyncio.sleep(0.1)` ticker (over-frequent); SQLite triggers (untestable, leaks logic outside Python).

## R-109 Active-race enforcement

**Decision**: `ActiveRaceContext` is an in-memory singleton (`src/race_context.py`) holding `current_race_id: int | None` guarded by a `threading.RLock`. Both the async telemetry subscriber and Streamlit pages read/write it via the lock. `RaceService.start_race()` is the only setter; `finish_race()` / `pause_race()` / `cancel_race()` clear it.

**Rationale**: Streamlit reruns are sync; the async task uses `to_thread`, so an `RLock` is sufficient. The DB column `status` is the durable source of truth on process restart — on startup we scan for any race in `running` and either auto-pause it (default) or re-attach (toggle via `race_management.recover_running_race`, default `false`).

**Alternatives considered**: storing only in DB and querying every event (extra DB hits on the hot path); using `asyncio.Lock` exclusively (excludes Streamlit's thread).

## R-110 Backwards-compatibility with existing CI / tests

**Decision**: `database.py` and `models.py` import at the **top** of new modules only — never from existing modules. The existing test suite must run without `data/` or any DB file present: new tests provide their own engine via the `db_session` fixture. CI matrix is unchanged (Ubuntu + macOS × Python 3.11/3.12). `requirements.txt` adds `SQLAlchemy>=2.0,<3` only.

**Rationale**: Keeps the 52 existing tests stable and avoids any conditional imports. ("52" is the pre-001 baseline; the total drifts as later slices land — see CI on `main` for the current count.)
