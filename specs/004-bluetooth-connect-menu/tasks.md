# Tasks: Bluetooth Connect Button (Dashboard Kebab Menu)

**Feature**: `004-bluetooth-connect-menu` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tasks are ordered by dependency. Each task references the FRs/SCs it satisfies.

## Phase 1 — Tests first (US1)

- [ ] **T001** Extend `tests/test_race_controls.py` with `test_runtime_settings_bluetooth_mac_round_trip` and `test_runtime_settings_bluetooth_mac_missing_key_defaults_to_none` (FR-001, SC-004).
- [ ] **T002** Create `tests/test_bluetooth_scanner.py` covering: (a) `scan_for_devices()` raises `ScannerUnavailableError` when `carreralib.connection` is unimportable, (b) wraps a generic `Exception` from `cl_conn.scan()` into `ScannerError`, (c) returns the list of `(mac, name)` pairs on success. Use `monkeypatch` to inject a fake `carreralib.connection` module via `sys.modules` (FR-002, SC-004).
- [ ] **T003** Create `tests/test_main_overrides.py` covering `_apply_overrides`: with no `args.mac` and `cfg.bluetooth.mac_address=None`, the result picks up `runtime_settings.bluetooth_mac` via a monkeypatched `get_bluetooth_mac` (FR-006, SC-002, SC-004).

## Phase 2 — Implementation (US1)

- [ ] **T010** Extend `src/services/runtime_settings.py`: add `"bluetooth_mac": None` to `_DEFAULTS`, allow `None`-valued keys through `_load` merge, add `get_bluetooth_mac` / `set_bluetooth_mac` (normalize `""` → `None`), expose module-level helpers, update `__all__` (FR-001).
- [ ] **T011** Create `src/services/bluetooth_scanner.py` exporting `ScannerError`, `ScannerUnavailableError`, `scan_for_devices` (FR-002, FR-005).
- [ ] **T012** Extend `src/main.py::_apply_overrides`: when `args.mac is None` and `cfg.bluetooth.mac_address is None`, fall back to `runtime_settings.get_bluetooth_mac()` (FR-006).
- [ ] **T013** Extend `src/dashboard.py`: add `_render_kebab_menu()` rendering a `st.popover("⋮")` with the **🔌 Bluetooth verbinden** button, scan results, **Auswählen** per row, **Zurücksetzen** when a MAC is persisted, error handling for both error types. Wire it into the header row of `_render_body` so it sits next to the title (FR-003, FR-004, FR-005).

## Phase 3 — Validate, polish, ship

- [ ] **T020** Run `ruff check src tests` + `mypy src` + `pytest -q`. All green.
- [ ] **T021** Commit & push the branch, open the PR, poll Actions via `gh api` until green; merge with `--squash --delete-branch`.

## Coverage matrix

| Requirement | Task(s)                |
|-------------|------------------------|
| FR-001      | T001, T010             |
| FR-002      | T002, T011             |
| FR-003      | T013                   |
| FR-004      | T013                   |
| FR-005      | T011, T013             |
| FR-006      | T003, T012             |
| FR-007      | (no-op — no new dep)   |
| FR-008      | (no-op — existing gitignore) |
| SC-001      | Manual quickstart smoke |
| SC-002      | T003, T012             |
| SC-003      | T002, T013             |
| SC-004      | T001, T002, T003, T020 |
