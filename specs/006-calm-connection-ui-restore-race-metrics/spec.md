# Feature Specification: Calm Connection UI + Restore Race Metrics

**Feature Branch**: `006-calm-connection-ui-restore-race-metrics`  
**Created**: 2026-05-16  
**Status**: Draft  
**Input**: User description: "Calm Connection UI + Restore Race Metrics"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Calm Connection Indicator in Dashboard Header (Priority: P1)

A race operator needs a stable and compact Bluetooth status indicator so the header remains readable during rapid reconnect transitions.

**Why this priority**: The current verbose connection text causes visual noise and perceived instability during reconnect loops.

**Independent Test**: Open the dashboard while forcing connection-state transitions (`connecting`, `ready`, `reconnecting`, `error`, `disconnected`) and verify the main header shows only a single icon indicator without long status text.

**Acceptance Scenarios**:

1. **Given** the main dashboard header is rendered, **When** connection state changes, **Then** the header shows icon-only status and no verbose status text next to it.
2. **Given** connection state is one of `ready` or `connected`, **When** header renders, **Then** the indicator uses the green icon (`🟢`).
3. **Given** connection state is one of `connecting`, `scanning`, `subscribing`, or `reconnecting`, **When** header renders, **Then** the indicator uses the yellow icon (`🟡`).
4. **Given** connection state is `stale`, **When** header renders, **Then** the indicator uses the orange icon (`🟠`).
5. **Given** connection state is `error`, **When** header renders, **Then** the indicator uses the red icon (`🔴`).
6. **Given** connection state is `disconnected` or `manually_disconnected`, **When** header renders, **Then** the indicator uses the black icon (`⚫`).
7. **Given** connection state is missing or unknown, **When** header renders, **Then** the indicator uses the fallback icon (`⚪`).
8. **Given** detailed connection diagnostics are needed, **When** operator opens diagnostics/overflow panel, **Then** full details (state, device, MAC, last seen, retries, last error) remain available there.

---

### User Story 2 - Always Visible and Correct Race Metrics (Priority: P1)

A race operator needs race metrics to always be visible and updated correctly from live telemetry events.

**Why this priority**: Missing race metrics blocks race operation and defeats the primary purpose of the dashboard.

**Independent Test**: Run mock or live telemetry with lap updates and verify race metrics cards plus per-car metrics (including safety-car metric behavior) update continuously; verify placeholder values are shown when race data is missing.

**Acceptance Scenarios**:

1. **Given** dashboard loads with no active race, **When** metrics section renders, **Then** race metrics cards are still visible and show placeholders (`-`) instead of disappearing.
2. **Given** an active race exists, **When** snapshot updates, **Then** top-level race metrics (name, status, mode, elapsed, progress) render and update.
3. **Given** lap events are received, **When** state is updated, **Then** per-car metrics (`lap_count`, `latest_lap`, `best_lap`, `average_lap`) update correctly.
4. **Given** compatible lap payload variants are received (`lap` with `lap_time_ms`, `lap_completed` with `time_ms`), **When** events are normalized, **Then** both update the same internal lap metric path.
5. **Given** unknown car IDs or missing lap time fields appear, **When** event is processed, **Then** processing remains safe and dashboard continues rendering.
6. **Given** safety-car status is unavailable from upstream sources, **When** global metrics render, **Then** safety-car metric remains visible with a placeholder value.

---

### User Story 3 - Stable Layout with Collapsed Diagnostics (Priority: P2)

A race operator needs a stable dashboard layout during live operation without noisy debug output in the primary view.

**Why this priority**: Layout jumps and excessive debug text reduce readability in race-critical workflows.

**Independent Test**: Keep dashboard open during active telemetry flow and reconnect events; verify metric layout height remains stable and diagnostics are available only in collapsed sections.

**Acceptance Scenarios**:

1. **Given** dashboard renders race metrics, **When** telemetry refreshes, **Then** card/table layout remains stable (no disappearing sections).
2. **Given** diagnostics are needed, **When** operator expands diagnostics panel, **Then** panel shows debug context (last telemetry timestamp, active race id, lap events processed, cars in snapshot, last lap payload, last state update time).
3. **Given** dashboard is in normal operation, **When** diagnostics panel is collapsed, **Then** verbose debug text is not shown in main dashboard area.

### Edge Cases

- Connection state value is missing, malformed, or unknown: use fallback icon (`⚪`) and keep UI rendering stable.
- Active race exists but no lap events yet: show zero/placeholder car metrics while preserving configured car list.
- Telemetry includes car IDs outside 1..6: ignore safely and keep dashboard stable.
- Lap event missing lap duration field: ignore event for lap timing metrics but keep pipeline alive.
- Event stream contains reconnect loops: header remains icon-only without repeated verbose status banners.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST render connection status in the main dashboard header as icon-only with no long status text.
- **FR-002**: System MUST map connection states to icons exactly as defined: `ready|connected -> 🟢`, `connecting|scanning|subscribing|reconnecting -> 🟡`, `stale -> 🟠`, `error -> 🔴`, `disconnected|manually_disconnected -> ⚫`, fallback `unknown -> ⚪`.
- **FR-003**: System MUST keep detailed Bluetooth status fields available in diagnostics/overflow UI, not in the main header label.
- **FR-004**: System MUST provide or update a dashboard-ready race snapshot model containing race-level and car-level metrics.
- **FR-005**: System MUST always render a race metrics section even when there is no active race, using placeholder values where data is absent.
- **FR-006**: System MUST display race-level metrics: race name, race status, race mode, elapsed time, and progress.
- **FR-007**: System MUST display per-car metrics for configured cars: car id, driver name, lap count, latest lap, best lap, average lap, position (if calculable), fuel (if available), pit status (if available).
- **FR-008**: System MUST display global metrics: total laps, leader, fastest lap overall, and safety-car status; when safety-car status cannot be derived, the metric MUST remain visible with placeholder value.
- **FR-009**: System MUST normalize lap event variants (`lap.payload.lap_time_ms` and `lap_completed.payload.time_ms`) into one internal lap update path.
- **FR-010**: System MUST safely handle missing lap time and unknown car IDs without crashing or removing dashboard sections.
- **FR-011**: Dashboard metric sourcing MUST follow priority: state snapshot first, repository/race service second, in-memory telemetry fallback third.
- **FR-012**: System MUST expose a dedicated rendering entry point for race metrics (or equivalent cohesive render function) that is always executed during dashboard refresh.
- **FR-013**: System MUST provide a collapsed-by-default diagnostics section for race-metric debug signals.
- **FR-014**: Changes MUST remain targeted to this fix scope and avoid unrelated architecture refactors.
- **FR-015**: System MUST add/update tests for connection icon-only behavior, race metric rendering with and without active race, lap normalization compatibility, and metric calculations.

### Key Entities *(include if feature involves data)*

- **RaceDashboardSnapshot**: Dashboard-facing race state aggregate containing race-level and car-level metrics.
- **CarRaceMetrics**: Per-car metrics (`lap_count`, `latest`, `best`, `average`, `position`, `fuel`, `pit_active`) used by dashboard rendering.
- **ConnectionIndicatorState**: Minimal presentation mapping from internal connection state to icon color/symbol for header display.
- **LapNormalizationInput**: Event compatibility abstraction for `lap` and `lap_completed` payload shapes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Main dashboard header shows only one connection status icon and no verbose status text labels.
- **SC-002**: Detailed Bluetooth status remains accessible in diagnostics/overflow UI.
- **SC-003**: Race metrics section is always visible on dashboard (active and inactive race scenarios).
- **SC-004**: For incoming lap telemetry, per-car lap count/latest/best/average and global fastest/leader metrics update correctly no later than 1 second after event ingestion, independent of configured dashboard refresh interval.
- **SC-005**: Placeholder values are shown for missing data instead of hidden metric cards.
- **SC-006**: Safety-car metric is always present in the global metrics row and shows either a concrete state or placeholder value.
- **SC-007**: Added or updated acceptance and regression tests for this feature pass in the project's standard quality gate suite.

## Assumptions

- Existing race domain models and repository APIs remain authoritative for persisted race metadata.
- Dashboard refresh loop remains file-snapshot based and continues to provide periodic updates without architecture changes.
- Safety-car status may be unavailable in some telemetry paths and will be displayed via placeholder until present.
- Car focus remains canonical 1..6 slots.
- This fix is additive/targeted and does not redesign the event bus architecture.
