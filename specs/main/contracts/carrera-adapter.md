# `CarreraAdapter` Protocol Contract

Internal Python contract that both the real (`carreralib`-backed) client and the mock client implement. It is the seam that keeps the rest of the system hardware-agnostic.

**Status note**: The post-003 in-tree implementation in [src/carrera_client.py](../../../src/carrera_client.py) and [src/mock_client.py](../../../src/mock_client.py) has converged on `events()` yielding fully-translated `TelemetryEvent` objects (not raw frames) so the runner can stay translation-agnostic. The original raw-frame contract below is preserved for historical reference; the **authoritative** post-003 shape is captured in [specs/003-live-adapter-carreralib/contracts/live-adapter.md](../../003-live-adapter-carreralib/contracts/live-adapter.md).

## Protocol

```python
from typing import AsyncIterator, Protocol, runtime_checkable

@runtime_checkable
class CarreraAdapter(Protocol):
    source_name: str  # "carrera_appconnect" (live) | "mock"

    async def connect(self, mac_address: str | None) -> None: ...
    async def disconnect(self) -> None: ...
    def events(self) -> AsyncIterator["TelemetryEvent"]: ...
    async def discovered_devices(self) -> list["DiscoveredDevice"]: ...
```

## Semantics

### `connect(mac_address)`

- If `mac_address` is `None`, perform a BLE scan and connect to the first AppConnect device found within `scan_timeout_seconds`.
- If `mac_address` is provided, skip scan and connect directly.
- Raises `AdapterConnectionError` on failure (typed exception in `src/carrera_client.py`).
- Mock implementation: returns immediately, ignores `mac_address`.

### `disconnect()`

- Idempotent. Safe to call when already disconnected. Never raises.

### `events()`

- Returns an async iterator that yields **translated `TelemetryEvent` objects** (the post-003 shape; see status note above for the historical `RawFrame` contract).
- Iteration MUST stop cleanly when `disconnect()` is called.
- On reader-task failure during iteration, the iterator MUST surface the underlying exception (per 003/FR-005) so `CarreraClientRunner` can trigger reconnect logic.

### `discovered_devices()`

- Returns the list of devices observed during the last scan; empty list if no scan has run.

## Types

```python
@dataclass(frozen=True)
class DiscoveredDevice:
    name: str
    address: str  # MAC

class RawFrame(TypedDict, total=False):
    kind: str            # required
    car_id: int
    lap_number: int
    lap_time_ms: int
    fuel_percent: float
    throttle: float
    brake: float
    speed_kmh: float
    in_pit: bool
    race_state: str
    raw: dict
```

`carrera_client.py` translates `RawFrame` → `TelemetryEvent` and is the sole place where `carreralib`-specific knowledge lives. Hardware-verification TODOs are limited to that translation function.

## Test obligations

- Both implementations MUST pass the same `tests/test_adapter_contract.py` suite (added in tasks phase): connect/disconnect idempotency, event stream stops on disconnect, error types.
