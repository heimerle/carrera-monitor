"""RacePulse 132 dashboard server.

Serves the static RacePulse dashboard (``src/dashboard/``) and exposes the
live telemetry snapshot written by :class:`~src.state_manager.StateManager`
at ``GET /api/state``. Stdlib-only (no Streamlit, no third-party deps) so it
starts instantly and never imports BLE.

The state snapshot is written atomically (temp file + rename) by the
StateManager, so a plain read here can never observe a partial JSON document.

Run standalone::

    python -m src.dashboard_server --port 8501 --state-file logs/state.json

``src.main`` launches this as a subprocess in place of the old Streamlit
dashboard; see ``_launch_dashboard`` there.
"""

from __future__ import annotations

import argparse
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory holding index.html + the .jsx/.css assets (this file's sibling).
_DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"


class _DashboardHandler(SimpleHTTPRequestHandler):
    """Static file handler with a single dynamic endpoint for live state.

    ``GET /api/state`` streams the current ``state.json`` with no-cache
    headers so the browser always sees the freshest snapshot. Everything
    else falls through to static file serving rooted at the dashboard dir.
    """

    # Bound via functools.partial in :func:`build_server`.
    state_file: Path = Path("logs/state.json")

    def __init__(self, *args: object, state_file: Path, **kwargs: object) -> None:
        self.state_file = state_file
        super().__init__(*args, directory=str(_DASHBOARD_DIR), **kwargs)  # type: ignore[arg-type]

    # Quieter logging — one line per request at DEBUG, not stderr spam.
    def log_message(self, fmt: str, *args: object) -> None:
        logger.debug("dashboard_server: " + fmt, *args)

    def do_GET(self) -> None:
        # Normalise so /api/state and /api/state?ts=123 both match.
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/state":
            self._serve_state()
            return
        super().do_GET()

    def _serve_state(self) -> None:
        """Return the raw state.json bytes, or an empty JSON object if absent.

        We deliberately forward the bytes verbatim (no parse/re-serialize) to
        keep the endpoint cheap and avoid re-encoding surprises. A missing or
        unreadable file yields ``{}`` with HTTP 200 so the frontend can treat
        "no telemetry yet" the same as "empty race" rather than erroring.
        """
        try:
            body = self.state_file.read_bytes()
        except (FileNotFoundError, OSError):
            body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def build_server(port: int, state_file: Path) -> ThreadingHTTPServer:
    handler = partial(_DashboardHandler, state_file=state_file)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="racepulse-dashboard",
        description="Serve the RacePulse 132 dashboard + live state endpoint.",
    )
    p.add_argument("--port", type=int, default=8501, help="HTTP port to listen on.")
    p.add_argument(
        "--state-file",
        type=Path,
        default=Path("logs/state.json"),
        help="Path to the StateManager snapshot served at /api/state.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    state_file = args.state_file.resolve()
    server = build_server(args.port, state_file)
    logger.info(
        "RacePulse dashboard on http://localhost:%d (state: %s)",
        args.port,
        state_file,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_server", "main", "parse_args"]
