"""Tiny JSON-backed runtime-settings store shared by the UI and the pipeline.

Used for flags the user can toggle from the Streamlit UI that the
``src.main`` entry point reads at process start (the live pipeline and
the Streamlit dashboard live in separate processes, so a file on disk is
the simplest correct IPC).

Currently exposes one flag:

``mock_mode``
    When ``True`` and ``carrera-monitor`` is started without an explicit
    ``--mock`` / ``--mac`` override, the pipeline uses the
    :class:`~src.mock_client.MockCarreraAdapter` instead of a live BLE
    adapter. Changes take effect on the next pipeline restart.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path("data") / "runtime_settings.json"

_DEFAULTS: dict[str, Any] = {
    "mock_mode": False,
}


class RuntimeSettings:
    """File-backed key/value settings store with atomic writes."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else DEFAULT_PATH

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------ I/O

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return dict(_DEFAULTS)
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning(
                "runtime_settings: failed to read %s, falling back to defaults",
                self._path,
            )
            return dict(_DEFAULTS)
        if not isinstance(raw, dict):
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        merged.update({k: v for k, v in raw.items() if k in _DEFAULTS})
        return merged

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmpfile in the same directory, then os.replace.
        fd, tmp_name = tempfile.mkstemp(
            prefix=self._path.name + ".",
            suffix=".tmp",
            dir=str(self._path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_name, self._path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    # ----------------------------------------------------------- Accessors

    def get_mock_mode(self) -> bool:
        return bool(self._load().get("mock_mode", False))

    def set_mock_mode(self, value: bool) -> bool:
        data = self._load()
        data["mock_mode"] = bool(value)
        self._save(data)
        return bool(value)

    def as_dict(self) -> dict[str, Any]:
        return self._load()


# Convenience module-level helpers backed by the default path.
_default = RuntimeSettings()


def get_mock_mode() -> bool:
    return _default.get_mock_mode()


def set_mock_mode(value: bool) -> bool:
    return _default.set_mock_mode(value)


__all__ = [
    "DEFAULT_PATH",
    "RuntimeSettings",
    "get_mock_mode",
    "set_mock_mode",
]
