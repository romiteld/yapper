"""The new Phase 1 symbols must be importable from the core package."""
import core


def test_new_symbols_exported():
    from core import (
        HotkeyManager,
        TextTyper,
        AudioRecorder,
        AudioDevice,
        Notifier,
        PermissionStatus,
        permission_status,
    )
    assert HotkeyManager is not None
    assert Notifier is not None
    assert callable(permission_status)


def test_platform_flags_exported():
    from core import IS_MAC, IS_WIN
    assert isinstance(IS_MAC, bool)
    assert isinstance(IS_WIN, bool)


def test_all_lists_new_symbols():
    for name in ("HotkeyManager", "Notifier", "PermissionStatus",
                 "permission_status", "IS_MAC", "IS_WIN"):
        assert name in core.__all__
