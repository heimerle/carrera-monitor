# Feature Specification: Race Controls (Finish Button, Safety Car, Mock Mode Toggle)

**Feature Branch**: `002-race-controls`
**Created**: 2026-05-16
**Status**: Implemented (merged to `main` via PR #5, commit `4ce8570`)
**Input**: User description: "Extend the existing Carrera race management/dashboard MVP with these controls: 1. Finish race by button, 2. Safety car phase by button, 3. Race simulator / mock mode switchable on/off from the UI"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Finish a Running Race from the UI (Priority: P1) 🎯 MVP

The race director clicks a prominent **🏁 Finish Race** button in the active-race panel to end a `running` or `paused` race cleanly. The race transitions to `finished`, `finished_at` is stamped, the lap-ingest pipeline stops accepting new laps for it, and a `race_summary` report is auto-generated.

**Why this priority**: The MVP can already auto-finish on lap-target / duration, but a human "stop the race now" affordance is the most-requested missing primitive — required for aborting test runs, ending duration races early, or handling out-of-band events.

**Independent Test**: Start a `fixed_laps=20`, 2-driver race, let it run for a few laps, click **🏁 Finish Race**. Verify the `races` row shows `status='finished'` and `finished_at IS NOT NULL`, a `race_events` row of type `race_finished` exists with `payload_json->>'triggered_by' = 'user'`, a `race_reports` row of type `race_summary` exists, and `ActiveRaceContext.get()` returns `None`.

**Acceptance Scenarios**:

1. **Given** a race with `status='running'`, **When** the user clicks **🏁 Finish Race**, **Then** the race transitions to `finished`, `finished_at` is set, the persisted `race_finished` event payload contains `triggered_by='user'`, and a `race_summary` report row is created.
2. **Given** a race with `status='paused'`, **When** the user clicks **🏁 Finish Race**, **Then** the race transitions directly to `finished` (no resume required).
3. **Given** a race with `status` ∈ `{draft, ready, finished, cancelled}`, **When** the service is invoked, **Then** an `InvalidRaceStateError` is raised whose message names the current status, and no DB writes occur. The UI MUST surface this error via `st.error(...)` and MUST NOT render the button for terminal states.
4. **Given** a finished race, **When** a `lap` telemetry event arrives for that race's `car_id`, **Then** no `race_laps` row is written (FR-120 preserved).

---

### User Story 2 — Toggle Safety Car Phase (Priority: P2)

The race director clicks **🟡 Safety Car** to declare a safety-car phase, and **🟢 End Safety Car** to clear it. While active, a yellow banner is shown above the standings. The phase boundaries are persisted to `race_events` for later analysis.

**Why this priority**: Safety-car phases are a normal part of any race longer than a couple of laps. v1 keeps state in memory + event log only (no schema change) so it can ship independently of US1.

**Independent Test**: With a `running` race, click **🟡 Safety Car** → verify one `race_events` row of type `safety_car_started` with `payload_json->>'active' = 'true'` exists and `is_safety_car_active(race_id)` returns `True`. Click again (idempotent) → no new row. Click **🟢 End Safety Car** → exactly one new `safety_car_ended` row with `payload_json->>'active' = 'false'`; `is_safety_car_active(race_id)` returns `False`. The yellow banner is shown only while active.

**Acceptance Scenarios**:

1. **Given** a race with `status` ∈ `{running, paused}` and no active phase, **When** the user toggles ON, **Then** `set_safety_car(race_id, True)` persists exactly one `safety_car_started` event and returns `True`.
2. **Given** an active safety-car phase, **When** the user re-asserts ON, **Then** the call is idempotent: no new event row is written and the return value is unchanged.
3. **Given** an active safety-car phase, **When** the user toggles OFF, **Then** exactly one `safety_car_ended` event is persisted in order after the start row.
4. **Given** an active safety-car phase, **When** the race is `finish`ed or `cancel`led, **Then** the in-memory flag is cleared (verified via `is_safety_car_active(race_id) == False`).
5. **Given** a race with `status` ∈ `{draft, ready, finished, cancelled}`, **When** the service is invoked, **Then** `InvalidRaceStateError` is raised and no event row is written.

---

### User Story 3 — Toggle Mock Mode (Race Simulator) from the UI (Priority: P3)

The user opens the Settings page and flips a **Mock mode (race simulator)** toggle. The choice persists to `data/runtime_settings.json` immediately. On the next start of `carrera-monitor`, the pipeline selects `MockCarreraAdapter` if no explicit `--mac` / `--mock` CLI flag was provided.

**Why this priority**: Currently mock mode is a CLI-only `--mock` flag. The toggle removes the need to memorize CLI arguments for the most common dev / demo flow.

**Independent Test**: From a fresh checkout, on the Settings page, set the toggle ON; verify `data/runtime_settings.json` exists with `{"mock_mode": true}`. Restart `carrera-monitor` with no CLI args → the adapter loaded is `MockCarreraAdapter`. Set the toggle OFF, restart again → adapter falls back to default (no mock) as long as the user provided `--mac` or accepts an error if neither flag nor toggle is set.

**Acceptance Scenarios**:

1. **Given** the Settings page is open, **When** the user flips the toggle, **Then** `data/runtime_settings.json` is rewritten atomically (`tempfile.mkstemp` + `os.replace`) and the page re-reads + displays the new value.
2. **Given** the runtime-settings file is missing, **When** `RuntimeSettings()` is instantiated, **Then** it returns defaults `{mock_mode: False}` without raising.
3. **Given** the runtime-settings file is corrupt JSON, **When** `RuntimeSettings()` is instantiated, **Then** it logs a WARNING and falls back to defaults without raising.
4. **Given** `runtime_settings.mock_mode = True` and CLI invocation `carrera-monitor` (no `--mac`, no `--mock`), **When** the pipeline starts, **Then** the loaded adapter is `MockCarreraAdapter`.
5. **Given** `runtime_settings.mock_mode = True` and CLI invocation `carrera-monitor --mac AA:BB:...`, **When** the pipeline starts, **Then** the explicit CLI flag wins and the live adapter is loaded.

---

### Edge Cases

- User clicks **🏁 Finish Race** twice rapidly → second call sees `status='finished'` and raises `InvalidRaceStateError`; UI shows the error but the first finish completed cleanly.
- Safety-car toggle is pressed during a race-state transition window (e.g., simultaneously with `pause_race`) → service revalidates status under the same session; if the race is no longer running/paused, raises `InvalidRaceStateError`.
- `runtime_settings.json` is on a read-only filesystem → write fails; UI shows the error and the in-memory value reverts.
- Two concurrent Streamlit sessions toggle mock mode → last writer wins; both sessions re-read on next interaction.

## Requirements *(mandatory)*

### Functional Requirements

#### Finish Race Button (US1)

- **FR-201**: `RaceService` MUST expose `finish_race_by_user(race_id: int) -> RaceRead` returning the Pydantic DTO (FR-130 compliance).
- **FR-202**: `finish_race_by_user` MUST delegate to the existing `finish_race(...)` so all existing side effects (status update, `finished_at` stamp, `ActiveRaceContext.clear()`, auto-snapshot `race_summary`) are preserved.
- **FR-203**: The persisted `race_finished` event MUST include `payload_json->>'triggered_by' = 'user'` for user-initiated finishes (vs. `'auto'` for lap-target / duration auto-finish).
- **FR-204**: The service MUST reject finish from `draft`, `ready`, `finished`, `cancelled` with `InvalidRaceStateError` whose message includes the current status.
- **FR-205**: The Race Management UI MUST render the **🏁 Finish Race** button only while `race.status ∈ {running, paused}`.
- **FR-206**: UI errors MUST be rendered via `st.error(str(exc))` without crashing the page.

#### Safety Car Phase (US2)

- **FR-210**: `RaceService` MUST expose `set_safety_car(race_id: int, active: bool) -> bool` returning the new state.
- **FR-211**: `RaceService` MUST expose `is_safety_car_active(race_id: int) -> bool` reading the in-memory cache.
- **FR-212**: `set_safety_car` MUST persist exactly one `safety_car_started` or `safety_car_ended` row to `race_events` per state change, with `payload_json = {"active": "true"|"false"}`.
- **FR-213**: `set_safety_car` MUST be idempotent: re-asserting the current value MUST NOT write a new event row.
- **FR-214**: `set_safety_car` MUST raise `InvalidRaceStateError` for `status ∉ {running, paused}`.
- **FR-215**: `finish_race` AND `cancel_race` MUST clear the in-memory safety-car flag for that race.
- **FR-216**: The UI MUST display a yellow banner above the standings while the phase is active.
- **FR-217**: v1 MUST NOT introduce a schema change (no new column on `races`); state is event-log + in-memory only.

#### Mock Mode Toggle (US3)

- **FR-220**: A new module `src/services/runtime_settings.py` MUST expose a `RuntimeSettings` class backed by `data/runtime_settings.json` with atomic writes (`tempfile.mkstemp` + `os.replace`).
- **FR-221**: `RuntimeSettings` MUST tolerate missing OR corrupt files by returning defaults (`{mock_mode: False}`) and logging at WARNING level on corruption.
- **FR-222**: `RuntimeSettings` MUST expose `get_mock_mode() -> bool` and `set_mock_mode(value: bool) -> bool` plus module-level helpers backed by a default singleton.
- **FR-223**: The Settings Streamlit page MUST present a **Mock mode (race simulator)** toggle that persists immediately on change.
- **FR-224**: The Settings page MUST display a "restart required" notice + a "CLI flags override" notice.
- **FR-225**: `src/main.py` adapter selection MUST follow the precedence: explicit `--mac` > explicit `--mock` > `runtime_settings.mock_mode`. Concretely: `use_mock = args.mock OR (args.mac is None AND runtime_settings.get_mock_mode())`.
- **FR-226**: `data/runtime_settings.json` MUST be gitignored (covered by existing `data/` rule).

#### Architecture

- **FR-230**: New service methods MUST live in `src/services/race_service.py`; UI in `src/pages/race_management.py` + `src/pages/settings.py`; runtime settings in `src/services/runtime_settings.py`. No ORM imports in UI layer (extends FR-130).
- **FR-231**: All new code MUST pass `ruff check .` and `mypy src/` (strict). All new tests MUST pass on the CI matrix (Python 3.11/3.12 × ubuntu/macos).

### Key Entities *(data)*

- **`race_events` payload extension (existing table)** — Two new `event_type` values: `safety_car_started`, `safety_car_ended`. Payload schema: `{"active": "true" | "false"}` (stringly typed for JSON-column homogeneity). `race_finished` payload extended with `triggered_by ∈ {"user","auto"}`.
- **`RuntimeSettings` (new, file-backed)** — JSON document at `data/runtime_settings.json`. v1 schema: `{"mock_mode": bool}`.
- **`SafetyCarFlag` (in-memory only, `dict[int, bool]` on `RaceService`)** — Ephemeral; lost on process restart; reconciled lazily from the last `safety_car_started`/`safety_car_ended` event row for that race on next read (optional polish).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-201**: A user can finish a running race in ≤ 1 UI click, with `<100 ms` round-trip from click to UI re-render.
- **SC-202**: 100% of user-initiated finishes persist `triggered_by='user'`; 100% of auto-finishes persist `triggered_by='auto'`. Verified by unit tests.
- **SC-203**: Safety-car toggle round-trip (UI → DB → UI re-render) is idempotent under double-click: re-asserting the same value writes zero additional event rows. Verified by unit test.
- **SC-204**: `data/runtime_settings.json` survives process restart and is read on the next `carrera-monitor` boot to select the adapter.
- **SC-205**: All pre-feature tests remain green; ≥ 21 new tests cover finish-by-user, safety-car (start/end/idempotency/state-guards/clearing on finish-or-cancel), and `RuntimeSettings` (round-trip/missing/corrupt). Verified — current total 137 / 137 passing.
- **SC-206**: `ruff check .` and `mypy src/` (strict) remain clean. Verified.

## Assumptions

- No new ORM table is required for safety-car in v1 — event log + in-memory cache is sufficient. A future polish slice may reconcile the cache from the event log on service init.
- "Mock mode" toggle requires a process restart to take effect; hot-swapping the adapter at runtime is out of scope.
- A single Streamlit user is assumed; multi-user race-director scenarios are out of scope.
- The CLI continues to honor `--mock` / `--mac` exactly as before for backward compatibility.
