# Feature Specification: Carrera Digital Telemetry Dashboard MVP

**Feature Branch**: `main`  
**Created**: 2026-05-15  
**Status**: Draft  
**Input**: User description: "Modular Python-based telemetry and visualization system for Carrera DIGITAL 124/132 race tracks using the Carrera AppConnect Bluetooth adapter, with full hardware-independent mock mode."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mock Mode End-to-End Telemetry (Priority: P1)

A hobbyist developer without access to Carrera hardware runs the application in mock mode and immediately observes a live dashboard with simulated 1–6 cars producing laps, fuel drain, and pit events. Events are persisted to a JSONL log file.

**Why this priority**: This is the MVP foundation. It proves the full stack (event model → bus → state → storage → dashboard) works without any BLE dependency, and unblocks all subsequent development.

**Independent Test**: Run `python -m src.main --mock` on a clean machine; open the Streamlit dashboard on the configured port; verify per-car lap counters increment, fuel decreases, occasional pit events appear, and a timestamped `logs/*.jsonl` file accumulates one JSON object per line per event.

**Acceptance Scenarios**:

1. **Given** no Carrera hardware is present, **When** the user starts the app with `--mock`, **Then** the dashboard renders connection state, per-car cards, and recent events within 2 seconds and updates at least once per second.
2. **Given** mock mode is running, **When** at least 60 seconds have elapsed, **Then** the JSONL log contains chronologically ordered lap, fuel, race-state, and pitlane events validating against the canonical event schema.
3. **Given** mock mode is running with `cars.count = 4`, **When** the dashboard renders, **Then** exactly 4 car cards are visible with independent lap, best-lap, fuel, and pit state.

---

### User Story 2 - Live Hardware Telemetry With Auto-Reconnect (Priority: P2)

An owner of a Carrera DIGITAL 124/132 set with an AppConnect adapter starts the application, the system discovers the adapter (or uses a configured MAC), connects, and streams live race telemetry to the dashboard. If the BLE link drops, the system automatically reconnects without operator intervention.

**Why this priority**: Hardware support is the headline value, but it is gated by adapter availability and `carreralib` quirks; it builds directly on the P1 stack with the same event model and dashboard.

**Independent Test**: With a Carrera AppConnect adapter powered on, run `python -m src.main` (no `--mock`); verify the connection state cycles through `scanning → connecting → connected`; physically toggle the adapter off/on and confirm the state machine transitions to `reconnecting → connected` and event flow resumes.

**Acceptance Scenarios**:

1. **Given** the adapter is reachable and `bluetooth.mac_address` is null, **When** the app starts, **Then** the dashboard reflects each connection state transition and begins emitting lap/race-state/fuel events normalized to the canonical schema within the configured scan timeout.
2. **Given** an active connection, **When** the adapter is powered off, **Then** the system enters `reconnecting`, logs the disconnect as a structured event, and reconnects within `reconnect_interval_seconds` after the adapter is restored — without restarting the process.
3. **Given** the configured MAC address is invalid or unreachable, **When** the scan times out, **Then** the system enters the `error` state, emits a structured error event, and does not crash the dashboard.

---

### User Story 3 - Race Replay From JSONL Logs (Priority: P3)

After a race session, the user inspects the JSONL log produced during the session to verify event coverage and (in a later iteration) feeds it into a replay/analytics module.

**Why this priority**: Persistence is mandatory for the MVP, but advanced replay/analytics are future extension points; only the log format and content guarantees are in scope here.

**Independent Test**: After completing a mock or live session, open the most recent log file; verify every line parses as a valid JSON object, conforms to the canonical event schema, and is monotonically ordered by `timestamp_monotonic_ms` within a single process run.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** the log file is read line-by-line, **Then** 100% of lines deserialize into the canonical event model with no schema errors.
2. **Given** `logging.csv_laps_enabled = true`, **When** at least one lap event has occurred, **Then** a companion CSV file with lap rows (car_id, lap_number, lap_time_ms, timestamp_iso) is also written.

---

### Edge Cases

- BLE adapter present but `carreralib` raises an unexpected exception during read → system must log a structured error event, not silently drop data, and remain in `connected` or transition to `error`.
- A telemetry field is reported by `carreralib` that has no canonical mapping → emit an event with `event_type = "raw"` or `"not_supported"` and preserve the raw payload in `raw_data`.
- Dashboard subscriber is slow → event bus must not block producers; backpressure strategy must be explicit (drop oldest vs. bounded queue) and documented.
- Log directory missing or read-only → storage layer creates it if missing, otherwise emits a structured warning and continues without crashing the pipeline.
- Multiple processes attempting to log to the same file → filenames must be timestamped to avoid collision; concurrent writes within one process must be serialized.
- Clock skew between wall clock and monotonic clock → both `timestamp_iso` and `timestamp_monotonic_ms` are always emitted; consumers prefer monotonic for ordering.

## Requirements *(mandatory)*

### Functional Requirements

#### Connectivity & Lifecycle

- **FR-001**: System MUST scan for Carrera AppConnect BLE devices on startup unless a fixed MAC address is configured. (Adapter-selection precedence — mock vs. live, with vs. without a MAC — is finalized in [002/FR-225](../002-race-controls/spec.md#mock-mode-toggle-us3): `--mock` > `--mac` > `runtime_settings.mock_mode`.)
- **FR-002**: System MUST support a configured MAC address that bypasses scanning. See FR-225 for the full precedence chain when combined with `--mock` and the persisted `runtime_settings.mock_mode`.
- **FR-003**: System MUST maintain a connection state machine with the states `disconnected`, `scanning`, `connecting`, `connected`, `reconnecting`, `error`.
- **FR-004**: System MUST automatically reconnect after a dropped BLE link, with a configurable retry interval. (Post-003 the cadence is exponential backoff capped at `bluetooth.max_reconnect_interval_seconds` per [003/FR-007](../003-live-adapter-carreralib/spec.md); the single-interval wording above is the original MVP shape.)
- **FR-005**: System MUST shut down gracefully on SIGINT/SIGTERM, flushing pending writes.
- **FR-006**: System MUST emit a structured event for every state transition.

#### Event Model & Bus

- **FR-007**: System MUST normalize every incoming telemetry signal into a canonical event with mandatory fields `timestamp_iso`, `timestamp_monotonic_ms`, `source`, `event_type`, `payload` and optional `car_id`, `controller_id`, `raw_data`, `metadata`.
- **FR-008**: System MUST validate events using Pydantic before dispatch.
- **FR-009**: System MUST distribute events through an internal pub/sub or queue-based bus that supports async consumers and multiple subscribers.
- **FR-010**: Producers MUST NOT be blocked indefinitely by slow consumers; the bus MUST define and document its backpressure policy.

#### Telemetry Coverage

- **FR-011**: System MUST emit canonical event types for at minimum: lap timing, race state, fuel values, controller input, speed, brake, pitlane events.
- **FR-012**: System MUST emit `event_type = "not_supported"` (or equivalent) with the raw payload preserved when `carreralib` reports a value that has no canonical mapping.
- **FR-013**: System MUST be able to emit raw/debug events behind a flag for future BLE reverse-engineering work. The flag is exposed both as the CLI option `--debug-raw` and the config key `logging.debug_raw_enabled` (off by default).

#### Persistence

- **FR-014**: System MUST persist every dispatched event to a JSONL file (one JSON object per line, append-only) under the configured log directory.
- **FR-015**: System MUST create the log directory automatically if missing.
- **FR-016**: System MUST use timestamped filenames to avoid collisions across runs.
- **FR-017**: System MUST optionally write a CSV file of lap events when enabled in configuration.
- **FR-018**: Storage writes MUST be fault-tolerant: a write error must not crash the pipeline.

#### State Management

- **FR-019**: System MUST maintain an in-memory state per car including latest telemetry, lap count, best lap, latest lap, fuel level, and pit status.
- **FR-020**: System MUST expose a snapshot interface to the dashboard rather than exposing raw events directly.
- **FR-021**: State MUST be updated only via subscribed events from the bus.

#### Dashboard

- **FR-022**: Dashboard MUST display connection state, current race state, per-car telemetry cards (1–6 cars), a recent-events stream, and aggregate race statistics.
- **FR-023**: Dashboard MUST auto-refresh between 500 ms and 1000 ms.
- **FR-024**: Dashboard MUST NOT contain any BLE or `carreralib` code; it only consumes state snapshots and event streams from the bus.
- **FR-025**: Dashboard MUST remain operational when the underlying client is in `disconnected`, `scanning`, `reconnecting`, or `error` states, surfacing the state to the user.

#### Mock Mode

- **FR-026**: System MUST provide a mock telemetry generator selectable via `--mock` CLI flag.
- **FR-027**: Mock mode MUST produce continuous lap, fuel, race-state, pitlane, and connection-state events for a configurable car count (1–6) with realistic timing variation.
- **FR-028**: Mock mode MUST be fully usable on a machine with no BLE hardware and no `carreralib` adapter present.

#### Configuration

- **FR-029**: System MUST load configuration from a YAML file with sections `bluetooth`, `logging`, `dashboard`, `cars`.
- **FR-030**: System MUST ship a `config.example.yaml` demonstrating every supported key.
- **FR-031**: System MUST apply sensible defaults when the configuration file is absent.

#### Logging & Errors

- **FR-032**: System MUST use structured logging (JSON-compatible) for connections, disconnects, telemetry parsing, errors, warnings, and reconnect attempts.
- **FR-033**: System MUST never silently swallow exceptions; every caught exception MUST produce either a structured warning/error log or a typed re-raise.

#### Testing

- **FR-034**: Project MUST include pytest-based tests for event-model validation, storage writer behavior, mock telemetry generator output, and state-manager transitions.

### Key Entities *(data)*

- **TelemetryEvent**: The canonical, immutable record of one observation. Carries timestamps (ISO wall-clock + monotonic ms), source identifier, event type, optional car/controller identifiers, structured payload, optional raw payload, and metadata. All downstream components consume this entity exclusively.
- **CarState**: In-memory aggregate per car id; holds latest lap number, latest lap time, best lap time, current fuel, pit status, and latest telemetry timestamp. Rebuilt by replaying events; never serialized except via dashboard snapshot.
- **RaceState**: Aggregate race-level status (e.g., idle, running, paused, finished) derived from race-state events.
- **ConnectionState**: Enumerated transport status (`disconnected`, `scanning`, `connecting`, `connected`, `reconnecting`, `error`) plus optional last error message and last-changed timestamp.
- **EventLogFile**: A timestamped JSONL file on disk; append-only; one TelemetryEvent per line.
- **AppConfig**: Validated configuration object derived from YAML, exposing typed sections for bluetooth, logging, dashboard, and cars.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with no Carrera hardware can clone the repo, install requirements, and have a live dashboard with simulated telemetry running in under 5 minutes following the README. (Verified manually against the quickstart; not pinned by an automated harness.)
- **SC-002**: In mock mode with 6 cars, the dashboard refreshes at the configured interval (500–1000 ms) without lag or dropped frames for at least a 10-minute continuous run. ("Without lag or dropped frames" is a qualitative, manually-verified criterion; the only automated proxy is the 60-events/s p95 < 50 ms storage budget from SC-006-adjacent benchmarks.)
- **SC-003**: 100% of events emitted by the system validate against the canonical TelemetryEvent schema (verified by tests and by replaying a recorded JSONL file).
- **SC-004**: A simulated BLE disconnect causes the system to reach `connected` again within 2× `reconnect_interval_seconds` without manual intervention.
- **SC-005**: Test suite (`pytest`) covers event model, storage, mock client, and state manager with all tests passing locally and in CI.
- **SC-006**: README enables a new contributor to (a) start mock mode, (b) configure hardware mode, (c) locate logs, (d) extend with a new event consumer, without reading source code.

## Assumptions

- `carreralib` exposes a usable Python API for the AppConnect adapter; exact method/attribute names may differ between versions, so the Carrera client wraps `carreralib` behind an adapter interface with explicit TODO markers for hardware verification.
- BLE reverse engineering of undocumented packets is out of scope for the MVP; raw packet support is provided only as a passthrough event type.
- Streamlit is acceptable for the MVP dashboard; a future web/mobile client may replace it without changing the event model or bus.
- The MVP runs as a single Python process on a developer workstation (Linux/macOS/Windows); multi-process or remote-streaming scenarios are future extension points.
- One simultaneous user of the dashboard per process; concurrent multi-user access is out of scope.
- Time synchronization between adapter and host is best-effort; the host's monotonic clock is authoritative for event ordering within a single process run.
