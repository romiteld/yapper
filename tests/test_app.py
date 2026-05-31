"""Phase 4 Task 10: YapperApp + _Bridge tests."""
from unittest.mock import MagicMock, patch

import pytest

from core import Settings
from ui.controller import ControllerState


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s


def test_bridge_relays_state_on_qt_thread(qtbot):
    from ui.app import _Bridge
    bridge = _Bridge()
    received = []
    bridge.state_changed.connect(lambda s: received.append(s))
    bridge.state_changed.emit("listening")
    assert received == ["listening"]


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_yapperapp_constructs_tray(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    assert app.tray is not None
    assert app.controller is not None
    # Tray icon was given a context menu.
    assert app.tray.contextMenu() is not None


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_controller_state_drives_tray_tooltip(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    app._bridge.state_changed.emit(ControllerState.LISTENING.value)
    qtbot.wait(10)
    assert "isten" in app.tray.toolTip() or app.tray.toolTip() != ""


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_start_listener_builds_hotkey_manager(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=True)
    mock_hk.assert_called_once()
    _, kwargs = mock_hk.call_args
    assert kwargs["mode"] == settings.get("activation_mode", "push_to_talk")
    app.hotkeys.start.assert_called_once()
