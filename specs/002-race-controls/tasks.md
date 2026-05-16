---
description: "Task list for the Race Controls feature (Finish button, Safety Car, Mock Mode toggle)"
---

# Tasks: Race Controls (Finish Button, Safety Car, Mock Mode Toggle)

**Feature Branch**: `002-race-controls` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Input**: Design documents in `specs/002-race-controls/`
**Prerequisites**: plan.md, spec.md

**Tests**: INCLUDED. The spec (SC-205) requires ≥ 21 new tests covering all three slices, and the project convention (FR-134 of the parent module) is to never regress the existing test count.

**Organization**: Tasks are grouped by user story (US1 Finish Button → US2 Safety Car → US3 Mock Mode) so each story can be implemented, tested, and shipped independently.

**Status**: All tasks below were implemented in PR #5 (commit `4ce8570`) and are marked `[X]`. This file exists so that any follow-up `/speckit.tasks` work has a normal `plan.md → tasks.md` anchor.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: Story tag for user-story phases (US1, US2, US3); omitted in Setup / Foundational / Polish
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: None — the feature reuses the existing layout, fixtures, and CI matrix from the parent race-management module. There is no new dependency, no new test fixture, and no new config section.

(Phase intentionally empty.)

**Checkpoint**: existing project state from `main` at `3a56911` is sufficient; proceed to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Internal-only additions to `RaceService` and a new `RuntimeSettings` module. Both must exist before any UI phase can wire them up.

- [X] T001 Extend `_transition(...)` in [src/services/race_service.py](../../src/services/race_service.py) with an optional `extra_payload: dict[str, str] | None = None` parameter that is merged into the persisted `race_events.payload_json` for that transition. Default `None` preserves all existing call sites byte-for-byte.
- [X] T002 Add an in-memory cache `self._safety_car_active: dict[int, bool] = {}` to `RaceService.__init__` in [src/services/race_service.py](../../src/services/race_service.py) for US2.
- [X] T003 [P] Create [src/services/runtime_settings.py](../../src/services/runtime_settings.py) implementing `RuntimeSettings(path=None)` per `plan.md` "Runtime-settings contract": atomic JSON writes via `tempfile.mkstemp` + `os.replace`, corrupt/missing file → defaults `{mock_mode: False}` with WARNING log on corruption, plus module-level helpers `get_mock_mode()` / `set_mock_mode(value)` backed by a `_default = RuntimeSettings()` singleton.

**Checkpoint**: Both new code paths exist, are typed, and pass `mypy --strict`. UI work for any of US1/US2/US3 can now proceed in parallel.

---

## Phase 3: User Story 1 — Finish Race by User (Priority: P1) 🎯 MVP

**Goal**: A primary-styled UI button that finishes a `running` or `paused` race, with the persisted `race_finished` event tagged `triggered_by='user'`.

**Independent Test**: Start a 2-driver `fixed_laps=20` race; click **🏁 Finish Race**; assert `races.status='finished'`, `finished_at IS NOT NULL`, `race_events` row of type `race_finished` with `payload_json->>'triggered_by'='user'`, `race_reports` row of type `race_summary`.

### Tests for User Story 1

- [X] T010 [P] [US1] In [tests/test_race_controls.py](../../tests/test_race_controls.py) add `test_finish_race_by_user_from_running` — start race → call `svc.finish_race_by_user(race.id)` → assert returned DTO is `RaceRead`, `status='finished'`, `finished_at` populated, event payload contains `triggered_by='user'`, `race_summary` report row created.
- [X] T011 [P] [US1] Add `test_finish_race_by_user_from_paused` — pause then `finish_race_by_user` succeeds.
- [X] T012 [P] [US1] Add `test_finish_race_by_user_rejects_invalid_status` parametrized over `{draft, ready, finished, cancelled}` — asserts `InvalidRaceStateError` with the current status name in the message and zero new DB rows.
- [X] T013 [P] [US1] Add `test_finish_race_by_user_clears_active_context` — asserts `ActiveRaceContext.get()` returns `None` after the call.

### Implementation for User Story 1

- [X] T014 [US1] Extend `RaceService.finish_race(race_id, *, triggered_by: str = "auto")` in [src/services/race_service.py](../../src/services/race_service.py) to thread `extra_payload={"triggered_by": triggered_by}` into `_transition(...)`.
- [X] T015 [US1] Add `RaceService.finish_race_by_user(race_id: int) -> RaceRead` in [src/services/race_service.py](../../src/services/race_service.py) as a thin wrapper calling `self.finish_race(race_id, triggered_by="user")`. Docstring documents `RaceRead` (DTO) per FR-130.
- [X] T016 [US1] In [src/pages/race_management.py](../../src/pages/race_management.py) add `_render_race_controls(race: RaceRead) -> None` invoked from `_render_running_view()` between the status badge and the reporting block. Render a primary-styled **🏁 Finish Race** button (key `finish_race_user_{race.id}`) that calls `svc.finish_race_by_user(race.id)` and surfaces `RaceNotFoundError | InvalidRaceStateError | RaceValidationError` via `st.error(str(exc))`.
- [X] T017 [US1] Guard the button so it renders only while `race.status ∈ {running, paused}` (FR-205).

**Checkpoint**: US1 is fully functional and independently shippable. Pre-feature suite + 4 new tests pass.

---

## Phase 4: User Story 2 — Safety Car Phase (Priority: P2)

**Goal**: Two-button toggle to start/end a safety-car phase, with idempotent persistence to `race_events` and a yellow banner in the UI.

**Independent Test**: With a running race, click **🟡 Safety Car** → assert exactly one `safety_car_started` event row + `is_safety_car_active(race_id) == True`. Click again → no new row (idempotent). Click **🟢 End Safety Car** → exactly one `safety_car_ended` row + flag is `False`.

### Tests for User Story 2

- [X] T020 [P] [US2] In [tests/test_race_controls.py](../../tests/test_race_controls.py) add `test_set_safety_car_on_running_persists_event` — assert event row count delta == 1, event_type == `safety_car_started`, payload == `{"active": "true"}`, `is_safety_car_active(...) is True`.
- [X] T021 [P] [US2] Add `test_set_safety_car_on_paused_succeeds`.
- [X] T022 [P] [US2] Add `test_set_safety_car_is_idempotent` — re-asserting ON writes zero additional rows.
- [X] T023 [P] [US2] Add `test_set_safety_car_end_persists_event_in_order` — start then end → exactly two rows, `safety_car_started` strictly before `safety_car_ended` by `created_at`.
- [X] T024 [P] [US2] Add `test_set_safety_car_rejects_invalid_status` parametrized over `{draft, ready, finished, cancelled}`.
- [X] T025 [P] [US2] Add `test_safety_car_cleared_on_finish` — flag is `False` after `finish_race_by_user`.
- [X] T026 [P] [US2] Add `test_safety_car_cleared_on_cancel` — flag is `False` after `cancel_race`.

### Implementation for User Story 2

- [X] T027 [US2] Add `RaceService.set_safety_car(race_id: int, active: bool) -> bool` in [src/services/race_service.py](../../src/services/race_service.py): re-loads race, guards `status ∈ {running, paused}`, short-circuits if cache value matches `active` (idempotent), otherwise inserts a `safety_car_started` or `safety_car_ended` `RaceEvent` row with `payload_json={"active": str(active).lower()}`, updates the cache, returns the new state.
- [X] T028 [US2] Add `RaceService.is_safety_car_active(race_id: int) -> bool` reading `self._safety_car_active.get(race_id, False)`.
- [X] T029 [US2] In `RaceService.finish_race(...)` and `RaceService.cancel_race(...)`, `self._safety_car_active.pop(race_id, None)` to clear the flag on lifecycle exit.
- [X] T030 [US2] In [src/pages/race_management.py](../../src/pages/race_management.py) inside `_render_race_controls(...)` add a two-column button row: column 1 holds the Finish button from T016; column 2 holds a toggle button (key `safety_car_{race.id}`) labeled **🟡 Safety Car** when inactive and **🟢 End Safety Car** when active. The handler calls `svc.set_safety_car(race.id, not sc_active)` with the same error-surface as T016.
- [X] T031 [US2] Above the standings table in `_render_running_view`, render a yellow `st.warning(...)` banner whenever `svc.is_safety_car_active(race.id)` returns `True`.

**Checkpoint**: US2 fully functional. Pre-feature suite + US1 tests + 7 new US2 tests pass.

---

## Phase 5: User Story 3 — Mock Mode Toggle (Priority: P3)

**Goal**: Settings-page toggle that flips `data/runtime_settings.json::mock_mode`; `src/main.py` adapter selection consults it on startup.

**Independent Test**: On the Settings page, toggle ON → `data/runtime_settings.json` written with `{"mock_mode": true}`. Restart `carrera-monitor` with no `--mac` / `--mock` → `MockCarreraAdapter` is loaded.

### Tests for User Story 3

- [X] T040 [P] [US3] In [tests/test_race_controls.py](../../tests/test_race_controls.py) add `test_runtime_settings_round_trip` — `set_mock_mode(True)`, new `RuntimeSettings(tmp_path)` reads `True` from disk; flip back to `False` and re-read.
- [X] T041 [P] [US3] Add `test_runtime_settings_missing_file_returns_defaults` — no file → `get_mock_mode() == False`, no exception raised.
- [X] T042 [P] [US3] Add `test_runtime_settings_corrupt_file_returns_defaults` — write `"not-json"` to the path → `get_mock_mode() == False`, WARNING logged, no exception raised.

### Implementation for User Story 3

- [X] T043 [US3] (Already done in T003 — listed here for traceability.) `src/services/runtime_settings.py` exists with `RuntimeSettings`, atomic-write + corrupt-recovery semantics, and module-level helpers.
- [X] T044 [US3] In [src/main.py](../../src/main.py) change adapter selection to `use_mock = args.mock or (args.mac is None and get_mock_mode())`, importing `from .services.runtime_settings import get_mock_mode`. CLI `--mock` / `--mac` still override (FR-225).
- [X] T045 [US3] In [src/pages/settings.py](../../src/pages/settings.py) add `_render_mock_mode_toggle()`: `st.toggle("Mock mode (race simulator)")` wired to `get_mock_mode()` / `set_mock_mode(value)`; on change, immediately persist and display the new state. Add a clear "restart required" notice and a "CLI flags override" notice (FR-224).

**Checkpoint**: US3 fully functional. Full suite green: 137 / 137 (was 116 pre-feature + 21 new = 137).

---

## Phase N: Polish & Cross-Cutting Concerns

- [X] T050 [P] Run `.venv/bin/ruff check .` — clean.
- [X] T051 [P] Run `.venv/bin/mypy src/` (strict) — `Success: no issues found in 30 source files`.
- [X] T052 [P] Run `.venv/bin/pytest -q` — 137 passed.
- [X] T053 Commit on branch `feat/race-controls`, push, open PR #5, watch CI, squash-merge with `--delete-branch`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: empty — no work.
- **Foundational (Phase 2)**: blocks all user-story phases. T001, T002, T003 can all run in parallel (T001 + T002 are different methods in the same file but non-overlapping diffs; T003 is a brand-new file).
- **US1, US2, US3**: all three are independent of each other and can be developed in parallel once Phase 2 ships. (US2 has a soft dependency on US1's `finish_race` payload extension only insofar as US2's `test_safety_car_cleared_on_finish` calls `finish_race_by_user` — but that's a test-time dependency only.)

### Within Each User Story

- Tests are written FIRST (red), then implementation flips them green.
- Models → services → endpoints → UI is degenerate here because there are no new models / no new endpoints; the order is simply `service method` → `UI wiring`.

### Parallel Opportunities

- T001, T002, T003 in parallel (Phase 2).
- All `[P]` tests within a story in parallel.
- US1, US2, US3 can be staffed in parallel after Phase 2 (no shared files except the same `race_service.py` and `race_management.py`, which need serialized commits but can be developed concurrently).

---

## Parallel Example: User Story 1

```bash
# After Phase 2 ships, kick off all four US1 tests in parallel against the in-memory engine fixture:
pytest -q tests/test_race_controls.py -k "test_finish_race_by_user" -n auto
```

---

## Implementation Strategy

### MVP First

Ship only US1 (T001 + T014–T017 + T010–T013). That's a < 50 LOC service change + a single button + four tests, and it delivers the most-requested missing primitive ("stop the race now"). US2 and US3 can land in follow-up PRs without coupling.

### Incremental Delivery

The feature was actually shipped as a single PR (#5) because the three slices total ~600 lines including tests and share the same review surface. Future similar bundles should default to splitting into three PRs of ≤ 200 LOC each.

### Suggested Slicing for Future Similar Features

1. PR #N: T001 + T002 + T003 (foundational additions, no UI).
2. PR #N+1: T010–T017 (US1 — finish button).
3. PR #N+2: T020–T031 (US2 — safety car).
4. PR #N+3: T040–T045 (US3 — mock-mode toggle).
