"""Tests for core.platform OS helpers."""
import importlib
from unittest.mock import patch

import pytest


def _reload_platform(system: str):
    """Reload core.platform with platform.system() mocked to `system`."""
    with patch("platform.system", return_value=system):
        import core.platform as p
        return importlib.reload(p)


def test_flags_mac():
    p = _reload_platform("Darwin")
    assert p.IS_MAC is True
    assert p.IS_WIN is False
    assert p.IS_LINUX is False


def test_flags_windows():
    p = _reload_platform("Windows")
    assert p.IS_WIN is True
    assert p.IS_MAC is False


def test_default_hotkey_per_os():
    assert _reload_platform("Darwin").default_hotkey() == "f8"
    assert _reload_platform("Windows").default_hotkey() == "f8"


def test_open_settings_pane_runs_open_on_mac():
    p = _reload_platform("Darwin")
    with patch("subprocess.run") as run:
        p.open_settings_pane("accessibility")
    run.assert_called_once()
    args = run.call_args[0][0]
    assert args[0] == "open"
    assert "Privacy_Accessibility" in args[1]


def test_open_settings_pane_noop_off_mac():
    p = _reload_platform("Windows")
    with patch("subprocess.run") as run:
        result = p.open_settings_pane("accessibility")
    run.assert_not_called()
    assert result is False


def test_open_folder_invokes_opener(tmp_path):
    p = _reload_platform("Linux")
    with patch("subprocess.run") as run:
        p.open_folder(str(tmp_path))
    run.assert_called_once()
    assert run.call_args[0][0][0] == "xdg-open"


def teardown_module(module):
    # Restore module to the real OS state for other test files.
    _reload_platform(__import__("platform").system())
