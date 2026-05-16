# Tasks: Robust Bluetooth Connection Supervisor

**Input**: Design documents from `/specs/005-bluetooth-connection-supervisor/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are included because the specification defines explicit measurable outcomes and CI quality gates.

**Organization**: Tasks are grouped by user story to preserve independent implementation and testability.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish shared Bluetooth lifecycle primitives and configuration baseline.

- [ ] T001 Align Bluetooth configuration defaults and validation constraints in src/config.py and config.example.yaml
- [ ] T002 [P] Create canonical Bluetooth state vocabulary in src/state/bluetooth_state.py
- [ ] T003 [P] Create Bluetooth status/device schema models in src/schemas/bluetooth_schema.py
- [ ] T004 [P] Extend runtime settings defaults and command helpers for Bluetooth IPC in src/services/runtime_settings.py
- [ ] T005 [P] Export Bluetooth modules for stable imports in src/state/__init__.py and src/schemas/__init__.py and src/services/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement runtime lifecycle supervision and status propagation required by all user stories.

**Critical**: User story work starts only after this phase is complete.

- [ ] T006 Implement supervisor run loop and desired-state convergence in src/services/bluetooth_connection_supervisor.py
- [ ] T007 [P] Implement runtime command-sequence consume/dedupe logic in src/services/bluetooth_connection_supervisor.py
- [ ] T008 [P] Implement bounded reconnect backoff policy and delay cap handling in src/services/bluetooth_connection_supervisor.py
- [ ] T009 [P] Implement stale telemetry detection and optional reconnect-on-stale behavior in src/services/bluetooth_connection_supervisor.py
- [ ] T010 Implement normalized lifecycle event payload emission in src/services/bluetooth_connection_supervisor.py and src/event_model.py
- [ ] T011 [P] Integrate enriched Bluetooth connection snapshot aggregation in src/state_manager.py
- [ ] T012 [P] Integrate supervisor startup/shutdown wiring in live runtime path in src/main.py
- [ ] T013 Implement Bluetooth service facade for runtime and UI proxy modes in src/services/bluetooth_service.py

**Checkpoint**: Runtime supervision, lifecycle events, and snapshot propagation are available for story-level features.

---

## Phase 3: User Story 1 - Keep Live Telemetry Connected Reliably (Priority: P1) 🎯 MVP

**Goal**: Live telemetry survives transient disconnects and stale conditions without process restart.

**Independent Test**: Induce disconnect/stale conditions and verify bounded reconnect flow, recovery to usable connected state, and manual disconnect suppression semantics.

### Tests for User Story 1

- [ ] T014 [P] [US1] Add unexpected disconnect and reconnect transition tests in tests/test_bluetooth_connection_supervisor.py
- [ ] T015 [P] [US1] Add reconnect backoff cap and reset-on-success tests in tests/test_bluetooth_connection_supervisor.py
- [ ] T016 [P] [US1] Add stale-timeout and reconnect-on-stale tests in tests/test_bluetooth_connection_supervisor.py
- [ ] T017 [P] [US1] Add manual disconnect suppression and retry re-enable tests in tests/test_bluetooth_connection_supervisor.py

### Implementation for User Story 1

- [ ] T018 [US1] Implement unexpected disconnect recovery path and state transitions in src/services/bluetooth_connection_supervisor.py
- [ ] T019 [US1] Implement explicit manual disconnect state behavior in src/services/bluetooth_connection_supervisor.py
- [ ] T020 [US1] Emit reconnect/stale/error lifecycle events with reason metadata in src/services/bluetooth_connection_supervisor.py and src/event_model.py
- [ ] T021 [US1] Persist reconnect attempts and telemetry freshness metadata to snapshots in src/state_manager.py

**Checkpoint**: Runtime reconnect reliability behaviors are independently testable and meet US1 acceptance criteria.

---

## Phase 4: User Story 2 - Control Bluetooth Lifecycle From the Dashboard (Priority: P1)

**Goal**: Dashboard users can connect, disconnect, scan, retry, and inspect rich Bluetooth status.

**Independent Test**: Use dashboard controls to issue all lifecycle actions and confirm runtime intent persistence plus status rendering updates.

### Tests for User Story 2

- [ ] T022 [P] [US2] Add Bluetooth control action request tests in tests/test_bluetooth_service.py
- [ ] T023 [P] [US2] Add button disabled-state and retry visibility tests in tests/test_bluetooth_service.py
- [ ] T024 [P] [US2] Add enriched lifecycle payload validation tests in tests/test_event_model.py
- [ ] T025 [P] [US2] Add connection snapshot field coverage tests in tests/test_state_manager.py

### Implementation for User Story 2

- [ ] T026 [US2] Implement connect/disconnect/scan/retry control panel interactions in src/pages/settings.py
- [ ] T027 [US2] Implement selected-device and desired-state request persistence in src/services/runtime_settings.py and src/pages/settings.py
- [ ] T028 [US2] Implement dashboard Bluetooth status badges (state, desired state, device, retries, last seen, error) in src/dashboard.py
- [ ] T029 [US2] Implement service-level control policy and status translation in src/services/bluetooth_service.py
- [ ] T030 [US2] Wire live runtime adapter ownership to supervisor interface in src/main.py

**Checkpoint**: Dashboard Bluetooth controls and status views are independently testable and satisfy US2 acceptance criteria.

---

## Phase 5: User Story 3 - Preserve Safe Coexistence With Simulator Mode (Priority: P2)

**Goal**: Simulator/mock mode and Bluetooth lifecycle controls remain independent and non-mutating.

**Independent Test**: Enable simulator mode, execute Bluetooth actions, and confirm simulator state and Bluetooth desired state only change when explicitly requested.

### Tests for User Story 3

- [ ] T031 [P] [US3] Add simulator-mode independence tests for Bluetooth actions in tests/test_bluetooth_service.py
- [ ] T032 [P] [US3] Add mock-mode precedence regression tests in tests/test_main_adapter_selection.py

### Implementation for User Story 3

- [ ] T033 [US3] Implement simulator warning helper and coexistence rules in src/services/bluetooth_service.py
- [ ] T034 [US3] Apply simulator coexistence messaging and UX safeguards in src/pages/settings.py
- [ ] T035 [US3] Enforce separation of mock-mode and Bluetooth command state in src/services/runtime_settings.py and src/main.py

**Checkpoint**: Simulator coexistence requirements are independently testable and satisfy US3 acceptance criteria.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize docs, verification, and release hygiene across stories.

- [ ] T036 [P] Update supervisor lifecycle documentation for operators in README.md and specs/005-bluetooth-connection-supervisor/quickstart.md
- [ ] T037 [P] Finalize lifecycle contract details after implementation in specs/005-bluetooth-connection-supervisor/contracts/bluetooth-supervisor-lifecycle.md
- [ ] T038 Run full quality gates and record verification outcomes in specs/005-bluetooth-connection-supervisor/quickstart.md
- [ ] T039 Verify runtime settings tracking exclusion remains correct in .gitignore and data/runtime_settings.json
- [ ] T040 Add backward-compatibility regression checks for legacy connection snapshot/event fields in tests/test_event_model.py and tests/test_state_manager.py
- [ ] T041 Execute 20 induced disconnect trials and record >=95% ready-state recovery evidence in specs/005-bluetooth-connection-supervisor/quickstart.md
- [ ] T042 Add and verify <=1s status visibility latency assertion from lifecycle transition to snapshot update in tests/test_state_manager.py
- [ ] T043 Commit, push, and verify CI matrix status defined in .github/workflows/ci.yml

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup completion and blocks all user stories.
- User Story phases (Phase 3-5): depend on Foundational completion.
- Polish (Phase 6): depends on all desired user stories being complete.

### User Story Dependencies

- US1 (P1): starts immediately after Foundational and defines core runtime resilience.
- US2 (P1): starts after Foundational; can run partially in parallel with late US1 tasks but should consume stabilized lifecycle/status contracts.
- US3 (P2): starts after US2 controls exist and relies on finalized dashboard/service interaction paths.

### Within Each User Story

- Write tests first and confirm failures before implementation tasks.
- Complete lifecycle/state implementation before UI wiring for that story.
- Validate each story independently at checkpoint before advancing.

## Parallel Opportunities

- Setup: T002-T005 can run in parallel after T001 baseline is set.
- Foundational: T007-T009 and T011-T012 can run in parallel after T006 skeleton exists.
- US1 tests: T014-T017 can run in parallel.
- US2 tests: T022-T025 can run in parallel.
- US3 tests: T031-T032 can run in parallel.
- Polish: T036-T037 and T040-T042 can run in parallel.

## Parallel Example: User Story 1

```bash
Task: "T014 [US1] reconnect transition tests in tests/test_bluetooth_connection_supervisor.py"
Task: "T015 [US1] backoff cap tests in tests/test_bluetooth_connection_supervisor.py"
Task: "T016 [US1] stale timeout tests in tests/test_bluetooth_connection_supervisor.py"
```

## Parallel Example: User Story 2

```bash
Task: "T022 [US2] control action request tests in tests/test_bluetooth_service.py"
Task: "T024 [US2] lifecycle payload validation in tests/test_event_model.py"
Task: "T025 [US2] snapshot field tests in tests/test_state_manager.py"
```

## Parallel Example: User Story 3

```bash
Task: "T031 [US3] simulator independence tests in tests/test_bluetooth_service.py"
Task: "T032 [US3] mock-mode precedence regression tests in tests/test_main_adapter_selection.py"
```

## Implementation Strategy

### MVP First (US1)

1. Complete Setup and Foundational phases.
2. Complete US1 and validate reconnect reliability independently.
3. Release runtime resilience improvements as MVP.

### Incremental Delivery

1. Add US2 dashboard controls and rich status display.
2. Add US3 simulator coexistence guarantees.
3. Finish with cross-cutting docs and quality verification.

### Team Parallelization Strategy

1. One engineer owns supervisor runtime behavior (US1).
2. One engineer owns dashboard/service interaction (US2).
3. One engineer owns coexistence safeguards and regressions (US3).

## Validation

- All tasks follow strict checklist format: `- [ ] T### [P?] [US?] Description with file path`.
- Setup, Foundational, and Polish tasks intentionally omit user-story labels.
- Story-phase tasks are labeled with `[US1]`, `[US2]`, or `[US3]`.
- Every task references concrete repository file paths.
