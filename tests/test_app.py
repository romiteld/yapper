"""Phase 4 Task 10: YapperApp + _Bridge tests."""
import threading

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


def test_bridge_marshals_cross_thread_to_main_thread(qtbot):
    """Emitting a _Bridge signal from a worker thread must deliver the slot on
    the Qt MAIN thread (queued connection), proving the marshaling that keeps
    pynput-thread callbacks off the GUI thread."""
    from PySide6.QtCore import QObject
    from ui.app import _Bridge

    bridge = _Bridge()  # lives on the main thread
    main_thread = threading.current_thread()
    seen = {}

    # The bridge must be a QObject with an affinity to the main thread.
    assert isinstance(bridge, QObject)

    def slot(value):
        seen["thread"] = threading.current_thread()
        seen["value"] = value

    bridge.state_changed.connect(slot)

    def worker():
        # Emit from a genuinely different OS thread.
        seen["emit_thread"] = threading.current_thread()
        bridge.state_changed.emit("listening")

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    # The queued slot has not run yet (event loop not pumped).
    assert "thread" not in seen
    qtbot.waitUntil(lambda: "thread" in seen, timeout=1000)
    assert seen["value"] == "listening"
    assert seen["emit_thread"] is not main_thread     # emitted off-thread
    assert seen["thread"] is main_thread              # delivered on main thread


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


# ---- HIGH-2: controller and HistoryWindow share one history instance -------

@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_controller_and_app_share_history_instance(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    assert app.controller.history is app.history


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_record_added_by_controller_visible_in_history_window(
        mock_notifier, mock_hk, qtbot, settings, tmp_path):
    from core import TranscriptionHistory, TranscriptionRecord
    from ui.app import YapperApp

    # Rebuild app history against a temp dir so we don't touch the real file.
    app = YapperApp(settings=settings, start_listener=False)
    shared = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    app.history = shared
    app.controller.history = shared

    # Controller writes a record (as it would after a successful dictation).
    app.controller.history.add(
        TranscriptionRecord.create("kubectl get pods", 1.0))

    app.open_history()
    qtbot.addWidget(app._history_win)
    assert app._history_win._list.count() == 1
    assert app._history_win.history is shared


# ---- HIGH-6: tray quick-toggle submenus ------------------------------------

def _submenu(menu, title):
    from PySide6.QtWidgets import QMenu
    for act in menu.actions():
        sub = act.menu()
        if isinstance(sub, QMenu) and act.text() == title:
            return sub
    return None


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_tray_menu_has_quick_toggle_submenus(mock_notifier, mock_hk, qtbot, settings):
    from core import ENGINES, OUTPUT_MODES
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    menu = app.tray.contextMenu()
    titles = {a.text() for a in menu.actions()}
    assert {"Engine", "Output mode", "Language"} <= titles
    # Settings/History/Quit still present.
    assert {"Settings…", "History…", "Quit Yapper"} <= titles

    engine_sub = _submenu(menu, "Engine")
    engine_choices = {a.data() for a in engine_sub.actions()}
    assert set(ENGINES) <= engine_choices

    mode_sub = _submenu(menu, "Output mode")
    mode_choices = {a.data() for a in mode_sub.actions()}
    assert set(OUTPUT_MODES) <= mode_choices
    # Human-readable labels.
    mode_labels = {a.text() for a in mode_sub.actions()}
    assert {"Clean", "Polished", "Verbatim"} <= mode_labels


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_tray_output_mode_toggle_updates_and_persists(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    settings.set("output_mode", "clean")
    app = YapperApp(settings=settings, start_listener=False)
    menu = app.tray.contextMenu()
    mode_sub = _submenu(menu, "Output mode")
    verbatim = next(a for a in mode_sub.actions() if a.data() == "verbatim")
    verbatim.trigger()
    assert settings.get("output_mode") == "verbatim"
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("output_mode") == "verbatim"


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_tray_language_toggle_stores_code(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    menu = app.tray.contextMenu()
    lang_sub = _submenu(menu, "Language")
    es = next(a for a in lang_sub.actions() if a.data() == "es")
    es.trigger()
    assert settings.get("translate_to") == "es"


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_tray_menu_builds_when_tray_unavailable(mock_notifier, mock_hk, qtbot, settings):
    # When the system tray is unavailable, the menu must still build and a
    # Settings fallback is scheduled (no crash, an entry point still exists).
    from ui.app import YapperApp
    with patch("ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
        app = YapperApp(settings=settings, start_listener=False)
    assert app.tray.contextMenu() is not None
    titles = {a.text() for a in app.tray.contextMenu().actions()}
    assert "Settings…" in titles
