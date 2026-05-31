"""
Yapper Permissions
==================
macOS TCC permission detection (Accessibility, Input Monitoring, Microphone).
On Windows/Linux every check returns True (no per-permission gating needed).

macOS only re-reads TCC at process launch, so a False here means the user must
grant the permission and *relaunch* the app. pynput injection fails silently
without Accessibility, so we never rely on exceptions — we probe up front.

pyobjc is macOS-only and must be lazily imported inside macOS branches only,
so this module imports cleanly on Linux/Windows without any native deps.

© 2026 Cloudelipute
"""

from dataclasses import dataclass

from .logger import get_logger
from .platform import IS_MAC

logger = get_logger("permissions")


@dataclass
class PermissionStatus:
    """Aggregated permission state for the wizard / HUD to act on."""
    microphone: bool
    accessibility: bool
    input_monitoring: bool

    @property
    def all_granted(self) -> bool:
        return self.microphone and self.accessibility and self.input_monitoring


def _load_hiservices():
    """Return the pyobjc HIServices module, or None if unavailable."""
    try:
        import HIServices  # type: ignore
        return HIServices
    except Exception:  # pragma: no cover - import path only on mac
        try:
            from ApplicationServices import HIServices  # type: ignore  # noqa: F811
            return HIServices
        except Exception:
            logger.debug("HIServices (pyobjc) not available")
            return None


def _keyboard_listener_cls():
    """Return pynput's keyboard Listener class, or None if unavailable."""
    try:
        from pynput import keyboard  # type: ignore
        return keyboard.Listener
    except Exception:
        logger.debug("pynput not available for input-monitoring probe")
        return None


def _load_sounddevice():
    """Return the sounddevice module, or None if unavailable."""
    try:
        import sounddevice  # type: ignore
        return sounddevice
    except Exception:
        logger.debug("sounddevice not available for mic probe")
        return None


def accessibility_trusted() -> bool:
    """True if the process may inject keystrokes (mac Accessibility)."""
    if not IS_MAC:
        return True
    hi = _load_hiservices()
    if hi is None:
        return False
    try:
        return bool(hi.AXIsProcessTrusted())
    except Exception as e:
        logger.error("AXIsProcessTrusted failed: %s", e)
        return False


def input_monitoring_ok() -> bool:
    """True if the process may observe global key events (mac Input Monitoring).

    On macOS, pynput's Quartz event tap is gated by AXIsProcessTrusted
    (Accessibility), so we probe that directly instead of reading the stale
    class-level ``IS_TRUSTED`` attribute (which is always False until a Listener
    instance has started its thread).
    """
    if not IS_MAC:
        return True
    hi = _load_hiservices()
    if hi is None:
        return False
    try:
        return bool(hi.AXIsProcessTrusted())
    except Exception as e:
        logger.error("AXIsProcessTrusted failed: %s", e)
        return False


def _probe_input_stream() -> bool:
    """Probe the mic by actually opening an input stream (exercises TCC gate)."""
    sd = _load_sounddevice()
    if sd is None:
        return False
    try:
        with sd.InputStream(channels=1, dtype="int16"):
            pass
        return True
    except Exception as e:
        logger.warning("Microphone stream probe failed: %s", e)
        return False


def microphone_ok() -> bool:
    """True if the mac Microphone permission is granted (TCC).

    check_input_settings() only probes format support (Pa_IsFormatSupported),
    which succeeds even when the TCC mic permission is denied. We use
    AVFoundation.AVCaptureDevice.authorizationStatus as the primary probe,
    falling back to opening a real InputStream so the TCC gate is exercised.
    """
    if not IS_MAC:
        return True
    try:
        from AVFoundation import (  # type: ignore
            AVCaptureDevice,
            AVMediaTypeAudio,
        )
        # 0=notDetermined, 1=restricted, 2=denied, 3=authorized
        status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
        return int(status) == 3
    except Exception as e:
        logger.debug("AVCaptureDevice mic auth check unavailable: %s", e)
        return _probe_input_stream()


def permission_status() -> PermissionStatus:
    """Snapshot all three permissions."""
    if not IS_MAC:
        return PermissionStatus(True, True, True)
    return PermissionStatus(
        microphone=microphone_ok(),
        accessibility=accessibility_trusted(),
        input_monitoring=input_monitoring_ok(),
    )
