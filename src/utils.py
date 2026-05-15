"""Shared utilities: time, structured logging, atomic JSON writes.

These helpers are deliberately tiny and dependency-free so every module can
import them without circular concerns.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Process start anchor for the monotonic clock. The pipeline is single-process
# so this is the single source of truth for `timestamp_monotonic_ms`.
_MONOTONIC_START: float = time.monotonic()


def now_iso() -> datetime:
    """Timezone-aware UTC wall-clock timestamp."""
    return datetime.now(tz=UTC)


def now_monotonic_ms() -> int:
    """Monotonic milliseconds since process start (≥ 0)."""
    elapsed = time.monotonic() - _MONOTONIC_START
    return max(0, int(elapsed * 1000))


def atomic_write_json(path: Path, obj: Any) -> None:
    """Atomically write `obj` as JSON to `path` using tmp + os.replace.

    Avoids torn reads by consumers (e.g. the Streamlit dashboard polling
    `logs/state.json`). The directory is created if missing.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class _JsonFormatter(logging.Formatter):
    """Render each log record as a single JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Promote any `extra={...}` fields that don't collide with builtins.
        for key, value in record.__dict__.items():
            if key in _LOG_BUILTIN_KEYS or key in base:
                continue
            try:
                json.dumps(value, default=str)
                base[key] = value
            except (TypeError, ValueError):
                base[key] = repr(value)
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False, default=str)


_LOG_BUILTIN_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


def configure_logging(level: str = "INFO") -> None:
    """Install a single stderr JSON-line handler at the configured level.

    Safe to call more than once: existing handlers on the root logger are
    cleared first so reconfiguration in tests is idempotent.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
