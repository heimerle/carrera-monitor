"""Tests for `JsonlEventWriter` + CSV companion (T014, T031)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.event_model import EventType, TelemetryEvent
from src.storage import JsonlEventWriter


def _ev(et: EventType, **payload_overrides):
    payload_map = {
        EventType.LAP: {"lap_number": 1, "lap_time_ms": 8000},
        EventType.FUEL: {"level_percent": 50.0},
        EventType.RACE_STATE: {"state": "running"},
    }
    payload = dict(payload_map[et])
    payload.update(payload_overrides)
    return TelemetryEvent(
        timestamp_iso=datetime.now(tz=UTC),
        timestamp_monotonic_ms=1,
        source="mock",
        event_type=et,
        car_id=1 if et is not EventType.RACE_STATE else None,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_jsonl_roundtrip_1000_events(tmp_path: Path):
    q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
    writer = JsonlEventWriter(q, log_dir=tmp_path, jsonl_enabled=True, csv_laps_enabled=False)
    await writer.start()
    for i in range(1000):
        q.put_nowait(_ev(EventType.LAP, lap_number=i + 1, lap_time_ms=7000 + i))
    # Allow writer time to drain.
    for _ in range(40):
        if q.empty():
            break
        await asyncio.sleep(0.05)
    await writer.stop()

    with open(writer.jsonl_path, encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1000
    for line in lines:
        TelemetryEvent.model_validate_json(line.strip())


@pytest.mark.asyncio
async def test_csv_header_and_row_order(tmp_path: Path):
    q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
    writer = JsonlEventWriter(q, log_dir=tmp_path, jsonl_enabled=False, csv_laps_enabled=True)
    await writer.start()
    for i in range(5):
        q.put_nowait(_ev(EventType.LAP, lap_number=i + 1, lap_time_ms=7000 + i))
    # Mix in a non-lap event to ensure it's excluded from CSV.
    q.put_nowait(_ev(EventType.FUEL, level_percent=10))
    for _ in range(40):
        if q.empty():
            break
        await asyncio.sleep(0.05)
    await writer.stop()

    with open(writer.csv_path, encoding="utf-8") as f:
        rows = f.read().splitlines()
    assert rows[0] == "car_id,lap_number,lap_time_ms,timestamp_iso"
    assert len(rows) == 6  # header + 5 lap rows
    nums = [int(r.split(",")[1]) for r in rows[1:]]
    assert nums == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_writer_swallows_oserror_on_write(tmp_path: Path, monkeypatch):
    """Simulated I/O failure during write must not bubble out of the writer task."""
    q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
    writer = JsonlEventWriter(q, log_dir=tmp_path, jsonl_enabled=True, csv_laps_enabled=False)
    await writer.start()

    # Replace the underlying file with one whose write() raises.
    class _Broken:
        def write(self, *_a, **_kw):
            raise OSError("disk full")

        def flush(self):
            pass

        def close(self):
            pass

    writer._jsonl_file = _Broken()  # type: ignore[assignment]

    q.put_nowait(_ev(EventType.LAP, lap_number=1, lap_time_ms=7000))
    await asyncio.sleep(0.4)  # give writer a chance to attempt write
    # Should not have raised. Stop cleanly.
    await writer.stop()


@pytest.mark.asyncio
async def test_500_event_session_roundtrip(tmp_path: Path):
    """T031 — 500 events written and parsed back at 100% rate, monotonic order."""
    q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
    writer = JsonlEventWriter(q, log_dir=tmp_path, jsonl_enabled=True, csv_laps_enabled=True)
    await writer.start()
    lap_count = 0
    for i in range(500):
        if i % 5 == 0:
            lap_count += 1
            q.put_nowait(_ev(EventType.LAP, lap_number=lap_count, lap_time_ms=8000 + i))
        else:
            q.put_nowait(_ev(EventType.FUEL, level_percent=100 - i * 0.1))
    for _ in range(60):
        if q.empty():
            break
        await asyncio.sleep(0.05)
    await writer.stop()

    parsed: list[TelemetryEvent] = []
    with open(writer.jsonl_path, encoding="utf-8") as f:
        for line in f:
            parsed.append(TelemetryEvent.model_validate_json(line.strip()))
    assert len(parsed) == 500
    mono = [ev.timestamp_monotonic_ms for ev in parsed]
    assert mono == sorted(mono)

    # CSV row count == lap event count.
    with open(writer.csv_path, encoding="utf-8") as f:
        csv_rows = f.read().splitlines()[1:]  # skip header
    assert len(csv_rows) == lap_count
