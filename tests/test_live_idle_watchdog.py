"""Idle-watchdog behaviour for `LiveCarreraAdapter._read_loop`.

Stubs `carreralib` + a fake `cu.poll()` that always raises the carreralib
TimeoutError, and asserts the loop raises `AdapterReadError` once the
idle threshold is reached so the runner can rebuild the BLE link.
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from src.carrera_client import AdapterReadError, LiveCarreraAdapter
from src.services.live_continuity import LinkHealthTracker


def _install_carreralib_stub() -> None:
    """Provide a minimal `carreralib` + `carreralib.connection` stub."""
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


@pytest.mark.asyncio
async def test_read_loop_raises_after_idle_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_carreralib_stub()
    from carreralib.connection import TimeoutError as CLTimeoutError

    class _FakeCU:
        def poll(self) -> None:
            raise CLTimeoutError("idle")

    adapter = LiveCarreraAdapter(idle_timeout_seconds=3)
    adapter._cu = _FakeCU()
    adapter._connected = True

    with pytest.raises(AdapterReadError, match="idle"):
        await asyncio.wait_for(adapter._read_loop(), timeout=2.0)


@pytest.mark.asyncio
async def test_read_loop_keeps_running_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single timeout must NOT raise — only sustained idle does."""
    _install_carreralib_stub()
    from carreralib.connection import TimeoutError as CLTimeoutError

    polls = 0

    class _FakeCU:
        def poll(self_inner) -> str:
            nonlocal polls
            polls += 1
            if polls < 3:
                raise CLTimeoutError("idle")
            # Stop the loop cleanly.
            adapter._connected = False
            return "sentinel"

    adapter = LiveCarreraAdapter(idle_timeout_seconds=10)
    adapter._cu = _FakeCU()
    adapter._connected = True

    # Should return without raising; idle streak (2) stays below threshold.
    await asyncio.wait_for(adapter._read_loop(), timeout=2.0)
    assert polls >= 3


def test_link_health_transitions_healthy_to_degraded_to_stalled_to_reconnecting_to_healthy() -> None:
    tracker = LinkHealthTracker(warning_threshold=2, hard_threshold=4)

    assert tracker.state.state == "healthy"

    tracker.on_timeout()  # 1
    assert tracker.state.state == "healthy"

    tracker.on_timeout()  # 2
    assert tracker.state.state == "degraded"
    assert tracker.state.reason == "timeout_streak_warning"

    tracker.on_timeout()  # 3
    tracker.on_timeout()  # 4
    assert tracker.state.state == "stalled"
    assert tracker.state.reason == "timeout_streak_hard"

    tracker.mark_reconnecting("watchdog_reconnect")
    assert tracker.state.state == "reconnecting"
    assert tracker.state.reason == "watchdog_reconnect"

    tracker.on_frame(now_monotonic_ms=1234)
    assert tracker.state.state == "healthy"
    assert tracker.state.timeout_streak == 0
    assert tracker.state.last_frame_at_ms == 1234
