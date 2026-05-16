"""BLE-stability hardening for the live adapter + runner.

Covers three fixes against the previously-shipped wiring:

1. A crashed `_read_loop` is surfaced through `LiveCarreraAdapter.events()`
   so the runner can rebuild the BLE link (previously the iterator hung
   on an idle queue forever).
2. `cu.reset()` is skipped on reconnects so the CU clock is preserved
   mid-race (previously every reconnect wiped the clock and corrupted
   subsequent lap-time deltas).
3. `CarreraClientRunner` uses exponential backoff (capped) between
   reconnect attempts (previously a fixed 5 s interval thrashed the
   BLE stack on persistent failure).
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import types
from typing import ClassVar

import pytest

from src.carrera_client import (
    AdapterConnectionError,
    AdapterReadError,
    CarreraClientRunner,
    DiscoveredDevice,
    LiveCarreraAdapter,
)
from src.event_model import ConnectionState, EventType, TelemetryEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _install_carreralib_stub() -> None:
    pkg = types.ModuleType("carreralib")

    class _Status: ...

    class _Timer: ...

    class _ControlUnit:
        Status = _Status
        Timer = _Timer

    pkg.ControlUnit = _ControlUnit  # type: ignore[attr-defined]

    conn = types.ModuleType("carreralib.connection")

    class _TimeoutError(Exception):
        pass

    conn.TimeoutError = _TimeoutError  # type: ignore[attr-defined]

    sys.modules["carreralib"] = pkg
    sys.modules["carreralib.connection"] = conn


# ---------------------------------------------------------------------------
# 1. Reader-task crash propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_iterator_surfaces_read_loop_failure() -> None:
    """If `_read_loop` raises `AdapterReadError`, the iterator must
    re-raise so the runner can react. Previously the iterator hung."""
    _install_carreralib_stub()
    from carreralib.connection import TimeoutError as CLTimeoutError

    class _FakeCU:
        def poll(self) -> None:
            raise CLTimeoutError("idle")

    adapter = LiveCarreraAdapter(idle_timeout_seconds=3)
    adapter._cu = _FakeCU()
    adapter._connected = True
    adapter._read_task = asyncio.create_task(adapter._read_loop())

    async def _consume() -> None:
        async for _ in adapter.events():
            pass

    with pytest.raises(AdapterReadError, match="idle"):
        await asyncio.wait_for(_consume(), timeout=2.0)


@pytest.mark.asyncio
async def test_events_iterator_exits_when_reader_finishes_cleanly() -> None:
    """A clean reader exit (no exception) must terminate the iterator
    without raising. Belongs in the same suite to lock the contract."""
    _install_carreralib_stub()

    adapter = LiveCarreraAdapter()
    adapter._connected = True

    async def _stop_after_tick() -> None:
        await asyncio.sleep(0.05)
        adapter._connected = False

    adapter._read_task = asyncio.create_task(_stop_after_tick())

    collected: list[TelemetryEvent] = []
    async for ev in adapter.events():
        collected.append(ev)
    assert collected == []


# ---------------------------------------------------------------------------
# 2. cu.reset() skipped on reconnect
# ---------------------------------------------------------------------------


class _FakeAdapterTracksReset:
    """Stand-in adapter that records reset_on_connect across instances."""

    source_name = "carrera_appconnect"
    instances: ClassVar[list[_FakeAdapterTracksReset]] = []

    def __init__(self) -> None:
        self._connected = False
        self._reset_on_connect = True
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        type(self).instances.append(self)

    async def connect(self, mac: str | None) -> None:
        # First instance fails so the runner forces a second attempt.
        if len(type(self).instances) == 1:
            raise AdapterConnectionError("simulated first-attempt failure")
        self._connected = True
        # Stop the consumer naturally after one tick.
        self._connected = False

    async def disconnect(self) -> None:
        self._connected = False

    async def events(self):  # type: ignore[no-untyped-def]
        while self._connected or not self._queue.empty():
            try:
                yield await asyncio.wait_for(self._queue.get(), timeout=0.05)
            except TimeoutError:
                if not self._connected:
                    return

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return []


@pytest.mark.asyncio
async def test_runner_skips_cu_reset_on_reconnect() -> None:
    """Second adapter instance must have `_reset_on_connect=False`."""
    _FakeAdapterTracksReset.instances = []
    runner = CarreraClientRunner(
        mac_address="AA:BB:CC:DD:EE:FF",
        reconnect_interval_seconds=0,
        max_reconnect_interval_seconds=0,
        adapter_factory=_FakeAdapterTracksReset,
    )
    await runner.connect(None)

    async def _drain() -> None:
        async for ev in runner.events():
            if ev.event_type == EventType.CONNECTION_STATE and ev.payload.get(
                "state"
            ) == ConnectionState.CONNECTED.value:
                return

    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(_drain(), timeout=3.0)
    await runner.disconnect()

    # First adapter: reset_on_connect stays True (default).
    # Second adapter: runner must have flipped it to False before connect().
    assert len(_FakeAdapterTracksReset.instances) >= 2
    assert _FakeAdapterTracksReset.instances[0]._reset_on_connect is True
    assert _FakeAdapterTracksReset.instances[1]._reset_on_connect is False


def test_live_adapter_init_default_reset_is_true() -> None:
    """First-construction default must remain unchanged so the very
    first connect of a session still calls cu.reset()."""
    adapter = LiveCarreraAdapter()
    assert adapter._reset_on_connect is True


def test_live_adapter_init_reset_can_be_disabled() -> None:
    adapter = LiveCarreraAdapter(reset_on_connect=False)
    assert adapter._reset_on_connect is False


# ---------------------------------------------------------------------------
# 3. Exponential backoff
# ---------------------------------------------------------------------------


class _AlwaysFailAdapter:
    """Adapter whose connect() always raises AdapterConnectionError."""

    source_name = "carrera_appconnect"

    def __init__(self) -> None:
        self._reset_on_connect = True

    async def connect(self, mac: str | None) -> None:
        raise AdapterConnectionError("nope")

    async def disconnect(self) -> None:
        return None

    async def events(self):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return []


@pytest.mark.asyncio
async def test_runner_uses_exponential_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sleep intervals between failed connects must double, capped."""
    sleeps: list[float] = []

    real_sleep = asyncio.sleep

    async def _fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        # Yield control without actually waiting.
        await real_sleep(0)

    monkeypatch.setattr("src.carrera_client.asyncio.sleep", _fake_sleep)

    runner = CarreraClientRunner(
        mac_address="AA:BB:CC:DD:EE:FF",
        reconnect_interval_seconds=1,
        max_reconnect_interval_seconds=8,
        adapter_factory=_AlwaysFailAdapter,
    )
    await runner.connect(None)
    # Let the runner cycle through several failed attempts.
    await real_sleep(0.2)
    await runner.disconnect()

    # First sleep is the initial interval; subsequent ones double until
    # capped at max_reconnect_interval_seconds (8).
    assert sleeps, "runner never slept"
    assert sleeps[0] == 1
    if len(sleeps) >= 2:
        assert sleeps[1] == 2
    if len(sleeps) >= 3:
        assert sleeps[2] == 4
    if len(sleeps) >= 4:
        assert sleeps[3] == 8
    # Cap holds.
    assert max(sleeps) <= 8


def test_runner_init_clamps_max_to_initial() -> None:
    """Misconfiguration (`max < initial`) must not produce shrinking backoff."""
    runner = CarreraClientRunner(
        mac_address=None,
        reconnect_interval_seconds=10,
        max_reconnect_interval_seconds=1,
    )
    assert runner._reconnect_max_s == 10
    assert runner._reconnect_initial_s == 10
