# Tasks: Manual Bluetooth Connection via Overflow Menu

**Input**: Design documents from `/specs/004-bluetooth-connect-menu/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are included because the spec defines explicit verification and CI quality gates.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the feature branch and baseline tooling for repeatable implementation.

- [ ] T001 Create and switch to feature branch `004-bluetooth-connect-menu` from `main` and verify clean working tree for files under specs/004-bluetooth-connect-menu/
- [ ] T002 [P] Verify local toolchain entry points (`python -m pytest`, `python -m mypy`, `python -m ruff`) from repository root in ./

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared service/state contracts that all user-story work depends on.

- [ ] T003 Create Bluetooth lifecycle enum and status snapshot model in src/services/bluetooth_state.py
- [ ] T004 [P] Create EventBus event payload helper for `bluetooth.state.changed` in src/services/bluetooth_events.py
- [ ] T005 [P] Extend runtime settings schema defaults for `bluetooth_mac` and `scan_timeout_seconds` in src/services/runtime_settings.py

**Checkpoint**: Shared Bluetooth state and event primitives are ready for story implementation.

---

## Phase 3: User Story 1 - Connect to Carrera AppConnect from Dashboard (Priority: P1) 🎯 MVP

**Goal**: Operator can scan/select/connect/disconnect from the overflow menu while seeing lifecycle status and preserving simulator independence.

**Independent Test**: Start dashboard, open overflow menu, run scan, select device, observe `CONNECTING -> CONNECTED`, disconnect to `DISCONNECTED`, and verify startup fallback MAC still obeys CLI/config precedence.

### Tests for User Story 1

- [ ] T006 [P] [US1] Add runtime settings tests for `bluetooth_mac` and bounded `scan_timeout_seconds` behavior in tests/test_race_controls.py
- [ ] T007 [P] [US1] Add scanner service tests for success, ImportError mapping, and generic error mapping in tests/test_bluetooth_scanner.py
- [ ] T008 [P] [US1] Add Bluetooth lifecycle/state transition tests for allowed transitions and error snapshots in tests/test_bluetooth_state_service.py
- [ ] T009 [P] [US1] Add `_apply_overrides` precedence tests for CLI/config/persisted fallback in tests/test_main_overrides.py
- [ ] T010 [P] [US1] Add dashboard overflow workflow tests for connect/disconnect/status/scan error rendering in tests/test_dashboard_bluetooth_menu.py

### Implementation for User Story 1

- [ ] T011 [US1] Implement scanner module with normalized device output and timeout support in src/services/bluetooth_scanner.py
- [ ] T012 [US1] Implement connection lifecycle service (`connect`, `disconnect`, `scan`, `get_status`) with EventBus emission in src/services/bluetooth_connection_service.py
- [ ] T013 [US1] Extend startup override fallback to persisted `bluetooth_mac` while preserving CLI/config precedence in src/main.py
- [ ] T014 [US1] Implement overflow menu entries (Connect, Disconnect, Scan, Status) and status rendering in src/dashboard.py
- [ ] T015 [US1] Integrate retry behavior and state transitions (`ERROR -> CONNECTING` or `ERROR -> SCANNING`) in src/dashboard.py
- [ ] T016 [US1] Enforce simulator/mock coexistence guardrails so Bluetooth actions do not mutate simulator mode in src/dashboard.py

**Checkpoint**: User Story 1 is fully functional and independently testable.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, documentation sync, and release workflow.

- [ ] T017 [P] Update user-facing usage notes for overflow Bluetooth workflow in specs/004-bluetooth-connect-menu/quickstart.md
- [ ] T018 Run full quality gate (`python -m ruff check src tests`, `python -m mypy src`, `python -m pytest -q`) from ./
- [ ] T019 Run manual quickstart validation for connect/disconnect/scan/status/retry/simulator coexistence from specs/004-bluetooth-connect-menu/quickstart.md
- [ ] T020 Verify no new hard dependency is introduced for this slice by checking packaging metadata and lock/update files remain unchanged for required deps in pyproject.toml
- [ ] T021 Verify runtime settings file remains excluded from source control by checking `.gitignore` coverage and ensuring `data/runtime_settings.json` is not tracked
- [ ] T022 Commit, push, open PR, monitor Actions via `gh api repos/heimerle/carrera-monitor/actions/runs?head_sha=$SHA`, and merge when green

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on setup completion.
- User Story 1 (Phase 3): depends on all foundational tasks T003-T005.
- Polish (Phase 4): depends on Phase 3 completion.

### User Story Dependencies

- User Story 1 (P1): starts after Phase 2, no dependency on other stories.

### Within User Story 1

- Tests T006-T010 are authored first and should fail before implementation.
- T011 depends on T007.
- T012 depends on T003, T004, T008, and T011.
- T013 depends on T005 and T009.
- T014 depends on T012 and T010.
- T015 depends on T014.
- T016 depends on T014.

## Parallel Opportunities

- Foundational tasks T004 and T005 can run in parallel after T003 scope is defined.
- Test tasks T006-T010 can run in parallel across separate test files.
- Implementation tasks T013 and T011 can run in parallel after their prerequisite tests exist.
- Implementation tasks T015 and T016 can run in parallel after T014 lands.

## Parallel Example: User Story 1

```bash
# Parallel test authoring
Task: "T006 [US1] runtime settings tests in tests/test_race_controls.py"
Task: "T007 [US1] scanner tests in tests/test_bluetooth_scanner.py"
Task: "T008 [US1] lifecycle tests in tests/test_bluetooth_state_service.py"
Task: "T009 [US1] overrides tests in tests/test_main_overrides.py"
Task: "T010 [US1] dashboard workflow tests in tests/test_dashboard_bluetooth_menu.py"

# Parallel implementation after tests exist
Task: "T011 [US1] scanner implementation in src/services/bluetooth_scanner.py"
Task: "T013 [US1] override fallback update in src/main.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Validate User Story 1 independently with test suite + quickstart.
4. Ship via PR after CI is green.

### Incremental Delivery

1. Land state/event foundations (T003-T005).
2. Land scanner + override compatibility (T011, T013).
3. Land dashboard interaction flow (T014-T016).
4. Complete polish and release workflow (T017-T022).

## Validation

- All tasks use strict checklist format: `- [ ] T### [P?] [US?] Description with file path`.
- Story tasks include `[US1]`; Setup/Foundational/Polish tasks omit story labels.
- Each task points to a concrete file path.
- Task ordering supports independent testing of User Story 1.
