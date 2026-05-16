"""Canonical telemetry event model + enums.

Single source of truth for what flows on the event bus and what gets
serialized to JSONL. Mirrors `specs/main/data-model.md` sections 1-5.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(StrEnum):
    LAP = "lap"
    RACE_STATE = "race_state"
    FUEL = "fuel"
    CONTROLLER_INPUT = "controller_input"
    SPEED = "speed"
    BRAKE = "brake"
    PITLANE = "pitlane"
    CONNECTION_STATE = "connection_state"
    RAW = "raw"
    NOT_SUPPORTED = "not_supported"


class RaceState(StrEnum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class ConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    MANUALLY_DISCONNECTED = "manually_disconnected"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBING = "subscribing"
    READY = "ready"
    STALE = "stale"
    DEGRADED = "degraded"
    STALLED = "stalled"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# Allowed payload keys per EventType. Unknown keys are rejected to catch typos
# early (data-model §1 validation rules).
_ALLOWED_PAYLOAD_KEYS: dict[EventType, set[str]] = {
    EventType.LAP: {"lap_number", "lap_time_ms", "cu_timestamp_ms"},
    EventType.RACE_STATE: {"state"},
    EventType.FUEL: {"level_percent"},
    EventType.CONTROLLER_INPUT: {"throttle", "brake"},
    EventType.SPEED: {"speed_kmh"},
    EventType.BRAKE: {"brake"},
    EventType.PITLANE: {"in_pit", "reason"},
    EventType.CONNECTION_STATE: {
        "state",
        "error",
        "reason",
        "timeout_streak",
        "event",
        "desired_connected",
        "device_id",
        "device_name",
        "mac_address",
        "rssi",
        "connected_at",
        "disconnected_at",
        "last_seen_at",
        "last_rx_monotonic_ms",
        "reconnect_attempts",
    },
    EventType.RAW: set(),  # passthrough, raw_data carries the frame
    EventType.NOT_SUPPORTED: {"reason"},
}

_PITLANE_REASONS = {"manual", "fuel", "unknown"}


class ConnectionStateRecord(BaseModel):
    """Runtime sidecar for the current connection state."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    state: ConnectionState = ConnectionState.DISCONNECTED
    since_ms: int = Field(default=0, ge=0)
    last_error: str | None = None
    reason: str | None = None
    timeout_streak: int | None = Field(default=None, ge=0)
    event: str | None = None
    desired_connected: bool = False
    device_id: str | None = None
    device_name: str | None = None
    mac_address: str | None = None
    rssi: int | None = None
    connected_at: str | None = None
    disconnected_at: str | None = None
    last_seen_at: str | None = None
    last_rx_monotonic_ms: int | None = Field(default=None, ge=0)
    reconnect_attempts: int = Field(default=0, ge=0)


class TelemetryEvent(BaseModel):
    """Canonical immutable telemetry event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_iso: datetime
    timestamp_monotonic_ms: int = Field(ge=0)
    source: Literal["carrera_appconnect", "mock", "system"]
    event_type: EventType
    # Carrera DIGITAL can report up to 8 car slots.
    car_id: int | None = Field(default=None, ge=1, le=8)
    controller_id: int | None = Field(default=None, ge=1, le=8)
    payload: dict[str, Any] = Field(default_factory=dict)
    raw_data: dict[str, Any] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("timestamp_iso")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp_iso must be timezone-aware")
        return v

    @model_validator(mode="after")
    def _payload_shape(self) -> TelemetryEvent:
        allowed = _ALLOWED_PAYLOAD_KEYS[self.event_type]
        if self.event_type is EventType.RAW:
            # Passthrough: payload may be empty; raw_data carries the frame.
            return self
        keys = set(self.payload.keys())
        unknown = keys - allowed
        if unknown:
            raise ValueError(f"unknown payload keys for {self.event_type.value}: {sorted(unknown)}")

        # Per-type required-field + value checks.
        p = self.payload
        if self.event_type is EventType.LAP:
            _require(p, "lap_number", int)
            _require(p, "lap_time_ms", int)
            if p["lap_number"] < 1:
                raise ValueError("lap_number must be ≥ 1")
            if p["lap_time_ms"] < 0:
                raise ValueError("lap_time_ms must be ≥ 0")
            if "cu_timestamp_ms" in p:
                if not isinstance(p["cu_timestamp_ms"], int):
                    raise ValueError("cu_timestamp_ms must be an int")
                if p["cu_timestamp_ms"] < 0:
                    raise ValueError("cu_timestamp_ms must be ≥ 0")
        elif self.event_type is EventType.RACE_STATE:
            _require(p, "state", str)
            # Validate it's a known RaceState value (coerce via enum lookup).
            RaceState(p["state"])
        elif self.event_type is EventType.FUEL:
            _require(p, "level_percent", (int, float))
            lvl = float(p["level_percent"])
            if not 0.0 <= lvl <= 100.0:
                raise ValueError("fuel level_percent must be in [0, 100]")
        elif self.event_type is EventType.CONTROLLER_INPUT:
            _require(p, "throttle", (int, float))
            _require(p, "brake", (int, float))
            if not 0.0 <= float(p["throttle"]) <= 1.0:
                raise ValueError("throttle must be in [0, 1]")
            if not 0.0 <= float(p["brake"]) <= 1.0:
                raise ValueError("brake must be in [0, 1]")
        elif self.event_type is EventType.SPEED:
            _require(p, "speed_kmh", (int, float))
            if float(p["speed_kmh"]) < 0:
                raise ValueError("speed_kmh must be ≥ 0")
        elif self.event_type is EventType.BRAKE:
            _require(p, "brake", (int, float))
            if not 0.0 <= float(p["brake"]) <= 1.0:
                raise ValueError("brake must be in [0, 1]")
        elif self.event_type is EventType.PITLANE:
            _require(p, "in_pit", bool)
            _require(p, "reason", str)
            if p["reason"] not in _PITLANE_REASONS:
                raise ValueError(f"pitlane reason must be one of {sorted(_PITLANE_REASONS)}")
        elif self.event_type is EventType.CONNECTION_STATE:
            _require(p, "state", str)
            ConnectionState(p["state"])
            if "error" in p and p["error"] is not None and not isinstance(p["error"], str):
                raise ValueError("connection_state.error must be str or null")
            if "reason" in p and p["reason"] is not None and not isinstance(p["reason"], str):
                raise ValueError("connection_state.reason must be str or null")
            if "timeout_streak" in p and (
                not isinstance(p["timeout_streak"], int) or p["timeout_streak"] < 0
            ):
                raise ValueError("connection_state.timeout_streak must be int >= 0")
            if "event" in p and p["event"] is not None and not isinstance(p["event"], str):
                raise ValueError("connection_state.event must be str or null")
            if "desired_connected" in p and not isinstance(p["desired_connected"], bool):
                raise ValueError("connection_state.desired_connected must be bool")
            for text_key in (
                "device_id",
                "device_name",
                "mac_address",
                "connected_at",
                "disconnected_at",
                "last_seen_at",
            ):
                if text_key in p and p[text_key] is not None and not isinstance(p[text_key], str):
                    raise ValueError(f"connection_state.{text_key} must be str or null")
            if "rssi" in p and p["rssi"] is not None and not isinstance(p["rssi"], int):
                raise ValueError("connection_state.rssi must be int or null")
            if "last_rx_monotonic_ms" in p and (
                p["last_rx_monotonic_ms"] is not None
                and (
                    not isinstance(p["last_rx_monotonic_ms"], int)
                    or p["last_rx_monotonic_ms"] < 0
                )
            ):
                raise ValueError(
                    "connection_state.last_rx_monotonic_ms must be int >= 0 or null"
                )
            if "reconnect_attempts" in p and (
                not isinstance(p["reconnect_attempts"], int)
                or p["reconnect_attempts"] < 0
            ):
                raise ValueError("connection_state.reconnect_attempts must be int >= 0")
        elif self.event_type is EventType.NOT_SUPPORTED:
            _require(p, "reason", str)
        return self


def _require(payload: dict[str, Any], key: str, types: type | tuple[type, ...]) -> None:
    if key not in payload:
        raise ValueError(f"payload missing required key: {key}")
    if not isinstance(payload[key], types):
        raise ValueError(f"payload[{key!r}] must be of type {types}")


__all__ = [
    "ConnectionState",
    "ConnectionStateRecord",
    "EventType",
    "RaceState",
    "TelemetryEvent",
]
