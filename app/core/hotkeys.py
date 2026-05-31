"""
Yapper Hotkey Manager
=====================
Cross-platform activation key capture via pynput. Supports push-to-talk,
toggle, and a wake-word bridge (key handling disabled; the wake-word listener
drives start/stop elsewhere).

PTT key auto-repeat is guarded by an internal `_active` flag so a held key only
fires on_start once. Ctrl/Alt *combos* are broken on macOS (pynput #297), so the
default activation is a single F-key.

© 2026 Cloudelipute
"""

import threading
from typing import Callable, Optional

from .logger import get_logger

logger = get_logger("hotkeys")

_VALID_MODES = ("push_to_talk", "toggle", "wake_word")


class HotkeyManager:
    """Owns a pynput keyboard.Listener and maps key events to start/stop."""

    def __init__(
        self,
        mode: str,
        hotkey: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ):
        if mode not in _VALID_MODES:
            logger.warning("Unknown mode %r, defaulting to push_to_talk", mode)
            mode = "push_to_talk"
        self.mode = mode
        self.hotkey = hotkey
        self._on_start = on_start
        self._on_stop = on_stop

        self._active = False          # PTT held / toggle currently recording
        self._lock = threading.Lock()
        self._listener = None
        self._target_key = self._parse_hotkey(hotkey)

    # --- listener lifecycle -------------------------------------------------

    def _load_keyboard(self):
        """Lazy import so the module imports on headless CI without pynput."""
        from pynput import keyboard
        return keyboard

    def _parse_hotkey(self, hotkey: str):
        """Resolve a hotkey string to a pynput Key/KeyCode, or None if unknown."""
        try:
            keyboard = self._load_keyboard()
        except Exception:
            logger.debug("pynput unavailable; hotkey parsing deferred")
            return None
        token = hotkey.strip().lower().split("+")[-1]  # ignore combo prefixes
        special = getattr(keyboard.Key, token, None)
        if special is not None:
            return special
        try:
            return keyboard.KeyCode.from_char(token)
        except Exception:
            logger.warning("Could not parse hotkey %r", hotkey)
            return None

    def start(self) -> None:
        """Begin listening for the activation key on a background thread."""
        if self._listener is not None:
            return
        try:
            keyboard = self._load_keyboard()
        except Exception as e:
            logger.error("Cannot start hotkeys (pynput missing): %s", e)
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        logger.info("Hotkey listener started (mode=%s, key=%s)",
                    self.mode, self.hotkey)

    def stop(self) -> None:
        """Stop the listener and reset state."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as e:
                logger.warning("Error stopping listener: %s", e)
            self._listener = None
        self._active = False

    # --- runtime reconfiguration -------------------------------------------

    def set_mode(self, mode: str) -> None:
        if mode not in _VALID_MODES:
            logger.warning("Ignoring invalid mode %r", mode)
            return
        self.mode = mode
        self._active = False
        logger.debug("Hotkey mode set to %s", mode)

    def set_hotkey(self, hotkey: str) -> None:
        self.hotkey = hotkey
        self._target_key = self._parse_hotkey(hotkey)
        self._active = False
        logger.debug("Hotkey set to %s", hotkey)

    # --- key matching -------------------------------------------------------

    def _matches(self, key) -> bool:
        if self._target_key is None:
            return False
        try:
            return key == self._target_key
        except Exception:
            return False

    # --- event handlers (pure, unit-tested directly) ------------------------

    def _on_press(self, key) -> None:
        if self.mode == "wake_word" or not self._matches(key):
            return
        with self._lock:
            if self.mode == "push_to_talk":
                if self._active:
                    return  # auto-repeat guard
                self._active = True
                fire_start = True
                fire_stop = False
            else:  # toggle
                self._active = not self._active
                fire_start = self._active
                fire_stop = not self._active
        if fire_start:
            self._safe(self._on_start)
        if fire_stop:
            self._safe(self._on_stop)

    def _on_release(self, key) -> None:
        if self.mode != "push_to_talk" or not self._matches(key):
            return
        with self._lock:
            if not self._active:
                return
            self._active = False
        self._safe(self._on_stop)

    @staticmethod
    def _safe(callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception as e:  # never let a callback kill the listener thread
            logger.error("Hotkey callback raised: %s", e)
