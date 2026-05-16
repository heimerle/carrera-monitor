---
description: "Task list for Carrera Digital Telemetry Dashboard MVP"
---

# Tasks: Carrera Digital Telemetry Dashboard MVP

**Input**: Design documents from `/specs/main/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)
**Regenerated**: 2026-05-15 (plan unchanged; status reflects shipped MVP + US2 + US3 + Polish)

**Tests**: INCLUDED. The feature spec (FR-034) explicitly requires pytest coverage for the event model, storage writer, mock telemetry generator, and state manager. Tests for the adapter contract are added to support US2.

**Organization**: Grouped by user story so each story is independently testable and shippable. US1 alone is a viable MVP.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story tag (`US1`, `US2`, `US3`) — only on story phases
- File paths are repository-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding and tooling.

- [X] T001 Create repository directory layout per plan: `src/`, `tests/`, `docs/`, `logs/` (with `.gitkeep`), `specs/` (already present). Create empty `src/__init__.py` and `tests/__init__.py`.
- [X] T002 Author `pyproject.toml` at repo root: project metadata, Python 3.11+, console script `carrera-monitor = src.main:cli_entry`, `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, ruff + mypy config blocks.
- [X] T003 Author `requirements.txt` at repo root: pinned `pydantic>=2`, `pyyaml`, `streamlit`, `carreralib` (live-mode only, lazy-imported), and dev extras `pytest`, `pytest-asyncio`, `ruff`, `mypy`.
- [X] T004 [P] Create `.gitignore` at repo root covering `.venv/`, `__pycache__/`, `logs/*.jsonl`, `logs/*.csv`, `logs/state.json`, `.pytest_cache/`, `.mypy_cache/`, build artifacts, plus `.github/` per spec-kit security note.
- [X] T005 [P] Create `config.example.yaml` at repo root mirroring `AppConfig` defaults from [data-model.md §6](./data-model.md): `bluetooth`, `logging`, `dashboard`, `cars` sections with inline comments.
- [X] T006 [P] Create `tests/conftest.py` with shared fixtures: `frozen_clock` (monkeypatches `utils.now_monotonic_ms` / `utils.now_iso`), `tmp_log_dir` (uses pytest `tmp_path`), and `event_factory` (builds valid `TelemetryEvent` instances).

**Checkpoint**: Repo installs via `pip install -r requirements.txt`; `pytest` runs (zero tests yet, exits 0).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Components every user story depends on. No story work begins until this phase is green.

- [X] T007 Implement time/log/atomic-write helpers in `src/utils.py`: `now_iso() -> datetime` (tz-aware UTC), `now_monotonic_ms() -> int` (rebased to process start), `atomic_write_json(path, obj)` (`tmp + os.replace`), `configure_logging(level)` (JSON formatter to stderr, one object per line per FR-032).
- [X] T008 Implement canonical event model in `src/event_model.py`: Pydantic `TelemetryEvent` (frozen), `EventType` / `RaceState` / `ConnectionState` string enums, `ConnectionStateRecord`, per-`event_type` payload validators (reject unknown payload keys), `forbid` extras on the top-level model. Match [data-model.md §1–§5](./data-model.md) exactly.
- [X] T009 [P] Implement configuration loader in `src/config.py`: Pydantic `AppConfig` with `BluetoothConfig`, `LoggingConfig`, `DashboardConfig`, `CarsConfig` submodels and defaults; `load_config(path: Path | None) -> AppConfig` that reads YAML if present, logs warnings on unknown keys, returns defaults if file absent.
- [X] T010 Implement async event bus in `src/event_bus.py`: `EventBus` class with `subscribe(name, maxsize) -> asyncio.Queue[TelemetryEvent]`, `publish(event)`, `close()`. Per-subscriber bounded queues; on full queue use **drop-oldest** policy and emit a single `bus_overflow` warning log per subscriber per second (R-002). No external deps.
- [X] T011 Implement structured logging bootstrap wired into `configure_logging` from T007: stderr-only, JSON-line format, fields `ts`, `level`, `logger`, `msg`, `**context`; honor `--log-level` from CLI contract.
- [X] T012 [P] Author `tests/test_event_model.py`: round-trip serialization, timezone-aware enforcement, per-`event_type` payload acceptance and rejection of unknown keys, `car_id` range validation, equality after JSON round-trip.

**Checkpoint**: `pytest tests/test_event_model.py` passes. Bus, config loader, utils, and event model are importable with no side effects.

---

## Phase 3: User Story 1 - Mock Mode End-to-End Telemetry (Priority: P1) 🎯 MVP

**Goal**: A developer with no Carrera hardware runs `python -m src.main --mock` and sees a live Streamlit dashboard fed by simulated 1–6 cars, while a JSONL log accumulates valid events.

**Independent Test**: Per [spec.md US1](./spec.md). Start the app with `--mock`, observe dashboard refresh, verify `logs/carrera-*.jsonl` lines validate against the event model.

### Tests for User Story 1

- [X] T013 [P] [US1] `tests/test_mock_client.py`: with a seeded RNG, run `MockCarreraAdapter` for a fixed simulated duration; assert it emits at least one event of every required `event_type` per FR-011 (`lap`, `fuel`, `race_state`, `pitlane`, `connection_state`, `controller_input`, `speed`, `brake`), respects `cars.count`, and produces monotonically non-decreasing `timestamp_monotonic_ms`.
- [X] T014 [P] [US1] `tests/test_storage.py`: write 1000 events through `JsonlEventWriter` to a `tmp_path`, then re-read the file line-by-line and `TelemetryEvent.model_validate_json` each line — 100% must parse. Separately verify the CSV lap writer emits header + correct row order. Verify a simulated `OSError` on write does not raise out of the writer task (graceful degradation per FR-018).
- [X] T015 [P] [US1] `tests/test_state_manager.py`: feed an event stream (`lap`, `fuel`, `pitlane`, `race_state`) into `StateManager`; assert `CarState.lap_count`, `best_lap_ms`, `latest_lap_ms`, `fuel_percent`, `in_pit`, and `RaceState` transitions match the rules in [data-model.md §3–§4](./data-model.md). Assert `snapshot()` returns a JSON-serializable `StateSnapshot` and that atomic write produces a readable `state.json`.

### Implementation for User Story 1

- [X] T016 [P] [US1] Implement `MockCarreraAdapter` in `src/mock_client.py` satisfying the `CarreraAdapter` Protocol (see T020): async tasks per car covering **all telemetry types required by FR-011** — `lap`, `fuel`, `race_state`, `pitlane`, `controller_input` (synthetic throttle/brake sine), `speed` (derived from throttle), `brake` (component of controller_input) — plus global `race_state` and `connection_state` transitions. Bernoulli pit logic per [research.md R-005](./research.md), seedable via `MOCK_SEED` env var. `source_name = "mock"`. Yields `RawFrame` dicts only (translation lives in `src/carrera_client.py`).
- [X] T017 [P] [US1] Implement `JsonlEventWriter` and optional `CsvLapWriter` in `src/storage.py`: dedicated async task consuming from a subscriber queue, batch-flush ≤ 250 ms (R-006), filename pattern `carrera-{YYYYMMDD-HHMMSS}-{pid}.jsonl` / `laps-...csv`, auto-create log dir, fault-tolerant writes that log and continue on `OSError`.
- [X] T018 [P] [US1] Implement `StateManager` in `src/state_manager.py`: subscribes to bus, updates `CarState` / `RaceState` / `ConnectionStateRecord`, maintains capped `recent_events` deque (100), exposes `snapshot() -> StateSnapshot`, writes `state.json` via `utils.atomic_write_json` on every state change and at least every `dashboard.refresh_interval_ms`.
- [X] T019 [US1] Implement small derivation helpers in `src/telemetry_processor.py`: `update_best_lap(current_best, new_lap_ms)`, clamp helpers for fuel/throttle/brake; pure functions used by `StateManager`. Add unit assertions inline (no separate test file required by spec).
- [X] T020 [US1] Define the `CarreraAdapter` Protocol, `RawFrame` TypedDict, `DiscoveredDevice` dataclass, and the typed exceptions `AdapterConnectionError` / `AdapterReadError` in `src/carrera_client.py` (live implementation is added in US2). Also implement `translate_raw_frame(frame: RawFrame, source: str) -> TelemetryEvent` here — the **only** place that knows about raw upstream frame shapes; emit `event_type = "not_supported"` with `raw_data` preserved when no canonical mapping exists (FR-012). This translator is reused by both mock and live clients.
- [X] T021 [US1] Wire `src/mock_client.py` to use `translate_raw_frame` (from T020) at the boundary of `events()` so its public stream is `TelemetryEvent`, not `RawFrame`. Update `tests/test_mock_client.py` accordingly.
- [X] T022 [US1] Implement Streamlit dashboard in `src/dashboard.py`: reads `logs/state.json` (path from `AppConfig`), uses `st_autorefresh` (or `st.fragment` when available) at `dashboard.refresh_interval_ms`, renders header (connection state), per-car cards (lap count, best/latest lap, fuel bar, pit badge), and a recent-events panel. Renders "initializing" if `state.json` missing; "stale data" banner if file mtime older than 5× refresh interval. MUST NOT import `carreralib` or any BLE code (FR-024).
- [X] T023 [US1] Implement CLI + async orchestration in `src/main.py`: argparse per [contracts/cli.md](./contracts/cli.md), `cli_entry()` and `async def run()` that builds `EventBus`, `StateManager`, `JsonlEventWriter`, selects `MockCarreraAdapter` when `--mock`, wires producer → bus → consumers, installs SIGINT/SIGTERM handler for graceful shutdown (flush ≤ 5 s, exit 0). When `dashboard.enabled` and not `--no-dashboard`, spawn `streamlit run src/dashboard.py --server.port {port}` as a subprocess and tear it down on shutdown.
- [X] T024 [US1] Run the quickstart against the mock pipeline end-to-end: start `python -m src.main --mock`, confirm `state.json` is updated within the configured interval, dashboard renders, JSONL grows; document any deviations and fix. Add a brief "verified" note timestamp to [quickstart.md](./quickstart.md) (no other changes).

**Checkpoint**: US1 is fully functional. MVP can ship here.

---

## Phase 4: User Story 2 - Live Hardware Telemetry With Auto-Reconnect (Priority: P2)

**Goal**: With a real Carrera AppConnect adapter present, the system connects (with optional MAC), streams normalized telemetry to the same dashboard, and auto-reconnects after dropouts.

**Independent Test**: Per [spec.md US2](./spec.md). Toggle adapter power and observe `reconnecting → connected` without restarting the process.

### Tests for User Story 2

- [X] T025 [P] [US2] `tests/test_adapter_contract.py`: parametrized over `MockCarreraAdapter` and a `FakeLiveCarreraAdapter` (a lightweight in-test fake that simulates the same Protocol surface, no real BLE). Verify: `disconnect()` is idempotent, the `events()` iterator stops cleanly after `disconnect()`, errors during iteration raise `AdapterReadError`. Covers the contract in [contracts/carrera-adapter.md](./contracts/carrera-adapter.md).
- [X] T026 [P] [US2] Reconnect-logic test in `tests/test_state_manager.py` (extend the existing file): inject a sequence of `connection_state` events `connected → reconnecting → connected`; assert `ConnectionStateRecord.state` and `since_ms` update correctly, no exceptions, and `recent_events` contains both transitions. Add a timing assertion (SC-004) using a fake monotonic clock injected into `CarreraClientRunner`: simulate a disconnect, assert the runner attempts reconnect and reaches `connected` again within `2 × bluetooth.reconnect_interval_seconds`.

### Implementation for User Story 2

- [X] T027 [US2] Implement `LiveCarreraAdapter` in `src/carrera_client.py` satisfying the Protocol: lazy-import `carreralib` inside `connect()` (raise `AdapterConnectionError` with a clear message if missing); scan with `bluetooth.scan_timeout_seconds` or use configured `mac_address`; expose `discovered_devices()`; yield `RawFrame` dicts from the underlying `carreralib` callbacks/iterator. Mark each unknown-field branch with an explicit `# TODO(hardware): verify carreralib field name` comment per R-001.
- [X] T028 [US2] Implement the connection state machine + reconnect loop in `src/carrera_client.py` (separate `CarreraClientRunner` class): emit `connection_state` events on every transition, retry connect with `bluetooth.reconnect_interval_seconds`, never crash the host pipeline on adapter errors; catch `AdapterReadError` / `AdapterConnectionError` and transition to `reconnecting` or `error` per [data-model.md §5](./data-model.md).
- [X] T029 [US2] Update `src/main.py` to choose `LiveCarreraAdapter` (via `CarreraClientRunner`) when `--mock` is absent; surface `--mac` to override `bluetooth.mac_address`. **Note**: the original `--mock` + `--mac` mutual-exclusion + exit-code-2 contract was superseded by 002/FR-225 (precedence model) and dropped from `specs/main/contracts/cli.md` in PR #15. Tasks file kept for historical completeness; the live contract is FR-225.
- [X] T030 [US2] Add troubleshooting entries to `docs/troubleshooting.md` for the most likely live-mode failures (adapter not found, `carreralib` import error, MAC unreachable, permission errors on macOS BLE).

**Checkpoint**: With a real adapter, the dashboard reflects live telemetry; toggling adapter power demonstrates auto-reconnect.

---

## Phase 5: User Story 3 - Race Replay From JSONL Logs (Priority: P3)

**Goal**: A post-session log is provably round-trippable through the canonical schema, making future replay/analytics a no-core-change extension.

**Independent Test**: Per [spec.md US3](./spec.md). Open the latest JSONL and confirm 100% parse rate against `TelemetryEvent`; if CSV enabled, confirm header + rows.

### Tests for User Story 3

- [X] T031 [P] [US3] `tests/test_storage.py` (extend): produce a session of ≥ 500 events via `MockCarreraAdapter` → `JsonlEventWriter` into a `tmp_path`; reopen the file, parse every line with `TelemetryEvent.model_validate_json`, assert (a) 100% parse rate, (b) monotonically non-decreasing `timestamp_monotonic_ms`, (c) when CSV enabled, CSV row count equals number of `lap` events in JSONL.

### Implementation for User Story 3

- [X] T032 [US3] Document the JSONL/CSV format guarantees and the planned (post-MVP) `tools/replay.py` extension point in `docs/architecture.md` (creating the file if absent) with a short diagram of producer → bus → consumers from [data-model.md §9](./data-model.md). Cross-link [contracts/event-log.md](./contracts/event-log.md).
- [X] T033 [US3] Author project `README.md` at repo root covering: overview, architecture summary + diagram link, installation, mock-mode startup, hardware setup, configuration, known limitations (no replay tool yet, single-process), roadmap (replay, websockets, REST, sniffer, analytics, OBS overlay — R-008), troubleshooting link.

**Checkpoint**: All three user stories independently deliverable.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T034 [P] Run `ruff check src tests` and `mypy src` (configured in T002); fix any reported issues without changing public behavior. Anchors SC-005 (CI green) and FR-034 (TDD / clean lint).
- [X] T035 [P] Verify `.gitignore` excludes `.github/` agent dir, all log artifacts, caches, and build artifacts; confirm no credentials are tracked (security note from spec-kit init). Anchors the spec-kit security note (no committed secrets) and supports SC-005.
- [X] T036 Run the full quickstart end-to-end on a clean checkout (fresh venv); ensure SC-001 (under 5 min) holds. Anchors SC-001 and SC-006 (quickstart accuracy). Update [quickstart.md](./quickstart.md) only if a step is wrong.
- [X] T037 Final review of `src/main.py` and `src/carrera_client.py` for any silent `except:` (FR-033) and any direct `carreralib` references outside `src/carrera_client.py` (FR-024); refactor on the spot.
- [X] T038 [P] Add CI workflow at `.github/workflows/ci.yml` (Ubuntu + macOS, Python 3.11 and 3.12 matrix): install `requirements.txt`, run `ruff check`, `mypy src`, `pytest -q`. Required by SC-005 ("tests passing locally and in CI").
- [X] T039 Implement raw/debug event passthrough (FR-013): add `logging.debug_raw_enabled: bool = false` to `AppConfig` (update [data-model.md §6](./data-model.md) and `config.example.yaml`) and `--debug-raw` CLI flag (update [contracts/cli.md](./contracts/cli.md) and `src/main.py` per T023). When enabled, `translate_raw_frame` (T020) additionally emits a companion `event_type = "raw"` event carrying the original frame in `raw_data`. Off by default to keep JSONL files lean.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no deps; can start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks all user stories**.
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 2; benefits from T020 (defined in US1) but can be re-ordered if US2 is built first — `translate_raw_frame` and the Protocol stubs in T020 are the only cross-story coupling.
- **Phase 5 (US3)**: depends on Phase 3 (needs `MockCarreraAdapter` + `JsonlEventWriter` to produce a real session).
- **Phase 6 (Polish)**: depends on whichever stories are in scope for delivery.

### Within-Story Order

- Tests are written **before** their corresponding implementation in each story (TDD per FR-034 spirit).
- Models/protocols before consumers: T008 / T020 before adapters and dashboard.
- `EventBus` (T010) before any subscriber implementation (T017 / T018).
- `MockCarreraAdapter` (T016, T021), `JsonlEventWriter` (T017), and `StateManager` (T018) before `main.py` orchestration (T023).

### Parallel Opportunities

- T004, T005, T006 (Setup) run in parallel.
- T009, T012 (Foundational) run in parallel with each other after T008.
- T013, T014, T015 (US1 tests) all parallel.
- T016, T017, T018 (US1 implementations) all parallel after T008 / T010.
- T025, T026 (US2 tests) parallel with each other.
- T031 (US3 test) is independent of US2 work.

### Parallel Example: User Story 1 implementation

```bash
# After T008 (event model) and T010 (event bus) are merged:
pytest tests/test_event_model.py          # baseline
# In parallel:
#   developer A: T016 src/mock_client.py
#   developer B: T017 src/storage.py
#   developer C: T018 src/state_manager.py
# Then sequentially: T019 → T020 → T021 → T022 → T023 → T024
```

---

## Implementation Strategy

1. **MVP first**: complete Phases 1, 2, 3 → ship US1 (`python -m src.main --mock`). Satisfies every "Acceptance Criteria" bullet in the spec except live-hardware reconnect.
2. **Increment**: add Phase 4 (US2) once a Carrera adapter is on hand for hardware verification of the TODOs in T027.
3. **Harden**: Phase 5 (US3) closes the persistence/replay guarantees and finalizes documentation.
4. **Polish**: Phase 6 only after the desired stories are delivered.

## Task Count Summary

| Phase | Tasks | Story |
|---|---|---|
| Setup | T001–T006 (6) | — |
| Foundational | T007–T012 (6) | — |
| US1 (MVP) | T013–T024 (12) | P1 |
| US2 | T025–T030 (6) | P2 |
| US3 | T031–T033 (3) | P3 |
| Polish | T034–T039 (6) | — |
| **Total** | **39** | |

## Independent Test Criteria (recap)

- **US1**: `python -m src.main --mock` shows live dashboard with N cars, `logs/*.jsonl` contains valid events of every required type.
- **US2**: Live adapter present → state cycles `scanning → connecting → connected`; toggling adapter cycles `reconnecting → connected` without process restart.
- **US3**: Latest `logs/*.jsonl` parses with 100% success; CSV row count equals `lap` event count when enabled.

## Suggested MVP Scope

**Phases 1 + 2 + 3 only** (T001–T024). This delivers a fully working mock-mode dashboard with persistence and tests, satisfying every "Acceptance Criteria" bullet that does not require physical hardware.

## Current Status (2026-05-15)

All 39 tasks complete; CI green on Ubuntu + macOS × Python 3.11 / 3.12. Latest commit on `main`: post-MVP dashboard polish (motorsport leaderboard, lap times in seconds with 3 decimals, smoother refresh interval bounds 100–2000 ms with 200 ms default) — applied directly to `src/dashboard.py` and `src/config.py`, no new tasks generated for that slice.

For work that landed on `main` after this date see the follow-on feature slices:

- `specs/001-race-management/` — race management (PR #1, T001–T044 + T043a).
- `specs/002-race-controls/` — race controls + `RuntimeSettings` refactor (PR #5/#6/#13, T001–T036).
- pending `specs/003-live-adapter-carreralib/` — retroactive slice for the carreralib live-adapter stack (PR #9 carreralib rewrite + `--scan` CLI, PR #10 TimeoutError handling, PR #12 BLE idle watchdog, PR #14 reader-task-failure propagation + `cu.reset` suppression on reconnect + exponential backoff).
