# JSONL Event Log Contract

## File layout

- Directory: configured via `logging.directory` (default `./logs`).
- Filename: `carrera-{YYYYMMDD-HHMMSS}-{pid}.jsonl` (UTC timestamp).
- Encoding: UTF-8, no BOM, line terminator `\n`.
- One `TelemetryEvent` per line (no pretty-printing, no trailing comma, no array wrapper).
- Append-only within a process; the file is closed on graceful shutdown.

## Line schema (JSON)

```json
{
  "timestamp_iso": "2026-05-15T14:23:12.421+02:00",
  "timestamp_monotonic_ms": 153421,
  "source": "carrera_appconnect",
  "event_type": "lap",
  "car_id": 1,
  "controller_id": null,
  "payload": { "lap_time_ms": 8123, "lap_number": 5 },
  "raw_data": null,
  "metadata": {}
}
```

### Field rules

- `timestamp_iso`: RFC 3339 / ISO 8601 with timezone offset. Required.
- `timestamp_monotonic_ms`: integer ≥ 0. Required. Authoritative for in-run ordering.
- `source`: one of `"carrera_appconnect" | "mock" | "system"`. Required.
- `event_type`: one of the values listed in `data-model.md §2`. Required.
- `car_id`, `controller_id`: integer 1–6 or `null`.
- `payload`: object; shape determined by `event_type` (see data-model.md §2).
- `raw_data`: any JSON-serializable value or `null`.
- `metadata`: object of string→string; defaults to `{}`.

## Ordering & atomicity

- Lines within a single file are monotonically non-decreasing by `timestamp_monotonic_ms`.
- A consumer MAY assume that any whole line that ends with `\n` is committed.
- Partial trailing lines (process killed mid-write) MUST be tolerated by consumers: drop the partial line, do not abort.

## CSV companion (optional)

When `logging.csv_laps_enabled` is `true`:

- Filename: `laps-{YYYYMMDD-HHMMSS}-{pid}.csv`
- Header line (exact): `car_id,lap_number,lap_time_ms,timestamp_iso`
- One row per `lap` event in arrival order.
- RFC 4180 quoting.

## Backwards-compatibility policy (post-MVP)

- New event types MAY be added; consumers MUST ignore unknown `event_type` values gracefully.
- New optional fields MAY be added to `payload`; consumers MUST ignore unknown keys.
- Existing field names and types are stable; breaking changes require a new file-format version (future `metadata.schema_version`).
