# Implementation Plan: Bluetooth Connect Button (Dashboard Kebab Menu)

**Branch**: `004-bluetooth-connect-menu` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-bluetooth-connect-menu/spec.md`

## Summary

Add a kebab (**⋮**) popover to the Streamlit dashboard header that lets the user trigger a BLE scan, pick a Carrera AppConnect Control Unit, and persist its MAC to `data/runtime_settings.json::bluetooth_mac`. The next `carrera-monitor` boot consults that persisted MAC as a fallback when neither `--mac` on the CLI nor `bluetooth.mac_address` in `config.yaml` is set. The slice extends the existing 002/FR-225 "settings on disk → adapter selection" pattern from `mock_mode` to `bluetooth_mac`. No new dependencies, no hot-swap of the live adapter.

## Technical Context

**Language/Version**: Python 3.11 / 3.12
**Primary Dependencies**: Streamlit ≥ 1.37 (`st.popover`), `carreralib` (optional, already declared as `[live]` extra), `pydantic`, `pyyaml`
**Storage**: `data/runtime_settings.json` (already used for `mock_mode`)
**Testing**: pytest unit tests for `RuntimeSettings`, `bluetooth_scanner`, and `_apply_overrides`. Streamlit popover UI verified via manual quickstart smoke (out of scope for an automated UI harness in v1).
**Target Platform**: Local developer machine (macOS / Linux). BLE scan requires `carreralib` extras.
**Project Type**: Single Python package (`src/`).
**Performance**: Scan completes in the `carreralib` default window (~3 s). No new hot path on the live pipeline.
**Constraints**: No regression in 002/FR-225 precedence. Backward-compatible with existing `runtime_settings.json` files that lack the new key. `mypy --strict` clean. No new runtime dependency.
**Scale/Scope**: Single-user, single-process Streamlit instance. Multi-CU is supported (device list).

## Constitution Check

The project constitution is the unratified template at `.specify/memory/constitution.md`. The gate passes vacuously: no concrete principles to violate. This slice adheres to the standing repo norms (test-first for the pure-logic changes; minimal change; backward-compatible JSON schema).

## Project Structure

### Documentation (this feature)

```
specs/004-bluetooth-connect-menu/
├── spec.md           # Feature specification
├── plan.md           # This file
└── tasks.md          # Ordered task list (US1 only)
```

### Source Code (repository root)

Changes are surgical edits to four existing files plus one new helper module:

```
src/
├── services/
│   ├── runtime_settings.py        # extend with bluetooth_mac key + helpers
│   └── bluetooth_scanner.py       # NEW: sync wrapper around carreralib.connection.scan
├── dashboard.py                   # add kebab popover with scan/select/reset
└── main.py                        # _apply_overrides: fallback to persisted MAC

tests/
├── test_race_controls.py          # extend RuntimeSettings tests
├── test_bluetooth_scanner.py      # NEW
└── test_main_overrides.py         # NEW (or extend test_main_adapter_selection.py)
```

## Phase 0 — Outline & Research

No genuine unknowns. The three "research" notes:

- **Decision**: Synchronous BLE scan in the Streamlit script run (using `carreralib.connection.scan()` directly, same call as `src.main._run_scan`).
  - **Rationale**: `carreralib.connection.scan()` is already proven and synchronous; ~3 s blocking inside a Streamlit interaction is acceptable for a user-initiated action. Asyncio bridging via `asyncio.run` inside Streamlit fragments is fragile.
  - **Alternatives considered**: (a) Re-use `LiveCarreraAdapter.discovered_devices()` via `asyncio.run(...)` — rejected: heavier, requires a `connect(None)` round-trip that may register the dashboard as a paired client. (b) Shell out to `carrera-monitor --scan` — rejected: harder to test, log noise, extra process.

- **Decision**: Persist-and-restart, not hot-swap, of the live adapter.
  - **Rationale**: Re-uses the established 002/FR-225 pattern; zero new IPC. The CarreraClientRunner is launched once per pipeline process; swapping it mid-flight would require a supervisor protocol that does not exist yet.
  - **Alternatives considered**: A SIGUSR1-driven restart hook — out of scope for v1.

- **Decision**: A new `ScannerError` / `ScannerUnavailableError` pair instead of re-using `AdapterConnectionError`.
  - **Rationale**: The scanner is a separate concern from adapter lifecycle and may evolve independently (e.g. add a `serial-port` backend). Distinct error types keep the dashboard branch logic cleaner.
  - **Alternatives considered**: Surface raw exceptions to the UI — rejected: leaks `bleak` internals.

## Phase 1 — Design & Contracts

### Data model

The on-disk JSON schema gains one optional key:

```json
{
  "mock_mode": false,
  "bluetooth_mac": null
}
```

`bluetooth_mac` is `str | None`. The default returned when the key is missing is `None`, so existing files are compatible. Empty string is normalized to `None` by the setter.

### Interface contracts

**`src.services.runtime_settings`**

```python
def get_bluetooth_mac() -> str | None: ...
def set_bluetooth_mac(value: str | None) -> str | None: ...

class RuntimeSettings:
    def get_bluetooth_mac(self) -> str | None: ...
    def set_bluetooth_mac(self, value: str | None) -> str | None: ...
```

**`src.services.bluetooth_scanner`**

```python
class ScannerError(RuntimeError): ...
class ScannerUnavailableError(ScannerError): ...

def scan_for_devices() -> list[tuple[str, str]]:
    """Return [(mac, name), ...]. Raises ScannerUnavailableError if carreralib
    is missing, ScannerError for any other failure."""
```

**`src.main._apply_overrides`** — new fallback rule:

```text
if args.mac is not None:                        cfg.bluetooth.mac_address = args.mac
elif cfg.bluetooth.mac_address is None:          cfg.bluetooth.mac_address = get_bluetooth_mac()
else:                                            (unchanged)
```

### Quickstart

```text
1. pip install -e .[live]
2. Power on the AppConnect.
3. streamlit run src/app.py
4. Open the dashboard, click ⋮ → 🔌 Bluetooth verbinden.
5. Pick a device → "Gespeichert. Restart erforderlich." appears.
6. Restart the pipeline:  python -m src.main
7. Verify the live adapter connects to the persisted MAC without scanning.
```

## Phase 2 — Tasks (see `tasks.md`)

Ordered, dependency-aware tasks live in `tasks.md`. All tasks belong to US1; no foundational/setup work is required beyond the routine tests-first cycle.
