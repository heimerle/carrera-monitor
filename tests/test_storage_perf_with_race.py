"""SC-106: existing JSONL writer p95 ≤50 ms when a race is active (T043a)."""

from __future__ import annotations

import asyncio
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.event_bus import EventBus
from src.event_model import EventType, TelemetryEvent
from src.race_runner import RaceTelemetryRunner
from src.schemas.race_schema import DriverAssignment, RaceCreate, RaceMode
from src.services.race_service import RaceService
from src.storage import JsonlEventWriter


def _lap(n: int) -> TelemetryEvent:
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=n * 1000,
        source="mock",
        event_type=EventType.LAP,
        car_id=1,
        payload={"lap_number": n, "lap_time_ms": 8000},
    )


@pytest.mark.asyncio
async def test_storage_p95_under_50ms_with_race_active(engine):
    svc = RaceService()
    r = svc.create_race(
        RaceCreate(
            name="P",
            mode=RaceMode.FIXED_LAPS,
            lap_target=10_000,
            driver_count=1,
            drivers=[DriverAssignment(car_id=1, driver_name="A")],
        )
    )
    svc.start_race(r.id)
    bus = EventBus()
    storage_q = bus.subscribe("storage", maxsize=8192)
    with tempfile.TemporaryDirectory() as td:
        writer = JsonlEventWriter(
            storage_q,
            log_dir=Path(td),
            jsonl_enabled=True,
            csv_laps_enabled=False,
        )
        runner = RaceTelemetryRunner(bus, svc, persist_all_events=False)
        await writer.start()
        await runner.start()

        latencies: list[float] = []
        try:
            for n in range(1, 201):
                t0 = time.perf_counter()
                await bus.publish(_lap(n))
                latencies.append((time.perf_counter() - t0) * 1000)
            await asyncio.sleep(0.2)
        finally:
            await runner.stop()
            await writer.stop()
            await bus.close()

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]
    assert p95 < 50, f"publish p95={p95:.2f} ms (>50 ms)"
