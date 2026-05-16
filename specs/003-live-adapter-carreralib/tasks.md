---
description: "Task list for the live-adapter-carreralib feature (LiveCarreraAdapter + --scan CLI + BLE reconnect hardening)"
---

# Tasks: Live Adapter (carreralib) + `--scan` CLI + BLE Reconnect Hardening

**Feature Branch**: `003-live-adapter-carreralib` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Input**: Design documents in `specs/003-live-adapter-carreralib/`
**Prerequisites**: plan.md, spec.md, research.md (D-001…D-008), data-model.md, contracts/live-adapter.md, quickstart.md

**Tests**: INCLUDED. Every functional requirement (FR-001…FR-009) and every success criterion (SC-001…SC-006) has at least one anchoring test under [tests/](../../tests/).

**Organization**: Tasks are grouped by the **four PRs that delivered the feature on `main`** (PR #9 → PR #10 → PR #12 → PR #14). Within each PR group, tasks are dependency-ordered.

**Status**: All tasks below were implemented on `main` via PRs #9, #10, #12, #14 and are marked `[X]`. This file exists so that any follow-up `/speckit.tasks` work has a normal `plan.md → tasks.md` anchor and so that each FR/SC has a traceable task ID.

## Format: `[ID] [P?] [PR?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[PR]**: PR tag (`[PR9]`, `[PR10]`, `[PR12]`, `[PR14]`) mapping the task to the PR that shipped it
- Every task includes an exact file path and references the FR/SC IDs it satisfies

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pull in the third-party library that the rest of the feature builds on.

- [X] T001 [PR9] Add `carreralib` to [requirements.txt](../../requirements.txt) so the live adapter has its BLE/serial dependency available on every CI matrix leg (Python 3.11 + 3.12 × ubuntu-latest + macos-latest). Anchors **FR-001**.

**Checkpoint**: `carreralib` importable in the project venv; CI matrix can resolve the dependency.

---

## Phase 2: Foundational (Adapter Contract Surface)

**Purpose**: None — the feature reuses the existing `TelemetryAdapter` protocol exercised by [tests/test_adapter_contract.py](../../tests/test_adapter_contract.py) and the existing `CarreraClientRunner` supervisor. No new abstractions are introduced before the first PR slice.

(Phase intentionally empty.)

**Checkpoint**: existing adapter contract from `main` pre-PR-#9 is sufficient; proceed to Phase 3.

---

## Phase 3: PR #9 — carreralib integration + `--scan` CLI (User Stories 1 + 2 baseline) 🎯 MVP

**Goal**: Replace the placeholder live adapter with a production `LiveCarreraAdapter` that wraps `carreralib`, translates `Status` / `Timer` frames into `TelemetryEvent`s, and add a side-effect-free `python -m src.main --scan` entry point.

**Independent Test** (PR-level):

1. `python -m src.main --scan` on a host with no CU exits 0 with no stdout device lines and creates no SQLite row / log file / dashboard process (SC-005).
2. `pytest -q tests/test_live_translation.py tests/test_adapter_contract.py tests/test_main_adapter_selection.py` green.

### Tests for PR #9

- [X] T010 [P] [PR9] In [tests/test_live_translation.py](../../tests/test_live_translation.py) add unit tests covering `carreralib.Status` → `TelemetryEvent` translation: fuel level, pit flags, position deltas, driver-id mapping. Anchors **FR-001**.
- [X] T011 [P] [PR9] In [tests/test_live_translation.py](../../tests/test_live_translation.py) add unit tests covering `carreralib.Timer` → `TelemetryEvent` translation: lap timestamps, sector splits, controller index. Anchors **FR-001**.
- [X] T012 [P] [PR9] Extend [tests/test_adapter_contract.py](../../tests/test_adapter_contract.py) to assert `LiveCarreraAdapter` honors the shared `TelemetryAdapter` protocol (`connect` / `events` / `close` shapes, async-iterator semantics). Anchors **FR-001** and the contract in [contracts/live-adapter.md](./contracts/live-adapter.md) §1.
- [X] T013 [P] [PR9] In [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) add `test_scan_flag_short_circuits` — invoking `src.main` with `--scan` MUST exit 0, print only `<MAC>\t<name>` lines, and MUST NOT create a SQLite race row, telemetry log file, or dashboard process. Anchors **FR-002**, **FR-008**, **SC-005**.
- [X] T014 [P] [PR9] In [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) add `test_scan_flag_no_devices_exits_zero` covering the empty-result path (no Bluetooth / no CU in range → zero stdout lines, exit 0). Anchors **FR-002**, **SC-005**.
- [X] T015 [P] [PR9] In [tests/test_main_adapter_selection.py](../../tests/test_main_adapter_selection.py) add coverage for the mock-vs-live adapter selection on the non-`--scan` path so the new CLI branch does not regress the existing selection logic. Anchors **FR-002** edge cases.

### Implementation for PR #9

- [X] T016 [PR9] Implement `LiveCarreraAdapter.__init__` in [src/carrera_client.py](../../src/carrera_client.py): accept connection parameters, initialize the internal event queue, the `_connected` flag, and the reader-task handle. Keep zero-arg construction valid for test fakes. Anchors **FR-001**.
- [X] T017 [PR9] Implement `LiveCarreraAdapter.connect()` in [src/carrera_client.py](../../src/carrera_client.py): open the `carreralib.ControlUnit`, call `cu.reset()`, start the background reader task that pushes `Status` / `Timer` frames onto the queue. Anchors **FR-001**, **D-001**.
- [X] T018 [PR9] Implement `LiveCarreraAdapter.events()` (async iterator) and `LiveCarreraAdapter.close()` in [src/carrera_client.py](../../src/carrera_client.py): drain the queue, translate frames to `TelemetryEvent`, cancel and await the reader task on close. Anchors **FR-001**, **D-001**.
- [X] T019 [PR9] Implement `Status` → `TelemetryEvent` translation in [src/carrera_client.py](../../src/carrera_client.py) (fuel, pit, position fields). Anchors **FR-001**.
- [X] T020 [PR9] Implement `Timer` → `TelemetryEvent` translation in [src/carrera_client.py](../../src/carrera_client.py) (lap timestamps, controller index). Anchors **FR-001**.
- [X] T021 [PR9] Add the `--scan` argument to the argparse setup in [src/main.py](../../src/main.py). Anchors **FR-002**, **D-002**.
- [X] T022 [PR9] Implement the `--scan` short-circuit in [src/main.py](../../src/main.py): when `args.scan` is truthy, call the carreralib scanner, print one `<MAC>\t<name>` line per discovered CU to stdout, exit 0, and skip all telemetry/DB/dashboard wiring. Anchors **FR-002**, **FR-008**, **SC-005**, contract [contracts/live-adapter.md](./contracts/live-adapter.md) §2.

**Checkpoint**: Live adapter shipped end-to-end; `--scan` works with zero side effects; PR #9 merged.

---

## Phase 4: PR #10 — `carreralib.TimeoutError` is non-fatal

**Goal**: Stop pre-race `TimeoutError`s (raised by `carreralib` roughly once per second when the CU is idle) from crashing the runner; route them through the existing reconnect path with a structured diagnostic.

**Independent Test** (PR-level): Inject a `carreralib.TimeoutError` during connect and during poll → runner logs a structured diagnostic and re-enters the reconnect loop instead of propagating the exception.

### Tests for PR #10

- [X] T030 [P] [PR10] In the live-adapter test suite (e.g. [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) / adjacent live-adapter tests), add a test that raises `carreralib.TimeoutError` from the connect path and asserts the runner catches it, emits a structured diagnostic, and re-enters reconnect rather than propagating. Anchors **FR-003**, **SC-006**.
- [X] T031 [P] [PR10] Add a sibling test that raises `carreralib.TimeoutError` from the poll/read path and asserts it is treated as "no event this tick" (non-fatal) rather than as a runner-killing exception. Anchors **FR-003**, **SC-006**.

### Implementation for PR #10

- [X] T032 [PR10] In [src/carrera_client.py](../../src/carrera_client.py), wrap the connect path so `carreralib.TimeoutError` is caught, a structured diagnostic is emitted, and the condition is routed through the reconnect path. Anchors **FR-003**, **D-007**.
- [X] T033 [PR10] In [src/carrera_client.py](../../src/carrera_client.py), wrap the poll/read path so `carreralib.TimeoutError` is caught and converted into a non-fatal "no event this tick" outcome (still emit a structured diagnostic so sustained timeout bursts remain observable). Anchors **FR-003**, **D-007**, **SC-006**.

**Checkpoint**: No pre-race or mid-race `TimeoutError` can crash the runner; PR #10 merged.

---

## Phase 5: PR #12 — BLE idle watchdog (User Story 3)

**Goal**: Detect silent AppConnect stalls (BLE socket healthy, no frames forwarded) and force a reconnect through the same path used for hard drops.

**Independent Test** (PR-level): Drive `LiveCarreraAdapter` with a fake source that delivers no `Status`/`Timer` frames for longer than the configured idle window → watchdog forces reconnect; CU clock preserved (no `cu.reset` on attempt > 0).

### Tests for PR #12

- [X] T040 [P] [PR12] In [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) add coverage that no frames for longer than the idle window triggers a forced reconnect. Anchors **FR-004**, **SC-004**.
- [X] T041 [P] [PR12] In [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) add coverage that, after a watchdog-triggered reconnect, the CU clock is preserved (reconnect attempt > 0 does not invoke `cu.reset`). Anchors **FR-004**, **FR-006**, **SC-003**, **SC-004**.
- [X] T042 [P] [PR12] In [tests/test_live_idle_watchdog.py](../../tests/test_live_idle_watchdog.py) add coverage that the watchdog does not stack additional reconnect attempts while a reconnect is already in progress. Anchors **FR-004** edge case.

### Implementation for PR #12

- [X] T043 [PR12] Add an idle-frame timer to `LiveCarreraAdapter` in [src/carrera_client.py](../../src/carrera_client.py): record the timestamp of every `Status`/`Timer` event and tick a watchdog that fires when the elapsed idle time exceeds the configured idle window. Anchors **FR-004**, **D-008**.
- [X] T044 [PR12] Wire the watchdog firing into the existing reconnect path in [src/carrera_client.py](../../src/carrera_client.py) so a silent stall is handled by the same machinery as a hard drop. Anchors **FR-004**, **D-008**.

**Checkpoint**: AppConnect silent stalls auto-recover without operator intervention; PR #12 merged.

---

## Phase 6: PR #14 — Reconnect-stability hardening (User Story 2)

**Goal**: Make live races survive transient BLE drops without losing the CU's race clock. Specifically: (1) `events()` MUST surface reader-task exceptions instead of hanging on an empty queue; (2) reconnect attempts (`attempt > 0`) MUST skip `cu.reset()`; (3) the runner MUST use exponential backoff capped at `max_reconnect_interval_seconds`.

**Independent Test** (PR-level): `pytest -q tests/test_live_ble_stability.py` — 7 new tests covering reader-task surfacing, `cu.reset` skip, exponential backoff cap, clamp, and clean shutdown during backoff.

### Tests for PR #14

- [X] T050 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that a reader-task exception is surfaced through `events()` (no silent hang on an empty queue) so the runner observes the drop. Anchors **FR-005**, **D-003**, **SC-002**.
- [X] T051 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that `LiveCarreraAdapter` accepts `reset_on_connect=False` and that `connect()` skips `cu.reset()` under that flag. Anchors **FR-006**, **D-004**.
- [X] T052 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that `CarreraClientRunner` sets `adapter._reset_on_connect = False` on reconnect attempts (`attempt > 0`) via the `hasattr` guard, so `cu.reset()` is called at most once across an arbitrary number of reconnects. Anchors **FR-006**, **D-004**, **SC-003**.
- [X] T053 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that consecutive reconnect failures double the backoff sleep starting from `reconnect_interval_seconds`. Anchors **FR-007**, **D-005**, **SC-002**.
- [X] T054 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that backoff is capped at `max_reconnect_interval_seconds` (default 30s) and that a successful connect resets backoff to the initial value. Anchors **FR-007**, **D-005**.
- [X] T055 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that `CarreraClientRunner.__init__` clamps `max_reconnect_interval_seconds` to be ≥ `reconnect_interval_seconds`. Anchors **D-006**.
- [X] T056 [P] [PR14] In [tests/test_live_ble_stability.py](../../tests/test_live_ble_stability.py) add a test that a shutdown request during a reconnect sleep is honored and the runner exits cleanly without raising. Anchors **FR-009**.

### Implementation for PR #14

- [X] T057 [PR14] Add the keyword-only `reset_on_connect: bool = True` kwarg to `LiveCarreraAdapter.__init__` in [src/carrera_client.py](../../src/carrera_client.py) and store it as `self._reset_on_connect`. Zero-arg construction MUST remain valid for test fakes. Anchors **FR-006**, **D-004**, contract [contracts/live-adapter.md](./contracts/live-adapter.md) §1.
- [X] T058 [PR14] In `LiveCarreraAdapter.connect()` in [src/carrera_client.py](../../src/carrera_client.py), gate `cu.reset()` on `self._reset_on_connect`; log `"live: initial connect — resetting CU clock"` vs. `"live: reconnect — preserving CU clock (skipping cu.reset)"`. Anchors **FR-006**, **D-004**.
- [X] T059 [PR14] Refactor `LiveCarreraAdapter._read_loop` in [src/carrera_client.py](../../src/carrera_client.py) to set `self._connected = False` in a `finally` block so the connected flag is always consistent with reader-task lifetime. Anchors **FR-005**, **D-003**.
- [X] T060 [PR14] Rewrite `LiveCarreraAdapter.events()` in [src/carrera_client.py](../../src/carrera_client.py) to drain buffered events first and then re-raise any stored reader-task exception (no more silent hang on an empty queue when the reader has died). Anchors **FR-005**, **D-003**, **SC-002**.
- [X] T061 [PR14] Add the keyword-only `max_reconnect_interval_seconds: int = 30` kwarg to `CarreraClientRunner.__init__` in [src/carrera_client.py](../../src/carrera_client.py); store as `self._reconnect_max_s` and clamp to `max(max_reconnect_interval_seconds, reconnect_interval_seconds)`. Anchors **FR-007**, **D-005**, **D-006**.
- [X] T062 [PR14] Implement exponential backoff with cap in the `CarreraClientRunner` reconnect loop in [src/carrera_client.py](../../src/carrera_client.py): `backoff_s = min(backoff_s * 2, self._reconnect_max_s)` on each failure; reset to `self._reconnect_initial_s` on every successful connect; sleep via `await asyncio.sleep(backoff_s)` so shutdown can interrupt it. Anchors **FR-007**, **FR-009**, **D-005**.
- [X] T063 [PR14] In the `CarreraClientRunner` reconnect loop in [src/carrera_client.py](../../src/carrera_client.py), on `attempt > 0` and only if `hasattr(adapter, "_reset_on_connect")`, set `adapter._reset_on_connect = False` before calling `adapter.connect()` so the CU clock is preserved across drops while keeping the zero-arg adapter factory contract intact. Anchors **FR-006**, **D-004**, **SC-003**.

**Checkpoint**: All 7 stability tests green; live races survive transient BLE drops without resetting the CU clock; PR #14 merged.

---

## Phase 7: Validation Gate (Polish & Cross-Cutting)

- [X] T070 [P] Run `.venv/bin/ruff check .` on `main` post-PR-#14 — clean.
- [X] T071 [P] Run `.venv/bin/mypy src/` (strict) on `main` post-PR-#14 — clean.
- [X] T072 [P] Run `.venv/bin/pytest -q` on `main` post-PR-#14 — green.
- [X] T073 **SC-001 anchor**: Confirm the full CI matrix (Python 3.11 + 3.12 × ubuntu-latest + macos-latest) is green on every push to `main` for PRs #9, #10, #12, #14. Per the PR #15 policy, the success signal is "all matrix jobs green," not a specific test count. Anchors **SC-001**.

---

## Dependencies & Execution Order

### PR Dependencies (as shipped on `main`)

- **PR #9** (Phase 3) is the foundation: it introduces `LiveCarreraAdapter`, the translation layer, and the `--scan` CLI. PRs #10, #12, #14 all depend on the adapter existing.
- **PR #10** (Phase 4) is independent of PR #12 and PR #14 in scope (just adds `TimeoutError` handling around the connect/poll paths from PR #9) and can land immediately after PR #9.
- **PR #12** (Phase 5) depends on PR #9's adapter and on PR #14's reconnect path *only* for the "CU clock preserved" assertion in T041; in practice it landed before PR #14 and the assertion was tightened in PR #14. Treat the watchdog → reconnect wiring as PR #12's contribution.
- **PR #14** (Phase 6) depends on PR #9's adapter. It is the largest slice (`events()` rewrite + `cu.reset` skip + exponential backoff) and lands last so that the reconnect path is fully hardened by the time the suite settles.

### Within Each PR

- Tests are listed before implementation tasks per the project convention; in practice PRs #9 / #10 / #12 / #14 each contain their tests and implementation in a single squash-merge.
- Within PR #14, T057–T063 can be sequenced or interleaved; the test tasks T050–T056 are fully parallel against the implementation set once the adapter exists.

### Parallel Opportunities

- All `[P]` tests within a PR phase can run in parallel.
- T070, T071, T072 in Phase 7 run in parallel (lint, type-check, test are independent invocations).

---

## Parallel Example: PR #14 stability tests

```bash
# All seven stability tests are independent and run in parallel:
.venv/bin/pytest -q tests/test_live_ble_stability.py -n auto
```

---

## Implementation Strategy

### MVP First

PR #9 alone (Phase 3) is the MVP: it ships a working live adapter and the `--scan` CLI, which are the two user-visible primitives the operator needs to run a real race. PRs #10, #12, #14 each harden one reliability axis on top of that MVP and could have shipped in any order.

### Incremental Delivery (as actually shipped)

The feature was shipped as **four sequential squash-merges** on `main`:

1. **PR #9** — carreralib integration + `--scan` CLI (Phase 3).
2. **PR #10** — `TimeoutError` is non-fatal (Phase 4).
3. **PR #12** — BLE idle watchdog (Phase 5).
4. **PR #14** — Reconnect-stability hardening (Phase 6).

Each PR was independently CI-green on the Python 3.11 + 3.12 × ubuntu/macos matrix before merge (SC-001).

### Suggested Slicing for Future Similar Features

The four-PR shape used here generalizes well for any "third-party SDK integration + resilience hardening" feature:

1. PR #N: SDK adoption + happy-path translation + discovery CLI.
2. PR #N+1: Transient-error taxonomy (catch + classify + route through reconnect).
3. PR #N+2: Liveness probe / watchdog for silent stalls.
4. PR #N+3: Reconnect-policy hardening (backoff, state preservation, observable failure mode).
