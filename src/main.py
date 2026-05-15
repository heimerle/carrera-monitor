"""Carrera Monitor entry point: CLI parsing, async orchestration, graceful shutdown.

Two run modes:
- `--mock`: spin up the `MockCarreraAdapter` (no BLE required).
- default: spin up the `LiveCarreraAdapter` (`carreralib`) via the
  `CarreraClientRunner`, with reconnect.

In both cases the producer publishes to a shared `EventBus`; the
`StateManager` and `JsonlEventWriter` subscribe. A Streamlit subprocess is
launched unless `--no-dashboard`.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from . import utils
from .config import AppConfig, load_config
from .database import init_db
from .event_bus import EventBus
from .mock_client import MockCarreraAdapter
from .race_runner import RaceTelemetryRunner
from .services.race_service import RaceService
from .state_manager import StateManager
from .storage import JsonlEventWriter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="carrera-monitor",
        description="Modular telemetry + live dashboard for Carrera DIGITAL 124/132.",
    )
    p.add_argument("--mock", action="store_true", help="Use the mock telemetry generator (no BLE).")
    p.add_argument("--config", type=Path, default=None, help="Path to YAML config file.")
    p.add_argument("--mac", type=str, default=None, help="Bypass BLE scan; connect to this MAC.")
    p.add_argument("--log-dir", type=Path, default=None, help="Override log directory.")
    p.add_argument(
        "--no-dashboard", action="store_true", help="Do not auto-launch Streamlit dashboard."
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Stderr log level.",
    )
    p.add_argument(
        "--debug-raw",
        action="store_true",
        help="Emit a companion `raw` event for every translated frame (FR-013).",
    )
    return p.parse_args(argv)


def _resolve_config_path(arg_path: Path | None) -> Path | None:
    if arg_path is not None:
        return arg_path
    default = Path("config.yaml")
    return default if default.exists() else None


def _apply_overrides(cfg: AppConfig, args: argparse.Namespace) -> AppConfig:
    """Apply CLI overrides onto the loaded config without mutating in place."""
    data = cfg.model_dump()
    if args.log_dir is not None:
        data["logging"]["directory"] = args.log_dir
    if args.mac is not None:
        data["bluetooth"]["mac_address"] = args.mac
    if args.debug_raw:
        data["logging"]["debug_raw_enabled"] = True
    if args.no_dashboard:
        data["dashboard"]["enabled"] = False
    return AppConfig.model_validate(data)


async def run(args: argparse.Namespace) -> int:
    # Config
    try:
        raw_cfg = load_config(_resolve_config_path(args.config))
        cfg = _apply_overrides(raw_cfg, args)
    except (ValidationError, ValueError, OSError) as exc:
        logger.error("config error: %s", exc)
        return 1

    log_dir = Path(cfg.logging.directory)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Initialize the race-management database (creates ./data/ and schema if
    # missing). Failure is fatal because the rest of the pipeline depends on
    # it; but the bare existing-tests pipeline does not call run() directly.
    try:
        init_db(cfg.database.url, echo=cfg.database.echo)
    except Exception:
        logger.exception("database: init_db failed")
        return 1
    race_service = RaceService(config=cfg.race_management)
    try:
        race_service.recover_on_startup()
    except Exception:
        logger.exception("race_service: recover_on_startup failed")

    bus = EventBus()
    storage_q = bus.subscribe("storage", maxsize=8192)
    state_q = bus.subscribe("state", maxsize=1024)

    state_mgr = StateManager(
        state_q,
        state_file=log_dir / "state.json",
        refresh_interval_ms=cfg.dashboard.refresh_interval_ms,
    )
    writer = JsonlEventWriter(
        storage_q,
        log_dir=log_dir,
        jsonl_enabled=cfg.logging.jsonl_enabled,
        csv_laps_enabled=cfg.logging.csv_laps_enabled,
    )

    # Adapter selection.
    if args.mock:
        adapter = MockCarreraAdapter(
            car_count=cfg.cars.count,
            debug_raw=cfg.logging.debug_raw_enabled,
        )
        await adapter.connect(None)
    else:
        # Lazy import so mock mode never touches carreralib code paths.
        from .carrera_client import CarreraClientRunner

        adapter = CarreraClientRunner(  # type: ignore[assignment]
            mac_address=cfg.bluetooth.mac_address,
            scan_timeout_seconds=cfg.bluetooth.scan_timeout_seconds,
            reconnect_interval_seconds=cfg.bluetooth.reconnect_interval_seconds,
            debug_raw=cfg.logging.debug_raw_enabled,
        )
        await adapter.connect(cfg.bluetooth.mac_address)

    await writer.start()
    await state_mgr.start()

    race_runner = RaceTelemetryRunner(
        bus,
        race_service,
        persist_all_events=cfg.race_management.persist_all_events,
    )
    await race_runner.start()

    # Optional dashboard subprocess.
    dashboard_proc: subprocess.Popen[bytes] | None = None
    if cfg.dashboard.enabled:
        dashboard_proc = _launch_dashboard(cfg.dashboard.port)
        if dashboard_proc is not None:
            print(f"Dashboard: http://localhost:{cfg.dashboard.port}", flush=True)

    # Shutdown plumbing.
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # pragma: no cover - Windows
            loop.add_signal_handler(sig, _request_stop)

    # Forward events from adapter to bus.
    async def pump() -> None:
        try:
            async for ev in adapter.events():
                await bus.publish(ev)
        except Exception:
            logger.exception("adapter event pump crashed")

    pump_task = asyncio.create_task(pump(), name="event-pump")

    exit_code = 0
    try:
        await stop_event.wait()
    finally:
        logger.info("shutdown: signalled, flushing within 5s")
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, Exception):
            await asyncio.wait_for(pump_task, timeout=1.0)
        try:
            await adapter.disconnect()
        except Exception:
            logger.exception("shutdown: adapter disconnect failed")
        await state_mgr.stop()
        await writer.stop()
        await race_runner.stop()
        await bus.close()
        if dashboard_proc is not None:
            dashboard_proc.terminate()
            try:
                dashboard_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                dashboard_proc.kill()
    return exit_code


def _launch_dashboard(port: int) -> subprocess.Popen[bytes] | None:
    """Best-effort `streamlit run` subprocess. Failure does not abort the pipeline."""
    try:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/app.py",
                "--server.port",
                str(port),
                "--server.headless",
                "true",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("dashboard: failed to launch streamlit: %s", exc)
        return None


def cli_entry() -> int:
    args = parse_args()
    utils.configure_logging(args.log_level)
    if args.mock and args.mac:
        print("error: --mock and --mac are mutually exclusive", file=sys.stderr)
        return 2
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0
    except Exception:
        logger.exception("unrecoverable runtime error")
        return 3


if __name__ == "__main__":
    sys.exit(cli_entry())


__all__ = ["cli_entry", "parse_args", "run"]
