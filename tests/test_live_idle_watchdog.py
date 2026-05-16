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
