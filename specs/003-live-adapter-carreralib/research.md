# Phase 0 Research: Live Continuity Hardening

**Feature**: 003-live-adapter-carreralib  
**Date**: 2026-05-16  
**Scope**: Auto car-count detection (max 6), reconnect data persistence, and Bluetooth stability policy.

## Decision 1: Canonical car identity must be capped to 1..6 in race pathways

- **Decision**: Introduce canonical slot normalization in the live pipeline and enforce max 6 for race/state persistence. Hardware slots outside canonical range are logged as diagnostics and excluded from race math.
- **Rationale**: Current runtime can emit slots 7/8 in some status payload paths while race schema and UI are 6-car constrained. The mismatch causes instability and phantom-car effects.
- **Alternatives considered**:
  - Keep 8-slot acceptance globally: rejected, because race domain is explicitly max 6.
  - Filter only in dashboard rendering: rejected, because invalid IDs would still contaminate ingest.

## Decision 2: Auto-detect active car count from live telemetry, not manual default

- **Decision**: Add an `ActiveCarDetector` that derives `active_car_ids` and `active_car_count` from recent canonical per-car events (lap/fuel/pit/speed), with a hard cap of 6.
- **Rationale**: Driver-count input is currently manual and static; live sessions should adapt to actual observed cars.
- **Alternatives considered**:
  - Keep manual driver count only: rejected, does not satisfy requirement.
  - Infer only from lap events: rejected, too slow before first completed lap.

## Decision 3: Persist lap continuity checkpoints durably

- **Decision**: Persist per-race/per-car continuity checkpoints (last CU timestamp, lap counter, last processed crossing marker) in SQLite and restore them on reconnect and startup.
- **Rationale**: Reconnect currently recreates adapter-local timer state, which can restart lap numbering and cause duplicate/drop behavior.
- **Alternatives considered**:
  - In-memory carry-over only: rejected, does not survive process restart.
  - Periodic snapshot file only: rejected, weaker transactional guarantees than DB.

## Decision 4: Make lap ingest idempotent under reconnects

- **Decision**: Add an idempotency key based on race + canonical car + CU crossing identity, and treat duplicate ingest as no-op instead of generic error.
- **Rationale**: Reconnects can replay boundaries; idempotency avoids accidental data loss from unique collisions and exception-based drops.
- **Alternatives considered**:
  - Remove uniqueness constraints: rejected, risks true duplicate laps.
  - Keep current swallow-on-error behavior: rejected, hides data loss.

## Decision 5: Prevent false dashboard resets on reconnect noise

- **Decision**: Reset visible lap aggregates only on explicit race lifecycle events (start/finish/cancel) and not on transient raw idle state during reconnect.
- **Rationale**: Raw race-state transitions around reconnect can currently make race data appear "gone" even when persistence still exists.
- **Alternatives considered**:
  - Keep raw idle reset semantics: rejected, directly linked to operator confusion.
  - Debounce idle only: partially helpful, still reconnect-fragile.

## Decision 6: Use probe-driven reconnect, not periodic forced reconnect during running race

- **Decision**: Keep watchdog/probe-triggered reconnect as primary policy. Optional periodic maintenance reconnect may exist, but disabled by default and only allowed when race is not running.
- **Rationale**: Forced reconnect on a timer introduces predictable blind windows and can drop laps during active racing.
- **Alternatives considered**:
  - Forced reconnect every X ms always-on: rejected, race-correctness risk.
  - No reconnect hardening: rejected, does not address real AppConnect stalls.

## Decision 7: Expose explicit link-health configuration and diagnostics

- **Decision**: Add explicit config knobs for soft/hard liveness thresholds and max reconnect backoff wiring; emit structured diagnostics (`reason`, `timeout_streak`, `restored_from_checkpoint`).
- **Rationale**: Operators need transparent behavior for troubleshooting, and tests need deterministic hooks.
- **Alternatives considered**:
  - Implicit hardcoded thresholds only: rejected, harder to tune and validate.

## Open Questions Resolved

- **Q1**: "Wie viele Autos sind gültig?" → Canonical race domain is max 6.
- **Q2**: "Warum sind nach Reconnect Daten weg?" → Combination of reconnect-local lap state reset and reset-prone state semantics; both addressed by Decisions 3-5.
- **Q3**: "Heartbeat oder periodischer Reconnect?" → Probe/watchdog first; periodic reconnect only optional and non-running.
