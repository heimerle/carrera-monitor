"""Unit tests for the carreralib Status / Timer → RawFrame translators.

We feed plain namedtuple-shaped fakes (no `carreralib` import required at
test time) into the private translators on `LiveCarreraAdapter` and
assert the resulting `RawFrame` dicts. The actual BLE / `cu.poll()` path
is intentionally NOT exercised here — it needs real hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.carrera_client import LiveCarreraAdapter


@dataclass
class _FakeStatus:
    fuel: list[int]
    pit: list[bool]
    start: int
    mode: int = 0
    display: int = 0


@dataclass
class _FakeTimer:
    address: int
    timestamp: int
    sector: int = 1


# --------------------------------------------------------- Timer → lap


def test_timer_first_crossing_emits_no_lap() -> None:
    adapter = LiveCarreraAdapter()
    frames = adapter._translate_timer(_FakeTimer(address=0, timestamp=1_000))
    assert frames == []


def test_timer_second_crossing_emits_lap_with_diff_time() -> None:
    adapter = LiveCarreraAdapter()
    adapter._translate_timer(_FakeTimer(address=0, timestamp=1_000))
    frames = adapter._translate_timer(_FakeTimer(address=0, timestamp=8_500))

    assert frames == [
        {
            "kind": "lap",
            "car_id": 1,
            "lap_number": 1,
            "lap_time_ms": 7_500,
            "cu_timestamp_ms": 8_500,
        }
    ]


def test_timer_lap_counts_are_per_car() -> None:
    adapter = LiveCarreraAdapter()
    # Car 0 (=> car_id=1) crosses twice; car 3 (=> car_id=4) crosses twice.
    adapter._translate_timer(_FakeTimer(address=0, timestamp=1_000))
    adapter._translate_timer(_FakeTimer(address=3, timestamp=1_200))
    out0 = adapter._translate_timer(_FakeTimer(address=0, timestamp=9_000))
    out3 = adapter._translate_timer(_FakeTimer(address=3, timestamp=11_400))

    assert out0 == [
        {
            "kind": "lap",
            "car_id": 1,
            "lap_number": 1,
            "lap_time_ms": 8_000,
            "cu_timestamp_ms": 9_000,
        }
    ]
    assert out3 == [
        {
            "kind": "lap",
            "car_id": 4,
            "lap_number": 1,
            "lap_time_ms": 10_200,
            "cu_timestamp_ms": 11_400,
        }
    ]


def test_timer_lap_number_increments() -> None:
    adapter = LiveCarreraAdapter()
    adapter._translate_timer(_FakeTimer(address=2, timestamp=0))
    adapter._translate_timer(_FakeTimer(address=2, timestamp=7_000))
    out = adapter._translate_timer(_FakeTimer(address=2, timestamp=14_500))
    assert out == [
        {
            "kind": "lap",
            "car_id": 3,
            "lap_number": 2,
            "lap_time_ms": 7_500,
            "cu_timestamp_ms": 14_500,
        }
    ]


def test_timer_slot_normalization_drops_non_canonical_slots() -> None:
    adapter = LiveCarreraAdapter()
    adapter._translate_timer(_FakeTimer(address=6, timestamp=1_000))
    out = adapter._translate_timer(_FakeTimer(address=6, timestamp=9_000))
    assert out == []


# --------------------------------------------------------- Status → diffs


def test_status_first_frame_emits_full_state() -> None:
    adapter = LiveCarreraAdapter()
    status = _FakeStatus(
        fuel=[15, 14, 0, 0, 0, 0, 0, 0],
        pit=[False, False, False, False, False, False, False, False],
        start=6,
    )
    frames = adapter._translate_status(status)
    kinds = [f["kind"] for f in frames]
    # Canonical race domain is max 6 cars: slots 7/8 are dropped.
    assert kinds.count("fuel") == 6
    assert kinds.count("pitlane") == 6
    assert kinds.count("race_state") == 1
    race_frame = next(f for f in frames if f["kind"] == "race_state")
    assert race_frame["race_state"] == "running"


def test_status_slot_normalization_keeps_car_ids_within_1_to_6() -> None:
    adapter = LiveCarreraAdapter()
    frames = adapter._translate_status(
        _FakeStatus(
            fuel=[15, 14, 13, 12, 11, 10, 9, 8],
            pit=[False, False, False, False, False, False, True, True],
            start=6,
        )
    )
    car_ids = sorted(
        {
            int(f["car_id"])
            for f in frames
            if f["kind"] in {"fuel", "pitlane"}
        }
    )
    assert car_ids == [1, 2, 3, 4, 5, 6]


def test_status_second_frame_diffs_only_changed_fields() -> None:
    adapter = LiveCarreraAdapter()
    adapter._translate_status(
        _FakeStatus(fuel=[15] * 8, pit=[False] * 8, start=6)
    )
    frames = adapter._translate_status(
        _FakeStatus(fuel=[15, 14, 15, 15, 15, 15, 15, 15], pit=[False] * 8, start=6)
    )

    # Only car 2 (index 1, car_id=2) changed.
    fuel_frames = [f for f in frames if f["kind"] == "fuel"]
    assert len(fuel_frames) == 1
    f = fuel_frames[0]
    assert f["car_id"] == 2
    assert abs(f["fuel_percent"] - (14 / 15 * 100)) < 1e-6
    # No race_state, no pit change.
    assert all(f["kind"] != "race_state" for f in frames)
    assert all(f["kind"] != "pitlane" for f in frames)


def test_status_start_byte_maps_to_race_state() -> None:
    adapter = LiveCarreraAdapter()
    # Prime with start=6 (running).
    adapter._translate_status(
        _FakeStatus(fuel=[0] * 8, pit=[False] * 8, start=6)
    )
    # Transition to start=7 (paused).
    frames = adapter._translate_status(
        _FakeStatus(fuel=[0] * 8, pit=[False] * 8, start=7)
    )
    race_frames = [f for f in frames if f["kind"] == "race_state"]
    assert race_frames == [{"kind": "race_state", "race_state": "paused"}]


def test_status_pit_transition_emits_pitlane_frame() -> None:
    adapter = LiveCarreraAdapter()
    adapter._translate_status(
        _FakeStatus(fuel=[0] * 8, pit=[False] * 8, start=6)
    )
    pit = [False] * 8
    pit[2] = True  # car_id=3 enters the pit
    frames = adapter._translate_status(
        _FakeStatus(fuel=[0] * 8, pit=pit, start=6)
    )
    pit_frames = [f for f in frames if f["kind"] == "pitlane"]
    assert pit_frames == [
        {"kind": "pitlane", "car_id": 3, "in_pit": True, "pit_reason": "unknown"}
    ]


# --------------------------------------------------------- pick_device heuristic


def test_pick_device_prefers_control_unit_name() -> None:
    from src.carrera_client import DiscoveredDevice

    adapter = LiveCarreraAdapter()
    adapter._devices = [
        DiscoveredDevice(name="Random", address="AA:BB:CC:DD:EE:FF"),
        DiscoveredDevice(name="Control_Unit", address="11:22:33:44:55:66"),
        DiscoveredDevice(name="Other", address="77:88:99:AA:BB:CC"),
    ]
    assert adapter._pick_device() == "11:22:33:44:55:66"


def test_pick_device_falls_back_to_first_when_no_control_unit() -> None:
    from src.carrera_client import DiscoveredDevice

    adapter = LiveCarreraAdapter()
    adapter._devices = [
        DiscoveredDevice(name="Random", address="AA:BB:CC:DD:EE:FF"),
    ]
    assert adapter._pick_device() == "AA:BB:CC:DD:EE:FF"


def test_pick_device_returns_none_when_no_devices() -> None:
    adapter = LiveCarreraAdapter()
    adapter._devices = []
    assert adapter._pick_device() is None
