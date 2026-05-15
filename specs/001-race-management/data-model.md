# Phase 1 — Data Model

## 1. Entity-Relationship overview

```text
                    +----------------+
                    |     Race       |
                    | id (PK)        |
                    | name           |
                    | mode           |
                    | lap_target     |
                    | duration_seconds
                    | driver_count   |
                    | status         |
                    | notes          |
                    | source_race_id |---+ (FK self-ref, nullable)
                    | created_at     |   |
                    | updated_at     |   |
                    | started_at     |   |
                    | finished_at    |   |
                    +-------+--------+   |
                            |             \
            +---------------+----+----+----+-------------+----------+
            |                    |    |    |             |          |
   +--------+-----+   +----------+-+  +----+-----+   +---+--------+
   | RaceDriver   |   |  RaceLap   |  | RaceEvent|   |RaceReport  |
   | id (PK)      |   | id (PK)    |  | id (PK)  |   | id (PK)    |
   | race_id (FK) |   | race_id    |  | race_id  |   | race_id    |
   | car_id 1..6  |   | car_id     |  | event_type|  | report_type|
   | driver_name  |   | driver_name|  | car_id?  |   | payload_json|
   | created_at   |   | lap_number |  | timestamp |   | created_at  |
   +--------------+   | lap_time_ms|  | payload_json |+------------+
                      | timestamp  |  | raw_data_json|
                      | created_at |  | created_at |
                      +------------+  +------------+
```

Cardinality: a `Race` has 1..6 `RaceDriver`, 0..N `RaceLap`, 0..N `RaceEvent`, 0..N `RaceReport`. `Race.source_race_id` is a nullable self-FK that points to the "original" of a repeated race.

## 2. Tables

### 2.1 `races`

| Column | Type | Nullable | Constraints |
|---|---|---|---|
| `id` | INTEGER | NO | PK, autoincrement |
| `name` | VARCHAR(120) | NO | non-empty (`CHECK length(trim(name)) > 0`) |
| `mode` | VARCHAR(20) | NO | `CHECK mode IN ('fixed_laps','fixed_duration')` |
| `lap_target` | INTEGER | YES | `CHECK lap_target IS NULL OR lap_target > 0` |
| `duration_seconds` | INTEGER | YES | `CHECK duration_seconds IS NULL OR duration_seconds > 0` |
| `driver_count` | INTEGER | NO | `CHECK driver_count BETWEEN 1 AND 6` |
| `status` | VARCHAR(20) | NO | `CHECK status IN ('draft','ready','running','paused','finished','cancelled')`, default `'draft'` |
| `notes` | TEXT | YES | — |
| `source_race_id` | INTEGER | YES | FK → `races.id`, ON DELETE SET NULL |
| `created_at` | DATETIME(UTC) | NO | default `now()` |
| `updated_at` | DATETIME(UTC) | NO | default `now()`, updated on each save |
| `started_at` | DATETIME(UTC) | YES | — |
| `finished_at` | DATETIME(UTC) | YES | — |

Composite invariants enforced in **service layer** (not DB):
- `mode = 'fixed_laps'` ⟹ `lap_target IS NOT NULL AND lap_target > 0` and `duration_seconds IS NULL`.
- `mode = 'fixed_duration'` ⟹ `duration_seconds IS NOT NULL AND duration_seconds > 0` and `lap_target IS NULL`.

Indices: `ix_races_status (status)`, `ix_races_created_at (created_at DESC)`, `ix_races_source_race_id (source_race_id)`.

### 2.2 `race_drivers`

| Column | Type | Nullable | Constraints |
|---|---|---|---|
| `id` | INTEGER | NO | PK |
| `race_id` | INTEGER | NO | FK → `races.id`, ON DELETE CASCADE |
| `car_id` | INTEGER | NO | `CHECK car_id BETWEEN 1 AND 6` |
| `driver_name` | VARCHAR(80) | NO | `CHECK length(trim(driver_name)) > 0` |
| `created_at` | DATETIME(UTC) | NO | default `now()` |

Unique: `UNIQUE (race_id, car_id)`.
Index: `ix_race_drivers_race_id (race_id)`.

### 2.3 `race_laps`

| Column | Type | Nullable | Constraints |
|---|---|---|---|
| `id` | INTEGER | NO | PK |
| `race_id` | INTEGER | NO | FK → `races.id`, ON DELETE CASCADE |
| `car_id` | INTEGER | NO | 1..6 |
| `driver_name` | VARCHAR(80) | NO | denormalized from `race_drivers` for fast reports |
| `lap_number` | INTEGER | NO | `CHECK lap_number > 0` |
| `lap_time_ms` | INTEGER | NO | `CHECK lap_time_ms > 0` |
| `timestamp_iso` | DATETIME(UTC) | NO | from `TelemetryEvent.timestamp_iso` |
| `created_at` | DATETIME(UTC) | NO | default `now()` |

Index: `ix_race_laps_race_car (race_id, car_id, lap_number)`. Optional `UNIQUE (race_id, car_id, lap_number)` to prevent double-counting; the service may suppress duplicate inserts on retry.

### 2.4 `race_events`

| Column | Type | Nullable | Constraints |
|---|---|---|---|
| `id` | INTEGER | NO | PK |
| `race_id` | INTEGER | NO | FK → `races.id`, ON DELETE CASCADE |
| `timestamp_iso` | DATETIME(UTC) | NO | — |
| `event_type` | VARCHAR(40) | NO | matches `EventType` enum |
| `car_id` | INTEGER | YES | 1..6 if present |
| `payload_json` | TEXT (JSON) | NO | serialized `event.payload` |
| `raw_data_json` | TEXT (JSON) | YES | when `--debug-raw` |
| `created_at` | DATETIME(UTC) | NO | default `now()` |

Index: `ix_race_events_race_type (race_id, event_type)`.

### 2.5 `race_reports`

| Column | Type | Nullable | Constraints |
|---|---|---|---|
| `id` | INTEGER | NO | PK |
| `race_id` | INTEGER | NO | FK → `races.id`, ON DELETE CASCADE |
| `report_type` | VARCHAR(40) | NO | e.g., `race_summary`, `driver_stats`, `final_standings` |
| `payload_json` | TEXT (JSON) | NO | full rendered report payload |
| `created_at` | DATETIME(UTC) | NO | default `now()` |

Index: `ix_race_reports_race_type (race_id, report_type)`.

## 3. Pydantic DTOs (`src/schemas/race_schema.py`)

```python
class RaceMode(StrEnum):
    FIXED_LAPS = "fixed_laps"
    FIXED_DURATION = "fixed_duration"

class DurationUnit(StrEnum):
    MINUTES = "minutes"
    HOURS = "hours"

class RaceStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"

class DriverAssignment(BaseModel):
    car_id: int = Field(ge=1, le=6)
    driver_name: str = Field(min_length=1, max_length=80)

class RaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    mode: RaceMode
    lap_target: int | None = Field(default=None, ge=1)
    duration_value: int | None = Field(default=None, ge=1)
    duration_unit: DurationUnit | None = None
    driver_count: int = Field(ge=1, le=6)
    drivers: list[DriverAssignment]
    notes: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "RaceCreate":
        # mode/lap_target/duration consistency
        # unique car_ids in drivers
        # len(drivers) == driver_count
        ...

class RaceUpdate(RaceCreate):
    """Same shape; all fields settable while race is in draft/ready."""

class RaceRead(BaseModel):
    id: int
    name: str
    mode: RaceMode
    lap_target: int | None
    duration_seconds: int | None
    driver_count: int
    status: RaceStatus
    notes: str | None
    source_race_id: int | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    drivers: list[DriverAssignment]
```

Report-payload DTOs (used by `ReportingService`):

```python
class DriverStats(BaseModel):
    car_id: int
    driver_name: str
    total_laps: int
    best_lap_ms: int | None
    average_lap_ms: int | None
    last_lap_ms: int | None
    total_race_time_ms: int | None
    pit_count: int | None
    fuel_summary: dict[str, float] | None  # e.g. {"start": 100.0, "end": 23.4, "consumed": 76.6}

class StandingsRow(BaseModel):
    position: int
    car_id: int
    driver_name: str
    lap_count: int
    best_lap_ms: int | None
    total_race_time_ms: int | None
    gap_to_leader_ms: int | None
    laps_behind: int

class RaceSummary(BaseModel):
    race: RaceRead
    duration_ms: int | None
    drivers: list[DriverStats]
    standings: list[StandingsRow]
```

## 4. State machine for `Race.status`

```text
        ┌────────────────────────────────────────────────────────────┐
        │                                                            │
        ▼                                                            │
    ┌───────┐  configure   ┌───────┐  start_race  ┌─────────┐ finish │
    │ draft │ ───────────► │ ready │ ───────────► │ running │ ──────►├─► finished
    └───────┘              └───┬───┘              └────┬────┘        │
        │                      │     pause_race        │             │
        │                      ▼                       ▼             │
        │                   (n/a)                 ┌────────┐ resume  │
        │                                         │ paused │ ────────┘
        │                                         └────┬───┘
        │                                              │
        │                  cancel_race  (any non-terminal)
        └──────────────────────────────┬──────────────────────────────► cancelled
                                       ▼
                                  ┌───────────┐
                                  │ cancelled │
                                  └───────────┘
```

Transitions implemented by `RaceService` (single source of truth):

| From | To | Method | Side effects |
|---|---|---|---|
| draft | ready | `mark_ready(race_id)` (implicit on `start_race` too) | — |
| draft / ready | running | `start_race(race_id)` | set `started_at`, set `ActiveRaceContext.current_race_id` |
| running | paused | `pause_race(race_id)` | clear `ActiveRaceContext` |
| paused | running | `resume_race(race_id)` | set `ActiveRaceContext.current_race_id` |
| running / paused | finished | `finish_race(race_id)` | set `finished_at`, clear `ActiveRaceContext` |
| draft / ready / running / paused | cancelled | `cancel_race(race_id)` | set `finished_at`, clear `ActiveRaceContext` |
| any | any new (repeat) | `repeat_race(race_id)` → new `Race` row | source_race_id set; default status from config |

Any transition outside this table raises `InvalidRaceStateError`.

Auto-finish (FR-109):
- `fixed_laps`: evaluated in `record_lap()` after each insert; finishes when `MIN(lap_count over drivers)` reaches `lap_target` for race-to-N-laps semantics. (Selectable variant: leader-reaches-N; default = leader-reaches-N for slot-car custom; configurable later.)
- `fixed_duration`: 1 Hz ticker in `race_runner.py` calls `finish_race()` when `started_at + duration_seconds < now()`.

## 5. Configuration extensions

`AppConfig` (in `src/config.py`) gains two submodels:

```python
class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/carrera_dashboard.sqlite3"
    echo: bool = False

class RaceManagementConfig(BaseModel):
    persist_all_events: bool = True
    allow_edit_running_race: bool = False
    default_race_status_after_create: RaceStatus = RaceStatus.DRAFT
    recover_running_race: bool = False  # if true, re-attach to running race on startup

class AppConfig(BaseModel):
    bluetooth: BluetoothConfig
    logging: LoggingConfig
    dashboard: DashboardConfig
    cars: CarsConfig
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    race_management: RaceManagementConfig = Field(default_factory=RaceManagementConfig)
```

Mirrored in `config.example.yaml` with comments.

## 6. Active-race context (`src/race_context.py`)

```python
class ActiveRaceContext:
    _race_id: int | None = None
    _lock: threading.RLock = threading.RLock()

    @classmethod
    def get(cls) -> int | None: ...
    @classmethod
    def set(cls, race_id: int | None) -> None: ...
```

Singleton — held at module level. Read by `RaceTelemetryRunner` (the new EventBus subscriber) on every event; written only by `RaceService` lifecycle methods.

## 7. Telemetry-to-DB flow

```text
   (existing) MockCarreraAdapter / LiveCarreraAdapter
                          │
                          ▼
                    EventBus.publish()
                          │
       ┌──────────────────┼─────────────────┐
       ▼                  ▼                 ▼
   StateManager     JsonlEventWriter   RaceTelemetryRunner    ← NEW
   (existing)       (existing)         │
                                       ▼
                              ActiveRaceContext.get()
                                       │
                            (race_id is not None?)
                                       │
                                       ▼
                          RaceService.record_lap(event) / record_event(event)
                                       │
                                       ▼  (synchronous; via to_thread)
                          RaceRepository.insert_lap / insert_event
                                       │
                                       ▼
                                    SQLite
```

`RaceTelemetryRunner` is wired in `src/main.py` alongside the existing `StateManager` and `JsonlEventWriter` subscribers; it is a no-op when `race_management.persist_all_events = false` and no race is running.
