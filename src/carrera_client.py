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
    "DiscoveredDevice",
    "RawFrame",
    "translate_raw_frame",
]
