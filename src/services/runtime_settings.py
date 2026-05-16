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
    "bluetooth_desired_connected": False,
    "bluetooth_selected_device_id": None,
    "bluetooth_command_seq": 0,
    "bluetooth_pending_command": None,
    "bluetooth_pending_command_device_id": None,
}

_BLUETOOTH_COMMANDS = {"connect", "disconnect", "scan", "retry"}


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

    def get_bluetooth_desired_connected(self) -> bool:
        return bool(self._load().get("bluetooth_desired_connected", False))

    def set_bluetooth_desired_connected(self, value: bool) -> bool:
        data = self._load()
        data["bluetooth_desired_connected"] = bool(value)
        self._save(data)
        return bool(value)

    def get_bluetooth_selected_device_id(self) -> str | None:
        raw = self._load().get("bluetooth_selected_device_id")
        return str(raw) if isinstance(raw, str) and raw else None

    def set_bluetooth_selected_device_id(self, value: str | None) -> str | None:
        data = self._load()
        data["bluetooth_selected_device_id"] = value if value is None else str(value)
        self._save(data)
        stored = data.get("bluetooth_selected_device_id")
        return str(stored) if isinstance(stored, str) and stored else None

    def request_bluetooth_command(self, command: str, *, device_id: str | None = None) -> int:
        normalized = str(command).strip().lower()
        if normalized not in _BLUETOOTH_COMMANDS:
            raise ValueError(f"unsupported bluetooth command: {command!r}")
        data = self._load()
        seq = int(data.get("bluetooth_command_seq", 0)) + 1
        data["bluetooth_command_seq"] = seq
        data["bluetooth_pending_command"] = normalized
        data["bluetooth_pending_command_device_id"] = (
            None if device_id is None else str(device_id)
        )
        if normalized == "connect":
            data["bluetooth_desired_connected"] = True
        elif normalized == "disconnect":
            data["bluetooth_desired_connected"] = False
        if device_id is not None:
            data["bluetooth_selected_device_id"] = str(device_id)
        self._save(data)
        return seq

    def consume_bluetooth_command(
        self,
        *,
        last_sequence: int,
    ) -> tuple[int, str | None, str | None]:
        data = self._load()
        seq = int(data.get("bluetooth_command_seq", 0))
        if seq <= int(last_sequence):
            return seq, None, None
        cmd_raw = data.get("bluetooth_pending_command")
        cmd = str(cmd_raw) if isinstance(cmd_raw, str) else None
        dev_raw = data.get("bluetooth_pending_command_device_id")
        device_id = str(dev_raw) if isinstance(dev_raw, str) and dev_raw else None
        return seq, cmd, device_id

    def as_dict(self) -> dict[str, Any]:
        return self._load()


# Convenience module-level helpers backed by the default path.
_default = RuntimeSettings()


def get_mock_mode() -> bool:
    return _default.get_mock_mode()


def set_mock_mode(value: bool) -> bool:
    return _default.set_mock_mode(value)


def get_bluetooth_desired_connected() -> bool:
    return _default.get_bluetooth_desired_connected()


def set_bluetooth_desired_connected(value: bool) -> bool:
    return _default.set_bluetooth_desired_connected(value)


def request_bluetooth_command(command: str, *, device_id: str | None = None) -> int:
    return _default.request_bluetooth_command(command, device_id=device_id)


__all__ = [
    "DEFAULT_PATH",
    "RuntimeSettings",
    "get_bluetooth_desired_connected",
    "get_mock_mode",
    "request_bluetooth_command",
    "set_bluetooth_desired_connected",
    "set_mock_mode",
]
