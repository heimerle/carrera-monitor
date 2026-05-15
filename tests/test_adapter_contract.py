"""Adapter contract tests — parametrized over mock + a fake live adapter.

Both producers MUST emit canonical `TelemetryEvent`s with the required
event_type vocabulary and ordering invariants.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest

from src.carrera_client import (
    CarreraAdapter,
    CarreraClientRunner,
    DiscoveredDevice,
    LiveCarreraAdapter,
    translate_raw_frame,
)
from src.event_model import ConnectionState, EventType, TelemetryEvent
from src.mock_client import MockCarreraAdapter

# ---------------------------------------------------------------------------
# A fake "live" adapter that satisfies the Protocol but uses translate_raw_frame
# the same way the live one would, without any BLE dependency.
# ---------------------------------------------------------------------------


class FakeLiveAdapter:
    source_name = "carrera_appconnect"

    def __init__(self, *, debug_raw: bool = False) -> None:
        self._debug_raw = debug_raw
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=128)
        self._connected = False

    async def connect(self, mac_address: str | None) -> None:
        self._connected = True
        # Seed a deterministic event sequence.
        await self._push({"kind": "connection_state", "connection_state": "connected"})
        await self._push({"kind": "race_state", "race_state": "running"})
        await self._push({"kind": "lap", "car_id": 1, "lap_number": 1, "lap_time_ms": 7800})
        await self._push({"kind": "fuel", "car_id": 1, "fuel_percent": 95.0})
        await self._push(
            {
                "kind": "controller_input",
                "car_id": 1,
                "throttle": 0.5,
                "brake": 0.0,
            }
        )
        await self._push({"kind": "speed", "car_id": 1, "speed_kmh": 24.0})
        await self._push({"kind": "brake", "car_id": 1, "brake": 0.0})
        await self._push({"kind": "pitlane", "car_id": 1, "in_pit": True, "pit_reason": "fuel"})
        # Signal end-of-stream so events() drains naturally.
        self._connected = False
        self._connected = False

    async def disconnect(self) -> None:
        self._connected = False

    async def events(self) -> AsyncIterator[TelemetryEvent]:
        while self._connected or not self._queue.empty():
            try:
                yield await asyncio.wait_for(self._queue.get(), timeout=0.05)
            except TimeoutError:
                if not self._connected:
                    return

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return []

    async def _push(self, frame: dict[str, Any]) -> None:
        for ev in translate_raw_frame(frame, self.source_name, debug_raw=self._debug_raw):
            await self._queue.put(ev)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_mock_satisfies_protocol() -> None:
    assert isinstance(MockCarreraAdapter(), CarreraAdapter)


def test_live_adapter_satisfies_protocol() -> None:
    assert isinstance(LiveCarreraAdapter(), CarreraAdapter)


def test_fake_live_satisfies_protocol() -> None:
    assert isinstance(FakeLiveAdapter(), CarreraAdapter)


# ---------------------------------------------------------------------------
# Both adapters emit canonical events with required types
# ---------------------------------------------------------------------------


@pytest.fixture(params=["mock", "fake_live"])
def adapter(request: pytest.FixtureRequest) -> Any:
    if request.param == "mock":
        os.environ["MOCK_SEED"] = "42"
        return MockCarreraAdapter(car_count=2, tick_interval_s=0.02)
    return FakeLiveAdapter()


async def test_adapter_emits_canonical_events(adapter: Any) -> None:
    await adapter.connect(None)
    collected: list[TelemetryEvent] = []

    async def _drain() -> None:
        async for ev in adapter.events():
            collected.append(ev)
            if len(collected) >= 200:
                break

    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(_drain(), timeout=2.0)
    await adapter.disconnect()

    assert collected, "adapter produced no events"
    types = {ev.event_type for ev in collected}
    # Both must produce at minimum: connection_state + race_state.
    assert EventType.CONNECTION_STATE in types
    assert EventType.RACE_STATE in types

    # Monotonic timestamps must be non-decreasing.
    times = [ev.timestamp_monotonic_ms for ev in collected]
    assert times == sorted(times)


# ---------------------------------------------------------------------------
# CarreraClientRunner: reconnect emits connection_state transitions
# ---------------------------------------------------------------------------


class FlakyAdapter:
    """First connect() fails, second succeeds and emits 2 events then ends."""

    source_name = "carrera_appconnect"
    _attempt = 0

    def __init__(self) -> None:
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self._connected = False

    async def connect(self, mac: str | None) -> None:
        FlakyAdapter._attempt += 1
        if FlakyAdapter._attempt == 1:
            from src.carrera_client import AdapterConnectionError

            raise AdapterConnectionError("simulated first-attempt failure")
        self._connected = True
        for ev in translate_raw_frame(
            {"kind": "race_state", "race_state": "running"}, self.source_name
        ):
            await self._queue.put(ev)
        # Drain naturally after this single event.
        self._connected = False

    async def disconnect(self) -> None:
        self._connected = False

    async def events(self) -> AsyncIterator[TelemetryEvent]:
        while self._connected or not self._queue.empty():
            try:
                yield await asyncio.wait_for(self._queue.get(), timeout=0.05)
            except TimeoutError:
                if not self._connected:
                    return

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return []


async def test_runner_reconnect_emits_state_transitions() -> None:
    FlakyAdapter._attempt = 0
    runner = CarreraClientRunner(
        mac_address="AA:BB:CC:DD:EE:FF",
        reconnect_interval_seconds=0,
        adapter_factory=FlakyAdapter,
    )
    await runner.connect(None)

    collected: list[TelemetryEvent] = []

    async def _drain() -> None:
        async for ev in runner.events():
            collected.append(ev)
            if any(e.event_type == EventType.RACE_STATE for e in collected):
                return

    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(_drain(), timeout=3.0)
    await runner.disconnect()

    states = [
        ev.payload.get("state") for ev in collected if ev.event_type == EventType.CONNECTION_STATE
    ]
    # Expect: connecting -> reconnecting (after fail) -> connecting -> connected
    assert ConnectionState.CONNECTING.value in states
    assert ConnectionState.RECONNECTING.value in states
    assert ConnectionState.CONNECTED.value in states
