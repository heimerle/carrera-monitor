# Phase 0 Research: live-adapter-carreralib

**Feature**: 003-live-adapter-carreralib
**Date**: 2026-05-16
**Status**: Retroactive — decisions captured after the fact from PRs #9, #10, #12, #14.

No `NEEDS CLARIFICATION` markers remain in the Technical Context; this slice
was implemented before being specified, so every decision is already
empirically validated by the test suite on `main`.

## Decisions

### D-001 — Use the third-party `carreralib` library for the live adapter

- **Decision**: Wrap [carreralib](https://github.com/jasonp/carreralib) inside `LiveCarreraAdapter` rather than implementing the Carrera CU BLE protocol from scratch.
- **Rationale**: carreralib already speaks both the CU's BLE profile and the legacy serial bridge, exposes typed `Status`/`Timer` payloads, and is maintained against the actual hardware. Reimplementing the protocol would duplicate non-trivial bit-level parsing and re-validate on every CU firmware revision.
- **Alternatives considered**:
  - Hand-rolled `bleak`-based BLE client — rejected: would re-derive the wire format and lose carreralib's `scan()` helper.
  - `pyserial` direct + custom framing — rejected: only covers the legacy bridge, not BLE.

### D-002 — One-shot `--scan` CLI mode lives in `src/main.py`

- **Decision**: Implement adapter discovery as a flag on the existing CLI (`python -m src.main --scan`) that short-circuits before any pipeline wiring runs, prints `<MAC>\t<name>` lines to stdout, and exits 0.
- **Rationale**: Operators already invoke `python -m src.main` to start sessions; a sibling flag avoids introducing a second entry point and reuses logging/config loading. Tab-separated output is trivially parseable by shell pipelines and humans.
- **Alternatives considered**:
  - Separate `python -m src.scan` script — rejected: doubles the CLI surface and config plumbing.
  - JSON-formatted scan output — rejected for now: the human-readable TSV is easier to eyeball during venue setup; JSON can be added behind a future `--format` flag if needed.

### D-003 — Surface reader-task exceptions through `events()`

- **Decision**: `LiveCarreraAdapter.events()` re-raises exceptions stored by its background reader task instead of returning silently when the internal queue empties. Implemented in PR #14.
- **Rationale**: The supervisor (`CarreraClientRunner`) needs an observable signal to enter the reconnect path. The pre-PR-#14 code returned an empty iterator on reader failure, causing the runner to think the connection was healthy while no events arrived — i.e. a silent hang.
- **Alternatives considered**:
  - Heartbeat sentinel events on the queue — rejected: complicates the queue type and conflates control-plane signals with telemetry events.
  - Separate "health" callback — rejected: would require parallel plumbing through the runner; re-raising through `events()` keeps the single iteration point.

### D-004 — Skip `cu.reset()` on reconnect attempts (`attempt > 0`)

- **Decision**: The adapter carries a `_reset_on_connect: bool` flag (default `True`); the runner clears it before the second and subsequent reconnect attempts via a `hasattr`-guarded assignment. Implemented in PR #14.
- **Rationale**: `cu.reset()` zeroes the CU's internal race clock. Calling it on every reconnect would invalidate the race after any transient drop. Skipping it preserves lap timing continuity across drops while still allowing the very first connect of a runner lifecycle to start from a known-good state.
- **Alternatives considered**:
  - Always skip `cu.reset()` — rejected: leaves the first connect non-deterministic if the CU was left in a weird state from a prior process.
  - Always call `cu.reset()` — rejected: causes the bug this decision exists to fix.
  - Pass the flag through a runner→adapter factory call — rejected: would break the existing zero-arg adapter factory contract relied on by tests like `FlakyAdapter`. The `hasattr` guard preserves that contract.

### D-005 — Exponential reconnect backoff capped at `max_reconnect_interval_seconds`

- **Decision**: `CarreraClientRunner` doubles its sleep between failed reconnect attempts (1 → 2 → 4 → 8 → …) starting from `reconnect_interval_seconds`, capped at `max_reconnect_interval_seconds` (default 30s). A successful connect resets backoff to the initial value. Implemented in PR #14.
- **Rationale**: Constant short retries spam the BLE stack and the CU during prolonged outages (radio interference, CU powered off). Exponential backoff with a cap is the standard pattern; the cap keeps reconnect latency bounded once the obstacle clears.
- **Alternatives considered**:
  - Fixed interval (pre-PR-#14 behavior) — rejected: see above.
  - Jittered exponential backoff — rejected for now: single-process single-CU, so thundering-herd is not a concern; can be added later if multi-process scenarios appear.
  - User-tunable backoff curve — rejected: two knobs (`initial`, `max`) already cover the practical configuration space.

### D-006 — Configuration clamp: `max ≥ initial`

- **Decision**: In `CarreraClientRunner.__init__`, the effective max is `max(max_reconnect_interval_seconds, reconnect_interval_seconds)`. Implemented in PR #14.
- **Rationale**: A user-configured max smaller than the initial interval is almost certainly a typo. Clamping is harmless, deterministic, and avoids defining backoff semantics in a degenerate region.
- **Alternatives considered**:
  - Raise on inconsistent config — rejected: too punishing; "obviously degenerate" inputs are best clamped silently with a structured log line on later iteration.

### D-007 — `carreralib.TimeoutError` is non-fatal

- **Decision**: Catch `carreralib.TimeoutError` in both the connect and poll paths; emit a structured diagnostic and route through the existing reconnect path rather than propagate. Implemented in PR #10.
- **Rationale**: carreralib raises `TimeoutError` periodically (≈ once per second) when idle. Pre-PR-#10, this could crash the runner during pre-race setup when the CU is powered but not yet broadcasting. Treating timeouts as "no event this tick" matches operator expectations.
- **Alternatives considered**:
  - Suppress timeouts entirely (no diagnostic) — rejected: a sustained burst of timeouts is a real signal that something is wrong; the diagnostic preserves observability.

### D-008 — BLE idle watchdog forces reconnect

- **Decision**: A timer-driven watchdog inside the adapter forces a reconnect when no `Status` or `Timer` event has been observed within a configurable idle window. Implemented in PR #12.
- **Rationale**: The CU's BLE bridge ("AppConnect") sometimes stops forwarding frames without dropping the socket. A healthy-looking socket with no data is invisible to the runner's reconnect logic; the watchdog gives the host an active probe.
- **Alternatives considered**:
  - Application-level keepalive frames from the CU — rejected: requires CU firmware changes outside our control.
  - Rely solely on BLE link-layer keepalive — rejected: the AppConnect issue happens above the BLE link.

## Best Practices Adopted

- **Async iterator semantics**: `events()` is an async iterator with a clear termination contract (re-raise on reader-task failure; clean exit on graceful close).
- **Single-source-of-truth flag**: `_reset_on_connect` is a single bool on the adapter; the runner is the sole writer for reconnect-attempt logic.
- **Interruptible sleeps**: backoff uses `asyncio.sleep`, which is naturally cancellable; shutdown requests cancel the runner task and the sleep wakes immediately.
- **Test isolation via fakes**: `FlakyAdapter` / `_FakeAdapterTracksReset` style fakes in `tests/test_live_ble_stability.py` keep the BLE-stability tests purely in-process.

## Open Questions

None. This is a retroactive plan; the implementation is on `main` and the
test suite green on the CI matrix.
