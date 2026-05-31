"""Phase 4 Task 9: SettingsWindow tests."""
import pytest

from core import Settings
from ui.settings_window import SettingsWindow, SettingsBinder


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    return s


def test_binder_reads_default(settings):
    b = SettingsBinder(settings)
    # default output_mode is "clean" (general-purpose framing)
    assert b.read("output_mode") == "clean"


def test_binder_writes_and_saves(settings):
    b = SettingsBinder(settings)
    b.write("output_mode", "polished")
    b.commit()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("output_mode") == "polished"


def test_binder_rejects_unknown_value_silently(settings):
    b = SettingsBinder(settings)
    # invalid hotkey not in HOTKEYS should not crash; value left at prior.
    b.write("hotkey", "not-a-key")
    assert b.read("hotkey") in (settings.get("hotkey"), "f8")


def test_settings_window_constructs_with_nav_sections(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    assert win.SECTIONS == [
        "General", "Engine & Models", "Vocabulary", "Formatting",
        "Hotkeys", "Audio", "History", "About",
    ]
    assert win._nav.count() == len(win.SECTIONS)


def test_settings_window_save_persists(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win.binder.write("expand_spoken_symbols", False)
    win._on_save()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("expand_spoken_symbols") is False
