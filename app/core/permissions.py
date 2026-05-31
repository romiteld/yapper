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
    """True if the process may observe global key events (mac Input Monitoring)."""
    if not IS_MAC:
        return True
    listener_cls = _keyboard_listener_cls()
    if listener_cls is None:
        return False
    try:
        return bool(getattr(listener_cls, "IS_TRUSTED", True))
    except Exception as e:
        logger.error("Listener.IS_TRUSTED check failed: %s", e)
        return False


def microphone_ok() -> bool:
    """True if an input stream can be opened (mac Microphone)."""
    if not IS_MAC:
        return True
    sd = _load_sounddevice()
    if sd is None:
        return False
    try:
        sd.check_input_settings()
        return True
    except Exception as e:
        logger.warning("Microphone probe failed: %s", e)
        return False


def permission_status() -> PermissionStatus:
    """Snapshot all three permissions."""
    if not IS_MAC:
        return PermissionStatus(True, True, True)
    return PermissionStatus(
        microphone=microphone_ok(),
        accessibility=accessibility_trusted(),
        input_monitoring=input_monitoring_ok(),
    )
