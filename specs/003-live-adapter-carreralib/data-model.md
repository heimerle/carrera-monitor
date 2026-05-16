# Data Model: Live Continuity Hardening

**Feature**: 003-live-adapter-carreralib  
**Date**: 2026-05-16  
**Scope**: Auto car detection (max 6), reconnect persistence, and link-health stabilization.

## Entities

### 1. `CarSlotMapping` (runtime)

Canonicalizes hardware slot/address values into race-domain `car_id` values.

| Field | Type | Description |
|---|---|---|
| `mapping_mode` | `Literal["zero_based", "one_based", "explicit"]` | How raw slot values are interpreted. |
| `slot_to_car_id` | `dict[int, int]` | Canonical mapping into `1..6`. |
| `locked` | `bool` | When true, mapping remains stable for the race session. |
| `source` | `Literal["status", "timer", "config"]` | Origin used to build mapping. |

**Validation Rules**:
- Mapped `car_id` values MUST be within `1..6`.
- A single raw slot MUST map to exactly one canonical `car_id` in a session.
- Mapping lock MUST only change at race boundaries (start/new race).

### 2. `ActiveCarSet` (runtime + snapshot)

Represents auto-detected active cars in the current session.

| Field | Type | Description |
|---|---|---|
| `active_car_ids` | `list[int]` | Sorted unique canonical IDs currently active. |
| `active_car_count` | `int` | Number of active cars (`1..6`, derived). |
| `last_seen_ms` | `dict[int, int]` | Last monotonic activity timestamp per car. |
| `window_ms` | `int` | Detection horizon for activity. |

**Validation Rules**:
- `active_car_count == len(active_car_ids)`.
- `active_car_count` is capped at 6.
- IDs in `active_car_ids` MUST be in `1..6`.

### 3. `LiveLapCheckpoint` (persistent)

Durable continuity checkpoint for reconnect and process restart.

| Field | Type | Description |
|---|---|---|
| `id` | `int` | PK |
| `race_id` | `int` | FK to race |
| `car_id` | `int` | Canonical car ID (`1..6`) |
| `last_cu_timestamp_ms` | `int` | Last CU crossing timestamp used for lap delta |
| `lap_count` | `int` | Last accepted lap count |
| `updated_at` | `datetime` | Last checkpoint update |

**Constraints**:
- Unique `(race_id, car_id)`.
- `lap_count >= 0`.
- `last_cu_timestamp_ms >= 0`.

### 4. `LapIngestIdentity` (persistent uniqueness)

Idempotency identity for lap insert path.

| Field | Type | Description |
|---|---|---|
| `race_id` | `int` | Race scope |
| `car_id` | `int` | Canonical car |
| `cu_timestamp_ms` | `int` | Raw crossing identity from CU clock |

**Constraint**:
- Unique `(race_id, car_id, cu_timestamp_ms)` to avoid duplicate writes during reconnect replay.

### 5. `LinkHealthState` (runtime + event)

Health state used for reconnect decisions and observability.

| Field | Type | Description |
|---|---|---|
| `state` | `Literal["healthy", "degraded", "stalled", "reconnecting"]` | Link-health state machine |
| `timeout_streak` | `int` | Consecutive poll timeouts |
| `last_frame_at_ms` | `int` | Last successful frame timestamp |
| `reason` | `str | None` | Most recent transition reason |

## Relationships

```text
LiveCarreraAdapter
  └─ produces raw per-slot events
      └─ CarSlotMapping normalizes slot -> car_id (1..6)
          ├─ ActiveCarSet tracks active_car_ids/count
          └─ RaceTelemetryRunner / RaceService ingest
              ├─ LapIngestIdentity enforces idempotency
              └─ LiveLapCheckpoint persists continuity

LinkHealthState (watchdog/probe) drives reconnect transitions and diagnostics.
```

## State Transitions

### A. Link-health transitions

```text
healthy -> degraded      (timeout_streak >= warning threshold)
degraded -> stalled      (timeout_streak >= hard threshold)
stalled -> reconnecting  (reconnect initiated)
reconnecting -> healthy  (first valid frame after reconnect)
```

### B. Active car detection lifecycle

```text
empty -> learning -> stable
stable -> learning (on race restart or explicit remap)
```

### C. Lap continuity lifecycle

```text
checkpoint_miss -> checkpoint_seeded -> checkpoint_updated (per lap)
checkpoint_updated -> restored (after reconnect/startup)
```

## Invariants

- Race-domain car IDs used for persistence/reporting MUST remain in `1..6`.
- Reconnect MUST NOT reset persisted lap continuity for active race.
- Dashboard lap counters MUST NOT reset due to transient reconnect noise alone.
- Idempotent lap ingest MUST treat replayed crossings as no-op, not failure.
