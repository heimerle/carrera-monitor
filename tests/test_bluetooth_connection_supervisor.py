"""Tests for BluetoothConnectionSupervisor lifecycle behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.carrera_client import AdapterConnectionError, AdapterReadError
from src.config import BluetoothConfig
from src.event_model import EventType, TelemetryEvent
from src.services.bluetooth_connection_supervisor import BluetoothConnectionSupervisor
from src.services.runtime_settings import RuntimeSettings
from src.state.bluetooth_state import BluetoothState


class _ScriptedAdapter:
    source_name = "carrera_appconnect"

    def __init__(
        self,
        *,
        connect_error: Exception | None = None,
        events: list[TelemetryEvent | Exception] | None = None,
    ) -> None:
        self._connect_error = connect_error
        self._events = list(events or [])
        self._connected = False
        self._disconnect_event = asyncio.Event()
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def connect(self, _mac: str | None) -> None:
        self.connect_calls += 1
        if self._connect_error is not None:
            raise self._connect_error
        self._connected = True
        self._disconnect_event.clear()

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self._connected = False
        self._disconnect_event.set()

    async def events(self):  # type: ignore[no-untyped-def]
        for item in self._events:
            if isinstance(item, Exception):
                raise item
            yield item
        if self._connected:
            await self._disconnect_event.wait()


async def _wait_until(predicate, max_wait_s: float = 1.5) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_wait_s
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def _make_cfg(**overrides: object) -> BluetoothConfig:
    base = {
        "connect_timeout_seconds": 1,
        "reconnect_interval_seconds": 1,
        "max_reconnect_interval_seconds": 5,
        "reconnect_backoff_seconds": [1, 2, 5],
        "idle_timeout_seconds": 5,
        "idle_warning_seconds": 1,
        "stale_timeout_seconds": 1,
        "reconnect_on_stale": True,
        "prefer_scan_device_object": False,
    }
    base.update(overrides)
    return BluetoothConfig(**base)


def _make_runtime(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(path=tmp_path / "runtime_settings.json")


@pytest.mark.asyncio
async def test_manual_disconnect_blocks_auto_reconnect(tmp_path: Path) -> None:
    adapter = _ScriptedAdapter()
    runtime = _make_runtime(tmp_path)
    supervisor = BluetoothConnectionSupervisor(
        config=_make_cfg(),
        runtime_settings=runtime,
        adapter_factory=lambda: adapter,
    )

    await supervisor.connect(None)
    await _wait_until(lambda: supervisor.get_status().state is BluetoothState.READY)

    await supervisor.disconnect(manual=True)
    await asyncio.sleep(0.05)

    status = supervisor.get_status()
    assert status.state is BluetoothState.MANUALLY_DISCONNECTED
    assert status.desired_connected is False
    assert adapter.connect_calls == 1

    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_unexpected_disconnect_triggers_reconnect(tmp_path: Path) -> None:
    first = _ScriptedAdapter(events=[AdapterReadError("reader crashed")])
    second = _ScriptedAdapter()
    adapters = [first, second]
    idx = {"value": 0}

    def _factory() -> _ScriptedAdapter:
        pos = idx["value"]
        idx["value"] = min(pos + 1, len(adapters) - 1)
        return adapters[pos]

    runtime = _make_runtime(tmp_path)
    supervisor = BluetoothConnectionSupervisor(
        config=_make_cfg(),
        runtime_settings=runtime,
        adapter_factory=_factory,
    )

    delays: list[float] = []

    async def _fast_wait(delay: float) -> None:
        delays.append(float(delay))
        await asyncio.sleep(0)

    supervisor._wait_or_wake = _fast_wait  # type: ignore[method-assign]

    await supervisor.connect(None)
    await _wait_until(lambda: first.connect_calls == 1)
    await _wait_until(lambda: second.connect_calls >= 1)

    status = supervisor.get_status()
    assert status.desired_connected is True
    assert status.state in {
        BluetoothState.READY,
        BluetoothState.RECONNECTING,
        BluetoothState.CONNECTING,
    }
    assert delays, "reconnect path should invoke wait/backoff"

    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_reconnect_uses_backoff_schedule(tmp_path: Path) -> None:
    runtime = _make_runtime(tmp_path)

    def _factory() -> _ScriptedAdapter:
        return _ScriptedAdapter(connect_error=AdapterConnectionError("connect failed"))

    supervisor = BluetoothConnectionSupervisor(
        config=_make_cfg(reconnect_backoff_seconds=[1, 2, 5]),
        runtime_settings=runtime,
        adapter_factory=_factory,
    )

    delays: list[float] = []

    async def _capture_wait(delay: float) -> None:
        delays.append(float(delay))
        if len(delays) >= 4:
            runtime.set_bluetooth_desired_connected(False)
            supervisor._desired_connected = False  # type: ignore[attr-defined]
        await asyncio.sleep(0)

    supervisor._wait_or_wake = _capture_wait  # type: ignore[method-assign]

    await supervisor.connect(None)
    await _wait_until(lambda: len(delays) >= 4)

    assert delays[:4] == [1.0, 2.0, 5.0, 5.0]

    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_stale_detection_ignores_mock_source_events(tmp_path: Path) -> None:
    clock = {"ms": 0}

    def _mono() -> int:
        return int(clock["ms"])

    class _MockOnlyAdapter(_ScriptedAdapter):
        async def events(self):  # type: ignore[no-untyped-def]
            for _ in range(4):
                clock["ms"] += 600
                yield TelemetryEvent(
                    timestamp_iso=datetime.now(tz=UTC),
                    timestamp_monotonic_ms=int(clock["ms"]),
                    source="mock",
                    event_type=EventType.RACE_STATE,
                    payload={"state": "running"},
                )
            if self._connected:
                await self._disconnect_event.wait()

    adapter = _MockOnlyAdapter()
    runtime = _make_runtime(tmp_path)
    supervisor = BluetoothConnectionSupervisor(
        config=_make_cfg(stale_timeout_seconds=1, reconnect_on_stale=False),
        runtime_settings=runtime,
        adapter_factory=lambda: adapter,
        monotonic_clock=_mono,
    )

    await supervisor.connect(None)
    await _wait_until(lambda: supervisor.get_status().state is BluetoothState.STALE)

    status = supervisor.get_status()
    assert status.state is BluetoothState.STALE
    assert status.last_error is not None

    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_lifecycle_events_include_named_connection_events(tmp_path: Path) -> None:
    adapter = _ScriptedAdapter()
    runtime = _make_runtime(tmp_path)
    supervisor = BluetoothConnectionSupervisor(
        config=_make_cfg(),
        runtime_settings=runtime,
        adapter_factory=lambda: adapter,
    )

    iterator = supervisor.events()

    await supervisor.connect(None)
    await _wait_until(lambda: supervisor.get_status().state is BluetoothState.READY)
    await supervisor.disconnect(manual=True)

    captured: list[TelemetryEvent] = []
    for _ in range(16):
        try:
            ev = await asyncio.wait_for(iterator.__anext__(), timeout=0.2)
        except TimeoutError:
            break
        captured.append(ev)
        if (
            ev.event_type is EventType.CONNECTION_STATE
            and ev.payload.get("event") == "bluetooth_manual_disconnect"
        ):
            break

    await supervisor.shutdown()

    lifecycle_events = [
        ev.payload.get("event")
        for ev in captured
        if ev.event_type is EventType.CONNECTION_STATE and ev.source == "system"
    ]
    assert "bluetooth_connecting" in lifecycle_events
    assert "bluetooth_ready" in lifecycle_events
    assert "bluetooth_manual_disconnect" in lifecycle_events
