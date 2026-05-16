# Contract: Dashboard Connection Indicator and Race Metrics

## Scope

Defines the dashboard-facing contract for:
- connection indicator rendering input
- race-level metrics payload
- per-car metrics payload
- lap-event normalization compatibility

## Contract 1: Connection Indicator Mapping

Input:
- `connection.state: string | null`

Output:
- `ConnectionIndicatorState.icon: string`

Mapping (normative):
- `ready`, `connected` -> `🟢`
- `connecting`, `scanning`, `subscribing`, `reconnecting` -> `🟡`
- `stale` -> `🟠`
- `error` -> `🔴`
- `disconnected`, `manually_disconnected` -> `⚫`
- unknown or missing -> `⚪`

Rules:
- Header MUST render icon-only for connection status.
- Verbose details MUST be shown only in diagnostics/overflow section.

## Contract 2: Dashboard Race Snapshot Shape

The dashboard render path consumes a stable object with this shape:

```json
{
  "taken_at_iso": "2026-05-16T16:00:00Z",
  "race": {
    "id": 42,
    "name": "Sprint Heat",
    "status": "running",
    "mode": "fixed_laps",
    "elapsed_ms": 123456,
    "progress_percent": 62.5,
    "leader_car_id": 2,
    "fastest_lap_ms": 5432,
    "total_laps": 87,
    "safety_car_active": false
  },
  "cars": [
    {
      "car_id": 1,
      "driver_name": "Driver 1",
      "lap_count": 14,
      "latest_lap_ms": 5500,
      "best_lap_ms": 5400,
      "average_lap_ms": 5522.3,
      "position": 3,
      "fuel_percent": 67.0,
      "pit_active": false,
      "speed_kmh": 108.4
    }
  ],
  "diagnostics": {
    "last_telemetry_at_iso": "2026-05-16T15:59:59Z",
    "last_state_update_at_iso": "2026-05-16T16:00:00Z",
    "active_race_id": 42,
    "processed_lap_events": 87,
    "cars_in_snapshot": [1, 2, 3, 4, 5, 6],
    "last_lap_payload": {"car_id": 2, "lap_time_ms": 5432},
    "dropped_lap_events": 0
  }
}
```

Rules:
- `cars` MUST remain present even with no active race.
- Missing values MUST be represented as `null` (or dashboard placeholder `-` in rendering), not by omitting keys.
- Unknown car IDs outside configured range MUST be ignored safely.

## Contract 3: Lap Normalization Compatibility

Accepted incoming variants:

Variant A:
```json
{
  "event_type": "lap",
  "car_id": 2,
  "payload": {
    "lap_number": 14,
    "lap_time_ms": 5432
  }
}
```

Variant B:
```json
{
  "event_type": "lap_completed",
  "car_id": 2,
  "payload": {
    "lap": 14,
    "time_ms": 5432
  }
}
```

Normalization result:
- Both variants MUST produce a single internal update with `lap_time_ms=5432` for the same per-car metric pipeline.

Error handling:
- If normalized lap time is missing/invalid, event MUST be ignored for lap math and counted in diagnostics; render path MUST remain operational.

## Contract 4: Rendering Behavior

- Race metrics section MUST always render, even with no active race.
- Placeholder display (`-`) MUST be used for absent values.
- Diagnostics section MUST be collapsed by default and contain troubleshooting fields from `diagnostics` payload.

## Backward Compatibility

- Existing telemetry/event bus models remain valid.
- New fields are additive for dashboard consumption.
- Existing pages and non-dashboard workflows must remain unaffected by this contract.
