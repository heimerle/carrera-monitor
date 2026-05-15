# Contract: `ReportingService`

Module: `src/services/reporting_service.py`. All methods are synchronous and pure with respect to the database (no writes except `save_report` and `_persist_summary_on_finish`).

## Methods

```python
def driver_stats(race_id: int) -> list[DriverStats]
```
Per-driver aggregates over `race_laps`:
- `total_laps` = `COUNT(*)`
- `best_lap_ms` = `MIN(lap_time_ms)`
- `average_lap_ms` = `AVG(lap_time_ms)` (integer-rounded)
- `last_lap_ms` = `lap_time_ms` of `MAX(lap_number)`
- `total_race_time_ms` = `SUM(lap_time_ms)`
- `pit_count`, `fuel_summary`: derived from `race_events` (event types `pit_lane`/`fuel`) when present; nullable otherwise.

Ordering: `car_id ASC`.

```python
def final_standings(race_id: int) -> list[StandingsRow]
```
For each driver:
- `lap_count` = total laps recorded
- `best_lap_ms` = `MIN(lap_time_ms)`
- Rank by (`lap_count DESC`, `total_race_time_ms ASC`).
- `position` = 1-based ordinal after sort.
- `gap_to_leader_ms` = leader's `total_race_time_ms` − this driver's, when on same lap count; else `null`.
- `laps_behind` = leader's `lap_count` − this driver's `lap_count`.

Returns `[]` if race has no laps yet.

```python
def race_summary(race_id: int) -> RaceSummary
```
Composes:
- `race` = `RaceService.get_race(race_id)`
- `duration_ms` = `(finished_at or now()) − started_at`, or `None` if race never started
- `drivers` = `driver_stats(race_id)`
- `standings` = `final_standings(race_id)`

**Performance budget**: ≤500 ms wall time for races with up to 1,000 laps (SC-105). All aggregates are computed in two SQL queries plus one Python join.

```python
def save_report(race_id: int, report_type: str, payload: dict) -> int
```
Persists a `race_reports` row. Returns its id. `report_type` is a free-form short string (`race_summary`, `driver_stats`, `final_standings`, or any custom value entered from the UI).

```python
def list_reports(race_id: int) -> list[ReportRead]
```
Order: `created_at DESC`.

```python
def export_summary_csv(race_id: int) -> bytes
```
UTF-8 CSV bytes with header row + one row per driver in standings order. Columns:
`position, car_id, driver_name, lap_count, best_lap_ms, gap_to_leader_ms, laps_behind, total_race_time_ms, average_lap_ms, pit_count`.

## Auto-snapshot on finish

`RaceService.finish_race()` (and `cancel_race()` when at least one lap exists) calls
`ReportingService.save_report(race_id, "race_summary", RaceSummary(...).model_dump(mode="json"))`
so a permanent JSON snapshot of the final state is preserved even if `race_laps` rows are later pruned.
