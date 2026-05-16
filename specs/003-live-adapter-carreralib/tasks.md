---
description: "Task list for the live-adapter-carreralib feature (LiveCarreraAdapter + --scan CLI + BLE reconnect hardening)"
---

# Tasks: Live Adapter (carreralib) + `--scan` CLI + BLE Reconnect Hardening

**Feature Branch**: `003-live-adapter-carreralib` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Input**: Design documents in `specs/003-live-adapter-carreralib/`
**Prerequisites**: plan.md, spec.md, research.md (D-001…D-008), data-model.md, contracts/live-adapter.md, quickstart.md

**Tests**: INCLUDED. Every functional requirement (FR-001…FR-009) and every success criterion (SC-001…SC-006) has at least one anchoring test under [tests/](../../tests/).

**Organization**: Tasks are grouped by **user story** (US1…US4 from [spec.md](./spec.md)). For traceability with the four squash-merges that shipped this feature on `main`, every task also carries its PR tag (`[PR9]`, `[PR10]`, `[PR12]`, `[PR14]`) in the description.

**Status**: All tasks below were implemented on `main` via PRs #9, #10, #12, #14 and are marked `[X]`. This file exists so that any follow-up `/speckit.tasks` work has a normal `plan.md → tasks.md` anchor and so that each FR/SC has a traceable task ID.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User-story label (`[US1]`…`[US4]`); omitted for Setup, Foundational, and Polish phases
- Every task includes an exact file path and references the FR/SC/D IDs it satisfies

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pull in the third-party library that the rest of the feature builds on.

- [X] T001 Add `carreralib` to [requirements.txt](../../requirements.txt) so the live adapter has its BLE/serial dependency available on every CI matrix leg (Python 3.11 + 3.12 × ubuntu-latest + macos-latest). Anchors **FR-001**, **D-001**. (Shipped in PR #9.)

**Checkpoint**: `carreralib` importable in the project venv; CI matrix can resolve the dependency.

---

## Phase 2: Foundational (Blocking Prerequisites for US2/US3/US4)

**Purpose**: Establish the base `LiveCarreraAdapter` shell (constructor + `connect` + `events` + `close` + `Status`/`Timer` translation). This is the shared substrate that user stories US2, US3, and US4 build on. US1 (`--scan`) is independent of this phase — it only needs `carreralib.scan()` from Phase 1.

**⚠️ CRITICAL**: No US2/US3/US4 task may start until Phase 2 is complete.

### Tests for Foundational Phase

- [X] T002 [P] In [tests/test_live_translation.py](../../tests/test_live_translation.py) add unit tests covering `carreralib.Status` → `TelemetryEvent` translation (fuel level, pit flags, position deltas, driver-id mapping). Anchors **FR-001**. (Shipped in PR #9.)
- [X] T003 [P] In [tests/test_live_translation.py](../../tests/test_live_translation.py) add unit tests covering `carreralib.Timer` → `TelemetryEvent` translation (lap timestamps, sector splits, controller index). Anchors **FR-001**. (Shipped in PR #9.)
- [X] T004 [P] Extend [tests/test_adapter_contract.py](../../tests/test_adapter_contract.py) to assert `LiveCarreraAdapter` honors the shared `TelemetryAdapter` protocol (`connect` / `events` / `close` shapes, async-iterator semantics). Anchors **FR-001** and contract [contracts/live-adapter.md](./contracts/live-adapter.md) §1. (Shipped in PR #9.)

### Implementation for Foundational Phase

- [X] T005 Implement `LiveCarreraAdapter.__init__` in [src/carrera_client.py](../../src/carrera_client.py): accept connection parameters, initialize the internal event queue, the `_connected` flag, and the reader-task handle. Keep zero-arg construction valid for test fakes. Anchors **FR-001**, **D-001**. (Shipped in PR #9.)
- [X] T006 Implement `LiveCarreraAdapter.connect()` in [src/carrera_client.py](../../src/carrera_client.py): open the `carreralib.ControlUnit`, call `cu.reset()` on first connect, start the background reader task that pushes `Status`/`Timer` frames onto the queue. Anchors **FR-001**, **D-001**. (Shipped in PR #9; gating logic added in PR #14 — see US2.)
- [X] T007 Implement `LiveCarreraAdapter.events()` (async iterator) and `LiveCarreraAdapter.close()` in [src/carrera_client.py](../../src/carrera_client.py): drain the queue, translate frames to `TelemetryEvent`, cancel and await the reader task on close. Anchors **FR-001**, **D-001**. (Shipped in PR #9; reader-exception surfacing added in PR #14 — see US2.)
- [X] T008 Implement `Status` → `TelemetryEvent` translation in [src/carrera_client.py](../../src/carrera_client.py) (fuel, pit, position fields). Anchors **FR-001**. (Shipped in PR #9.)
- [X] T009 Implement `Timer` → `TelemetryEvent` translation in [src/carrera_client.py](../../src/carrera_client.py) (lap timestamps, controller index). Anchors **FR-001**. (Shipped in PR #9.)

**Checkpoint**: `LiveCarreraAdapter` satisfies the shared adapter contract; `Status`/`Timer` frames translate cleanly; US2/US3/US4 unblocked.

---

## Phase 3: User Story 1 — Discover Control Units before a race (Priority: P1) 🎯 MVP

**Story Goal**: A race operator at a new venue can list reachable Carrera Control Units before committing to a full run, via a side-effect-free `python -m src.main --scan` invocation.

**Independent Test**: Run `python -m src.main --scan` on a host with no CU in range — process MUST print zero device lines, exit 0, and create no SQLite race row, no telemetry log file, and no dashboard process (SC-005).

**Dependencies**: Phase 1 only (Phase 2 is **not** required — `--scan` uses `carreralib.scan()` directly and does not instantiate `LiveCarreraAdapter`).

### Tests for US1

- [X] T010 [P] [US1] In [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) add `test_scan_flag_short_circuits` — invoking `src.main` with `--scan` MUST exit 0, print only `<MAC>\t<name>` lines, and MUST NOT create a SQLite race row, telemetry log file, or dashboard process. Anchors **FR-002**, **FR-008**, **SC-005**, contract [contracts/live-adapter.md](./contracts/live-adapter.md) §2. (Shipped in PR #9.)
- [X] T011 [P] [US1] In [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) add `test_scan_flag_no_devices_exits_zero` covering the empty-result path (no Bluetooth / no CU in range → zero stdout lines, exit 0). Anchors **FR-002**, **SC-005**. (Shipped in PR #9.)
- [X] T012 [P] [US1] In [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) add coverage for the mock-vs-live adapter selection on the non-`--scan` path so the new CLI branch does not regress the existing selection logic. Anchors **FR-002** edge cases. (Shipped in PR #9.)

### Implementation for US1

- [X] T013 [US1] Add the `--scan` argument to the argparse setup in [src/main.py](../../src/main.py). Anchors **FR-002**, **D-002**. (Shipped in PR #9.)
- [X] T014 [US1] Implement the `--scan` short-circuit in [src/main.py](../../src/main.py): when `args.scan` is truthy, call the carreralib scanner, print one `<MAC>\t<name>` line per discovered CU to stdout, exit 0, and skip all telemetry/DB/dashboard wiring. Anchors **FR-002**, **FR-008**, **SC-005**, contract [contracts/live-adapter.md](./contracts/live-adapter.md) §2. (Shipped in PR #9.)

**Checkpoint** (US1 independently shippable): Operator can discover CUs with `python -m src.main --scan`; zero side effects beyond stdout. PR #9 merged → MVP complete.

---

## Phase 4: User Story 2 — Live race survives a transient BLE drop (Priority: P1)

**Story Goal**: A mid-race BLE drop is auto-recovered by `CarreraClientRunner` without resetting the CU's race clock; exponential backoff keeps the BLE stack from being spammed during prolonged outages; shutdown requests interrupt the reconnect sleep cleanly.

**Independent Test**: `pytest -q tests/test_live_ble_stability.py` — 7 tests covering reader-task exception surfacing, `cu.reset` skip on reconnect, exponential backoff doubling, cap at `max_reconnect_interval_seconds`, clamp `max ≥ initial`, and clean shutdown during backoff sleep (SC-002, SC-003).

**Dependencies**: Phase 2 (Foundational) must be complete — `LiveCarreraAdapter.connect()`, `events()`, `close()` must exist before reconnect hardening is meaningful.

### Tests for US2

- [X] T020 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that a reader-task exception is surfaced through `events()` (no silent hang on an empty queue) so the runner observes the drop. Anchors **FR-005**, **D-003**, **SC-002**. (Shipped in PR #14.)
- [X] T021 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that `LiveCarreraAdapter` accepts `reset_on_connect=False` and that `connect()` skips `cu.reset()` under that flag. Anchors **FR-006**, **D-004**. (Shipped in PR #14.)
- [X] T022 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that `CarreraClientRunner` sets `adapter._reset_on_connect = False` on reconnect attempts (`attempt > 0`) via the `hasattr` guard, so `cu.reset()` is called at most once across an arbitrary number of reconnects. Anchors **FR-006**, **D-004**, **SC-003**. (Shipped in PR #14.)
- [X] T023 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that consecutive reconnect failures double the backoff sleep starting from `reconnect_interval_seconds`. Anchors **FR-007**, **D-005**, **SC-002**. (Shipped in PR #14.)
- [X] T024 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that backoff is capped at `max_reconnect_interval_seconds` (default 30s) and that a successful connect resets backoff to the initial value. Anchors **FR-007**, **D-005**. (Shipped in PR #14.)
- [X] T025 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that `CarreraClientRunner.__init__` clamps `max_reconnect_interval_seconds` to be ≥ `reconnect_interval_seconds`. Anchors **D-006**. (Shipped in PR #14.)
- [X] T026 [P] [US2] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that a shutdown request during a reconnect sleep is honored and the runner exits cleanly without raising. Anchors **FR-009**. (Shipped in PR #14.)

### Implementation for US2

- [X] T027 [US2] Add the keyword-only `reset_on_connect: bool = True` kwarg to `LiveCarreraAdapter.__init__` in [src/carrera_client.py](../../src/carrera_client.py) and store it as `self._reset_on_connect`. Zero-arg construction MUST remain valid for test fakes. Anchors **FR-006**, **D-004**, contract [contracts/live-adapter.md](./contracts/live-adapter.md) §1. (Shipped in PR #14.)
- [X] T028 [US2] In `LiveCarreraAdapter.connect()` in [src/carrera_client.py](../../src/carrera_client.py), gate `cu.reset()` on `self._reset_on_connect`; log `"live: initial connect — resetting CU clock"` vs. `"live: reconnect — preserving CU clock (skipping cu.reset)"`. Anchors **FR-006**, **D-004**. (Shipped in PR #14.)
- [X] T029 [US2] Refactor `LiveCarreraAdapter._read_loop` in [src/carrera_client.py](../../src/carrera_client.py) to set `self._connected = False` in a `finally` block so the connected flag is always consistent with reader-task lifetime. Anchors **FR-005**, **D-003**. (Shipped in PR #14.)
- [X] T030 [US2] Rewrite `LiveCarreraAdapter.events()` in [src/carrera_client.py](../../src/carrera_client.py) to drain buffered events first and then re-raise any stored reader-task exception (no more silent hang on an empty queue when the reader has died). Anchors **FR-005**, **D-003**, **SC-002**. (Shipped in PR #14.)
- [X] T031 [US2] Add the keyword-only `max_reconnect_interval_seconds: int = 30` kwarg to `CarreraClientRunner.__init__` in [src/carrera_client.py](../../src/carrera_client.py); store as `self._reconnect_max_s` and clamp to `max(max_reconnect_interval_seconds, reconnect_interval_seconds)`. Anchors **FR-007**, **D-005**, **D-006**. (Shipped in PR #14.)
- [X] T032 [US2] Implement exponential backoff with cap in the `CarreraClientRunner` reconnect loop in [src/carrera_client.py](../../src/carrera_client.py): `backoff_s = min(backoff_s * 2, self._reconnect_max_s)` on each failure; reset to `self._reconnect_initial_s` on every successful connect; sleep via `await asyncio.sleep(backoff_s)` so shutdown can interrupt it. Anchors **FR-007**, **FR-009**, **D-005**. (Shipped in PR #14.)
- [X] T033 [US2] In the `CarreraClientRunner` reconnect loop in [src/carrera_client.py](../../src/carrera_client.py), on `attempt > 0` and only if `hasattr(adapter, "_reset_on_connect")`, set `adapter._reset_on_connect = False` before calling `adapter.connect()` so the CU clock is preserved across drops while keeping the zero-arg adapter factory contract intact. Anchors **FR-006**, **D-004**, **SC-003**. (Shipped in PR #14.)

**Checkpoint** (US2 independently shippable): Live races survive transient BLE drops without losing the CU race clock; backoff bounded; shutdown clean. PR #14 merged.

---

## Phase 5: User Story 3 — Silent AppConnect stalls auto-recover (Priority: P2)

**Story Goal**: When the CU's BLE bridge ("AppConnect") stops forwarding frames without dropping the socket, an idle-frame watchdog forces a reconnect through the same path used for hard drops, and the CU clock is preserved across the recovery.

**Independent Test**: Drive `LiveCarreraAdapter` with a fake source that delivers no `Status`/`Timer` frames for longer than the configured idle window → watchdog forces a reconnect; `cu.reset()` is **not** invoked (attempt > 0); the watchdog does not stack reconnect attempts while one is already in flight (SC-004).

**Dependencies**: Phase 2 (Foundational) must be complete. US3 also assumes US2's reconnect-attempt counter is in place for the "CU clock preserved" assertion in T041; in the shipped sequence US3 (PR #12) landed before US2 (PR #14) and that final assertion was tightened in PR #14.

### Tests for US3

- [X] T040 [P] [US3] In [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) add coverage that no frames for longer than the idle window triggers a forced reconnect. Anchors **FR-004**, **SC-004**. (Shipped in PR #12.)
- [X] T041 [P] [US3] In [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) add coverage that, after a watchdog-triggered reconnect, the CU clock is preserved (reconnect attempt > 0 does not invoke `cu.reset`). Anchors **FR-004**, **FR-006**, **SC-003**, **SC-004**. (Shipped in PR #12; assertion tightened by PR #14.)
- [X] T042 [P] [US3] In [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) add coverage that the watchdog does not stack additional reconnect attempts while a reconnect is already in progress. Anchors **FR-004** edge case. (Shipped in PR #12.)

### Implementation for US3

- [X] T043 [US3] Add an idle-frame timer to `LiveCarreraAdapter` in [src/carrera_client.py](../../src/carrera_client.py): record the timestamp of every `Status`/`Timer` event and tick a watchdog that fires when the elapsed idle time exceeds `live.idle_timeout_seconds` (default `15`, clamped to `>= 3`). Anchors **FR-004**, **D-008**. (Shipped in PR #12.)
- [X] T044 [US3] Wire the watchdog firing into the existing reconnect path in [src/carrera_client.py](../../src/carrera_client.py) so a silent stall is handled by the same machinery as a hard drop. Anchors **FR-004**, **D-008**. (Shipped in PR #12.)

**Checkpoint** (US3 independently shippable): AppConnect silent stalls auto-recover; CU clock preserved across watchdog-triggered reconnects. PR #12 merged.

---

## Phase 6: User Story 4 — Pre-race timeouts no longer kill the process (Priority: P2)

**Story Goal**: `carreralib.TimeoutError` (raised by carreralib roughly once per second when the CU is idle) is treated as non-fatal in both the connect and poll paths; the runner logs a structured diagnostic and routes the condition through the existing reconnect path instead of crashing.

**Independent Test**: Inject `carreralib.TimeoutError` at the connect path and at the poll path → runner catches each, emits a structured diagnostic, and re-enters reconnect rather than propagating the exception (SC-006).

**Dependencies**: Phase 2 (Foundational) must be complete.

### Tests for US4

- [X] T050 [P] [US4] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) (or adjacent live-adapter tests) add a test that raises `carreralib.TimeoutError` from the connect path and asserts the runner catches it, emits a structured diagnostic, and re-enters reconnect rather than propagating. Anchors **FR-003**, **SC-006**. (Shipped in PR #10.)
- [X] T051 [P] [US4] Add a sibling test that raises `carreralib.TimeoutError` from the poll/read path and asserts it is treated as "no event this tick" (non-fatal) rather than as a runner-killing exception. Anchors **FR-003**, **SC-006**. (Shipped in PR #10.)

### Implementation for US4

- [X] T052 [US4] In [src/carrera_client.py](../../src/carrera_client.py), wrap the connect path so `carreralib.TimeoutError` is caught, a structured diagnostic is emitted, and the condition is routed through the reconnect path. Anchors **FR-003**, **D-007**. (Shipped in PR #10.)
- [X] T053 [US4] In [src/carrera_client.py](../../src/carrera_client.py), wrap the poll/read path so `carreralib.TimeoutError` is caught and converted into a non-fatal "no event this tick" outcome (still emit a structured diagnostic so sustained timeout bursts remain observable). Anchors **FR-003**, **D-007**, **SC-006**. (Shipped in PR #10.)

**Checkpoint** (US4 independently shippable): No pre-race or mid-race `TimeoutError` can crash the runner. PR #10 merged.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation gate that runs after all user-story phases.

- [X] T060 [P] Run `.venv/bin/ruff check .` on `main` post-PR-#14 — clean.
- [X] T061 [P] Run `.venv/bin/mypy src/` (strict) on `main` post-PR-#14 — clean.
- [X] T062 [P] Run `.venv/bin/pytest -q` on `main` post-PR-#14 — green.
- [X] T063 **SC-001 anchor**: Confirm the full CI matrix (Python 3.11 + 3.12 × ubuntu-latest + macos-latest) is green on every push to `main` for PRs #9, #10, #12, #14. Per the PR #15 policy, the success signal is "all matrix jobs green," not a specific test count. Anchors **SC-001**.

---

## Dependencies & Execution Order

### Phase-Level Dependencies

```text
Phase 1 (Setup)
   │
   ├──► Phase 3 (US1: --scan)            ← independent of Phase 2
   │
   └──► Phase 2 (Foundational adapter)
            │
            ├──► Phase 4 (US2: drop survival)        ← P1
            ├──► Phase 5 (US3: idle watchdog)        ← P2; needs US2's attempt-counter for T041
            └──► Phase 6 (US4: TimeoutError)         ← P2

   All user-story phases ──► Phase 7 (Polish / CI matrix)
```

### User-Story Dependencies

- **US1** is **fully independent**: it does not touch `LiveCarreraAdapter` at all (uses `carreralib.scan()` directly). It is the MVP and can ship alone after Setup.
- **US2**, **US3**, **US4** all depend on the Foundational `LiveCarreraAdapter` base from Phase 2.
- **US3** has a soft dependency on **US2**'s `attempt > 0` counter for the "CU clock preserved" assertion in T041 (the assertion was tightened by PR #14 after PR #12 shipped).
- **US2** and **US4** are independent of each other and could ship in either order.

### As-Shipped PR Order

1. **PR #9** (Phase 2 Foundational + Phase 3 US1) — MVP slice.
2. **PR #10** (Phase 6 US4) — `TimeoutError` non-fatal.
3. **PR #12** (Phase 5 US3) — idle watchdog.
4. **PR #14** (Phase 4 US2) — reconnect-stability hardening.

### Parallel Opportunities

- All `[P]` tasks within a phase can run in parallel.
- Phase 3 (US1) can run in parallel with Phase 2 (Foundational) once Phase 1 is done.
- Phase 4 (US2), Phase 5 (US3), Phase 6 (US4) can run in parallel once Phase 2 is done (modulo the US3↔US2 soft dependency on the attempt counter).
- T060, T061, T062 in Phase 7 run in parallel (lint, type-check, test are independent invocations).

---

## Parallel Example: US2 stability tests

```bash
# T020–T026 are all independent and run in parallel:
.venv/bin/pytest -q tests/test_live_ble_stability.py -n auto
```

---

## Implementation Strategy

### MVP First

**Phase 3 (US1) alone is the MVP.** Operators get a working `--scan` discovery tool with zero side effects; the live race pipeline keeps using whatever adapter shipped before this slice. US1 carries no dependency on US2/US3/US4 and could have shipped on its own.

### Incremental Delivery (as actually shipped)

The feature was delivered as **four sequential squash-merges** on `main`, each story landing as one PR:

1. **PR #9** — Foundational adapter base + US1 (`--scan`).
2. **PR #10** — US4 (`TimeoutError` non-fatal).
3. **PR #12** — US3 (idle watchdog).
4. **PR #14** — US2 (reconnect-stability hardening).

Each PR was independently green on the CI matrix before the next one started; no PR depended on a still-open PR.

---

## Independent Test Criteria Recap

| Story | Independent Test (one-line summary) | Anchoring tests |
|---|---|---|
| US1 | `python -m src.main --scan` with no CU in range → exit 0, zero stdout lines, no DB/log/dashboard side effects | [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) |
| US2 | Reader-task exception → `events()` re-raises, runner reconnects with capped exponential backoff, `cu.reset()` invoked at most once per runner lifecycle | [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) |
| US3 | No frames for > `live.idle_timeout_seconds` → forced reconnect; CU clock preserved; no stacked reconnects | [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) |
| US4 | `carreralib.TimeoutError` at connect or poll → structured diagnostic + reconnect, no propagation | [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) (and adjacent live-adapter tests) |

---

## Coverage Matrix (FR / SC → Task IDs)

| Requirement | Tasks |
|---|---|
| **FR-001** (LiveCarreraAdapter + translation) | T001, T002, T003, T004, T005, T006, T007, T008, T009 |
| **FR-002** (`--scan` CLI) | T010, T011, T012, T013, T014 |
| **FR-003** (`TimeoutError` non-fatal) | T050, T051, T052, T053 |
| **FR-004** (idle watchdog) | T040, T041, T042, T043, T044 |
| **FR-005** (`events()` surfaces reader exceptions) | T020, T029, T030 |
| **FR-006** (`cu.reset` skip on attempt > 0) | T021, T022, T027, T028, T033, T041 |
| **FR-007** (exponential backoff with cap) | T023, T024, T025, T031, T032 |
| **FR-008** (`--scan` side-effect-free) | T010, T011, T014 |
| **FR-009** (shutdown interrupts backoff) | T026, T032 |
| **SC-001** (CI matrix green) | T063 |
| **SC-002** (reconnect within initial + max backoff) | T020, T023 |
| **SC-003** (`cu.reset` at most once per lifecycle) | T022, T033, T041 |
| **SC-004** (idle stall → forced reconnect) | T040, T041 |
| **SC-005** (`--scan` zero side effects) | T010, T011, T014 |
| **SC-006** (`TimeoutError` never propagates) | T050, T051, T053 |
