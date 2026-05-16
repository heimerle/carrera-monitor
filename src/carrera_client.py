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
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, TypedDict, runtime_checkable

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
            source=source,
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
            source=source,
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
            source=source,
            event_type=EventType.RACE_STATE,
            payload={"state": state_str},
            metadata=metadata,
        )
    elif kind == "controller_input":
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,
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
            source=source,
            event_type=EventType.SPEED,
            car_id=car_id,
            payload={"speed_kmh": max(0.0, float(frame["speed_kmh"]))},
            metadata=metadata,
        )
    elif kind == "brake":
        primary = TelemetryEvent(
            timestamp_iso=ts_iso,
            timestamp_monotonic_ms=ts_mono,
            source=source,
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
            source=source,
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
            source=source,
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
            source=source,
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
            source=source,
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
    """Bluetooth-backed adapter. Lazy-imports `carreralib` so mock mode is BLE-free.

    Wraps `carreralib.ControlUnit` (which speaks the Carrera DIGITAL
    132/124 + AppConnect protocol over BLE on macOS via bleak or over
    serial elsewhere). The blocking `cu.poll()` call is offloaded to a
    worker thread via `asyncio.to_thread`; translated events are pushed
    onto an `asyncio.Queue` that `events()` drains.
    """

    source_name: str = "carrera_appconnect"

    # Heuristic mapping of the Status.start byte to our RaceState enum.
    # See carreralib/__main__.py for the upstream interpretation:
    #  - 0  → idle / no race armed
    #  - 1..5 → start-light countdown
    #  - 6 → running
    #  - 7 → paused
    # TODO(hardware): confirm against a real CU; mapping is a best-effort
    # interpretation of the upstream demo and the protocol notes.
    _START_TO_STATE: ClassVar[dict[int, str]] = {
        0: "idle",
        1: "countdown",
        2: "countdown",
        3: "countdown",
        4: "countdown",
        5: "countdown",
        6: "running",
        7: "paused",
    }

    def __init__(
        self,
        *,
        scan_timeout_seconds: int = 10,
        debug_raw: bool = False,
    ) -> None:
        self._scan_timeout = scan_timeout_seconds
        self._debug_raw = debug_raw
        self._connected = False
        self._cu: Any = None
        self._devices: list[DiscoveredDevice] = []
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=4096)
        self._read_task: asyncio.Task[None] | None = None
        # Per-car translation state.
        self._prev_status: Any = None
        self._lap_counts: dict[int, int] = {}
        self._prev_lap_ts: dict[int, int] = {}

    async def connect(self, mac_address: str | None) -> None:
        try:
            from carreralib import ControlUnit
            from carreralib import connection as cl_conn
        except ImportError as exc:
            raise AdapterConnectionError(
                "carreralib is not installed; install it with "
                "`pip install carreralib` (or `pip install -e .[live]`), "
                "or run with --mock"
            ) from exc

        # Best-effort discovery so `discovered_devices()` is populated and
        # we can pick a default Control Unit when no MAC was given.
        try:
            scanned = await asyncio.to_thread(lambda: list(cl_conn.scan()))
        except Exception as exc:  # pragma: no cover - hardware path
            raise AdapterConnectionError(f"BLE/serial scan failed: {exc}") from exc
        self._devices = [
            DiscoveredDevice(name=str(name or "?"), address=str(addr))
            for addr, name in scanned
        ]
        logger.info("live: scan found %d device(s): %s", len(self._devices), self._devices)

        target = mac_address or self._pick_device()
        if target is None:
            raise AdapterConnectionError(
                "no Carrera Control Unit found via BLE/serial scan; "
                "power the AppConnect on (it must not be paired with the "
                "iOS/Android app at the same time), or pass --mac <address> "
                "explicitly"
            )

        logger.info("live: opening Control Unit at %s", target)
        try:
            self._cu = await asyncio.to_thread(ControlUnit, target)
        except Exception as exc:  # pragma: no cover - hardware path
            raise AdapterConnectionError(
                f"failed to open Control Unit at {target!r}: {exc}"
            ) from exc

        # Reset the CU timer so lap timestamps start at 0 for this session.
        # Non-fatal on failure; we just keep the existing CU clock.
        try:
            await asyncio.to_thread(self._cu.reset)
        except Exception:  # pragma: no cover - hardware path
            logger.exception("live: cu.reset() failed; continuing without reset")

        self._connected = True
        self._read_task = asyncio.create_task(
            self._read_loop(), name="live-cu-reader"
        )

    def _pick_device(self) -> str | None:
        """Pick the most likely Control Unit from the scan results."""
        for d in self._devices:
            if d.name == "Control_Unit":
                return d.address
        return self._devices[0].address if self._devices else None

    async def _read_loop(self) -> None:
        # Re-import inside the loop so the isinstance discriminators are
        # bound to the same classes carreralib actually returns.
        from carreralib import ControlUnit

        cu = self._cu
        prev_data: Any = None
        try:
            while self._connected:
                try:
                    data = await asyncio.to_thread(cu.poll)
                except TimeoutError:
                    # No CU traffic within the poll timeout; keep looping.
                    continue
                except Exception as exc:  # pragma: no cover - hardware path
                    raise AdapterReadError(
                        f"Control Unit poll failed: {exc}"
                    ) from exc

                # De-dupe identical consecutive frames; matches the
                # carreralib reference demo to avoid double-counting laps
                # when the CU re-broadcasts the last frame.
                if data == prev_data:
                    continue
                prev_data = data

                if isinstance(data, ControlUnit.Status):
                    frames = self._translate_status(data)
                elif isinstance(data, ControlUnit.Timer):
                    frames = self._translate_timer(data)
                else:
                    frames = [
                        {"kind": "unknown", "raw": {"repr": repr(data)}}
                    ]

                for frame in frames:
                    for ev in translate_raw_frame(
                        frame, self.source_name, debug_raw=self._debug_raw
                    ):
                        self._enqueue(ev)
        except AdapterReadError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - hardware path
            raise AdapterReadError(
                f"live: read loop crashed: {exc}"
            ) from exc

    def _enqueue(self, ev: TelemetryEvent) -> None:
        try:
            self._queue.put_nowait(ev)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                _ = self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(ev)

    def _translate_status(self, status: Any) -> list[RawFrame]:
        """Diff the latest Status frame against the previous one and emit
        one RawFrame per per-car change plus a race_state frame when the
        ``start`` byte changes.
        """
        out: list[RawFrame] = []
        prev = self._prev_status

        # Fuel: per-car level (0..15).
        for i, fuel in enumerate(status.fuel):
            prev_fuel = prev.fuel[i] if prev is not None else None
            if prev_fuel != fuel:
                out.append(
                    {
                        "kind": "fuel",
                        "car_id": i + 1,
                        "fuel_percent": float(fuel) * 100.0 / 15.0,
                    }
                )

        # Pit: per-car in/out flag.
        for i, pit in enumerate(status.pit):
            prev_pit = prev.pit[i] if prev is not None else None
            if prev_pit != pit:
                out.append(
                    {
                        "kind": "pitlane",
                        "car_id": i + 1,
                        "in_pit": bool(pit),
                        "pit_reason": "unknown",
                    }
                )

        # Race state: start-byte transitions.
        prev_start = prev.start if prev is not None else None
        if prev_start != status.start:
            out.append(
                {
                    "kind": "race_state",
                    "race_state": self._START_TO_STATE.get(
                        int(status.start), "idle"
                    ),
                }
            )

        self._prev_status = status
        return out

    def _translate_timer(self, timer: Any) -> list[RawFrame]:
        """Convert a CU Timer event into a `lap` RawFrame.

        The CU only fires a Timer when a car crosses a sensor; we emit
        one lap event per crossing after the first (the first crossing
        has no lap-time reference). Lap numbering is local to this
        session and is independent of the CU's own lap counter.
        """
        addr = int(timer.address)
        ts = int(timer.timestamp)
        car_id = addr + 1
        prev_ts = self._prev_lap_ts.get(addr)
        self._prev_lap_ts[addr] = ts
        if prev_ts is None:
            return []
        lap_time_ms = ts - prev_ts
        lap_n = self._lap_counts.get(addr, 0) + 1
        self._lap_counts[addr] = lap_n
        return [
            {
                "kind": "lap",
                "car_id": car_id,
                "lap_number": lap_n,
                "lap_time_ms": lap_time_ms,
            }
        ]

    async def disconnect(self) -> None:
        # Idempotent: safe to call when never connected.
        self._connected = False
        if self._read_task is not None:
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._read_task
            self._read_task = None
        if self._cu is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(self._cu.close)
            self._cu = None

    async def events(self) -> AsyncIterator[TelemetryEvent]:
        while self._connected or not self._queue.empty():
            try:
                ev = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except TimeoutError:
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
            except TimeoutError:
                self._task.cancel()
            except Exception:
                logger.exception("runner: task raised on shutdown")
            self._task = None

    async def events(self) -> AsyncIterator[TelemetryEvent]:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                ev = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except TimeoutError:
                continue
            yield ev

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        if self._current is None:
            return []
        devices: list[DiscoveredDevice] = await self._current.discovered_devices()
        return devices

    # ----- Internals ------------------------------------------------------

    async def _emit_connection(self, state: ConnectionState, error: str | None = None) -> None:
        self._state = state
        ev = TelemetryEvent(
            timestamp_iso=utils.now_iso(),
            timestamp_monotonic_ms=self._mono(),
            source=self.source_name,
            event_type=EventType.CONNECTION_STATE,
            payload={"state": state.value, "error": error},
        )
        try:
            self._queue.put_nowait(ev)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                _ = self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(ev)

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
                            with contextlib.suppress(asyncio.QueueEmpty):
                                _ = self._queue.get_nowait()
                            with contextlib.suppress(asyncio.QueueFull):
                                self._queue.put_nowait(ev)
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
                    with contextlib.suppress(Exception):
                        await adapter.disconnect()
                    self._current = None

                if self._stop.is_set():
                    break
                await asyncio.sleep(self._reconnect_s)
        except asyncio.CancelledError:
            raise
        finally:
            await self._emit_connection(ConnectionState.DISCONNECTED)
