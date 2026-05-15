# Phase 0 Research: Carrera Digital Telemetry Dashboard MVP

**Feature**: Carrera Digital Telemetry Dashboard MVP  
**Plan**: [plan.md](./plan.md)  
**Spec**: [spec.md](./spec.md)

Each entry resolves a `NEEDS CLARIFICATION` from Technical Context or a load-bearing technology choice.

---

## R-001 — `carreralib` adapter surface

**Decision**: Wrap `carreralib` behind a thin `CarreraAdapter` Protocol inside `src/carrera_client.py`. The adapter exposes only:

- `async connect(mac_address: str | None) -> None`
- `async disconnect() -> None`
- `async events() -> AsyncIterator[RawCarreraEvent]` (yielding loosely-typed dicts)
- `discovered_devices() -> list[Device]`

The carrera client module then translates `RawCarreraEvent` → canonical `TelemetryEvent`.

**Rationale**:
- `carreralib` is community-maintained; its public symbols differ between releases. Pinning UI/state code to its current shape would create churn.
- The Protocol allows the mock client to satisfy the same interface, so the rest of the system is hardware-agnostic.
- Explicit translation layer is the natural place for `not_supported` fallbacks and TODO markers for hardware verification.

**Alternatives considered**:
- Direct use of `carreralib` types throughout — rejected: couples dashboard and storage to a third-party schema.
- Forking `carreralib` — rejected: out of MVP scope and creates maintenance burden.

**TODOs for hardware verification** (must be marked in code):
- Exact iterator/callback API for telemetry frames.
- Field names for lap time, fuel, controller input, brake, speed.
- Pit-lane event semantics on DIGITAL 124 vs. 132.

---

## R-002 — Event bus implementation

**Decision**: An in-process `asyncio` pub/sub built on `asyncio.Queue` per subscriber, fan-out from a single dispatcher coroutine. Backpressure policy: each subscriber queue is bounded (default 1024); on overflow the bus **drops the oldest** event for that subscriber and emits a structured `bus_overflow` warning. Storage subscriber uses a larger bound (default 8192) so disk hiccups don't lose data.

**Rationale**:
- Pure-stdlib, no extra dependency; aligns with "avoid unnecessary dependencies".
- Drop-oldest gives the dashboard "latest wins" semantics naturally while keeping storage durable up to the larger queue.
- Async-native, integrates with both the BLE client (which is I/O-bound) and the mock generator (timer-driven).

**Alternatives considered**:
- `blinker` / `pyee` synchronous signals — rejected: harder to integrate with async producers/consumers cleanly.
- `aio-pika` / Redis — rejected: external broker, violates "fully local/offline capable".

---

## R-003 — Time representation

**Decision**: Every event carries both `timestamp_iso` (timezone-aware ISO-8601, host wall clock at emission) and `timestamp_monotonic_ms` (`time.monotonic_ns() // 1_000_000` rebased to process start = 0). Monotonic ms is authoritative for ordering within a single process run.

**Rationale**:
- Wall-clock is needed for human-readable logs/dashboard.
- Monotonic is needed because Carrera frames may arrive faster than 1 ms wall-clock resolution on some platforms, and wall-clock can jump (NTP, suspend/resume).
- Two fields are cheap and unblock future analytics (replay, latency stats).

**Alternatives**: single ISO timestamp (rejected: ordering hazards), single monotonic (rejected: not human-readable in logs).

---

## R-004 — Dashboard refresh model with Streamlit

**Decision**: Use Streamlit's `st_autorefresh` (or `st.experimental_rerun()` on a timer fallback) with a default interval of 1000 ms. The dashboard reads from a `StateSnapshot` object provided by `StateManager.snapshot()`; the snapshot is a plain dataclass/Pydantic model that is cheap to copy on each refresh.

**Rationale**:
- Streamlit's rerun model rebuilds the page on each refresh; reading an immutable snapshot avoids race conditions vs. mutating shared state during render.
- 1 Hz is sufficient for the MVP and well below the bound in FR-023; configurable down to 500 ms.

**Alternatives**:
- WebSockets / FastAPI + a JS client — rejected: out of scope for MVP, but the snapshot model is the seam where a future websocket transport can plug in (see R-008).

---

## R-005 — Mock telemetry realism

**Decision**: Mock client runs at three independent async tasks per simulated car:
- Lap tick: base lap time per car drawn from a normal distribution (μ ≈ 8000 ms, σ ≈ 400 ms) clamped to [5000, 15000] ms.
- Fuel drain: linear with small noise, refilled on pit events.
- Pit events: low-probability per-lap Bernoulli (~5%) plus forced pit when fuel < 10%.

Race-state events fire on a global state machine (idle → countdown → running → finished) controllable via env var `MOCK_RACE_DURATION_S` (default 600).

**Rationale**:
- Produces realistic-looking dashboards out of the box.
- Deterministic seed available via `MOCK_SEED` env var for reproducible tests.

**Alternatives**: pre-recorded fixture replay — kept as a future extension point (R-009), not blocking for MVP.

---

## R-006 — Storage durability

**Decision**:
- One JSONL file per process run, filename `logs/carrera-{YYYYMMDD-HHMMSS}-{pid}.jsonl`.
- Writer is a dedicated async task consuming from the storage subscriber queue.
- After each batch (or at most every 250 ms) the file is `flush()`-ed; `os.fsync` is **not** called per-event (would dominate latency) but is called on graceful shutdown.
- Optional CSV writer enabled by `logging.csv_laps_enabled` writes lap rows only.

**Rationale**:
- Append-only JSONL is the standard durable event log; trivial to tail/inspect.
- Batched flush keeps overhead bounded while bounding data loss on crash to ≤ 250 ms.

**Alternatives**: SQLite — rejected for MVP (heavier, complicates concurrent reads from dashboard); kept as future extension.

---

## R-007 — Configuration loading

**Decision**: `src/config.py` defines a Pydantic `AppConfig` (with `BluetoothConfig`, `LoggingConfig`, `DashboardConfig`, `CarsConfig` submodels). `load_config(path: Path | None)` reads YAML if present, else returns defaults; missing keys fall back to defaults; unknown keys produce a warning but do not crash. CLI flags override config values for a small whitelist (`--mock`, `--config`, `--mac`, `--log-dir`).

**Rationale**:
- Pydantic gives validation + IDE autocomplete + free serialization for tests.
- YAML is friendly for hobbyists; PyYAML is already in the dependency list.

**Alternatives**: TOML (less familiar to hobby users), JSON (no comments) — rejected.

---

## R-008 — Future extension seams

**Decision**: Reserve three explicit extension points, documented in `docs/`:
1. **New event consumer**: subscribe to the bus and consume `TelemetryEvent`. No core changes required.
2. **Alternative transport**: anything implementing the `CarreraAdapter` Protocol can replace `carreralib` (e.g., a future BLE sniffer or a network bridge).
3. **Alternative dashboard / API**: anything that reads `StateManager.snapshot()` and/or subscribes to the bus can replace Streamlit (websocket server, REST, OBS overlay).

**Rationale**: Encodes the "future extension points" list from the spec into actual code seams rather than aspirational prose.

---

## R-009 — Replay (deferred)

**Decision**: Replay-from-JSONL is **not** implemented in the MVP but the JSONL format guarantees it is feasible. A small `tools/replay.py` is on the roadmap and is described in the README's roadmap section only.

**Rationale**: Keeps MVP scope bounded; the JSONL contract (R-006) makes replay a pure-consumer feature with no core changes needed.

---

## R-010 — Python version & async runtime

**Decision**: Python 3.11+ (matches user constraint); single-event-loop `asyncio` runtime started by `src/main.py`. Streamlit runs as a separate process (it manages its own loop); they communicate via a shared on-disk handoff or a lightweight IPC. For the MVP they communicate via the **state snapshot serialized to a small in-memory file or shared module-level state in single-process mode** — see R-011.

**Rationale**: Streamlit's process model conflicts with hosting an asyncio loop in the same process. Keeping them decoupled matches FR-024 (dashboard contains no BLE code).

---

## R-011 — Single-process vs. two-process layout

**Decision**: MVP supports **two run modes**:
- `python -m src.main [--mock]` — runs the async pipeline (client → bus → state → storage); writes a periodically refreshed `state.json` snapshot under `logs/` (atomic write).
- `streamlit run src/dashboard.py` — reads the latest `state.json` and the latest JSONL tail to render. Started independently, optionally launched by `main.py` as a subprocess when `dashboard.enabled = true`.

**Rationale**:
- Cleanest separation; matches Streamlit's expected lifecycle.
- Snapshot file is a hard, observable contract — perfect for future replacement with websockets or REST.
- "Auto-launch" via subprocess gives the hobbyist a single command (`python -m src.main --mock`) that still respects the architectural seam.

**Alternatives**: embed Streamlit via custom bootstrap — rejected: brittle, version-sensitive.

---

## Open Items (none blocking)

All NEEDS CLARIFICATION items from Technical Context are resolved above. The remaining uncertainties (exact `carreralib` field names) are isolated behind the `CarreraAdapter` Protocol with TODO markers and do not block any other component.
