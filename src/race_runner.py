"""``RaceTelemetryRunner`` — bridges the async EventBus into ``RaceService``.

Subscribes to the bus once, then on every ``TelemetryEvent`` decides
whether to persist it (lap → ``record_lap``; other types →
``record_event`` when ``persist_all_events=True``). All DB calls cross
into a worker thread via ``asyncio.to_thread`` so the bus is never
blocked.

Also runs a 1 Hz ticker that calls ``finish_race`` when a
``fixed_duration`` race's wall-clock budget is up (R-108).

# TODO(hardware): verify lap event payload mapping against real Carrera
# DIGITAL traffic (FR-135).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from ._time import utcnow_naive
from .event_model import EventType, TelemetryEvent
from .race_context import ActiveRaceContext

if TYPE_CHECKING:
    from .event_bus import EventBus
    from .services.race_service import RaceService

logger = logging.getLogger(__name__)


class RaceTelemetryRunner:
    def __init__(
        self,
        bus: EventBus,
        race_service: RaceService,
        *,
        persist_all_events: bool = True,
        ticker_interval_s: float = 1.0,
        clock: Callable[[], datetime] = utcnow_naive,
    ) -> None:
        self._bus = bus
        self._svc = race_service
        self._persist_all = persist_all_events
        self._ticker_interval = ticker_interval_s
        self._clock = clock
        self._latest_race_state: str | None = None
        self._queue: asyncio.Queue[TelemetryEvent] | None = None
        self._consumer_task: asyncio.Task[None] | None = None
        self._ticker_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._queue = self._bus.subscribe("race_runner", maxsize=2048)
        self._consumer_task = asyncio.create_task(self._consume(), name="race-runner")
        self._ticker_task = asyncio.create_task(
            self._fixed_duration_ticker(), name="race-runner-ticker"
        )
        logger.debug("race_runner: started")

    async def stop(self) -> None:
        self._stop.set()
        for task in (self._consumer_task, self._ticker_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        logger.debug("race_runner: stopped")

    async def _consume(self) -> None:
        assert self._queue is not None
        try:
            while not self._stop.is_set():
                event = await self._queue.get()
                try:
                    await self._dispatch(event)
                except Exception:
                    logger.exception("race_runner: dispatch failed")
        except asyncio.CancelledError:
            raise

    async def _dispatch(self, event: TelemetryEvent) -> None:
        if event.event_type is EventType.RACE_STATE:
            state = event.payload.get("state")
            if isinstance(state, str):
                self._latest_race_state = state
        if ActiveRaceContext.get() is None:
            return
        if event.event_type is EventType.LAP:
            await asyncio.to_thread(self._svc.record_lap, event)
        elif self._persist_all:
            await asyncio.to_thread(self._svc.record_event, event)

    @property
    def latest_race_state(self) -> str | None:
        return self._latest_race_state

    async def _fixed_duration_ticker(self) -> None:
        """Once per second, finish any running fixed_duration race that has elapsed."""
        try:
            while not self._stop.is_set():
                await asyncio.sleep(self._ticker_interval)
                race_id = ActiveRaceContext.get()
                if race_id is None:
                    continue
                try:
                    race = await asyncio.to_thread(self._svc.get_race, race_id)
                except Exception:
                    logger.exception("race_runner: ticker get_race failed")
                    continue
                if (
                    race.status.value != "running"
                    or race.mode.value != "fixed_duration"
                    or race.started_at is None
                    or race.duration_seconds is None
                ):
                    continue
                now = self._clock()
                # `started_at` is naive UTC; align via timestamps if tz-aware.
                started = race.started_at
                if started.tzinfo is not None and now.tzinfo is None:
                    started = started.replace(tzinfo=None)
                elapsed = (now - started).total_seconds()
                if elapsed >= race.duration_seconds:
                    try:
                        await asyncio.to_thread(self._svc.finish_race, race_id)
                        logger.info(
                            "race_runner: fixed_duration race %d auto-finished "
                            "(elapsed=%.1fs target=%ds)",
                            race_id,
                            elapsed,
                            race.duration_seconds,
                        )
                    except Exception:
                        logger.exception(
                            "race_runner: failed to auto-finish race %d", race_id
                        )
        except asyncio.CancelledError:
            raise


__all__ = ["RaceTelemetryRunner"]
