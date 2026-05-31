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


def test_input_monitoring_uses_ax_is_process_trusted_on_mac():
    """input_monitoring_ok() now uses AXIsProcessTrusted (not the stale class
    attribute), mirroring accessibility_trusted()."""
    fake_hi = MagicMock()
    fake_hi.AXIsProcessTrusted.return_value = True
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert input_monitoring_ok() is True
    fake_hi.AXIsProcessTrusted.return_value = False
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert input_monitoring_ok() is False


def test_input_monitoring_false_when_pyobjc_missing_on_mac():
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=None):
        assert input_monitoring_ok() is False


def test_microphone_probe_true_via_avfoundation_authorized():
    """microphone_ok() returns True when AVFoundation reports status==3 (authorized)."""
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 3
    with patch("core.permissions.IS_MAC", True), \
         patch.dict("sys.modules", {"AVFoundation": fake_av}):
        assert microphone_ok() is True


def test_microphone_probe_false_via_avfoundation_denied():
    """microphone_ok() returns False when AVFoundation reports status==2 (denied)."""
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 2
    with patch("core.permissions.IS_MAC", True), \
         patch.dict("sys.modules", {"AVFoundation": fake_av}):
        assert microphone_ok() is False


def test_microphone_falls_back_to_stream_probe_when_avfoundation_missing():
    """When AVFoundation is not available, fall back to _probe_input_stream()."""
    import sys
    # Make the import of AVFoundation raise ImportError.
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else None
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._probe_input_stream", return_value=True) as probe_mock, \
         patch.dict("sys.modules", {"AVFoundation": None}):
        result = microphone_ok()
    # _probe_input_stream should have been called as the fallback.
    probe_mock.assert_called_once()
    assert result is True


def test_permission_status_aggregates_on_mac():
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions.microphone_ok", return_value=True), \
         patch("core.permissions.accessibility_trusted", return_value=False), \
         patch("core.permissions.input_monitoring_ok", return_value=True):
        st = permission_status()
    assert st == PermissionStatus(True, False, True)
