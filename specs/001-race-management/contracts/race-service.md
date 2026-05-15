# Contract: `RaceService`

Module: `src/services/race_service.py`. All methods are synchronous and use a fresh `Session` per call. Telemetry-ingest methods are called from the async pipeline via `asyncio.to_thread()`.

## Exceptions

```python
class RaceServiceError(Exception): ...
class RaceNotFoundError(RaceServiceError): ...
class RaceValidationError(RaceServiceError): ...
class InvalidRaceStateError(RaceServiceError): ...
class RaceAlreadyRunningError(RaceServiceError): ...   # used internally; start_race auto-pauses instead of raising
class RaceNotEditableError(RaceServiceError): ...
```

## Methods

### CRUD

```python
def create_race(payload: RaceCreate) -> RaceRead
```
- **Pre**: payload validates per `RaceCreate` (mode/lap_target/duration consistency, unique car_ids, `len(drivers) == driver_count`).
- **Post**: a row exists in `races` with `status` from config (default `draft`), plus N rows in `race_drivers`.
- **Raises**: `RaceValidationError` on shape/cross-field failures.

```python
def get_race(race_id: int) -> RaceRead
```
- **Raises**: `RaceNotFoundError`.

```python
def list_races(
    status: RaceStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RaceRead]
```
- Order: `created_at DESC`. Returns `RaceRead` (includes drivers).

```python
def update_race(race_id: int, payload: RaceUpdate) -> RaceRead
```
- **Pre**: race exists; race status ∈ {`draft`, `ready`} (or any if `race_management.allow_edit_running_race = True`).
- **Raises**: `RaceNotFoundError`, `RaceNotEditableError`, `RaceValidationError`.

```python
def delete_race(race_id: int) -> None
```
- **Pre**: race exists; race status != `running`. Cascades children.
- **Raises**: `RaceNotFoundError`, `InvalidRaceStateError`.

### Lifecycle

```python
def mark_ready(race_id: int) -> RaceRead          # draft -> ready (idempotent if already ready)
def start_race(race_id: int) -> RaceRead          # draft|ready -> running; auto-pauses any other running race
def pause_race(race_id: int) -> RaceRead          # running -> paused
def resume_race(race_id: int) -> RaceRead         # paused -> running; auto-pauses any other running race
def finish_race(race_id: int) -> RaceRead         # running|paused -> finished; sets finished_at
def cancel_race(race_id: int) -> RaceRead         # draft|ready|running|paused -> cancelled; sets finished_at
```

All lifecycle methods:
- **Pre**: race exists; status transition is valid per [data-model.md §4](../data-model.md).
- **Side effects**:
  - `start_race` / `resume_race` set `ActiveRaceContext.set(race_id)` and emit a `RaceEvent(event_type='race_started' | 'race_resumed')`.
  - `pause_race` / `finish_race` / `cancel_race` clear `ActiveRaceContext` (if currently pointing at this race) and emit the corresponding `race_paused` / `race_finished` / `race_cancelled` event.
- **Raises**: `RaceNotFoundError`, `InvalidRaceStateError`.

### Repeat

```python
def repeat_race(source_race_id: int, new_name: str | None = None) -> RaceRead
```
- **Post**: a new `races` row with `source_race_id=source_race_id`, new `id`/`created_at`, status from config (default `draft`), 0 child rows in laps/events/reports. Driver rows copied 1:1.
- **Raises**: `RaceNotFoundError`.

### Telemetry ingest (called from `race_runner.py`)

```python
def record_lap(event: TelemetryEvent) -> None
```
- **Pre**: an active race exists (`ActiveRaceContext.get() is not None`) and that race has `status='running'`; `event.event_type == 'lap'`; `event.car_id` is one of the active race's `RaceDriver.car_id`.
- **Behavior**:
  - If active race is `paused` → log debug and return (drop).
  - If `event.car_id` not in active drivers → log warning and return (drop, per Edge Case #2).
  - Insert into `race_laps` (denormalized `driver_name` looked up once per session).
  - If race mode is `fixed_laps`, evaluate auto-finish: if leader's `lap_count >= lap_target`, call `finish_race(race_id)`.
- **Errors**: catches `SQLAlchemyError`, logs structurally, **does not re-raise** (FR-121).

```python
def record_event(event: TelemetryEvent) -> None
```
- **Pre**: `race_management.persist_all_events = True` and an active race is `running` or `paused`.
- **Behavior**: insert into `race_events`. Same error policy as `record_lap`.

### Recovery

```python
def recover_on_startup() -> None
```
- Called once from `src/main.py` at boot. Finds any race with `status='running'`. If `race_management.recover_running_race`, sets `ActiveRaceContext`; else calls `pause_race`.

## Concurrency & sessions

- Every method opens its own `with SessionLocal() as session:` context; no shared sessions across method calls.
- Lifecycle methods are guarded by a per-process `threading.RLock` (`ActiveRaceContext._lock`) so concurrent UI clicks + telemetry ticks cannot interleave a transition.
- Read methods (`get_race`, `list_races`) are lock-free.
