"""In-process async event bus.

A tiny pub/sub built on `asyncio.Queue`. Each subscriber owns a bounded
queue; on overflow the OLDEST item is dropped (drop-oldest backpressure,
R-002) and a single warning is logged per subscriber per second so the
log doesn't flood under sustained overload.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_model import TelemetryEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Fan-out async queues for `TelemetryEvent`s."""

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[TelemetryEvent]] = {}
        self._last_overflow_log: dict[str, float] = {}
        self._closed = False

    def subscribe(
        self, name: str, maxsize: int = 1024
    ) -> asyncio.Queue[TelemetryEvent]:
        """Register a subscriber and return its bounded queue.

        Names must be unique; re-subscribing under the same name raises
        `ValueError` to surface accidental double-wiring.
        """
        if self._closed:
            raise RuntimeError("EventBus is closed")
        if name in self._subscribers:
            raise ValueError(f"subscriber {name!r} already registered")
        q: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers[name] = q
        self._last_overflow_log[name] = 0.0
        logger.debug("event_bus: subscribed %s (maxsize=%d)", name, maxsize)
        return q

    async def publish(self, event: TelemetryEvent) -> None:
        """Deliver `event` to every subscriber, dropping oldest on full queues."""
        if self._closed:
            return
        for name, q in self._subscribers.items():
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest item to make room; log at most 1x / sec / sub.
                try:
                    _ = q.get_nowait()
                    q.task_done()
                except asyncio.QueueEmpty:
                    pass
                with contextlib.suppress(asyncio.QueueFull):
                    # Shouldn't happen after a drain, but be defensive.
                    q.put_nowait(event)
                now = time.monotonic()
                if now - self._last_overflow_log[name] >= 1.0:
                    self._last_overflow_log[name] = now
                    logger.warning(
                        "event_bus: bus_overflow",
                        extra={"subscriber": name, "maxsize": q.maxsize},
                    )

    async def close(self) -> None:
        """Mark the bus closed. In-flight queues remain readable until drained."""
        self._closed = True
        logger.debug("event_bus: closed")

    @property
    def subscribers(self) -> list[str]:
        return list(self._subscribers.keys())


__all__ = ["EventBus"]
