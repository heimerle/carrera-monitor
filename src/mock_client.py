"""`MockCarreraAdapter` - generates a plausible telemetry stream for 1-6 cars.

Implements the `CarreraAdapter` Protocol but yields canonical
`TelemetryEvent`s (translation happens through `carrera_client.translate_raw_frame`).
Seedable via the `MOCK_SEED` environment variable for deterministic tests.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import os
import random
from collections.abc import AsyncIterator

from .carrera_client import DiscoveredDevice, RawFrame, translate_raw_frame
from .event_model import TelemetryEvent

logger = logging.getLogger(__name__)


class MockCarreraAdapter:
    """In-process mock telemetry generator."""

    source_name: str = "mock"

    def __init__(
        self,
        *,
        car_count: int = 6,
        debug_raw: bool = False,
        tick_interval_s: float = 0.05,
        seed: int | None = None,
    ) -> None:
        if not 1 <= car_count <= 6:
            raise ValueError("car_count must be in 1..6")
        self._car_count = car_count
        self._debug_raw = debug_raw
        self._tick_s = tick_interval_s
        env_seed = os.environ.get("MOCK_SEED")
        if seed is None and env_seed is not None:
            try:
                seed = int(env_seed)
            except ValueError:
                logger.warning("mock: ignoring invalid MOCK_SEED=%r", env_seed)
        self._rng = random.Random(seed)
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=4096)
        self._producer_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._connected = False
        self._tick = 0

    # ----- Protocol -------------------------------------------------------

    async def connect(self, mac_address: str | None) -> None:
        if self._connected:
            return
        self._connected = True
        self._stop.clear()
        self._producer_task = asyncio.create_task(self._producer(), name="mock-producer")
        # Emit a startup connection_state.
        await self._emit_raw({"kind": "connection_state", "connection_state": "connected"})
        await self._emit_raw({"kind": "race_state", "race_state": "running"})

    async def disconnect(self) -> None:
        if not self._connected:
            return
        self._connected = False
        self._stop.set()
        if self._producer_task is not None:
            self._producer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._producer_task
            self._producer_task = None

    async def events(self) -> AsyncIterator[TelemetryEvent]:
        while self._connected or not self._queue.empty():
            try:
                ev = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except TimeoutError:
                if not self._connected:
                    break
                continue
            yield ev

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return [DiscoveredDevice(name="MockCarrera", address="00:00:00:00:00:00")]

    # ----- Internals ------------------------------------------------------

    async def _emit_raw(self, frame: RawFrame) -> None:
        for ev in translate_raw_frame(frame, self.source_name, debug_raw=self._debug_raw):
            try:
                self._queue.put_nowait(ev)
            except asyncio.QueueFull:
                # Drop oldest to keep producer non-blocking.
                with contextlib.suppress(asyncio.QueueEmpty):
                    _ = self._queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    self._queue.put_nowait(ev)

    async def _producer(self) -> None:
        """Drive per-car simulation at ~20 Hz."""
        # Per-car state
        lap_count = dict.fromkeys(range(1, self._car_count + 1), 0)
        fuel = dict.fromkeys(range(1, self._car_count + 1), 100.0)
        in_pit = dict.fromkeys(range(1, self._car_count + 1), False)
        last_lap_t = dict.fromkeys(range(1, self._car_count + 1), 0.0)
        # Stagger base lap durations a bit for visual variety.
        base_lap_s = {
            i: 8.0 + 0.4 * (i - 1) + self._rng.uniform(-0.3, 0.3)
            for i in range(1, self._car_count + 1)
        }
        sim_t = 0.0
        try:
            while not self._stop.is_set():
                self._tick += 1
                sim_t += self._tick_s
                for car_id in range(1, self._car_count + 1):
                    # Throttle / brake (sine wave + noise + pit drop).
                    throttle_base = (
                        0.5 + 0.45 * math.sin(sim_t * 0.8 + car_id) + self._rng.uniform(-0.05, 0.05)
                    )
                    brake_base = max(
                        0.0, -0.4 * math.sin(sim_t * 0.8 + car_id) + self._rng.uniform(-0.02, 0.05)
                    )
                    if in_pit[car_id]:
                        throttle_base = max(0.0, throttle_base * 0.1)
                        brake_base = min(1.0, brake_base + 0.4)
                    throttle = max(0.0, min(1.0, throttle_base))
                    brake = max(0.0, min(1.0, brake_base))
                    speed = throttle * 100.0  # km/h (purely cosmetic)

                    await self._emit_raw(
                        {
                            "kind": "controller_input",
                            "car_id": car_id,
                            "throttle": throttle,
                            "brake": brake,
                        }
                    )
                    await self._emit_raw({"kind": "speed", "car_id": car_id, "speed_kmh": speed})
                    await self._emit_raw({"kind": "brake", "car_id": car_id, "brake": brake})

                    # Fuel burn
                    if not in_pit[car_id]:
                        fuel[car_id] = max(0.0, fuel[car_id] - 0.05 * (0.5 + throttle))
                    else:
                        # Pit refuel
                        fuel[car_id] = min(100.0, fuel[car_id] + 1.5)
                    # Emit fuel every ~10 ticks
                    if self._tick % 10 == 0:
                        await self._emit_raw(
                            {
                                "kind": "fuel",
                                "car_id": car_id,
                                "fuel_percent": fuel[car_id],
                            }
                        )

                    # Lap completion
                    lap_duration = base_lap_s[car_id] * (1.5 if in_pit[car_id] else 1.0)
                    if sim_t - last_lap_t[car_id] >= lap_duration:
                        last_lap_t[car_id] = sim_t
                        lap_count[car_id] += 1
                        lap_time_ms = int(lap_duration * 1000 + self._rng.uniform(-200, 200))
                        await self._emit_raw(
                            {
                                "kind": "lap",
                                "car_id": car_id,
                                "lap_number": lap_count[car_id],
                                "lap_time_ms": max(0, lap_time_ms),
                            }
                        )

                    # Pit entry / exit (Bernoulli per R-005, ~1% per tick when low fuel).
                    if not in_pit[car_id]:
                        p_enter = 0.001 if fuel[car_id] > 30 else 0.02
                        if self._rng.random() < p_enter:
                            in_pit[car_id] = True
                            await self._emit_raw(
                                {
                                    "kind": "pitlane",
                                    "car_id": car_id,
                                    "in_pit": True,
                                    "pit_reason": "fuel" if fuel[car_id] < 30 else "manual",
                                }
                            )
                    else:
                        # Exit when refueled enough.
                        if fuel[car_id] > 80 and self._rng.random() < 0.1:
                            in_pit[car_id] = False
                            await self._emit_raw(
                                {
                                    "kind": "pitlane",
                                    "car_id": car_id,
                                    "in_pit": False,
                                    "pit_reason": "manual",
                                }
                            )

                await asyncio.sleep(self._tick_s)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mock producer crashed")
            raise


__all__ = ["MockCarreraAdapter"]
