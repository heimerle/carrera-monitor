"""Pydantic schemas for Bluetooth connection management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..state.bluetooth_state import BluetoothState


class BluetoothDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    device_name: str | None = None
    mac_address: str | None = None
    rssi: int | None = None


class BluetoothConnectionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: BluetoothState = BluetoothState.DISCONNECTED
    desired_connected: bool = False
    device_id: str | None = None
    device_name: str | None = None
    mac_address: str | None = None
    rssi: int | None = None
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_rx_monotonic_ms: int | None = Field(default=None, ge=0)
    reconnect_attempts: int = Field(default=0, ge=0)
    last_error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @field_validator("connected_at", "disconnected_at", "last_seen_at", "updated_at")
    @classmethod
    def _validate_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime fields must be timezone-aware")
        return value

    def with_updates(self, **kwargs: Any) -> BluetoothConnectionStatus:
        data = self.model_dump()
        data.update(kwargs)
        data["updated_at"] = datetime.now(tz=UTC)
        return BluetoothConnectionStatus.model_validate(data)

    def to_connection_payload(
        self,
        *,
        event: str,
        reason: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "event": event,
            "state": self.state.value,
            "desired_connected": self.desired_connected,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "mac_address": self.mac_address,
            "rssi": self.rssi,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": (
                self.disconnected_at.isoformat() if self.disconnected_at else None
            ),
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "last_rx_monotonic_ms": self.last_rx_monotonic_ms,
            "reconnect_attempts": self.reconnect_attempts,
            "reason": reason,
            "error": error if error is not None else self.last_error,
        }


__all__ = ["BluetoothConnectionStatus", "BluetoothDevice", "BluetoothState"]
