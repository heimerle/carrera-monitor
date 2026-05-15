# `CarreraAdapter` Protocol Contract

Internal Python contract that both the real (`carreralib`-backed) client and the mock client implement. It is the seam that keeps the rest of the system hardware-agnostic.

## Protocol

```python
from typing import AsyncIterator, Protocol, runtime_checkable

@runtime_checkable
class CarreraAdapter(Protocol):
    source_name: str  # "carrera_appconnect" | "mock"

    async def connect(self, mac_address: str | None) -> None: ...
    async def disconnect(self) -> None: ...
    def events(self) -> AsyncIterator["RawFrame"]: ...
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

- Returns an async iterator that yields `RawFrame` (a loosely typed dict with at least a `kind: str` discriminator).
- Iteration MUST stop cleanly when `disconnect()` is called.
- On BLE errors during iteration, raises `AdapterReadError`; caller (`carrera_client.py`) catches and triggers reconnect logic.

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
