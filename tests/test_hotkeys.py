"""Tests for core.hotkeys HotkeyManager state machine (pynput mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from core.hotkeys import HotkeyManager


class FakeKey:
    """Stand-in for a pynput key with a usable name attribute."""
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return isinstance(other, FakeKey) and other.name == self.name
    def __hash__(self):
        return hash(self.name)


def _make(mode="push_to_talk", hotkey="f8"):
    on_start = MagicMock()
    on_stop = MagicMock()
    mgr = HotkeyManager(mode=mode, hotkey=hotkey,
                        on_start=on_start, on_stop=on_stop)
    # Force the matcher to recognise our FakeKey("f8").
    mgr._target_key = FakeKey("f8")
    return mgr, on_start, on_stop


def test_ptt_press_starts_release_stops():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f8"))
    on_start.assert_called_once()
    on_stop.assert_not_called()
    mgr._on_release(FakeKey("f8"))
    on_stop.assert_called_once()


def test_ptt_autorepeat_guarded():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f8"))
    mgr._on_press(FakeKey("f8"))   # OS key auto-repeat
    mgr._on_press(FakeKey("f8"))
    assert on_start.call_count == 1  # guarded by _active flag


def test_ptt_ignores_other_keys():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f9"))
    on_start.assert_not_called()


def test_toggle_alternates_on_press_only():
    mgr, on_start, on_stop = _make("toggle")
    mgr._on_press(FakeKey("f8"))
    on_start.assert_called_once()
    mgr._on_release(FakeKey("f8"))   # release is a no-op in toggle
    on_stop.assert_not_called()
    mgr._on_press(FakeKey("f8"))
    on_stop.assert_called_once()
    mgr._on_press(FakeKey("f8"))
    assert on_start.call_count == 2


def test_set_mode_resets_active_state():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f8"))      # _active True
    mgr.set_mode("toggle")
    assert mgr._active is False
    mgr._on_press(FakeKey("f8"))      # toggle -> start
    assert on_start.call_count == 2


def test_set_hotkey_reparses_target():
    mgr, _, _ = _make("push_to_talk", "f8")
    with patch.object(mgr, "_parse_hotkey", return_value="PARSED") as parse:
        mgr.set_hotkey("f9")
    parse.assert_called_once_with("f9")
    assert mgr._target_key == "PARSED"


def test_start_creates_and_runs_listener():
    mgr, _, _ = _make("push_to_talk")
    fake_listener = MagicMock()
    fake_keyboard = MagicMock()
    fake_keyboard.Listener.return_value = fake_listener
    with patch.object(mgr, "_load_keyboard", return_value=fake_keyboard):
        mgr.start()
    fake_listener.start.assert_called_once()


def test_stop_stops_listener():
    mgr, _, _ = _make("push_to_talk")
    fake_listener = MagicMock()
    mgr._listener = fake_listener
    mgr.stop()
    fake_listener.stop.assert_called_once()
    assert mgr._listener is None


def test_wake_word_mode_does_not_react_to_keys():
    mgr, on_start, on_stop = _make("wake_word")
    mgr._on_press(FakeKey("f8"))
    mgr._on_release(FakeKey("f8"))
    on_start.assert_not_called()
    on_stop.assert_not_called()
