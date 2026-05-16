# Data Model: Calm Connection UI + Restore Race Metrics

## Entity: ConnectionIndicatorState

Purpose: Minimal UI-facing representation for header connection status.

Fields:
- `raw_state: str` - Original connection state value from runtime snapshot.
- `icon: str` - One of `🟢`, `🟡`, `🟠`, `🔴`, `⚫`, `⚪`.
- `semantic_group: str` - One of `healthy`, `transitional`, `warning`, `error`, `offline`, `unknown`.

Validation Rules:
- Unknown or missing state maps to `icon=⚪`, `semantic_group=unknown`.
- Mapping is deterministic and side-effect free.

State Transitions:
- Recomputed on every dashboard refresh from current snapshot.

## Entity: RaceDashboardSnapshot

Purpose: Dashboard-ready aggregate for race-level and per-car metrics.

Fields:
- `taken_at_iso: str` - Snapshot timestamp.
- `race_id: int | null` - Active race identifier.
- `race_name: str | null` - Active race name.
- `race_status: str | null` - Domain race status (`running`, `paused`, `idle`, `finished`, etc.).
- `race_mode: str | null` - Domain race mode.
- `elapsed_ms: int | null` - Elapsed race time in milliseconds.
- `progress_percent: float | null` - Progress percentage where calculable.
- `leader_car_id: int | null` - Current leader if calculable.
- `fastest_lap_ms: int | null` - Best lap overall.
- `total_laps: int` - Sum of valid laps across tracked cars.
- `safety_car_active: bool | null` - Optional safety-car status.
- `cars: list[CarRaceMetrics]` - Fixed-length list for configured cars (canonical ids 1..6).
- `diagnostics: RaceMetricDiagnostics` - Debug/trace values for collapsed diagnostics panel.

Validation Rules:
- `cars` must always be present; missing cars are emitted with placeholders/default values.
- Unknown car IDs outside configured range are ignored.
- Numeric fields must be non-negative when present.

State Transitions:
- Updated every telemetry/state refresh cycle.
- Maintains stable shape regardless of active-race presence.

## Entity: CarRaceMetrics

Purpose: Per-car scoreboard metrics for dashboard rendering.

Fields:
- `car_id: int` - Canonical car id.
- `driver_name: str | null` - Driver display name.
- `lap_count: int` - Completed lap count.
- `latest_lap_ms: int | null` - Most recent valid lap time.
- `best_lap_ms: int | null` - Minimum valid lap time.
- `average_lap_ms: float | null` - Average valid lap time.
- `position: int | null` - Race position when calculable.
- `fuel_percent: float | null` - Last known fuel value.
- `pit_active: bool | null` - Last known pitlane status.
- `speed_kmh: float | null` - Last known speed metric if available.

Validation Rules:
- `lap_count >= 0`.
- Lap times and averages are `>= 0` when present.
- Fuel percent clamped to `[0, 100]`.

State Transitions:
- On normalized lap event: increment/derive lap fields.
- On fuel/pit/speed events: update corresponding optional fields.

## Entity: LapNormalizationInput

Purpose: Compatibility abstraction for multiple lap event payload formats.

Fields:
- `event_type: str` - Raw incoming event type (`lap` or `lap_completed`).
- `car_id: int | null` - Car id candidate.
- `lap_number: int | null` - Optional lap ordinal.
- `lap_time_ms: int | null` - Normalized lap time.
- `raw_payload: dict[str, object]` - Original payload for diagnostics.

Normalization Rules:
- `lap.payload.lap_time_ms` -> `lap_time_ms`.
- `lap_completed.payload.time_ms` -> `lap_time_ms`.
- If `lap_time_ms` missing/invalid, event is ignored for metric math and tracked in diagnostics.

## Entity: RaceMetricDiagnostics

Purpose: Collapsed debug panel data for troubleshooting metric gaps.

Fields:
- `last_telemetry_at_iso: str | null`
- `last_state_update_at_iso: str | null`
- `active_race_id: int | null`
- `processed_lap_events: int`
- `cars_in_snapshot: list[int]`
- `last_lap_payload: dict[str, object] | null`
- `dropped_lap_events: int`

Validation Rules:
- Counters are non-negative.
- Diagnostics may be partial and must never block dashboard rendering.

## Relationships

- `RaceDashboardSnapshot` 1-to-many `CarRaceMetrics`.
- `RaceDashboardSnapshot` 1-to-1 `RaceMetricDiagnostics`.
- `LapNormalizationInput` feeds updates into one `CarRaceMetrics` record.
- `ConnectionIndicatorState` is independent from race entities but rendered in the same dashboard frame.
