# Phase 1 Data Model: Carrera Digital Telemetry Dashboard MVP

**Spec**: [spec.md](./spec.md)  
**Plan**: [plan.md](./plan.md)

All persistent/transported entities are defined here. Implementation lives in `src/event_model.py` (TelemetryEvent + enums) and `src/state_manager.py` (in-memory aggregates). Validation is Pydantic.

---

## 1. TelemetryEvent (canonical)

Pydantic model. Immutable (`model_config.frozen = True`).

| Field | Type | Required | Notes |
|---|---|---|---|
| `timestamp_iso` | `datetime` (tz-aware) | yes | ISO-8601, host wall clock at emission. |
| `timestamp_monotonic_ms` | `int` (≥ 0) | yes | Monotonic ms since process start. Authoritative for ordering. |
| `source` | `Literal["carrera_appconnect", "mock", "system"]` | yes | Identifies the producer. |
| `event_type` | `EventType` enum | yes | See enum below. |
| `car_id` | `int \| None` (1–6 when present) | no | Absent for race-level events. |
| `controller_id` | `int \| None` (1–6 when present) | no | Reserved for future controller-only events. |
| `payload` | `dict[str, Any]` | yes | Event-type-specific structured data. Schema per type below. |
| `raw_data` | `dict[str, Any] \| None` | no | Untouched upstream frame for debugging / future RE. |
| `metadata` | `dict[str, str]` | yes (defaults `{}`) | Free-form tags (e.g., `{"adapter_version": "..."}`). |

### Validation rules

- `timestamp_iso` MUST be timezone-aware.
- `car_id` ∈ [1, 6] when present.
- `payload` MUST conform to the per-`event_type` shape below; unknown keys are rejected to catch typos early.
- `raw_data` MUST be JSON-serializable.

### Serialization

- `model_dump_json()` → one JSON line for JSONL.
- Round-trip stable: `TelemetryEvent.model_validate_json(e.model_dump_json()) == e`.

---

## 2. EventType (enum, string-valued)

| Value | Payload shape |
|---|---|
| `lap` | `{ "lap_number": int ≥ 1, "lap_time_ms": int ≥ 0 }` |
| `race_state` | `{ "state": RaceState }` |
| `fuel` | `{ "level_percent": float 0–100 }` |
| `controller_input` | `{ "throttle": float 0–1, "brake": float 0–1 }` |
| `speed` | `{ "speed_kmh": float ≥ 0 }` |
| `brake` | `{ "brake": float 0–1 }` |
| `pitlane` | `{ "in_pit": bool, "reason": "manual" \| "fuel" \| "unknown" }` |
| `connection_state` | `{ "state": ConnectionState, "error": str \| None }` |
| `raw` | passthrough (`raw_data` carries the actual frame) |
| `not_supported` | `{ "reason": str }` (raw_data preserved) |

### State transitions

- `connection_state`: must reflect a valid `ConnectionState` transition (see §5). Invalid transitions are still emitted but flagged in `metadata.transition_warning`.
- `race_state`: see RaceState below.

---

## 3. CarState (in-memory aggregate)

Built incrementally by `StateManager` from subscribed events. Plain dataclass (not persisted directly; only via dashboard snapshot).

| Field | Type | Init | Updated by |
|---|---|---|---|
| `car_id` | `int` | constructor | n/a |
| `lap_count` | `int` | `0` | `lap` event (max of seen `lap_number`) |
| `best_lap_ms` | `int \| None` | `None` | `lap` event (min) |
| `latest_lap_ms` | `int \| None` | `None` | `lap` event |
| `fuel_percent` | `float \| None` | `None` | `fuel` event |
| `in_pit` | `bool` | `False` | `pitlane` event |
| `last_speed_kmh` | `float \| None` | `None` | `speed` event |
| `last_event_at_ms` | `int \| None` | `None` | any event with matching `car_id` |

### Invariants

- `best_lap_ms ≤ latest_lap_ms` whenever both set (otherwise `best_lap_ms` is updated).
- `lap_count` is monotonically non-decreasing during a single race; resets on `race_state.state == "idle"`.
- `fuel_percent` is clamped to [0, 100] on ingest.

---

## 4. RaceState (enum)

`idle | countdown | running | paused | finished`

Transitions:

```
idle → countdown → running
running → paused → running
running → finished
finished → idle (manual reset)
```

Unknown source states are coerced to `idle` and a `metadata.coerced_from` tag is set on the emitted event.

---

## 5. ConnectionState (enum)

`disconnected | scanning | connecting | connected | reconnecting | error`

Valid transitions:

```
disconnected → scanning
scanning → connecting | error | disconnected
connecting → connected | error | reconnecting
connected → reconnecting | disconnected | error
reconnecting → connecting | connected | error | disconnected
error → disconnected | scanning
```

A `ConnectionStateRecord` accompanies the enum at runtime:

| Field | Type | Notes |
|---|---|---|
| `state` | `ConnectionState` | |
| `since_ms` | `int` | monotonic ms when entered |
| `last_error` | `str \| None` | populated on entry to `error` |

---

## 6. AppConfig (Pydantic, loaded from YAML)

Top-level model with nested submodels.

### `BluetoothConfig`
| Field | Type | Default |
|---|---|---|
| `mac_address` | `str \| None` | `None` |
| `scan_timeout_seconds` | `int ≥ 1` | `10` |
| `reconnect_interval_seconds` | `int ≥ 1` | `5` |

### `LoggingConfig`
| Field | Type | Default |
|---|---|---|
| `directory` | `Path` | `./logs` |
| `jsonl_enabled` | `bool` | `true` |
| `csv_laps_enabled` | `bool` | `true` |
| `debug_raw_enabled` | `bool` | `false` |

### `DashboardConfig`
| Field | Type | Default |
|---|---|---|
| `enabled` | `bool` | `true` |
| `port` | `int 1024–65535` | `8501` |
| `refresh_interval_ms` | `int 500–1000` | `1000` |

### `CarsConfig`
| Field | Type | Default |
|---|---|---|
| `count` | `int 1–6` | `6` |

Validation: unknown top-level keys → warning; unknown nested keys → warning. Range violations → `pydantic.ValidationError` (fatal).

---

## 7. StateSnapshot (dashboard contract)

What `StateManager.snapshot()` returns and what the dashboard consumes. Pydantic, JSON-serializable so it can be written to `logs/state.json` for the Streamlit process (see R-011).

| Field | Type |
|---|---|
| `taken_at_iso` | `datetime` (tz-aware) |
| `taken_at_monotonic_ms` | `int` |
| `connection` | `ConnectionStateRecord` |
| `race` | `RaceState` |
| `cars` | `list[CarState]` |
| `recent_events` | `list[TelemetryEvent]` (capped at 100, newest first) |

Atomic write contract: snapshot file is written via `tmp + os.replace` to avoid torn reads by the dashboard.

---

## 8. EventLogFile (on-disk format)

- Path: `logs/carrera-{YYYYMMDD-HHMMSS}-{pid}.jsonl`
- One `TelemetryEvent.model_dump_json()` per line, UTF-8, `\n` line terminator.
- Append-only within a single run; new file per process start.
- Companion `logs/laps-{YYYYMMDD-HHMMSS}-{pid}.csv` when CSV is enabled, with header `car_id,lap_number,lap_time_ms,timestamp_iso`.

---

## 9. Entity relationships

```
TelemetryEvent ──► EventBus ──► [StateManager, StorageWriter, DashboardSubscriber*]
                                       │             │
                                       ▼             ▼
                                 StateSnapshot   EventLogFile (+ CSV)
                                       │
                                       ▼
                                    Dashboard
```

*Dashboard does not subscribe directly in the MVP; it reads `state.json` written by `StateManager`. The seam remains so a websocket/REST subscriber can be added without core changes (R-008).
