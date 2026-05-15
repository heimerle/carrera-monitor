"""Tests for `MockCarreraAdapter` (T013, T021)."""

from __future__ import annotations

import asyncio
import os

import pytest

from src.event_model import EventType, TelemetryEvent
from src.mock_client import MockCarreraAdapter

REQUIRED_TYPES = {
    EventType.LAP,
    EventType.FUEL,
    EventType.RACE_STATE,
    EventType.PITLANE,
    EventType.CONNECTION_STATE,
    EventType.CONTROLLER_INPUT,
    EventType.SPEED,
    EventType.BRAKE,
}


@pytest.mark.asyncio
async def test_mock_emits_all_required_types(monkeypatch):
    monkeypatch.setenv("MOCK_SEED", "42")
    adapter = MockCarreraAdapter(car_count=2, tick_interval_s=0.01)
    await adapter.connect(None)
    seen: set[EventType] = set()
    car_ids: set[int] = set()
    last_mono = -1

    async def consume():
        nonlocal last_mono
        async for ev in adapter.events():
            assert isinstance(ev, TelemetryEvent)
            assert ev.timestamp_monotonic_ms >= last_mono
            last_mono = ev.timestamp_monotonic_ms
            seen.add(ev.event_type)
            if ev.car_id is not None:
                car_ids.add(ev.car_id)
            # Force lap events by running long enough; bail when all required types seen
            # OR after ~20 sim seconds.
            if seen >= REQUIRED_TYPES or last_mono > 20_000:
                break

    # Run with reasonable wall-clock budget.
    try:
        await asyncio.wait_for(consume(), timeout=15.0)
    finally:
        await adapter.disconnect()

    missing = REQUIRED_TYPES - seen
    assert not missing, f"missing event types: {missing}"
    assert car_ids.issubset({1, 2})
    assert car_ids  # at least one car emitted


@pytest.mark.asyncio
async def test_mock_respects_car_count():
    adapter = MockCarreraAdapter(car_count=3, tick_interval_s=0.01)
    await adapter.connect(None)
    car_ids: set[int] = set()

    async def consume():
        async for ev in adapter.events():
            if ev.car_id is not None:
                car_ids.add(ev.car_id)
            if len(car_ids) >= 3:
                break

    try:
        await asyncio.wait_for(consume(), timeout=5.0)
    finally:
        await adapter.disconnect()
    assert car_ids == {1, 2, 3}


@pytest.mark.asyncio
async def test_mock_invalid_car_count_rejected():
    with pytest.raises(ValueError):
        MockCarreraAdapter(car_count=0)
    with pytest.raises(ValueError):
        MockCarreraAdapter(car_count=7)
