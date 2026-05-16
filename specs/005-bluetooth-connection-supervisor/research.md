# Phase 0 Research: Robust Bluetooth Connection Supervisor

## Decision 1: Keep lifecycle ownership in a long-running runtime supervisor

- Decision: A single runtime-owned BluetoothConnectionSupervisor owns connect/disconnect/reconnect state and outlives Streamlit rerenders.
- Rationale: Dashboard and runtime run in separate processes. UI-triggered rerenders cannot safely own transport lifecycle.
- Alternatives considered:
  - Keep lifecycle in dashboard callbacks (rejected: unstable ownership and rerun side effects).
  - Embed lifecycle in legacy runner only (rejected: weaker explicit desired-state controls for UI-driven operations).

## Decision 2: Use persisted runtime settings as process bridge for control intent

- Decision: Dashboard writes desired connection intent and commands (`connect`, `disconnect`, `scan`, `retry`) to runtime settings; supervisor consumes commands by sequence.
- Rationale: Existing file-backed settings are already used successfully for mock mode and provide simple, robust local IPC.
- Alternatives considered:
  - In-memory process-local channel (rejected: does not work across separate processes).
  - Add new network transport for commands (rejected: unnecessary complexity for local deployment).

## Decision 3: Use explicit state model with desired-state metadata

- Decision: Track explicit Bluetooth states and always include desired_connected and reconnect metadata in status snapshots.
- Rationale: Operators need to distinguish manual disconnect from transient failure and understand whether auto-reconnect should occur.
- Alternatives considered:
  - Infer state from sparse booleans (rejected: ambiguous UX and harder testability).
  - Expose raw adapter internals directly (rejected: leaky abstraction and unstable contract).

## Decision 4: Bounded reconnect backoff plus stale telemetry recovery

- Decision: Apply configurable reconnect backoff schedule with cap, and detect stale telemetry by monotonic timeout with optional reconnect-on-stale.
- Rationale: Prevents reconnect thrashing while still recovering from silent stalls where transport may appear connected but data flow is dead.
- Alternatives considered:
  - Fixed reconnect interval only (rejected: either too aggressive or too slow across conditions).
  - No stale detection (rejected: silent dead links remain undetected).

## Decision 5: Preserve simulator and Bluetooth independence

- Decision: Bluetooth actions never toggle mock mode; mock mode changes never implicitly modify Bluetooth desired state.
- Rationale: Required by feature scope and essential for predictable operator workflows during demos and tests.
- Alternatives considered:
  - Auto-switch modes on Bluetooth actions (rejected: surprising side effects).
  - Disable Bluetooth actions in mock mode (rejected: removes useful diagnostics and status visibility).

## Decision 6: Keep downstream compatibility via normalized lifecycle payloads

- Decision: Emit normalized connection_state telemetry payloads and enrich state snapshots with additive fields.
- Rationale: Existing consumers remain compatible while gaining richer status context.
- Alternatives considered:
  - Introduce a separate incompatible event type only for supervisor lifecycle (rejected: migration overhead without clear value).
  - Store status only in supervisor memory (rejected: dashboard and diagnostics lose visibility).
