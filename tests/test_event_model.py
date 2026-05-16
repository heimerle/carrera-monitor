"""Tests for `src.event_model` (T012)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.event_model import EventType, RaceState, TelemetryEvent


def _base(**overrides):
    base = {
        "timestamp_iso": datetime.now(tz=UTC),
        "timestamp_monotonic_ms": 10,
        "source": "mock",
        "event_type": EventType.LAP,
        "car_id": 1,
        "payload": {"lap_number": 1, "lap_time_ms": 7500},
    }
    base.update(overrides)
    return base


class TestRoundTrip:
    def test_lap_event_roundtrips(self):
        e = TelemetryEvent(**_base())
        clone = TelemetryEvent.model_validate_json(e.model_dump_json())
        assert clone == e

    def test_event_with_metadata_roundtrips(self):
        e = TelemetryEvent(**_base(metadata={"adapter_version": "1.2.3"}))
        clone = TelemetryEvent.model_validate_json(e.model_dump_json())
        assert clone.metadata == {"adapter_version": "1.2.3"}


class TestTimezone:
    def test_naive_datetime_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(**_base(timestamp_iso=datetime(2026, 1, 1, 12, 0, 0)))


class TestPayloadShapes:
    @pytest.mark.parametrize(
        "event_type,payload",
        [
            (EventType.LAP, {"lap_number": 1, "lap_time_ms": 8000}),
            (EventType.LAP, {"lap_number": 1, "lap_time_ms": 8000, "cu_timestamp_ms": 12345}),
            (EventType.LAP, {"lap": 1, "time_ms": 8000}),
            (EventType.RACE_STATE, {"state": "running"}),
            (EventType.FUEL, {"level_percent": 75.5}),
            (EventType.CONTROLLER_INPUT, {"throttle": 0.4, "brake": 0.0}),
            (EventType.SPEED, {"speed_kmh": 33.2}),
            (EventType.BRAKE, {"brake": 0.9}),
            (EventType.PITLANE, {"in_pit": True, "reason": "fuel"}),
            (
                EventType.CONNECTION_STATE,
                {
                    "state": "degraded",
                    "error": None,
                    "reason": "timeout_streak_warning",
                    "timeout_streak": 5,
                },
            ),
            (
                EventType.CONNECTION_STATE,
                {
                    "event": "bluetooth_ready",
                    "state": "ready",
                    "desired_connected": True,
                    "device_id": "AA:BB:CC:DD:EE:FF",
                    "device_name": "Control_Unit",
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "rssi": -55,
                    "connected_at": "2026-01-01T12:00:00+00:00",
                    "disconnected_at": None,
                    "last_seen_at": "2026-01-01T12:00:01+00:00",
                    "last_rx_monotonic_ms": 123,
                    "reconnect_attempts": 0,
                    "reason": "subscriptions_ready",
                    "error": None,
                },
            ),
            (EventType.NOT_SUPPORTED, {"reason": "unknown frame"}),
        ],
    )
    def test_valid_payload_accepted(self, event_type, payload):
        e = TelemetryEvent(**_base(event_type=event_type, payload=payload))
        assert e.event_type is event_type

    @pytest.mark.parametrize(
        "event_type,payload",
        [
            (EventType.LAP, {"lap_number": 1, "lap_time_ms": 8000, "extra": "x"}),
            (EventType.FUEL, {"level_percent": 50, "typo_key": 1}),
            (EventType.CONTROLLER_INPUT, {"throttle": 0.5, "brake": 0.1, "boost": 1}),
        ],
    )
    def test_unknown_payload_keys_rejected(self, event_type, payload):
        with pytest.raises(ValidationError):
            TelemetryEvent(**_base(event_type=event_type, payload=payload))

    def test_fuel_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(**_base(event_type=EventType.FUEL, payload={"level_percent": 150}))

    def test_throttle_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(
                **_base(
                    event_type=EventType.CONTROLLER_INPUT,
                    payload={"throttle": 1.5, "brake": 0.0},
                )
            )

    def test_invalid_pitlane_reason_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(
                **_base(
                    event_type=EventType.PITLANE,
                    payload={"in_pit": True, "reason": "bogus"},
                )
            )

    def test_invalid_race_state_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(
                **_base(
                    event_type=EventType.RACE_STATE,
                    payload={"state": "warp_speed"},
                )
            )

    def test_connection_state_invalid_desired_connected_type_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(
                **_base(
                    event_type=EventType.CONNECTION_STATE,
                    payload={
                        "state": "ready",
                        "desired_connected": "yes",
                    },
                )
            )

    def test_lap_alias_payload_normalizes_to_canonical_keys(self):
        ev = TelemetryEvent(
            **_base(
                event_type=EventType.LAP,
                payload={"lap": 3, "time_ms": 7123},
            )
        )
        assert ev.payload["lap_number"] == 3
        assert ev.payload["lap_time_ms"] == 7123
        assert "lap" not in ev.payload
        assert "time_ms" not in ev.payload


class TestCarIdRange:
    @pytest.mark.parametrize("car_id", [0, 9, -1, 100])
    def test_invalid_car_id_rejected(self, car_id):
        with pytest.raises(ValidationError):
            TelemetryEvent(**_base(car_id=car_id))

    @pytest.mark.parametrize("car_id", [1, 2, 3, 4, 5, 6, 7, 8, None])
    def test_valid_car_id_accepted(self, car_id):
        e = TelemetryEvent(
            **_base(car_id=car_id, event_type=EventType.RACE_STATE, payload={"state": "running"})
        )
        assert e.car_id == car_id


class TestTopLevelExtra:
    def test_unknown_top_level_rejected(self):
        with pytest.raises(ValidationError):
            TelemetryEvent(**_base(unknown_extra_field="boom"))


class TestRawEvent:
    def test_raw_passthrough_allows_empty_payload(self):
        e = TelemetryEvent(
            **_base(
                event_type=EventType.RAW,
                payload={},
                raw_data={"kind": "weird", "bytes": "01020304"},
            )
        )
        assert e.event_type is EventType.RAW
        assert e.raw_data == {"kind": "weird", "bytes": "01020304"}


class TestEnumValues:
    def test_race_state_values(self):
        assert {s.value for s in RaceState} == {
            "idle",
            "countdown",
            "running",
            "paused",
            "finished",
        }
