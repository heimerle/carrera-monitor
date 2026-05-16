---
description: "Task list for Live Continuity Hardening follow-up (auto car detection, reconnect persistence, BLE stability)"
---

# Tasks: Live Continuity Hardening

**Input**: Design documents from `/specs/003-live-adapter-carreralib/`  
**Prerequisites**: plan.md (required), spec.md (reference), research.md, data-model.md, contracts/live-adapter.md, contracts/live-reliability-hardening.md, quickstart.md

**Tests**: Included. This plan explicitly requires behavior and regression tests for all user stories.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare configuration and scaffolding shared by all stories.

- [X] T001 Add new bluetooth hardening defaults and validation fields in `src/config.py` and `config.example.yaml`
- [X] T002 Create continuity service scaffold in `src/services/live_continuity.py`
- [X] T003 Export continuity service symbols in `src/services/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add persistence and repository primitives required by all user stories.

**⚠️ CRITICAL**: No user story work starts before this phase is complete.

- [X] T004 Add `RaceLapCheckpoint` and `RaceLapIngestIdentity` ORM models in `src/models.py`
- [X] T005 Add schema smoke coverage for new tables and constraints in `tests/test_database_init.py`
- [X] T006 Implement checkpoint and lap-identity repository operations in `src/repositories/race_repository.py`
- [X] T007 Add repository tests for checkpoint/idempotency behavior in `tests/test_race_repository.py`
- [X] T008 Wire continuity dependencies into race ingest path in `src/services/race_service.py` and `src/race_runner.py`
- [X] T009 Create reconnect continuity test harness and fixtures in `tests/test_live_continuity.py`

**Checkpoint**: Foundation complete. User stories can now proceed.

---

## Phase 3: User Story 1 - Auto Detect Active Cars (Priority: P1) 🎯 MVP

**Goal**: Detect active race cars automatically from live telemetry, capped at 6 canonical car IDs.

**Independent Test**: Start live mode with one car active and verify snapshot/UI reports one active car; add a second car and verify count updates; never exceed 6.

### Tests for User Story 1

- [X] T010 [P] [US1] Add status-slot normalization tests for canonical `car_id` range in `tests/test_live_translation.py`
- [X] T011 [P] [US1] Add timer-slot normalization tests for canonical `car_id` mapping in `tests/test_live_translation.py`
- [X] T012 [P] [US1] Add active-car detection window tests in `tests/test_state_manager.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement `CarSlotMapping` and `ActiveCarDetector` in `src/services/live_continuity.py`
- [X] T014 [US1] Apply canonical slot mapping and max-6 filtering in `src/carrera_client.py`
- [X] T015 [US1] Persist `active_car_ids` and `active_car_count` in snapshots in `src/state_manager.py`
- [X] T016 [US1] Render active car metrics in dashboard header in `src/dashboard.py`
- [X] T017 [US1] Display auto-detected active car count in running race view in `src/pages/race_management.py`

**Checkpoint**: US1 is fully functional and independently testable.

---

## Phase 4: User Story 2 - Preserve Race Data Across Reconnect/Restart (Priority: P1)

**Goal**: Keep lap continuity and race history intact through reconnects and process restarts.

**Independent Test**: Run a race, force reconnect, and verify lap counts continue without reset or duplicate loss; restart process and verify continuity restoration.

### Tests for User Story 2

- [X] T018 [P] [US2] Add replayed-crossing idempotency test in `tests/test_race_service_ingest.py`
- [X] T019 [P] [US2] Add reconnect lap continuity regression test in `tests/test_live_continuity.py`
- [X] T020 [P] [US2] Add startup recovery continuity test in `tests/test_race_runner.py`

### Implementation for User Story 2

- [X] T021 [US2] Extend timer raw frame payload with `cu_timestamp_ms` in `src/carrera_client.py`
- [X] T022 [US2] Implement checkpoint load/save API in `src/services/live_continuity.py`
- [X] T023 [US2] Restore/update lap checkpoints during ingest in `src/services/race_service.py`
- [X] T024 [US2] Enforce idempotent lap ingest using repository identity checks in `src/repositories/race_repository.py`
- [X] T025 [US2] Update running-race recovery defaults for continuity in `src/config.py` and `src/services/race_service.py`
- [X] T026 [US2] Add structured continuity diagnostics in `src/services/race_service.py`

**Checkpoint**: US2 is fully functional and independently testable.

---

## Phase 5: User Story 3 - Stabilize Bluetooth Liveness Policy (Priority: P2)

**Goal**: Improve BLE stability using probe/watchdog transitions and optional maintenance reconnect that is disabled by default and blocked during running races.

**Independent Test**: Simulate stale link and verify `healthy -> degraded -> stalled -> reconnecting -> healthy` transitions; verify periodic reconnect is skipped while race is running.

### Tests for User Story 3

- [X] T027 [P] [US3] Add link-health transition tests in `tests/test_live_idle_watchdog.py`
- [X] T028 [P] [US3] Add bluetooth hardening config validation tests in `tests/test_main_adapter_selection.py`
- [X] T029 [P] [US3] Add periodic-reconnect running-race guard test in `tests/test_live_ble_stability.py`

### Implementation for User Story 3

- [X] T030 [US3] Add new bluetooth liveness config fields in `src/config.py`
- [X] T031 [US3] Pass liveness and backoff knobs to runner wiring in `src/main.py`
- [X] T032 [US3] Emit degraded/stalled watchdog health states in `src/carrera_client.py`
- [X] T033 [US3] Implement optional periodic maintenance reconnect gate in `src/carrera_client.py` and `src/race_runner.py`
- [X] T034 [US3] Surface link-health reason metadata in snapshot and UI in `src/state_manager.py` and `src/dashboard.py`

**Checkpoint**: US3 is fully functional and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening, docs, and validation across all user stories.

- [X] T035 [P] Update operator troubleshooting and recovery guidance in `docs/troubleshooting.md`
- [X] T036 [P] Update verification flow and config examples in `specs/003-live-adapter-carreralib/quickstart.md`
- [X] T037 Run focused continuity verification command set from `specs/003-live-adapter-carreralib/quickstart.md`
- [X] T038 Run full quality gates and fix regressions across `src/` and `tests/`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): start immediately
- Foundational (Phase 2): depends on Setup; blocks all user stories
- User stories (Phase 3+): depend on Foundational completion
- Polish (Phase 6): depends on all user stories

### User Story Dependencies

- US1 (P1): starts after Phase 2; no dependency on other stories
- US2 (P1): starts after Phase 2; depends on canonical mapping outcomes from US1
- US3 (P2): starts after Phase 2; should integrate after US2 continuity behavior is stable

### Within Each User Story

- Write tests first and confirm they fail
- Implement core logic next
- Integrate with UI/state/repository wiring
- Re-run story-specific tests before moving on

## Parallel Opportunities

- Tasks marked [P] in each phase can run in parallel
- US1 test tasks T010-T012 can run in parallel
- US2 test tasks T018-T020 can run in parallel
- US3 test tasks T027-T029 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Run US1 test tasks in parallel workstreams:
Task: "T010 Add status-slot normalization tests in tests/test_live_translation.py"
Task: "T011 Add timer-slot normalization tests in tests/test_live_translation.py"
Task: "T012 Add active-car detection window tests in tests/test_state_manager.py"
```

## Parallel Example: User Story 2

```bash
# Run US2 test tasks in parallel workstreams:
Task: "T018 Add replayed-crossing idempotency test in tests/test_race_service_ingest.py"
Task: "T019 Add reconnect lap continuity regression test in tests/test_live_continuity.py"
Task: "T020 Add startup recovery continuity test in tests/test_race_runner.py"
```

## Parallel Example: User Story 3

```bash
# Run US3 test tasks in parallel workstreams:
Task: "T027 Add link-health transition tests in tests/test_live_idle_watchdog.py"
Task: "T028 Add bluetooth hardening config validation tests in tests/test_main_adapter_selection.py"
Task: "T029 Add periodic-reconnect running-race guard test in tests/test_live_ble_stability.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2
2. Complete US1 (Phase 3)
3. Validate active-car detection end-to-end
4. Ship MVP if needed

### Incremental Delivery

1. Deliver US1 (auto car detection)
2. Deliver US2 (reconnect/restart data continuity)
3. Deliver US3 (advanced BLE liveness policy)
4. Finish with polish and full quality gates

### Validation Gate

- Story-specific tests must pass at each checkpoint
- Final gate requires lint, type checks, and full pytest run
