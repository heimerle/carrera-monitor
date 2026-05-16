# Implementation Plan: Race Controls (Finish Button, Safety Car, Mock Mode Toggle)

**Branch**: `002-race-controls` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-race-controls/spec.md`
**Status**: Implemented (merged to `main` via PR #5, commit `4ce8570`). This plan is retroactive — it documents the design that shipped so that follow-up speckit slices have a normal `plan.md → tasks.md` anchor.

## Summary

Three small, independent additions to the existing race-management module:

1. **Finish-by-user**: thin service wrapper (`finish_race_by_user`) over the existing `finish_race`, tagging the persisted `race_finished` event with `payload['triggered_by']='user'`, plus a primary-styled UI button.
2. **Safety-car phase**: two new service methods (`set_safety_car` / `is_safety_car_active`) backed by `race_events` rows + an in-memory `dict[int, bool]` cache, plus a UI toggle and a banner.
3. **Mock-mode toggle**: a new `RuntimeSettings` service backed by a JSON file (`data/runtime_settings.json`, atomic writes), a Streamlit toggle on the Settings page, and a single-line change to `src/main.py` adapter selection.

No new ORM tables, no schema migrations, no new dependencies. Service layer remains the only writer; UI calls services and never imports SQLAlchemy. The state machine's existing `_VALID_TRANSITIONS` is the single source of truth for validation.

## Technical Context

**Language/Version**: Python 3.11+ (matches existing project).
**Primary Dependencies**: existing — `SQLAlchemy>=2.0`, `pydantic>=2`, `streamlit>=1.30`, stdlib only for `runtime_settings` (`json`, `os`, `tempfile`, `pathlib`, `logging`).
**Storage**: existing SQLite at `data/carrera_dashboard.sqlite3` (no new tables); one new JSON file at `data/runtime_settings.json`.
**Testing**: `pytest` with the existing in-memory-SQLite fixtures (`db_session`, `race_factory`).
**Target Platform**: unchanged (single-user dev workstation).
**Project Type**: unchanged (single Python package).
**Performance Goals**: UI round-trip < 100 ms for finish/safety-car click (SC-201).
**Constraints**: UI layer remains ORM-free (FR-130); telemetry pipeline must not crash on DB errors (FR-121); ruff + mypy strict on `src/` must stay green.
**Scale/Scope**: ≤ 6 cars, single concurrent `running` race per process (FR-110), single Streamlit user.

## Constitution Check

The constitution at `.specify/memory/constitution.md` is still an unratified template. No principles are in force, so no gate can fail. This plan self-imposes the same principles the parent race-management plan adopted (modularity, observability, testability, simplicity, fail-loudly). All three slices add < 200 LOC of production code each and 21 lines of tests total — well within the simplicity envelope.

## Project Structure

### Documentation (this feature)

```text
specs/002-race-controls/
├── plan.md              # This file
├── spec.md              # Feature specification
└── tasks.md             # /speckit.tasks output
```

(No `research.md`, `data-model.md`, `quickstart.md`, or `contracts/` — the feature is small enough that the parent module's design docs already cover the substrate; spec.md + plan.md + tasks.md is sufficient.)

### Source Code Changes

```text
carrera-monitor/
├── src/
│   ├── main.py                                # MODIFIED — adapter-selection now consults RuntimeSettings
│   ├── pages/
│   │   ├── race_management.py                 # MODIFIED — new _render_race_controls() panel
│   │   └── settings.py                        # MODIFIED — Mock-mode toggle
│   └── services/
│       ├── race_service.py                    # MODIFIED — finish_race_by_user, set_safety_car, is_safety_car_active
│       └── runtime_settings.py                # NEW — JSON-backed settings store + module-level helpers
└── tests/
    └── test_race_controls.py                  # NEW — 21 tests covering all three slices
```

**Structure Decision**: All three slices live in existing layers (`src/services/`, `src/pages/`, `src/main.py`). The only new file in `src/` is `runtime_settings.py`. Tests are consolidated in one new file because they share fixtures and stay under ~300 lines.

## Phase 0 — Research

(Empty — all decisions are direct consequences of the existing `race_service.py` state machine and the existing `data/` directory convention. No new dependencies, no new patterns.)

Key prior-art references already in the repo:

- `RaceService._transition(...)` already accepts a payload dict that becomes the `race_events.payload_json` for the transition — extending it with an `extra_payload` parameter lets us inject `triggered_by='user'` without duplicating the transition path.
- `_VALID_TRANSITIONS` in `race_service.py` defines `finish_race` as valid only from `{running, paused}` — `finish_race_by_user` inherits this guard automatically.
- `ActiveRaceContext.clear()` is already called from `finish_race` and `cancel_race`; the safety-car cache piggybacks on those same exit points.
- `data/.gitkeep` + `data/*` gitignore rule covers the new `runtime_settings.json` without additional `.gitignore` edits.

## Phase 1 — Design & Contracts

### Service contracts (additions to `RaceService`)

```python
def finish_race_by_user(self, race_id: int) -> RaceRead:
    """Finish a race via explicit user action.

    Tags the persisted race_finished event with payload['triggered_by']='user'.
    Inherits the {running, paused} state guard from finish_race.

    Raises:
        RaceNotFoundError, InvalidRaceStateError, RaceValidationError
    """

def set_safety_car(self, race_id: int, active: bool) -> bool:
    """Idempotently toggle the safety-car phase for a race.

    Persists exactly one safety_car_started or safety_car_ended event per
    state change. Re-asserting the current value is a no-op.

    Status guard: {running, paused}.
    Raises: RaceNotFoundError, InvalidRaceStateError
    Returns: the new active state.
    """

def is_safety_car_active(self, race_id: int) -> bool:
    """Read the in-memory safety-car flag for a race. Returns False if unknown."""
```

### Runtime-settings contract

```python
class RuntimeSettings:
    _DEFAULTS = {"mock_mode": False}
    def __init__(self, path: Path | None = None) -> None: ...
    def get_mock_mode(self) -> bool: ...
    def set_mock_mode(self, value: bool) -> bool: ...
    def as_dict(self) -> dict[str, Any]: ...
    @property
    def path(self) -> Path: ...

# Module-level helpers
def get_mock_mode() -> bool: ...
def set_mock_mode(value: bool) -> bool: ...
```

Atomic-write strategy: `fd, tmp = tempfile.mkstemp(dir=path.parent)`; write JSON; `os.replace(tmp, path)`. Corrupt-file recovery: catch `json.JSONDecodeError` + `OSError`, log WARNING, return defaults.

### State-machine extension

No new states. `_VALID_TRANSITIONS` is unchanged. `_transition(...)` gains an `extra_payload: dict[str, str] | None = None` parameter that is merged into the event payload pre-persist.

### Constitution Re-Check (post-design)

No violations introduced. Sync SQLAlchemy paths are preserved; UI stays ORM-free; ingest path is untouched. Gate passes.

## Phase 2 — Tasks (deferred)

`tasks.md` is generated by `/speckit.tasks`. See the companion file.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| In-memory safety-car cache (vs. a dedicated DB column or read-from-event-log) | YAGNI — feature ships in one slice; cache survives the lifetime of the `RaceService` instance which is also the lifetime of the active race | Adding a `safety_car_active` column to `races` requires a schema migration with no Alembic in v1; reconstructing from event log on every read is a perf-and-correctness footgun for a v1 polish item |
| JSON file (vs. DB row) for `RuntimeSettings` | Decoupled from the DB lifecycle so the Settings UI works even before any race exists, and the pipeline process can read it without opening the DB | DB column would couple process startup ordering to schema migration; environment variable would not persist across restarts |
