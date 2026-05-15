"""Carrera adapter contract + translation layer.

The `CarreraAdapter` Protocol is the sole seam between the rest of the
pipeline and Bluetooth-specific code. `translate_raw_frame` is the **only**
place in the codebase that understands raw upstream frame shapes — the
mock client uses it too so both producers emit the same canonical
`TelemetryEvent`s.

A real `LiveCarreraAdapter` (US2) lives in this module as well so that
`carreralib` knowledge stays contained per FR-024.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, runtime_checkable

from . import utils
from .event_model import (
    ConnectionState,
    EventType,
    RaceState,
    TelemetryEvent,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredDevice:
    name: str
    address: str  # MAC


class RawFrame(TypedDict, total=False):
    """Loose dict from the adapter; `kind` is the discriminator."""

    kind: str
    car_id: int
    controller_id: int
    lap_number: int
    lap_time_ms: int
    fuel_percent: float
    throttle: float
    brake: float
    speed_kmh: float
    in_pit: bool
    pit_reason: str
    race_state: str
    connection_state: str
    error: str
    raw: dict[str, Any]


class AdapterConnectionError(Exception):
    """Raised when the adapter cannot establish a connection."""


class AdapterReadError(Exception):
    """Raised when reading from a connected adapter fails mid-stream."""


@runtime_checkable
class CarreraAdapter(Protocol):
    source_name: str  # "carrera_appconnect" | "mock"

    async def connect(self, mac_address: str | None) -> None: ...
    async def disconnect(self) -> None: ...
    def events(self) -> AsyncIterator[TelemetryEvent]: ...
    async def discovered_devices(self) -> list[DiscoveredDevice]: ...


# ---------------------------------------------------------------------------
# RawFrame → TelemetryEvent translation
# ---------------------------------------------------------------------------


def translate_raw_frame(
    frame: RawFrame,
    source: str,
    *,
    debug_raw: bool = False,
) -> list[TelemetryEvent]:
    """Translate a single raw frame into one or more canonical events.

    Returns a list because a frame may produce a primary event plus a
    companion `raw` passthrough event when `debug_raw` is on (FR-013).
    Unknown `kind`s yield a single `not_supported` event preserving the
    raw frame in `raw_data` (FR-012).
    """
    kind = frame.get("kind", "")
    car_id = frame.get("car_id")
    controller_id = frame.get("controller_id")
    ts_iso = utils.now_iso()
    ts_mono = utils.now_monotonic_ms()
    metadata: dict[str, str] = {}

    primary: TelemetryEvent | None = None
    raw_data_for_primary: dict[str, Any] | None = None

    if kind == "lap":
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.LAP,
            car_id=car_id,
            controller_id=controller_id,
            payload={
                "lap_number": int(frame["lap_number"]),
                "lap_time_ms": int(frame["lap_time_ms"]),
            },
            metadata=metadata,
        )
    elif kind == "fuel":
        level = _clamp(float(frame["fuel_percent"]), 0.0, 100.0)
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.FUEL,
            car_id=car_id,
            controller_id=controller_id,
            payload={"level_percent": level},
            metadata=metadata,
        )
    elif kind == "race_state":
        state_str = str(frame["race_state"])
        try:
            RaceState(state_str)
        except ValueError:
            metadata["coerced_from"] = state_str
            state_str = RaceState.IDLE.value
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.RACE_STATE,
            payload={"state": state_str},
            metadata=metadata,
        )
    elif kind == "controller_input":
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.CONTROLLER_INPUT,
            car_id=car_id,
            controller_id=controller_id,
            payload={
                "throttle": _clamp(float(frame["throttle"]), 0.0, 1.0),
                "brake": _clamp(float(frame["brake"]), 0.0, 1.0),
            },
            metadata=metadata,
        )
    elif kind == "speed":
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.SPEED,
            car_id=car_id,
            payload={"speed_kmh": max(0.0, float(frame["speed_kmh"]))},
            metadata=metadata,
        )
    elif kind == "brake":
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.BRAKE,
            car_id=car_id,
            payload={"brake": _clamp(float(frame["brake"]), 0.0, 1.0)},
            metadata=metadata,
        )
    elif kind == "pitlane":
        reason = str(frame.get("pit_reason", "unknown"))
        if reason not in {"manual", "fuel", "unknown"}:
            reason = "unknown"
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.PITLANE,
            car_id=car_id,
            payload={"in_pit": bool(frame["in_pit"]), "reason": reason},
            metadata=metadata,
        )
    elif kind == "connection_state":
        state_str = str(frame["connection_state"])
        try:
            ConnectionState(state_str)
        except ValueError:
            metadata["coerced_from"] = state_str
            state_str = ConnectionState.DISCONNECTED.value
        err = frame.get("error")
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.CONNECTION_STATE,
            payload={"state": state_str, "error": err if err is None else str(err)},
            metadata=metadata,
        )
    else:
        # Unknown / not yet supported. Preserve frame for later RE work.
        raw_data_for_primary = {"frame": dict(frame)}
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.NOT_SUPPORTED,
            payload={"reason": f"unknown frame kind: {kind!r}"},
            raw_data=raw_data_for_primary,
            metadata=metadata,
        )

    out: list[TelemetryEvent] = [primary]
    if debug_raw and primary.event_type is not EventType.NOT_SUPPORTED:
        raw_event = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,  # type: ignore[arg-type]
            event_type=EventType.RAW,
            car_id=car_id,
            controller_id=controller_id,
            payload={},
            raw_data={"frame": dict(frame)},
            metadata={"companion_of": primary.event_type.value},
        )
        out.append(raw_event)
    return out


def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


__all__ = [
    "AdapterConnectionError",
    "AdapterReadError",
    "CarreraAdapter",
    "CarreraClientRunner",
    "DiscoveredDevice",
    "LiveCarreraAdapter",
    "RawFrame",
    "translate_raw_frame",
]


# ---------------------------------------------------------------------------
# Live adapter (carreralib-backed)
# ---------------------------------------------------------------------------


class LiveCarreraAdapter:
    """Bluetooth-backed adapter. Lazy-imports `carreralib` so mock mode is BLE-free."""

    source_name: str = "carrera_appconnect"

    def __init__(
        self,
        *,
        scan_timeout_seconds: int = 10,
        debug_raw: bool = False,
    ) -> None:
        self._scan_timeout = scan_timeout_seconds
        self._debug_raw = debug_raw
        self._connected = False
        self._client: Any = None
        self._devices: list[DiscoveredDevice] = []
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=4096)
        self._read_task: asyncio.Task[None] | None = None

    async def connect(self, mac_address: str | None) -> None:
        try:
            import carreralib  # noqa: F401  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AdapterConnectionError(
                "carreralib is not installed; install it for live mode, "
                "or run with --mock"
            ) from exc

        # TODO(hardware): verify carreralib field name — scan/connect API
        # surface and event callback shape need confirmation against a real
        # adapter before shipping a non-mock build.
        try:
            # Placeholder: carreralib exact API is not finalized here.
            # The full live wiring is gated by R-001 (hardware-verification).
            raise AdapterConnectionError(
                "LiveCarreraAdapter wiring is not yet hardware-verified (R-001). "
                "Run with --mock until US2 is closed against real hardware."
            )
        except AdapterConnectionError:
            raise
        except Exception as exc:  # pragma: no cover - hardware path
            raise AdapterConnectionError(str(exc)) from exc

    async def disconnect(self) -> None:
        # Idempotent: safe to call when never connected.
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, Exception):
                pass
            self._read_task = None
        self._connected = False
        self._client = None

    async def events(self) -> AsyncIterator[TelemetryEvent]:  # type: ignore[override]
        while self._connected or not self._queue.empty():
            try:
                ev = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                if not self._connected:
                    break
                continue
            yield ev

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return list(self._devices)


# ---------------------------------------------------------------------------
# Reconnect-aware client runner
# ---------------------------------------------------------------------------


class CarreraClientRunner:
    """Manages a `LiveCarreraAdapter` with reconnect-on-failure semantics.

    Exposes the same surface as a `CarreraAdapter` so `main.py` does not
    care whether it's talking to mock or live. Emits `connection_state`
    events on every transition.
    """

    source_name: str = "carrera_appconnect"

    def __init__(
        self,
        *,
        mac_address: str | None = None,
        scan_timeout_seconds: int = 10,
        reconnect_interval_seconds: int = 5,
        debug_raw: bool = False,
        monotonic_clock: Any = None,
        adapter_factory: Any = None,
    ) -> None:
        self._mac = mac_address
        self._scan_timeout = scan_timeout_seconds
        self._reconnect_s = reconnect_interval_seconds
        self._debug_raw = debug_raw
        self._mono = monotonic_clock or utils.now_monotonic_ms
        self._adapter_factory = adapter_factory or (
            lambda: LiveCarreraAdapter(
                scan_timeout_seconds=scan_timeout_seconds,
                debug_raw=debug_raw,
            )
        )
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=4096)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._current: Any = None  # current adapter instance
        self._state: ConnectionState = ConnectionState.DISCONNECTED

    async def connect(self, mac_address: str | None) -> None:
        if mac_address is not None:
            self._mac = mac_address
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="carrera-runner")

    async def disconnect(self) -> None:
        self._stop.set()
        if self._current is not None:
            try:
                await self._current.disconnect()
            except Exception:
                logger.exception("runner: adapter disconnect raised")
            self._current = None
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            except Exception:
                logger.exception("runner: task raised on shutdown")
            self._task = None

    async def events(self) -> AsyncIterator[TelemetryEvent]:  # type: ignore[override]
        while not self._stop.is_set() or not self._queue.empty():
            try:
                ev = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            yield ev

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        if self._current is None:
            return []
        return await self._current.discovered_devices()

    # ----- Internals ------------------------------------------------------

    async def _emit_connection(
        self, state: ConnectionState, error: str | None = None
    ) -> None:
        self._state = state
        ev = TelemetryEvent(
            timestamp_iso=utils.now_iso(),
            timestamp_monotonic_ms=self._mono(),
            source=self.source_name,  # type: ignore[arg-type]
            event_type=EventType.CONNECTION_STATE,
            payload={"state": state.value, "error": error},
        )
        try:
            self._queue.put_nowait(ev)
        except asyncio.QueueFull:
            try:
                _ = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                # Scan / connect
                if self._mac is None:
                    await self._emit_connection(ConnectionState.SCANNING)
                else:
                    await self._emit_connection(ConnectionState.CONNECTING)
                adapter = self._adapter_factory()
                self._current = adapter
                try:
                    await adapter.connect(self._mac)
                    await self._emit_connection(ConnectionState.CONNECTED)
                except AdapterConnectionError as exc:
                    logger.warning("runner: connect failed: %s", exc)
                    await self._emit_connection(ConnectionState.RECONNECTING, str(exc))
                    self._current = None
                    if self._stop.is_set():
                        break
                    await asyncio.sleep(self._reconnect_s)
                    continue

                # Pump events
                try:
                    async for ev in adapter.events():
                        try:
                            self._queue.put_nowait(ev)
                        except asyncio.QueueFull:
                            try:
                                _ = self._queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                            try:
                                self._queue.put_nowait(ev)
                            except asyncio.QueueFull:
                                pass
                        if self._stop.is_set():
                            break
                except AdapterReadError as exc:
                    logger.warning("runner: read error: %s", exc)
                    await self._emit_connection(ConnectionState.RECONNECTING, str(exc))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("runner: unexpected error during read")
                    await self._emit_connection(ConnectionState.ERROR, str(exc))
                finally:
                    try:
                        await adapter.disconnect()
                    except Exception:
                        pass
                    self._current = None

                if self._stop.is_set():
                    break
                await asyncio.sleep(self._reconnect_s)
        except asyncio.CancelledError:
            raise
        finally:
            await self._emit_connection(ConnectionState.DISCONNECTED)
