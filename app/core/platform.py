"""
Yapper Platform Helpers
=======================
OS detection (`IS_MAC`/`IS_WIN`/`IS_LINUX`), per-OS default hotkey,
open-System-Settings deep links, open-folder helper.

© 2026 Cloudelipute
"""

import platform as _platform
import subprocess
from typing import Final

from .logger import get_logger

logger = get_logger("platform")

_SYSTEM: Final[str] = _platform.system()

IS_MAC: Final[bool] = _SYSTEM == "Darwin"
IS_WIN: Final[bool] = _SYSTEM == "Windows"
IS_LINUX: Final[bool] = _SYSTEM == "Linux"

# macOS System Settings deep links (Ventura+ "x-apple.systempreferences" URLs).
_MAC_SETTINGS_PANES = {
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


def default_hotkey() -> str:
    """Return the default activation key for the current OS.

    A single F-key is used everywhere: pynput Ctrl/Alt *combos* are broken on
    macOS (pynput issue #297), and F8 is safe and unused on Win/Mac/Linux.
    """
    return "f8"


def open_settings_pane(pane: str) -> bool:
    """Open a macOS System Settings privacy pane. No-op (False) off macOS.

    Args:
        pane: one of 'accessibility', 'input_monitoring', 'microphone'.
    """
    if not IS_MAC:
        return False
    url = _MAC_SETTINGS_PANES.get(pane)
    if not url:
        logger.warning("Unknown settings pane: %s", pane)
        return False
    try:
        subprocess.run(["open", url], check=False)
        return True
    except OSError as e:
        logger.error("Failed to open settings pane %s: %s", pane, e)
        return False


def open_folder(path: str) -> bool:
    """Reveal a folder in the OS file manager. Returns True on success."""
    try:
        if IS_MAC:
            subprocess.run(["open", path], check=False)
        elif IS_WIN:
            subprocess.run(["explorer", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except OSError as e:
        logger.error("Failed to open folder %s: %s", path, e)
        return False
