"""AppConfig: Pydantic models + YAML loader.

Mirrors `specs/main/data-model.md` §6. Unknown keys produce warnings (not
fatal); range violations are fatal so misconfiguration surfaces immediately.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class BluetoothConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mac_address: str | None = None
    scan_timeout_seconds: int = Field(default=10, ge=1)
    reconnect_interval_seconds: int = Field(default=5, ge=1)
    idle_timeout_seconds: int = Field(default=15, ge=3)


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path = Field(default=Path("./logs"))
    jsonl_enabled: bool = True
    csv_laps_enabled: bool = True
    debug_raw_enabled: bool = False


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    port: int = Field(default=8501, ge=1024, le=65535)
    refresh_interval_ms: int = Field(default=200, ge=100, le=2000)


class CarsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(default=6, ge=1, le=6)


class DatabaseConfig(BaseModel):
    """Race-management SQLite database connection settings."""

    model_config = ConfigDict(extra="forbid")

    url: str = "sqlite:///./data/carrera_dashboard.sqlite3"
    echo: bool = False


class RaceManagementConfig(BaseModel):
    """Behaviour flags for the race-management module."""

    model_config = ConfigDict(extra="forbid")

    persist_all_events: bool = True
    allow_edit_running_race: bool = False
    # Stored as raw string (validated against RaceStatus in src/schemas).
    default_race_status_after_create: str = "draft"
    recover_running_race: bool = False


class AppConfig(BaseModel):
    # Top-level: tolerate unknown keys with a warning (see _strip_unknown).
    model_config = ConfigDict(extra="forbid")

    bluetooth: BluetoothConfig = Field(default_factory=BluetoothConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    cars: CarsConfig = Field(default_factory=CarsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    race_management: RaceManagementConfig = Field(default_factory=RaceManagementConfig)


_KNOWN_TOP = {"bluetooth", "logging", "dashboard", "cars", "database", "race_management"}
_KNOWN_NESTED: dict[str, set[str]] = {
    "bluetooth": set(BluetoothConfig.model_fields.keys()),
    "logging": set(LoggingConfig.model_fields.keys()),
    "dashboard": set(DashboardConfig.model_fields.keys()),
    "cars": set(CarsConfig.model_fields.keys()),
    "database": set(DatabaseConfig.model_fields.keys()),
    "race_management": set(RaceManagementConfig.model_fields.keys()),
}


def _strip_unknown(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown top-level + nested keys, emitting WARNING for each.

    Pydantic's `extra="forbid"` would make these fatal; the spec demands
    warnings only.
    """
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in _KNOWN_TOP:
            logger.warning("config: ignoring unknown top-level key %r", key)
            continue
        if isinstance(value, dict):
            sub_clean: dict[str, Any] = {}
            for sk, sv in value.items():
                if sk not in _KNOWN_NESTED[key]:
                    logger.warning("config: ignoring unknown key %r under %r", sk, key)
                    continue
                sub_clean[sk] = sv
            cleaned[key] = sub_clean
        else:
            cleaned[key] = value
    return cleaned


def load_config(path: Path | None) -> AppConfig:
    """Load YAML config from `path`. Returns defaults if `path` is falsy or
    missing on disk. Raises `pydantic.ValidationError` on range violations
    (callers should map this to exit code 1 per the CLI contract).
    """
    if path is None:
        return AppConfig()
    p = Path(path)
    if not p.exists():
        logger.warning("config: file %s not found, using built-in defaults", p)
        return AppConfig()
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"config: top-level YAML must be a mapping, got {type(raw).__name__}")
    cleaned = _strip_unknown(raw)
    try:
        return AppConfig.model_validate(cleaned)
    except ValidationError:
        # Re-raise unchanged; main.py turns this into exit code 1.
        raise


__all__ = [
    "AppConfig",
    "BluetoothConfig",
    "CarsConfig",
    "DashboardConfig",
    "DatabaseConfig",
    "LoggingConfig",
    "RaceManagementConfig",
    "load_config",
]
