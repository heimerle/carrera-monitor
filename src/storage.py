"""JSONL event log + optional CSV lap companion (T017).

A dedicated async task consumes from a bus subscriber queue and batches
writes to disk with at most ~250 ms latency. I/O failures are logged and
swallowed so a transient FS error never crashes the pipeline (FR-018).
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, TextIO

from .event_model import EventType, TelemetryEvent

logger = logging.getLogger(__name__)

_FLUSH_INTERVAL_S = 0.25  # ≤ 250 ms latency (R-006)


def _timestamp_tag(now: datetime) -> str:
    return now.strftime("%Y%m%d-%H%M%S")


def make_log_paths(directory: Path, now: datetime) -> tuple[Path, Path]:
    """Compute the JSONL + CSV file paths for this process."""
    tag = _timestamp_tag(now)
    pid = os.getpid()
    return (
        directory / f"carrera-{tag}-{pid}.jsonl",
        directory / f"laps-{tag}-{pid}.csv",
    )


class JsonlEventWriter:
    """Drains a subscriber queue and appends JSONL lines to disk."""

    def __init__(
        self,
        queue: asyncio.Queue[TelemetryEvent],
        log_dir: Path,
        *,
        jsonl_enabled: bool = True,
        csv_laps_enabled: bool = True,
        now: datetime | None = None,
    ) -> None:
        self._queue = queue
        self._dir = Path(log_dir)
        self._jsonl_enabled = jsonl_enabled
        self._csv_enabled = csv_laps_enabled
        from . import utils  # local to avoid cycles
        t = now or utils.now_iso()
        self._jsonl_path, self._csv_path = make_log_paths(self._dir, t)
        self._jsonl_file: TextIO | None = None
        self._csv_file: TextIO | None = None
        self._csv_writer: Any = None
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def jsonl_path(self) -> Path:
        return self._jsonl_path

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    async def start(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        if self._jsonl_enabled:
            try:
                self._jsonl_file = open(self._jsonl_path, "a", encoding="utf-8", buffering=1)
            except OSError as exc:
                logger.error("storage: cannot open JSONL %s: %s", self._jsonl_path, exc)
                self._jsonl_enabled = False
        if self._csv_enabled:
            try:
                new_file = not self._csv_path.exists()
                self._csv_file = open(self._csv_path, "a", encoding="utf-8", newline="")
                self._csv_writer = csv.writer(self._csv_file)
                if new_file:
                    self._csv_writer.writerow(["car_id", "lap_number", "lap_time_ms", "timestamp_iso"])
                    self._csv_file.flush()
            except OSError as exc:
                logger.error("storage: cannot open CSV %s: %s", self._csv_path, exc)
                self._csv_enabled = False
        self._task = asyncio.create_task(self._run(), name="storage-writer")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                self._task.cancel()
            except Exception:
                logger.exception("storage: writer task raised on shutdown")
            self._task = None
        # Final drain in case anything slipped in.
        await self._drain_remaining()
        for fh in (self._jsonl_file, self._csv_file):
            if fh is not None:
                try:
                    fh.flush()
                    fh.close()
                except OSError:
                    logger.exception("storage: error closing file")
        self._jsonl_file = None
        self._csv_file = None

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                batch = await self._collect_batch()
                if batch:
                    self._write_batch(batch)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("storage: writer task crashed")

    async def _collect_batch(self) -> list[TelemetryEvent]:
        try:
            first = await asyncio.wait_for(self._queue.get(), timeout=_FLUSH_INTERVAL_S)
        except TimeoutError:
            return []
        batch = [first]
        # Drain anything else already queued without waiting.
        while not self._queue.empty() and len(batch) < 512:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch

    async def _drain_remaining(self) -> None:
        batch: list[TelemetryEvent] = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            self._write_batch(batch)

    def _write_batch(self, batch: list[TelemetryEvent]) -> None:
        if self._jsonl_enabled and self._jsonl_file is not None:
            try:
                buf = StringIO()
                for ev in batch:
                    buf.write(ev.model_dump_json())
                    buf.write("\n")
                self._jsonl_file.write(buf.getvalue())
                self._jsonl_file.flush()
            except OSError:
                logger.exception("storage: JSONL write failed; continuing")
        if self._csv_enabled and self._csv_writer is not None:
            try:
                wrote = False
                for ev in batch:
                    if ev.event_type is EventType.LAP and ev.car_id is not None:
                        self._csv_writer.writerow([
                            ev.car_id,
                            ev.payload["lap_number"],
                            ev.payload["lap_time_ms"],
                            ev.timestamp_iso.isoformat(),
                        ])
                        wrote = True
                if wrote and self._csv_file is not None:
                    self._csv_file.flush()
            except OSError:
                logger.exception("storage: CSV write failed; continuing")


__all__ = ["JsonlEventWriter", "make_log_paths"]
