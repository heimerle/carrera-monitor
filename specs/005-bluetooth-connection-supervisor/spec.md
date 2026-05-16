# Feature Specification: Robust Bluetooth Connection Supervisor

**Feature Branch**: `005-bluetooth-connection-supervisor`  
**Created**: 2026-05-16  
**Status**: Draft  
**Input**: User description: "Robust Bluetooth Connection Supervisor"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep Live Telemetry Connected Reliably (Priority: P1)

A race operator needs the Bluetooth link to recover automatically from transient drops so telemetry remains usable during live operation without manual restarts.

**Why this priority**: Link instability during a race can interrupt race visibility and operator trust. Automatic recovery is the core value of this feature.

**Independent Test**: Start in connected state, induce an unexpected disconnect, and verify the system transitions to reconnecting and returns to `ready` (the feature definition of usable connected state) without restarting the application.

**Acceptance Scenarios**:

1. **Given** the desired connection state is connected, **When** the transport drops unexpectedly, **Then** the system transitions to reconnecting and retries automatically using a bounded retry policy.
2. **Given** reconnect succeeds, **When** telemetry resumes, **Then** the connection state returns to `ready` and clears prior transient error condition.
3. **Given** reconnect keeps failing, **When** maximum retry delay is reached, **Then** retries continue at that cap and status remains observable to the operator.

---

### User Story 2 - Control Bluetooth Lifecycle From the Dashboard (Priority: P1)

A dashboard user needs explicit controls to connect, disconnect, scan, and retry while always seeing the current Bluetooth health and desired state.

**Why this priority**: Operators must be able to deliberately control Bluetooth behavior and understand current status without using terminal commands.

**Independent Test**: Use dashboard controls to request connect, disconnect, scan, and retry; verify each request is applied by the runtime lifecycle owner and reflected in status output.

**Acceptance Scenarios**:

1. **Given** a user requests connect, **When** the runtime processes the request, **Then** desired state becomes connected and lifecycle transitions are visible in the status view.
2. **Given** a user requests manual disconnect, **When** disconnect is applied, **Then** the system enters manually disconnected state and does not auto-reconnect until a new explicit connect or retry request.
3. **Given** a user requests scan, **When** device discovery completes, **Then** discovered devices or an explicit empty-state message is shown.
4. **Given** status changes occur, **When** the dashboard refreshes, **Then** state, selected device identity, reconnect attempts, last seen telemetry time, and last error are visible.

---

### User Story 3 - Preserve Safe Coexistence With Simulator Mode (Priority: P2)

A team member using simulator mode needs Bluetooth lifecycle actions to remain isolated so simulator behavior and Bluetooth behavior do not unintentionally change each other.

**Why this priority**: Independent control paths reduce operator confusion and prevent accidental mode changes during testing or demos.

**Independent Test**: Enable simulator mode, perform Bluetooth connect/disconnect/scan/retry actions, and verify simulator mode remains unchanged throughout.

**Acceptance Scenarios**:

1. **Given** simulator mode is enabled, **When** Bluetooth actions are requested, **Then** simulator mode state does not change.
2. **Given** simulator mode toggles, **When** no Bluetooth action is requested, **Then** Bluetooth desired state is unchanged.

### Edge Cases

- Telemetry becomes stale without a hard disconnect: system marks stale state and applies configured stale-recovery behavior.
- Manual disconnect is requested while an automatic reconnect attempt is in progress: manual intent wins and reconnect loop stops.
- Device scan returns no candidates: user receives a clear empty-state response instead of ambiguous status.
- Runtime settings file cannot be written: user receives an actionable error and previous persisted values remain intact.
- Connection errors occur repeatedly: status remains observable and retry remains user-invokable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain a single long-running Bluetooth lifecycle owner independent of dashboard rerender cycles.
- **FR-002**: System MUST support explicit desired connection intent (`connected` or `disconnected`) and converge runtime behavior to that intent.
- **FR-003**: System MUST provide user actions for connect, disconnect, scan, and retry.
- **FR-004**: System MUST suppress automatic reconnect after a manual disconnect until the user explicitly requests connect or retry.
- **FR-005**: System MUST automatically attempt reconnect after unexpected disconnect when desired state remains connected.
- **FR-006**: System MUST use a bounded reconnect delay strategy with configurable schedule and cap.
- **FR-007**: System MUST detect stale telemetry after a configurable timeout and surface stale state.
- **FR-008**: System MUST optionally trigger reconnect behavior when stale state is detected and stale-reconnect is enabled.
- **FR-009**: System MUST expose a normalized connection status snapshot containing at minimum current state, desired state, selected device identity, reconnect attempts, last seen telemetry timestamp, and last error.
- **FR-010**: System MUST emit normalized lifecycle transition events with state and reason metadata for downstream consumers.
- **FR-011**: System MUST persist runtime Bluetooth control intent so dashboard requests can be processed by the runtime lifecycle owner.
- **FR-012**: System MUST support selecting a target device identity that is persisted and reused until changed.
- **FR-013**: System MUST ensure dashboard Bluetooth actions do not mutate simulator mode state.
- **FR-014**: System MUST ensure simulator mode changes do not implicitly change Bluetooth desired state.
- **FR-015**: System MUST shutdown Bluetooth lifecycle operations cleanly and release active connections during process stop.
- **FR-016**: System MUST preserve backward-compatible behavior for existing telemetry consumers by retaining `connection_state` event type and existing snapshot fields (`state`, `since_ms`, `last_error`, `reason`, `timeout_streak`) while allowing additive fields.

### Key Entities *(include if feature involves data)*

- **BluetoothConnectionStatus**: Snapshot of lifecycle state, desired state, selected device details, reconnect metadata, last seen telemetry time, and latest error.
- **BluetoothControlRequest**: Persisted user intent for connect, disconnect, scan, or retry actions, including ordering metadata.
- **BluetoothDevice**: Normalized discovered device identity used for selection and display.
- **BluetoothLifecycleEvent**: Transition event record containing current state, prior state when applicable, timestamp, and reason metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In at least 19 of 20 induced transient disconnect trials (>=95%), the system re-enters `ready` without process restart.
- **SC-002**: Manual disconnect prevents automatic reconnect attempts for a 10-minute observation window until an explicit user reconnect action occurs.
- **SC-003**: Dashboard status reflects lifecycle transitions and key metadata updates within 1 second of each transition.
- **SC-004**: Operators can complete connect, disconnect, scan, and retry actions from the dashboard without terminal interaction in all scripted acceptance scenarios.
- **SC-005**: In simulator-enabled acceptance scenarios, Bluetooth actions produce zero unintended simulator mode state changes.

## Assumptions

- For this feature, "usable connected state" is defined as lifecycle state `ready`.
- The feature targets one active Bluetooth connection session at a time per runtime process.
- Operators have sufficient platform permissions to use local Bluetooth hardware.
- Existing runtime settings persistence is available and writable under normal operation.
- Device discovery latency can vary by environment, but user feedback is always shown for scan outcomes.
- This feature does not introduce multi-runtime synchronization across different hosts.
