"""Long-running Bluetooth connection supervisor for live Carrera telemetry.

This supervisor owns BLE lifecycle state and runs outside Streamlit render
cycles. Streamlit requests connect/disconnect/scan/retry indirectly via
runtime-settings IPC; the supervisor translates those requests into adapter
lifecycle operations and publishes normalized lifecycle events.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any

from .. import utils
from ..carrera_client import (
    AdapterConnectionError,
    AdapterReadError,
    DiscoveredDevice,
    LiveCarreraAdapter,
)
from ..config import BluetoothConfig
from ..event_model import EventType, TelemetryEvent
from ..schemas.bluetooth_schema import BluetoothConnectionStatus, BluetoothDevice
from ..state.bluetooth_state import BluetoothState, is_connected_state
from .runtime_settings import RuntimeSettings

logger = logging.getLogger(__name__)


class BluetoothConnectionSupervisor:
    """Supervise a single BLE client and keep desired connection state stable."""

    source_name = "carrera_appconnect"

    def __init__(
        self,
        *,
        config: BluetoothConfig,
        runtime_settings: RuntimeSettings | None = None,
        adapter_factory: Callable[[], LiveCarreraAdapter] | None = None,
        scan_fn: Callable[[], Sequence[tuple[str, str | None]]] | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic_clock: Callable[[], int] = utils.now_monotonic_ms,
        now_fn: Callable[[], datetime] = utils.now_iso,
    ) -> None:
        self._cfg = config
        self._runtime = runtime_settings or RuntimeSettings()
        self._scan_fn = scan_fn
        self._sleep = sleep_fn
        self._mono = monotonic_clock
        self._now = now_fn
        self._adapter_factory = adapter_factory or (
            lambda: LiveCarreraAdapter(
                scan_timeout_seconds=self._cfg.scan_timeout_seconds,
                debug_raw=False,
                idle_timeout_seconds=self._cfg.idle_timeout_seconds,
                idle_warning_seconds=self._cfg.idle_warning_seconds,
            )
        )

        desired = self._runtime.get_bluetooth_desired_connected()
        self._status = BluetoothConnectionStatus(
            state=BluetoothState.DISCONNECTED,
            desired_connected=desired,
            updated_at=self._now(),
        )
        self._desired_connected = desired
        self._selected_device_id = self._runtime.get_bluetooth_selected_device_id()

        self._events: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=4096)
        self._operation_lock = asyncio.Lock()
        self._wake_event = asyncio.Event()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

        self._adapter: LiveCarreraAdapter | None = None
        self._adapter_iter: AsyncIterator[TelemetryEvent] | None = None
        self._known_devices: list[BluetoothDevice] = []
        self._last_command_seq = 0
        self._manual_disconnect = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self, device_id: str | None = None) -> BluetoothConnectionStatus:
        if not self._cfg.allow_manual_connect:
            self._status = self._status.with_updates(
                state=BluetoothState.ERROR,
                last_error="manual connect is disabled by configuration",
            )
            await self._emit_lifecycle_event("bluetooth_error", reason="manual_connect_disabled")
            return self.get_status()
        async with self._operation_lock:
            self._desired_connected = True
            self._manual_disconnect = False
            if device_id is not None:
                self._selected_device_id = str(device_id)
                self._runtime.set_bluetooth_selected_device_id(self._selected_device_id)
            self._runtime.set_bluetooth_desired_connected(True)
            self._status = self._status.with_updates(
                desired_connected=True,
                state=(self._status.state if self._status.state is not BluetoothState.MANUALLY_DISCONNECTED else BluetoothState.DISCONNECTED),
                last_error=None,
            )
            await self._ensure_started_locked()
            self._wake_event.set()
            return self.get_status()

    async def disconnect(self, *, manual: bool = True) -> BluetoothConnectionStatus:
        if manual and not self._cfg.allow_manual_disconnect:
            self._status = self._status.with_updates(
                state=BluetoothState.ERROR,
                last_error="manual disconnect is disabled by configuration",
            )
            await self._emit_lifecycle_event(
                "bluetooth_error",
                reason="manual_disconnect_disabled",
            )
            return self.get_status()

        async with self._operation_lock:
            self._desired_connected = False
            self._manual_disconnect = manual
            self._runtime.set_bluetooth_desired_connected(False)
            await self._disconnect_current_locked(
                manual=manual,
                reason="manual_disconnect" if manual else "desired_disconnected",
            )
            self._wake_event.set()
            return self.get_status()

    async def retry_now(self) -> BluetoothConnectionStatus:
        async with self._operation_lock:
            self._desired_connected = True
            self._manual_disconnect = False
            self._runtime.set_bluetooth_desired_connected(True)
            self._runtime.request_bluetooth_command("retry")
            self._status = self._status.with_updates(
                desired_connected=True,
                state=BluetoothState.RECONNECTING,
            )
            await self._emit_lifecycle_event("bluetooth_reconnecting", reason="manual_retry")
            await self._disconnect_current_locked(manual=False, reason="manual_retry")
            await self._ensure_started_locked()
            self._wake_event.set()
            return self.get_status()

    async def scan_devices(self) -> list[BluetoothDevice]:
        async with self._operation_lock:
            if self._status.state in {
                BluetoothState.CONNECTING,
                BluetoothState.CONNECTED,
                BluetoothState.SUBSCRIBING,
                BluetoothState.RECONNECTING,
                BluetoothState.READY,
            }:
                return list(self._known_devices)
            await self._set_status_locked(state=BluetoothState.SCANNING, last_error=None)
            await self._emit_lifecycle_event("bluetooth_scan_started", reason="manual_scan")
            devices = await self._perform_scan_locked()
            self._known_devices = devices
            if not self._desired_connected:
                await self._set_status_locked(state=BluetoothState.DISCONNECTED)
            await self._emit_lifecycle_event(
                "bluetooth_scan_completed",
                reason=f"found_{len(devices)}_devices",
            )
            return list(devices)

    def get_status(self) -> BluetoothConnectionStatus:
        return BluetoothConnectionStatus.model_validate(self._status.model_dump())

    def is_connected(self) -> bool:
        return is_connected_state(self._status.state)

    def is_ready(self) -> bool:
        return self._status.state is BluetoothState.READY

    async def events(self) -> AsyncIterator[TelemetryEvent]:
        while not self._stop.is_set() or not self._events.empty():
            try:
                ev = await asyncio.wait_for(self._events.get(), timeout=0.2)
            except TimeoutError:
                continue
            yield ev

    async def discovered_devices(self) -> list[DiscoveredDevice]:
        return [
            DiscoveredDevice(name=d.device_name or "?", address=d.mac_address or d.device_id)
            for d in self._known_devices
        ]

    async def shutdown(self) -> None:
        self._stop.set()
        self._wake_event.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        async with self._operation_lock:
            await self._disconnect_current_locked(manual=False, reason="shutdown")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _ensure_started_locked(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="bluetooth-supervisor")

    async def _set_status_locked(self, **updates: Any) -> None:
        self._status = self._status.with_updates(**updates)

    async def _emit_lifecycle_event(self, event_name: str, *, reason: str | None = None) -> None:
        payload = self._status.to_connection_payload(
            event=event_name,
            reason=reason,
            error=self._status.last_error,
        )
        await self._enqueue_event(
            TelemetryEvent(
                timestamp_iso=self._now(),
                timestamp_monotonic_ms=self._mono(),
                source="system",
                event_type=EventType.CONNECTION_STATE,
                payload=payload,
            )
        )

    async def _enqueue_event(self, event: TelemetryEvent) -> None:
        try:
            self._events.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                _ = self._events.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._events.put_nowait(event)

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._sync_runtime_requests()
                if not self._desired_connected:
                    await self._wait_or_wake(0.25)
                    continue

                if self._adapter is None:
                    await self._connect_cycle()
                    continue

                await self._pump_live_events_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("bluetooth_supervisor: run loop failure")
                await self._set_error("supervisor loop failure")
                await self._wait_or_wake(1.0)

    async def _connect_cycle(self) -> None:
        try:
            await self._connect_once_locked()
        except Exception as exc:
            self._status = self._status.with_updates(
                state=BluetoothState.ERROR,
                last_error=str(exc),
                reconnect_attempts=self._status.reconnect_attempts + 1,
                desired_connected=self._desired_connected,
            )
            await self._emit_lifecycle_event("bluetooth_error", reason="connect_failed")
            if not self._desired_connected:
                return
            self._status = self._status.with_updates(state=BluetoothState.RECONNECTING)
            await self._emit_lifecycle_event("bluetooth_reconnecting", reason="connect_failed")
            delay = self._next_backoff_delay(self._status.reconnect_attempts)
            await self._wait_or_wake(delay)

    async def _connect_once_locked(self) -> None:
        async with self._operation_lock:
            target_device = await self._resolve_target_device_locked()
            await self._set_status_locked(
                state=BluetoothState.CONNECTING,
                desired_connected=self._desired_connected,
                device_id=target_device.device_id if target_device else self._selected_device_id,
                device_name=target_device.device_name if target_device else None,
                mac_address=target_device.mac_address if target_device else self._cfg.mac_address,
                last_error=None,
            )
            await self._emit_lifecycle_event("bluetooth_connecting", reason="desired_connected")

            adapter = self._adapter_factory()
            target = (
                target_device.mac_address
                if target_device is not None and target_device.mac_address
                else self._cfg.mac_address
            )
            try:
                await asyncio.wait_for(
                    adapter.connect(target),
                    timeout=float(self._cfg.connect_timeout_seconds),
                )
            except TimeoutError as exc:
                raise AdapterConnectionError("connect timeout") from exc

            self._adapter = adapter
            self._adapter_iter = adapter.events()
            now = self._now()
            await self._set_status_locked(
                state=BluetoothState.CONNECTED,
                connected_at=now,
                disconnected_at=None,
                desired_connected=True,
            )
            await self._emit_lifecycle_event("bluetooth_connected", reason="transport_connected")

            await self._set_status_locked(state=BluetoothState.SUBSCRIBING)
            await self._emit_lifecycle_event("bluetooth_subscribing", reason="subscribe_notifications")
            await self._subscribe_notifications_locked(adapter)

            await self._set_status_locked(
                state=BluetoothState.READY,
                reconnect_attempts=0,
                last_error=None,
                last_seen_at=now,
                last_rx_monotonic_ms=self._mono(),
            )
            await self._emit_lifecycle_event("bluetooth_ready", reason="subscriptions_ready")

    async def _subscribe_notifications_locked(self, _adapter: LiveCarreraAdapter) -> None:
        # TODO(hardware): Validate exact carreralib/BLE characteristic subscription
        # flow against real Carrera AppConnect firmware. The current live adapter
        # wraps carreralib's polling API, which internally manages BLE notifications.
        return None

    async def _pump_live_events_once(self) -> None:
        assert self._adapter_iter is not None
        try:
            ev = await asyncio.wait_for(self._adapter_iter.__anext__(), timeout=0.5)
        except TimeoutError:
            await self._maybe_mark_stale()
            return
        except StopAsyncIteration:
            await self._handle_unexpected_disconnect("stream_ended")
            return
        except AdapterReadError as exc:
            await self._handle_unexpected_disconnect(str(exc))
            return

        if ev.source == self.source_name and ev.event_type is not EventType.CONNECTION_STATE:
            now = self._now()
            self._status = self._status.with_updates(
                last_seen_at=now,
                last_rx_monotonic_ms=ev.timestamp_monotonic_ms,
            )
            if self._status.state in {
                BluetoothState.STALE,
                BluetoothState.CONNECTED,
                BluetoothState.SUBSCRIBING,
            }:
                self._status = self._status.with_updates(
                    state=BluetoothState.READY,
                    last_error=None,
                    reconnect_attempts=0,
                )
                await self._emit_lifecycle_event("bluetooth_ready", reason="telemetry_rx")

        if ev.event_type is EventType.CONNECTION_STATE:
            await self._ingest_connection_event(ev)

        await self._enqueue_event(ev)
        await self._maybe_mark_stale()

    async def _ingest_connection_event(self, event: TelemetryEvent) -> None:
        raw_state = event.payload.get("state")
        if not isinstance(raw_state, str):
            return
        with contextlib.suppress(ValueError):
            mapped = BluetoothState(raw_state)
            if mapped in {BluetoothState.STALE, BluetoothState.RECONNECTING, BluetoothState.ERROR}:
                self._status = self._status.with_updates(state=mapped)

    async def _maybe_mark_stale(self) -> None:
        if self._status.state is not BluetoothState.READY:
            return
        last_rx = self._status.last_rx_monotonic_ms
        if last_rx is None:
            return
        elapsed_ms = self._mono() - int(last_rx)
        if elapsed_ms < int(self._cfg.stale_timeout_seconds * 1000):
            return
        self._status = self._status.with_updates(
            state=BluetoothState.STALE,
            last_error="telemetry stale timeout",
        )
        await self._emit_lifecycle_event("bluetooth_stale", reason="telemetry_timeout")
        if self._cfg.reconnect_on_stale and self._desired_connected:
            await self._disconnect_current_locked(manual=False, reason="stale_reconnect")
            self._status = self._status.with_updates(
                state=BluetoothState.RECONNECTING,
                reconnect_attempts=self._status.reconnect_attempts + 1,
            )
            await self._emit_lifecycle_event("bluetooth_reconnecting", reason="stale_reconnect")

    async def _handle_unexpected_disconnect(self, error: str) -> None:
        if self._manual_disconnect and not self._desired_connected:
            return
        await self._disconnect_current_locked(manual=False, reason="unexpected_disconnect")
        if not self._desired_connected:
            return
        self._status = self._status.with_updates(
            state=BluetoothState.RECONNECTING,
            reconnect_attempts=self._status.reconnect_attempts + 1,
            last_error=error,
            desired_connected=True,
        )
        await self._emit_lifecycle_event("bluetooth_reconnecting", reason="unexpected_disconnect")
        await self._wait_or_wake(self._next_backoff_delay(self._status.reconnect_attempts))

    async def _disconnect_current_locked(self, *, manual: bool, reason: str) -> None:
        adapter = self._adapter
        self._adapter = None
        self._adapter_iter = None
        if adapter is not None:
            with contextlib.suppress(Exception):
                await adapter.disconnect()

        disconnected_state = (
            BluetoothState.MANUALLY_DISCONNECTED if manual else BluetoothState.DISCONNECTED
        )
        self._status = self._status.with_updates(
            state=disconnected_state,
            desired_connected=self._desired_connected,
            disconnected_at=self._now(),
        )
        lifecycle_event = (
            "bluetooth_manual_disconnect" if manual else "bluetooth_disconnected"
        )
        await self._emit_lifecycle_event(lifecycle_event, reason=reason)

    async def _set_error(self, message: str) -> None:
        self._status = self._status.with_updates(
            state=BluetoothState.ERROR,
            last_error=message,
            reconnect_attempts=self._status.reconnect_attempts + 1,
        )
        await self._emit_lifecycle_event("bluetooth_error", reason="supervisor_error")

    async def _resolve_target_device_locked(self) -> BluetoothDevice | None:
        if self._cfg.prefer_scan_device_object:
            devices = await self._perform_scan_locked()
            self._known_devices = devices
            selected = self._pick_device(devices)
            if selected is not None:
                self._selected_device_id = selected.device_id
                self._runtime.set_bluetooth_selected_device_id(self._selected_device_id)
                return selected

        if self._selected_device_id:
            return BluetoothDevice(
                device_id=self._selected_device_id,
                device_name=None,
                mac_address=self._selected_device_id,
            )
        if self._cfg.mac_address:
            return BluetoothDevice(
                device_id=self._cfg.mac_address,
                device_name=None,
                mac_address=self._cfg.mac_address,
            )
        return None

    def _pick_device(self, devices: Sequence[BluetoothDevice]) -> BluetoothDevice | None:
        if not devices:
            return None
        if self._selected_device_id is not None:
            for dev in devices:
                if dev.device_id == self._selected_device_id:
                    return dev
        for dev in devices:
            if (dev.device_name or "") == "Control_Unit":
                return dev
        return devices[0]

    async def _perform_scan_locked(self) -> list[BluetoothDevice]:
        if self._scan_fn is None:
            try:
                from carreralib import connection as cl_conn
            except ImportError:
                return []
            rows = await asyncio.to_thread(lambda: list(cl_conn.scan()))
        else:
            scan_fn = self._scan_fn
            assert scan_fn is not None
            rows = await asyncio.to_thread(lambda: list(scan_fn()))

        out: list[BluetoothDevice] = []
        for address, name in rows:
            addr = str(address)
            out.append(
                BluetoothDevice(
                    device_id=addr,
                    device_name=str(name) if name else None,
                    mac_address=addr,
                )
            )
        return out

    async def _sync_runtime_requests(self) -> None:
        self._desired_connected = self._runtime.get_bluetooth_desired_connected()
        self._status = self._status.with_updates(desired_connected=self._desired_connected)

        seq, command, device_id = self._runtime.consume_bluetooth_command(
            last_sequence=self._last_command_seq,
        )
        if seq <= self._last_command_seq:
            return
        self._last_command_seq = seq
        if command == "connect":
            self._desired_connected = True
            self._manual_disconnect = False
            if device_id is not None:
                self._selected_device_id = device_id
        elif command == "disconnect":
            self._desired_connected = False
            self._manual_disconnect = True
            await self._disconnect_current_locked(manual=True, reason="ui_disconnect")
        elif command == "retry":
            self._desired_connected = True
            self._manual_disconnect = False
            await self._disconnect_current_locked(manual=False, reason="ui_retry")
            self._status = self._status.with_updates(state=BluetoothState.RECONNECTING)
        elif command == "scan":
            await self.scan_devices()

    async def _wait_or_wake(self, timeout_s: float) -> None:
        self._wake_event.clear()
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=max(0.0, float(timeout_s)))
        except TimeoutError:
            return

    def _next_backoff_delay(self, attempts: int) -> float:
        schedule = self._cfg.reconnect_backoff_seconds
        if not schedule:
            return float(self._cfg.reconnect_interval_seconds)
        idx = min(max(0, int(attempts) - 1), len(schedule) - 1)
        return float(schedule[idx])


__all__ = ["BluetoothConnectionSupervisor"]
