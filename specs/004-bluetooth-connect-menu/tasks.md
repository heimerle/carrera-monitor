# Tasks: Bluetooth Connect Button (Dashboard Kebab Menu)

**Feature**: `004-bluetooth-connect-menu` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Input**: Design documents from `specs/004-bluetooth-connect-menu/`
**Prerequisites**: plan.md ✅, spec.md ✅ (single User Story US1; data-model and contracts are inlined in plan.md — no separate `contracts/` or `data-model.md` files)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on uncompleted tasks)
- **[Story]**: User-story label (e.g. `[US1]`) — required for user-story phase tasks only
- File paths are repository-relative

## Path Conventions

Single Python project: `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new shared infrastructure required. The feature reuses the existing `RuntimeSettings` file-backed store and the existing `streamlit run src/app.py` entry point.

- [ ] T001 Verify the working tree is clean and on a fresh `004-bluetooth-connect-menu` feature branch from `main`; activate `.venv` and confirm `ruff`, `mypy`, and `pytest` resolve via `python -m`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Documentation-only nudge so the new persisted key is auditable before tests reference it. MUST land before any user-story task.

- [ ] T002 [P] Extend the module-level doc-string in src/services/runtime_settings.py to mention the new `bluetooth_mac` key alongside `mock_mode`. Docs-only; no behavior change yet.

---

## Phase 3: User Story 1 — Connect to the Carrera AppConnect from the Dashboard (Priority: P1) 🎯 MVP

**Goal**: One-click bind of a specific Carrera Control Unit from the dashboard kebab menu, persisted across pipeline restarts.

**Independent Test**: With `carreralib` installed and an AppConnect powered on, open `streamlit run src/app.py`, click **⋮ → 🔌 Bluetooth verbinden**, pick a device, see the "Restart erforderlich" notice, then run `python -m src.main` (no `--mac`) and confirm the live adapter connects directly to the persisted MAC.

### Tests for User Story 1 (write first, expect to fail)

- [ ] T010 [P] [US1] Extend tests/test_race_controls.py with `test_runtime_settings_bluetooth_mac_round_trip` and `test_runtime_settings_bluetooth_mac_missing_key_defaults_to_none` covering: default `None`, set/get round-trip, on-disk JSON contains `"bluetooth_mac"`, fresh `RuntimeSettings(path=...)` reads the value, empty-string setter normalizes to `None`, files written before this feature (no key) still load with default `None` (FR-001, SC-004).
- [ ] T011 [P] [US1] Create tests/test_bluetooth_scanner.py covering: (a) `scan_for_devices()` raises `ScannerUnavailableError` when `carreralib.connection` cannot be imported (monkeypatch `builtins.__import__` to raise `ImportError` for `carreralib.connection`), (b) wraps a generic `RuntimeError` from `cl_conn.scan()` into `ScannerError(str(exc))`, (c) returns the list of `(mac, name)` tuples on success when the fake `cl_conn.scan()` yields them (FR-002, FR-005, SC-004).
- [ ] T012 [P] [US1] Create tests/test_main_overrides.py covering `_apply_overrides`: with `args.mac=None`, `cfg.bluetooth.mac_address=None`, and monkeypatched `get_bluetooth_mac` returning `"AA:BB:CC:DD:EE:FF"`, the resulting `AppConfig.bluetooth.mac_address` equals that MAC; with `args.mac="11:22:33:44:55:66"`, the CLI MAC still wins; with `cfg.bluetooth.mac_address="33:44:55:66:77:88"` already set, the config value wins over the persisted one (FR-006, SC-002, SC-004).

### Implementation for User Story 1

- [ ] T013 [US1] Extend src/services/runtime_settings.py: add `"bluetooth_mac": None` to `_DEFAULTS`; add `get_bluetooth_mac()` and `set_bluetooth_mac(value: str | None)` instance methods with `""` → `None` normalization; expose module-level `get_bluetooth_mac` / `set_bluetooth_mac` helpers backed by `_default`; update `__all__` (FR-001).
- [ ] T014 [P] [US1] Create src/services/bluetooth_scanner.py exporting `ScannerError(RuntimeError)`, `ScannerUnavailableError(ScannerError)`, and `scan_for_devices() -> list[tuple[str, str]]` that imports `carreralib.connection` lazily, calls `cl_conn.scan()`, returns `[(mac, name or "?")]`, and maps `ImportError → ScannerUnavailableError`, generic `Exception → ScannerError(str(exc))` (FR-002, FR-005).
- [ ] T015 [US1] Extend src/main.py `_apply_overrides`: after the existing `if args.mac is not None:` branch, add an `elif data["bluetooth"]["mac_address"] is None:` branch that imports `get_bluetooth_mac` from `src.services.runtime_settings` and assigns the result. Preserve CLI / config precedence (FR-006).
- [ ] T016 [US1] Extend src/dashboard.py: add a private `_render_kebab_menu()` rendering a `st.popover("⋮", use_container_width=False)` containing: (a) currently-persisted MAC line, (b) **🔌 Bluetooth verbinden** button → on click set `st.session_state["ble_scan_result"]` to either `scan_for_devices()`'s return value or the captured exception, (c) for each `(mac, name)` row an **Auswählen** button → `set_bluetooth_mac(mac)` (wrapped in `try/except OSError` → `st.error(str(exc))`) + on success `st.success("Gespeichert. Restart erforderlich.")` + `st.rerun()`, (d) if a `bluetooth_mac` is set, a **Zurücksetzen** button → `set_bluetooth_mac(None)` + same notice, (e) on `ScannerUnavailableError` show `st.error("carreralib nicht installiert. Bitte mit 'pip install carreralib' nachinstallieren.")`, on `ScannerError` show `st.error(str(exc))`, (f) when the scan returned an empty list, show `st.info("Keine Geräte gefunden — ist die AppConnect eingeschaltet?")`. Wire the popover into the header row inside `_render_body` using a `st.columns([0.95, 0.05])` split (FR-003, FR-004, FR-005, SC-001, SC-003).

### Checkpoint US1

At the end of US1: dashboard exposes the BLE-connect popover, persists the MAC, and the next pipeline boot picks it up — all FRs satisfied. No regressions in existing tests.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T020 Run `ruff check src tests`, `mypy src`, and `pytest -q` from the repo root; all three MUST be green. Fix any lint/type/test issue surfaced.
- [ ] T021 Manual smoke per plan.md quickstart: open dashboard, click **⋮ → 🔌 Bluetooth verbinden**, observe the device list (or actionable error when no AppConnect is reachable / `carreralib` is missing) (SC-001, SC-003).
- [ ] T022 Commit on `004-bluetooth-connect-menu`, push, open a PR against `main`, poll CI via `gh api repos/heimerle/carrera-monitor/actions/runs?head_sha=$SHA` until green; fix any failure and push again; squash-merge with `--delete-branch` once green (SC-004).

---

## Dependencies

- **T001 → T002**: setup → docs touch.
- **T002 → T010, T011, T012**: tests reference the new contracts; the doc-string update lands first so intent is in the tree.
- **T010, T011, T012 [P]**: independent test files; parallel-safe.
- **T013 → T010**: implementation makes T010 pass.
- **T014 → T011**: implementation makes T011 pass; brand-new file, parallel-safe with T013/T015.
- **T015 → T012, T013**: makes T012 pass; imports the new helper from T013.
- **T016 → T013, T014**: dashboard imports both modules.
- **T020 → T010..T016**: validation gate.
- **T021 → T020**: smoke only after the suite is green.
- **T022 → T020, T021**: ship only after green + smoke.

## Parallel Execution Opportunities

Within US1, the test-writing trio (T010, T011, T012) can be authored in parallel — three different test files depending only on the foundational doc-string update.

Within US1 implementation, T014 (new bluetooth_scanner.py) can be authored in parallel with T013 (runtime_settings.py) — separate modules. T015 must wait for T013; T016 must wait for both T013 and T014.

## Implementation Strategy

**MVP scope = US1 in full**. Single user story, no P2/P3 to defer. Incremental delivery boundaries:

1. **Cut 1** — T010..T013: `runtime_settings.bluetooth_mac` round-trips on disk (test-only delivery; no UI yet).
2. **Cut 2** — T014..T015: scanner helper + main-side wiring; persisted MAC honoured at boot.
3. **Cut 3** — T016: dashboard kebab popover; end-user-driven flow.
4. **Cut 4** — T020..T022: ship.

If time pressure forces a stop after Cut 2, an operator can already use the feature by hand-editing `data/runtime_settings.json` with `{"bluetooth_mac": "..."}`; the UI is the convenience layer.

## Coverage Matrix (FR / SC → Tasks)

| Requirement | Task(s)                  |
|-------------|--------------------------|
| FR-001      | T002, T010, T013         |
| FR-002      | T011, T014               |
| FR-003      | T016                     |
| FR-004      | T016                     |
| FR-005      | T011, T014, T016         |
| FR-006      | T012, T015               |
| FR-007      | (no-op — no new dep)     |
| FR-008      | (no-op — already gitignored) |
| SC-001      | T016, T021               |
| SC-002      | T012, T015               |
| SC-003      | T011, T014, T016, T021   |
| SC-004      | T010, T011, T012, T020, T022 |

## Validation

- Every task carries the required `- [ ] TID [P?] [Story?] Description` shape.
- US1 covers every FR and SC from [spec.md](./spec.md); no orphan requirements.
- Setup (T001) and Foundational (T002) tasks carry no `[US?]` label, as required.
- Polish tasks (T020..T022) carry no `[US?]` label.
- US1 is independently testable as described above.
- Total tasks: **11** (Setup 1, Foundational 1, US1 7, Polish 3).
- US1 split: 3 test tasks + 4 implementation tasks.
- Parallel opportunities: T010/T011/T012 (tests); T013‖T014 (implementation).
