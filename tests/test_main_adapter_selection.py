"""Unit tests for `resolve_use_mock` — adapter-selection precedence (FR-225).

Pure-logic tests, no Streamlit / no DB / no BLE.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import load_config
from src.main import resolve_use_mock


def test_cli_mock_flag_wins_even_with_settings_off() -> None:
    assert resolve_use_mock(
        cli_mock=True, cli_mac=None, get_mock_mode_fn=lambda: False
    ) is True


def test_cli_mock_flag_wins_even_with_mac() -> None:
    # --mock + --mac is a user oddity but --mock takes precedence per FR-225.
    assert resolve_use_mock(
        cli_mock=True, cli_mac="AA:BB:CC:DD:EE:FF", get_mock_mode_fn=lambda: False
    ) is True


def test_cli_mac_forces_live_even_with_settings_on() -> None:
    assert resolve_use_mock(
        cli_mock=False, cli_mac="AA:BB:CC:DD:EE:FF", get_mock_mode_fn=lambda: True
    ) is False


def test_settings_on_selects_mock_when_no_cli_flags() -> None:
    assert resolve_use_mock(
        cli_mock=False, cli_mac=None, get_mock_mode_fn=lambda: True
    ) is True


def test_settings_off_selects_live_when_no_cli_flags() -> None:
    assert resolve_use_mock(
        cli_mock=False, cli_mac=None, get_mock_mode_fn=lambda: False
    ) is False


def test_oserror_in_settings_falls_back_to_live(caplog: pytest.LogCaptureFixture) -> None:
    def _boom() -> bool:
        raise OSError("settings file unreadable")

    with caplog.at_level("WARNING", logger="src.main"):
        result = resolve_use_mock(
            cli_mock=False, cli_mac=None, get_mock_mode_fn=_boom
        )
    assert result is False
    assert any("failed to read runtime_settings" in rec.message for rec in caplog.records)


def test_bluetooth_hardening_config_fields_are_loaded(tmp_path) -> None:
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        "\n".join(
            [
                "bluetooth:",
                "  reconnect_interval_seconds: 2",
                "  max_reconnect_interval_seconds: 10",
                "  idle_timeout_seconds: 15",
                "  idle_warning_seconds: 5",
                "  periodic_forced_reconnect_seconds: 0",
                "  periodic_reconnect_only_when_not_running: true",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)
    assert cfg.bluetooth.max_reconnect_interval_seconds == 10
    assert cfg.bluetooth.idle_warning_seconds == 5
    assert cfg.bluetooth.periodic_forced_reconnect_seconds == 0
    assert cfg.bluetooth.periodic_reconnect_only_when_not_running is True


def test_bluetooth_config_rejects_idle_warning_gte_timeout(tmp_path) -> None:
    cfg_file = tmp_path / "bad.yaml"
    cfg_file.write_text(
        "\n".join(
            [
                "bluetooth:",
                "  reconnect_interval_seconds: 2",
                "  max_reconnect_interval_seconds: 10",
                "  idle_timeout_seconds: 5",
                "  idle_warning_seconds: 5",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(cfg_file)


def test_bluetooth_config_rejects_max_reconnect_below_initial(tmp_path) -> None:
    cfg_file = tmp_path / "bad2.yaml"
    cfg_file.write_text(
        "\n".join(
            [
                "bluetooth:",
                "  reconnect_interval_seconds: 10",
                "  max_reconnect_interval_seconds: 5",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(cfg_file)
