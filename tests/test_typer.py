"""Tests for the reworked TextTyper (clipboard-paste primary, pynput fallback)."""
from unittest.mock import MagicMock, patch

import pytest

from core.typer import TextTyper


def _typer():
    t = TextTyper(delay_before_typing=0.0, clipboard_restore_delay=0.0)
    return t


def test_empty_text_returns_false():
    assert _typer().type_text("") is False


def test_paste_sets_clipboard_and_sends_shortcut(monkeypatch):
    fake_clip = MagicMock()
    fake_clip.paste.return_value = "ORIGINAL"
    fake_kb = MagicMock()
    controller = MagicMock()
    fake_kb.Controller.return_value = controller
    fake_kb.Key.cmd = "CMD"
    fake_kb.Key.ctrl = "CTRL"

    t = _typer()
    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", False):
        ok = t.type_text("hello.py --help", method="paste")

    assert ok is True
    fake_clip.copy.assert_any_call("hello.py --help")
    controller.press.assert_called()      # Ctrl held
    controller.release.assert_called()


def test_paste_restores_clipboard_on_daemon_thread(monkeypatch):
    fake_clip = MagicMock()
    fake_clip.paste.return_value = "ORIGINAL"
    fake_kb = MagicMock()
    fake_kb.Controller.return_value = MagicMock()
    fake_kb.Key.ctrl = "CTRL"

    t = TextTyper(delay_before_typing=0.0, clipboard_restore_delay=0.0)
    started = {}

    real_thread = __import__("threading").Thread

    def capture_thread(*args, **kwargs):
        started["daemon"] = kwargs.get("daemon")
        th = real_thread(*args, **kwargs)
        return th

    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", False), \
         patch("core.typer.threading.Thread", side_effect=capture_thread):
        t.type_text("x", method="paste")

    # restore must happen off the main thread (daemon=True)
    assert started.get("daemon") is True


def test_paste_skips_restore_when_clipboard_empty():
    """An empty original clipboard must NOT spawn a restore thread (else a
    fresh user copy in the ~1.5s window could be clobbered with '')."""
    fake_clip = MagicMock()
    fake_clip.paste.return_value = ""   # nothing worth restoring
    fake_kb = MagicMock()
    fake_kb.Controller.return_value = MagicMock()
    fake_kb.Key.ctrl = "CTRL"

    t = TextTyper(delay_before_typing=0.0, clipboard_restore_delay=0.0)

    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", False), \
         patch("core.typer.threading.Thread") as thread_cls:
        ok = t.type_text("x", method="paste")

    assert ok is True
    thread_cls.assert_not_called()   # no restore scheduled for empty clipboard


def test_type_method_uses_controller_type():
    fake_kb = MagicMock()
    controller = MagicMock()
    fake_kb.Controller.return_value = controller
    t = _typer()
    with patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True):
        ok = t.type_text("café 🚀 中文", method="type")
    assert ok is True
    controller.type.assert_called_once_with("café 🚀 中文")


def test_unicode_not_routed_through_isascii_branch():
    # Regression: the old isascii() ASCII/non-ASCII split must be gone.
    import inspect
    src = inspect.getsource(TextTyper)
    assert "isascii" not in src


def test_blocked_when_accessibility_missing_on_mac():
    t = _typer()
    with patch("core.typer.IS_MAC", True), \
         patch.object(t, "_accessibility_ok", return_value=False):
        assert t.type_text("hi", method="paste") is False


def test_paste_uses_cmd_on_mac():
    fake_clip = MagicMock()
    fake_clip.paste.return_value = ""
    fake_kb = MagicMock()
    controller = MagicMock()
    fake_kb.Controller.return_value = controller
    fake_kb.Key.cmd = "CMD"
    t = _typer()
    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", True):
        t.type_text("z", method="paste")
    # the modifier pressed must be Cmd on mac
    controller.press.assert_any_call("CMD")
