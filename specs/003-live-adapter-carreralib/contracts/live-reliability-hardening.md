# Contract: Live Reliability Hardening

**Feature**: 003-live-adapter-carreralib  
**Date**: 2026-05-16  
**Scope**: Auto car detection (max 6), reconnect continuity persistence, and Bluetooth liveness policy.

## 1. Car Identity Contract

### Canonical Range

- All race-domain `car_id` values used for persistence, standings, and dashboard race views MUST be in `1..6`.
- Raw hardware slots outside canonical range MUST NOT be persisted as race laps/events.

### Mapping Behavior

- The live pipeline MUST normalize raw slot/address values into canonical `car_id` values before race ingestion.
- Mapping mode (`zero_based`, `one_based`, or explicit override) MUST remain stable for the active race session.
- Mapping decisions MUST be logged with structured metadata (`raw_slot`, `canonical_car_id`, `mapping_mode`).

## 2. Auto Active-Car Detection Contract

- System MUST publish `active_car_ids` and `active_car_count` derived from recent canonical per-car telemetry activity.
- `active_car_count` MUST satisfy `1 <= active_car_count <= 6` when activity exists.
- Detection MUST use more than lap events alone (for example fuel/pit/speed/lap) to converge early.
- Active-car detection MUST be monotonic within a short smoothing window (no per-tick oscillation).

## 3. Reconnect Continuity Contract

### Durable Checkpointing

- For each active race/car, system MUST persist continuity checkpoint data:
  - `last_cu_timestamp_ms`
  - `lap_count`
  - `updated_at`
- On reconnect and startup recovery, checkpoint data MUST be restored before lap ingest resumes.

### Idempotent Lap Ingest

- Lap ingest MUST be idempotent using identity `(race_id, car_id, cu_timestamp_ms)`.
- Replay of an already-ingested crossing MUST be treated as no-op, not as fatal error.
- Duplicate suppression MUST be observable via structured logs.

### Race-State Preservation

- Reconnect noise MUST NOT reset dashboard lap aggregates.
- Lap reset MUST only occur on explicit race lifecycle transitions (new race start, finish, cancel).

## 4. Bluetooth Liveness Contract

### Probe-Driven Policy

- Primary reconnect trigger MUST be liveness failure (timeout streak/watchdog), not periodic forced reconnect.
- Periodic forced reconnect, if configured, MUST default disabled and MUST NOT run while race status is `running`.

### Health States

- System MUST expose at least these health states:
  - `healthy`
  - `degraded`
  - `stalled`
  - `reconnecting`
- Transitions MUST be accompanied by reason metadata.

## 5. Configuration Contract

Expected knobs:

```yaml
bluetooth:
  reconnect_interval_seconds: int >= 1
  max_reconnect_interval_seconds: int >= reconnect_interval_seconds
  idle_timeout_seconds: int >= 3
  idle_warning_seconds: int >= 1 and < idle_timeout_seconds
  periodic_forced_reconnect_seconds: int >= 0
  periodic_reconnect_only_when_not_running: bool
```

Default policy:

- `periodic_forced_reconnect_seconds = 0`
- `periodic_reconnect_only_when_not_running = true`

## 6. Test Contract

Minimum required tests for this hardening slice:

- Slot normalization tests ensure canonical max 6 behavior.
- Active-car detection tests for 1-car and multi-car sessions.
- Reconnect continuity tests prove lap count continuity and no duplicate-loss behavior.
- Restart recovery test validates checkpoint restore path.
- Link-health policy tests validate probe-driven transitions and periodic-reconnect guard.