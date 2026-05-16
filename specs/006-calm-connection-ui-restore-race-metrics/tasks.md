# Tasks: Calm Connection UI + Restore Race Metrics

**Input**: Design documents from /specs/006-calm-connection-ui-restore-race-metrics/
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are included because the specification explicitly requires behavior coverage for icon mapping, race metrics rendering, lap normalization compatibility, and metric calculations (FR-015).

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare shared fixtures and test scaffolding used across story phases.

- [X] T001 Create dashboard race-metrics fixture snapshots for no-race and active-race scenarios in tests/fixtures/dashboard_state_no_race.json and tests/fixtures/dashboard_state_active_race.json
- [X] T002 [P] Add reusable telemetry event fixture builders for lap and lap_completed payload variants in tests/conftest.py
- [X] T003 [P] Add dashboard metrics regression test module scaffold in tests/test_dashboard_metrics.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement core normalization and snapshot foundations required before any user-story UI work.

**Critical**: User story implementation begins only after this phase is complete.

- [X] T004 Implement shared connection-state to indicator mapping helper with deterministic fallback behavior in src/dashboard.py
- [X] T005 [P] Extend race snapshot aggregation shape to include race-level metrics, per-car metrics, and diagnostics fields in src/state_manager.py
- [X] T006 [P] Extend canonical event/state compatibility for lap normalization inputs in src/event_model.py
- [X] T007 [P] Implement unified lap payload normalization helper for lap and lap_completed variants in src/carrera_client.py
- [X] T008 Implement malformed-lap and unknown-car safe handling with diagnostics counters in src/state_manager.py
- [X] T009 Implement dashboard metric-source priority resolution (state snapshot, repository/service fallback, in-memory fallback) in src/dashboard.py and src/services/race_service.py

**Checkpoint**: Core mapping, normalization, and snapshot contracts are stable and ready for independent user story delivery.

---

## Phase 3: User Story 1 - Calm Connection Indicator in Dashboard Header (Priority: P1) MVP

**Goal**: Replace noisy connection header text with an icon-only indicator while retaining detailed diagnostics elsewhere.

**Independent Test**: Force connection-state transitions and verify the header only renders one status icon while detailed fields remain available in diagnostics.

### Tests for User Story 1

- [X] T010 [P] [US1] Add connection indicator icon mapping tests for all required states in tests/test_dashboard_metrics.py
- [X] T011 [P] [US1] Add header-no-verbose-text regression test in tests/test_dashboard_metrics.py
- [X] T012 [P] [US1] Add diagnostics-panel detail visibility test for connection metadata in tests/test_dashboard_metrics.py

### Implementation for User Story 1

- [X] T013 [US1] Replace verbose connection header label with icon-only indicator rendering in src/dashboard.py
- [X] T014 [US1] Move detailed connection fields (state, device, MAC, retries, last seen, error) into diagnostics/overflow rendering in src/dashboard.py
- [X] T015 [US1] Implement unknown-state fallback indicator behavior and guardrails in src/dashboard.py

**Checkpoint**: US1 is complete when header remains calm and icon-only across all connection transitions.

---

## Phase 4: User Story 2 - Always Visible and Correct Race Metrics (Priority: P1)

**Goal**: Ensure race metrics always render and update correctly from normalized telemetry and snapshot sources.

**Independent Test**: Run telemetry updates with both lap payload variants and verify race-level plus per-car metrics update correctly, with placeholders when data is missing.

### Tests for User Story 2

- [X] T016 [P] [US2] Add lap normalization compatibility tests for lap.payload.lap_time_ms and lap_completed.payload.time_ms in tests/test_live_translation.py
- [X] T017 [P] [US2] Add race snapshot aggregation tests for active and inactive race scenarios in tests/test_state_manager.py
- [X] T018 [P] [US2] Add per-car metric calculation tests (lap_count, latest, best, average) in tests/test_state_manager.py
- [X] T019 [P] [US2] Add resilient handling tests for unknown car IDs and missing lap times in tests/test_state_manager.py

### Implementation for User Story 2

- [X] T020 [US2] Implement always-visible race metrics section with placeholder rendering for missing values in src/dashboard.py
- [X] T021 [US2] Implement race-level metric rendering (name, status, mode, elapsed, progress) in src/dashboard.py
- [X] T022 [US2] Implement per-car and global metrics rendering path (leader, fastest lap, total laps, fuel, pit, speed) in src/dashboard.py
- [X] T023 [US2] Wire normalized lap updates into unified state update flow for race metrics in src/state_manager.py and src/carrera_client.py
- [X] T024 [US2] Ensure repository/service fallback hydration for race metadata when snapshot fields are absent in src/dashboard.py and src/services/race_service.py

**Checkpoint**: US2 is complete when race metrics are continuously visible and accurate for both telemetry variants.

---

## Phase 5: User Story 3 - Stable Layout with Collapsed Diagnostics (Priority: P2)

**Goal**: Keep dashboard layout stable in live operation and confine verbose debug output to collapsed diagnostics.

**Independent Test**: Keep dashboard running through telemetry and reconnect churn, verify stable metrics layout and diagnostics visibility only on expand.

### Tests for User Story 3

- [X] T025 [P] [US3] Add dashboard layout stability regression test across refresh cycles in tests/test_dashboard_metrics.py
- [X] T026 [P] [US3] Add collapsed-by-default diagnostics panel behavior test in tests/test_dashboard_metrics.py
- [X] T027 [P] [US3] Add diagnostics payload field coverage test (last telemetry, active race id, lap counters, last payload) in tests/test_dashboard_metrics.py

### Implementation for User Story 3

- [X] T028 [US3] Refactor race metrics rendering into dedicated always-invoked render entry point in src/dashboard.py
- [X] T029 [US3] Implement collapsed diagnostics section for race-metric debug context in src/dashboard.py
- [X] T030 [US3] Propagate race-metric diagnostics fields (timestamps, counters, payload echoes) from state assembly in src/state_manager.py
- [X] T031 [US3] Remove verbose debug output from primary dashboard layout path in src/dashboard.py

**Checkpoint**: US3 is complete when the main dashboard remains stable and diagnostics stay optional/collapsed.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, documentation alignment, and release hygiene.

- [X] T032 [P] Update operator verification steps and expected outcomes for this feature in specs/006-calm-connection-ui-restore-race-metrics/quickstart.md
- [X] T033 [P] Update dashboard behavior notes for icon-only connection and always-visible metrics in README.md
- [X] T034 Run full quality gates (ruff, mypy, pytest) and record outcomes in specs/006-calm-connection-ui-restore-race-metrics/quickstart.md
- [X] T035 Commit feature changes, push branch, and verify CI run status for the head commit via GitHub Actions in .github/workflows/ci.yml

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup completion and blocks all user stories.
- User Story phases (Phase 3-5): depend on Foundational completion.
- Polish (Phase 6): depends on all desired user stories being complete.

### User Story Dependencies

- US1 (P1): starts after Foundational and is independently shippable as the calm-header MVP.
- US2 (P1): starts after Foundational; can run in parallel with late US1 tasks but should consume finalized normalization foundations.
- US3 (P2): starts after US2 rendering paths exist and hardens layout/diagnostics behavior.

### Within Each User Story

- Tests must be written first and fail before implementation.
- Normalize data and state updates before UI rendering changes.
- Complete story checkpoint validation before moving to the next priority.

## Parallel Opportunities

- Setup: T002 and T003 can run in parallel after T001 fixtures are created.
- Foundational: T005, T006, and T007 can run in parallel after T004 mapping helper exists.
- US1 tests: T010, T011, and T012 can run in parallel.
- US2 tests: T016, T017, T018, and T019 can run in parallel.
- US3 tests: T025, T026, and T027 can run in parallel.
- Polish: T032 and T033 can run in parallel before T034.

## Parallel Example: User Story 1

- Task: T010 [US1] icon mapping tests in tests/test_dashboard_metrics.py
- Task: T011 [US1] header-no-verbose-text test in tests/test_dashboard_metrics.py
- Task: T012 [US1] diagnostics visibility test in tests/test_dashboard_metrics.py

## Parallel Example: User Story 2

- Task: T016 [US2] lap normalization compatibility tests in tests/test_live_translation.py
- Task: T017 [US2] race snapshot aggregation tests in tests/test_state_manager.py
- Task: T018 [US2] per-car metric calculation tests in tests/test_state_manager.py
- Task: T019 [US2] malformed payload resilience tests in tests/test_state_manager.py

## Parallel Example: User Story 3

- Task: T025 [US3] layout stability test in tests/test_dashboard_metrics.py
- Task: T026 [US3] collapsed diagnostics default test in tests/test_dashboard_metrics.py
- Task: T027 [US3] diagnostics payload field coverage test in tests/test_dashboard_metrics.py

## Implementation Strategy

### MVP First (US1)

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate icon-only calm header behavior independently.
3. Demo/deploy the calm connection indicator as first increment.

### Incremental Delivery

1. Deliver US1 (calm header).
2. Deliver US2 (restored always-visible race metrics and normalization).
3. Deliver US3 (layout stability and collapsed diagnostics).
4. Run polish phase and final quality gates.

### Parallel Team Strategy

1. One developer handles state normalization and diagnostics propagation (Foundational, US2 backend path).
2. One developer handles dashboard rendering updates (US1 and US3 UI path).
3. One developer handles regression tests and quality validation across stories.

## Validation

- All tasks follow the checklist format: - [ ] T### [P?] [US?] Description with file path.
- Setup, Foundational, and Polish tasks intentionally have no story label.
- Story-phase tasks use [US1], [US2], and [US3] labels.
- Every task references concrete repository paths.
