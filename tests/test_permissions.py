"""Tests for core.permissions (macOS TCC detection, no-op off-mac)."""
from unittest.mock import MagicMock, patch

from core.permissions import (
    PermissionStatus,
    microphone_ok,
    accessibility_trusted,
    input_monitoring_ok,
    permission_status,
)


def test_dataclass_shape():
    s = PermissionStatus(microphone=True, accessibility=False, input_monitoring=True)
    assert s.microphone is True
    assert s.accessibility is False
    assert s.input_monitoring is True


def test_all_true_off_mac():
    with patch("core.permissions.IS_MAC", False):
        assert microphone_ok() is True
        assert accessibility_trusted() is True
        assert input_monitoring_ok() is True
        st = permission_status()
        assert st == PermissionStatus(True, True, True)


def test_accessibility_uses_axis_process_trusted_on_mac():
    fake_hi = MagicMock()
    fake_hi.AXIsProcessTrusted.return_value = True
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert accessibility_trusted() is True
    fake_hi.AXIsProcessTrusted.return_value = False
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert accessibility_trusted() is False


def test_accessibility_false_when_pyobjc_missing_on_mac():
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=None):
        assert accessibility_trusted() is False


def test_input_monitoring_uses_listener_is_trusted_on_mac():
    fake_listener = MagicMock()
    fake_listener.IS_TRUSTED = True
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._keyboard_listener_cls", return_value=fake_listener):
        assert input_monitoring_ok() is True
    fake_listener.IS_TRUSTED = False
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._keyboard_listener_cls", return_value=fake_listener):
        assert input_monitoring_ok() is False


def test_microphone_probe_true_when_stream_opens_on_mac():
    fake_sd = MagicMock()
    fake_sd.check_input_settings.return_value = None  # no exception => ok
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_sounddevice", return_value=fake_sd):
        assert microphone_ok() is True


def test_microphone_probe_false_when_stream_raises_on_mac():
    fake_sd = MagicMock()
    fake_sd.PortAudioError = Exception
    fake_sd.check_input_settings.side_effect = Exception("denied")
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_sounddevice", return_value=fake_sd):
        assert microphone_ok() is False


def test_permission_status_aggregates_on_mac():
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions.microphone_ok", return_value=True), \
         patch("core.permissions.accessibility_trusted", return_value=False), \
         patch("core.permissions.input_monitoring_ok", return_value=True):
        st = permission_status()
    assert st == PermissionStatus(True, False, True)
