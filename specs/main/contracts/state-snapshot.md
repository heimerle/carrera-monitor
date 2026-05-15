# State Snapshot Contract

The pipeline process writes a state snapshot file that the Streamlit dashboard reads. This file is the **only** runtime coupling between the two processes; everything else is decoupled.

## Path

- `{logging.directory}/state.json` (default `./logs/state.json`).

## Write protocol

- Producer: `StateManager` in the pipeline process.
- Cadence: every `dashboard.refresh_interval_ms` (default 1000 ms), and on every state change.
- Atomicity: write to `state.json.tmp` then `os.replace(...)` to `state.json`. Readers therefore always see a complete file.
- Encoding: UTF-8 JSON, pretty-printed (2-space indent) for human inspection.

## Read protocol

- Consumer: Streamlit dashboard.
- Read on every rerun (driven by `st_autorefresh`).
- Tolerate the file being briefly missing on first start (poll once per refresh, render an "initializing" placeholder).
- Tolerate stale files (older than 5× refresh interval): show a "stale data" banner.

## Schema

```json
{
  "taken_at_iso": "2026-05-15T14:23:12.421+02:00",
  "taken_at_monotonic_ms": 153421,
  "connection": {
    "state": "connected",
    "since_ms": 12000,
    "last_error": null
  },
  "race": "running",
  "cars": [
    {
      "car_id": 1,
      "lap_count": 5,
      "best_lap_ms": 7900,
      "latest_lap_ms": 8123,
      "fuel_percent": 73.2,
      "in_pit": false,
      "last_speed_kmh": 142.0,
      "last_event_at_ms": 153400
    }
  ],
  "recent_events": [
    /* up to 100 TelemetryEvent objects, newest first */
  ]
}
```

Field semantics are identical to `data-model.md §7 StateSnapshot`. Unknown keys MUST be ignored by readers.
