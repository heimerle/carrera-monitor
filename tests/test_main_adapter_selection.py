"""Unit tests for `resolve_use_mock` — adapter-selection precedence (FR-225).

Pure-logic tests, no Streamlit / no DB / no BLE.
"""

from __future__ import annotations

import pytest

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
