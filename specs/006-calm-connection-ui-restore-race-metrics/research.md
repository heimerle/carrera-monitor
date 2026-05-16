# Research: Calm Connection UI + Restore Race Metrics

## Decision 1: Header connection status should be icon-only
- Decision: Render a single icon in the dashboard header for connection state and move verbose connection text/details to a collapsed diagnostics section.
- Rationale: Operators need low-noise, high-glance visibility during reconnect cycles; icon-only status reduces layout churn and cognitive load.
- Alternatives considered:
  - Keep text plus icon in header: rejected because reconnect transitions produce distracting label changes.
  - Hide connection status entirely: rejected because operators still need immediate connection awareness.

## Decision 2: Normalize connection states with explicit color/icon mapping
- Decision: Use a deterministic mapping for all known states, including fallback for unknown state.
- Rationale: Guarantees consistent operator feedback and stable behavior across all runtime states.
- Alternatives considered:
  - Use only color CSS without icon symbol: rejected because color-only cues are less explicit and less accessible.
  - Group many states into a single icon: rejected because transient phases (`connecting`, `reconnecting`, `stale`, `error`) need distinct operational meaning.

## Decision 3: Always render race metrics section with placeholders
- Decision: Keep race metrics cards/table visible at all times; when data is missing, show placeholders (`-`) rather than removing UI blocks.
- Rationale: Stable layout improves operability and makes data absence explicit instead of ambiguous.
- Alternatives considered:
  - Hide metric section when no active race: rejected because it appears broken and causes UI jump.
  - Show empty table without placeholders: rejected because placeholders communicate expected data shape more clearly.

## Decision 4: Introduce a dashboard-ready race snapshot aggregate
- Decision: Add/extend a `RaceDashboardSnapshot` payload from state assembly, including race-level fields and per-car metric fields.
- Rationale: Dashboard rendering should consume one stable model rather than combining many ad-hoc sources inline.
- Alternatives considered:
  - Query repository directly from dashboard render path only: rejected because it increases render-path coupling and latency variability.
  - Keep fully implicit dictionary structures: rejected because fixed schema is easier to test and maintain.

## Decision 5: Support both lap event payload variants via normalization
- Decision: Normalize both `lap.payload.lap_time_ms` and `lap_completed.payload.time_ms` into one internal lap-update path.
- Rationale: Existing telemetry sources already emit both variants; compatibility is required to restore metrics reliably.
- Alternatives considered:
  - Accept only one variant and drop others: rejected because it would recreate missing metrics in mixed environments.
  - Branch rendering by event type: rejected because normalization belongs in ingestion/state logic, not UI.

## Decision 6: Maintain strict safety for malformed telemetry
- Decision: Ignore unknown car IDs and malformed lap payloads without throwing, while recording diagnostics counters/last payload.
- Rationale: Live telemetry is noisy and dashboard must remain available even when some events are invalid.
- Alternatives considered:
  - Raise on malformed payload: rejected because one bad frame should not disrupt race operation.
  - Silently drop without diagnostics: rejected because operators and developers need traceability.

## Decision 7: Preserve source-priority order for metric hydration
- Decision: Hydrate dashboard metrics using this order: state snapshot first, race service/repository second, in-memory telemetry fallback third.
- Rationale: Matches existing architecture and allows resilient display when one source lags.
- Alternatives considered:
  - Repository-only reads: rejected because this can lag behind near-real-time telemetry.
  - Telemetry-only reads: rejected because persisted race metadata is still required for names/status context.
