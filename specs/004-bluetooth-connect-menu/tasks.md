# Tasks: Manual Bluetooth Connection via Overflow Menu

**Input**: Design documents from `/specs/004-bluetooth-connect-menu/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are included because the specification defines explicit verification and CI quality gates (SC-005).

**Organization**: Tasks are grouped by user story so the slice can be implemented and validated independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the Bluetooth domain scaffolding and shared settings primitives.

- [ ] T001 Create Bluetooth state vocabulary module in src/state/bluetooth_state.py
- [ ] T002 [P] Create Bluetooth schema models for status/device payloads in src/schemas/bluetooth_schema.py
- [ ] T003 [P] Export Bluetooth modules for package-level imports in src/state/__init__.py and src/schemas/__init__.py
- [ ] T004 Extend runtime settings defaults for Bluetooth desired state and command IPC in src/services/runtime_settings.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement core supervisor lifecycle and data propagation required by all user-facing Bluetooth actions.

**Critical**: No story-level UI workflow should be finalized before this phase is complete.

- [ ] T005 Implement supervisor run loop and desired-state reconciliation in src/services/bluetooth_connection_supervisor.py
- [ ] T006 [P] Implement reconnect backoff, stale detection, and manual disconnect handling in src/services/bluetooth_connection_supervisor.py
- [ ] T007 [P] Emit normalized lifecycle payloads for connection-state events in src/services/bluetooth_connection_supervisor.py and src/event_model.py
- [ ] T008 Implement supervisor-backed Bluetooth service facade for runtime and UI proxy modes in src/services/bluetooth_service.py
- [ ] T009 [P] Integrate live runtime startup/shutdown with BluetoothConnectionSupervisor in src/main.py
- [ ] T010 [P] Extend state snapshots with enriched Bluetooth fields in src/state_manager.py

**Checkpoint**: Core Bluetooth lifecycle management is stable and observable without dashboard-specific UI behavior.

---

## Phase 3: User Story 1 - Manage Bluetooth Connection from the Dashboard (Priority: P1)

**Goal**: Operator can scan/connect/disconnect/retry from dashboard controls, observe accurate lifecycle state, and keep simulator mode independent.

**Independent Test**: Use dashboard controls to trigger connect/disconnect/scan/retry, verify state transitions and persisted selection behavior, and confirm simulator mode remains unchanged.

### Tests for User Story 1

- [ ] T011 [P] [US1] Add supervisor lifecycle transition tests in tests/test_bluetooth_connection_supervisor.py
- [ ] T012 [P] [US1] Add stale/reconnect and duplicate-loop prevention tests in tests/test_bluetooth_connection_supervisor.py
- [ ] T013 [P] [US1] Add Bluetooth service button-state and simulator-warning policy tests in tests/test_bluetooth_service.py
- [ ] T014 [P] [US1] Add enriched connection payload validation tests in tests/test_event_model.py
- [ ] T015 [P] [US1] Add connection snapshot propagation tests in tests/test_state_manager.py

### Implementation for User Story 1

- [ ] T016 [US1] Implement Settings page Bluetooth controls using request-based service calls in src/pages/settings.py
- [ ] T017 [US1] Implement dashboard connection status rendering (device, desired state, stale, retries, last seen) in src/dashboard.py
- [ ] T018 [US1] Implement Connect/Disconnect/Scan/Retry button enablement policy in src/services/bluetooth_service.py and src/pages/settings.py
- [ ] T019 [US1] Persist selected device and desired connection requests via runtime settings in src/services/runtime_settings.py and src/pages/settings.py
- [ ] T020 [US1] Enforce simulator coexistence messaging and non-mutating behavior in src/services/bluetooth_service.py and src/pages/settings.py

**Checkpoint**: User Story 1 is independently functional and testable from the dashboard.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, documentation, and release hygiene.

- [ ] T021 [P] Update operator documentation for Bluetooth supervisor workflow in README.md and specs/004-bluetooth-connect-menu/quickstart.md
- [ ] T022 Run full quality gates from ./ against src/ and tests/
- [ ] T023 Run manual quickstart validation scenarios from specs/004-bluetooth-connect-menu/quickstart.md
- [ ] T024 Verify runtime settings tracking exclusion for data/runtime_settings.json in .gitignore
- [ ] T025 Commit, push, and verify CI status for .github/workflows/ci.yml

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup completion.
- User Story 1 (Phase 3): depends on Foundational completion.
- Polish (Phase 4): depends on User Story 1 completion.

### User Story Dependencies

- User Story 1 (P1): can start once Phase 2 is complete; no dependency on additional stories.

### Within User Story 1

- Write tests T011-T015 first and confirm failures before implementation tasks.
- Complete T016-T018 before finalizing persistence/state edge cases in T019-T020.
- Validate dashboard behavior after each lifecycle capability change.

## Parallel Opportunities

- T002 and T003 can run in parallel after T001 scope is clear.
- T006, T007, T009, and T010 can run in parallel after T005 skeleton is in place.
- T011-T015 are parallelizable because they target different validation slices.
- T021 and T024 can run in parallel during polish.

## Parallel Example: User Story 1

```bash
# Parallel test authoring
Task: "T011 [US1] lifecycle transitions in tests/test_bluetooth_connection_supervisor.py"
Task: "T013 [US1] service button policy in tests/test_bluetooth_service.py"
Task: "T014 [US1] connection payload validation in tests/test_event_model.py"

# Parallel implementation after test scaffolds exist
Task: "T017 [US1] dashboard status rendering in src/dashboard.py"
Task: "T018 [US1] button enablement policy in src/services/bluetooth_service.py and src/pages/settings.py"
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (tests first, then implementation).
3. Validate independent Story 1 behavior from quickstart scenarios.
4. Ship after Phase 4 quality gates are green.

### Incremental Delivery

1. Land lifecycle foundation (state/schema/settings/supervisor).
2. Land UI control flow and status rendering.
3. Land tests and tighten edge-case behavior.
4. Finish documentation, quality gates, and CI verification.

## Validation

- All checklist entries follow strict format: `- [ ] T### [P?] [US?] Description with file path`.
- Setup, Foundational, and Polish tasks intentionally omit story labels.
- User-story tasks are labeled `[US1]`.
- Each task references concrete workspace paths.