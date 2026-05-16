# Phase 0 Research: Manual Bluetooth Overflow Workflow

## Decision 1: Use a service abstraction with async-capable internals and synchronous UI trigger boundaries

- Decision: Keep Streamlit action handlers synchronous at the UI boundary, but delegate scan/connect/disconnect operations to a dedicated Bluetooth service that can internally use async primitives.
- Rationale: Streamlit rerun semantics favor short, deterministic callbacks. A service boundary enables non-blocking progress updates and future migration to background workers without UI rewrites.
- Alternatives considered:
  - Call low-level BLE APIs directly in `dashboard.py` (rejected: tight coupling and hard-to-test state logic).
  - Move all BLE operations to `src.main` only (rejected: no interactive manual control from the dashboard).

## Decision 2: Model connection lifecycle explicitly and publish transitions on EventBus

- Decision: Represent state as one of `DISCONNECTED`, `SCANNING`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, `ERROR`, and emit transition events to EventBus.
- Rationale: Explicit lifecycle improves observability, retry behavior, and UI consistency while preserving existing telemetry architecture.
- Alternatives considered:
  - Derive UI state from ad-hoc booleans in session state (rejected: fragile and difficult to integrate with non-UI components).
  - Use only logs without state events (rejected: insufficient for deterministic UI rendering).

## Decision 3: Keep simulator/mock mode orthogonal to Bluetooth connection state

- Decision: Bluetooth state transitions do not toggle simulator/mock mode and simulator controls do not mutate Bluetooth state.
- Rationale: Requirement explicitly asks for coexistence independence. This prevents hidden side effects and accidental mode flips.
- Alternatives considered:
  - Auto-disable simulator on Bluetooth connect (rejected: violates separation of concerns).
  - Block Bluetooth controls while in simulator mode (rejected: unnecessary restriction and poorer operator UX).

## Decision 4: Retry is user-driven and bounded

- Decision: On connect failure, transition to `ERROR`, render actionable message, and allow explicit retry via `Connect Bluetooth` action. Optionally map immediate retry path to `RECONNECTING` if previous state was `CONNECTED`.
- Rationale: Predictable UX, no runaway loops, and aligns with existing explicit-control dashboard patterns.
- Alternatives considered:
  - Automatic infinite reconnect loop (rejected: noisy and potentially disruptive).
  - No retry affordance (rejected: fails usability requirement).

## Decision 5: Normalize scan results to stable device objects

- Decision: Return scan results as normalized objects containing `mac`, `name`, and optional `rssi` when available; UI contract may display only `mac` and `name` for v1.
- Rationale: Stable shape improves testability and future extensibility while supporting current tuple-based implementation compatibility.
- Alternatives considered:
  - Keep raw tuples everywhere (rejected: weak schema clarity).
  - Expose backend-specific BLE payloads (rejected: leaks transport details into UI).

## Decision 6: Configurable timeout with safe default

- Decision: Define a scan timeout setting with a conservative default (for example 3-5 seconds) and a hard upper bound to protect UI responsiveness.
- Rationale: Satisfies timeout configurability without sacrificing perceived responsiveness.
- Alternatives considered:
  - Fixed hardcoded timeout only (rejected: does not satisfy requirement).
  - Unbounded scan duration (rejected: can freeze user workflow).
