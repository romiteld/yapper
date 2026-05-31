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
from typing import Callable, Optional, Set, Tuple

from .logger import get_logger

logger = get_logger("hotkeys")

_VALID_MODES = ("push_to_talk", "toggle", "wake_word")

# Tokens that act as modifiers in a "mod+mod+key" hotkey string. macOS pynput
# ctrl/alt combos are broken (#297), but cmd/shift work — those are the only
# combo entries we ship in constants.HOTKEYS. "command"/"control"/"option"
# aliases are accepted defensively.
_MODIFIER_ALIASES = {
    "cmd": "cmd",
    "command": "cmd",
    "win": "cmd",
    "super": "cmd",
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
}


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
        self._held_modifiers: Set[str] = set()  # canonical mods currently down
        # _required_modifiers is a frozenset of canonical mod names; _target_key
        # is the main pynput Key/KeyCode (or None if unparseable).
        self._required_modifiers, self._target_key = self._parse_hotkey(hotkey)

    # --- listener lifecycle -------------------------------------------------

    def _load_keyboard(self):
        """Lazy import so the module imports on headless CI without pynput."""
        from pynput import keyboard
        return keyboard

    def _parse_hotkey(self, hotkey: str) -> Tuple[frozenset, object]:
        """Resolve a hotkey string into (required_modifiers, main_key).

        Splits on '+': every token but the last that is a known modifier
        (cmd/shift/ctrl/alt and aliases) becomes a required modifier; the final
        token is the main key. Spaces in special-key names (e.g. "scroll lock")
        are normalized to underscores so they resolve to ``Key.scroll_lock``.

        Returns (frozenset_of_canonical_mods, pynput Key/KeyCode or None).
        """
        try:
            keyboard = self._load_keyboard()
        except Exception:
            logger.debug("pynput unavailable; hotkey parsing deferred")
            return frozenset(), None

        tokens = [t.strip().lower() for t in hotkey.split("+") if t.strip()]
        if not tokens:
            logger.warning("Empty hotkey %r", hotkey)
            return frozenset(), None

        main_token = tokens[-1]
        modifiers = set()
        for tok in tokens[:-1]:
            canon = _MODIFIER_ALIASES.get(tok)
            if canon is None:
                logger.warning("Unknown modifier %r in hotkey %r", tok, hotkey)
                continue
            modifiers.add(canon)

        # Normalize spaces in special-key names: "scroll lock" -> "scroll_lock".
        attr = main_token.replace(" ", "_")
        special = getattr(keyboard.Key, attr, None)
        if special is not None:
            return frozenset(modifiers), special
        try:
            return frozenset(modifiers), keyboard.KeyCode.from_char(main_token)
        except Exception:
            logger.warning("Could not parse hotkey %r", hotkey)
            return frozenset(modifiers), None

    @staticmethod
    def _modifier_name(key) -> Optional[str]:
        """Return the canonical modifier name for a pynput key, or None.

        pynput delivers left/right variants (cmd_l, shift_r, …); we strip the
        _l/_r suffix and map to a canonical cmd/shift/ctrl/alt name.
        """
        name = getattr(key, "name", None) or getattr(key, "_name_", None)
        if not name:
            return None
        base = name
        if base.endswith("_l") or base.endswith("_r"):
            base = base[:-2]
        return _MODIFIER_ALIASES.get(base)

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
        with self._lock:
            self._active = False
            self._held_modifiers.clear()

    # --- runtime reconfiguration -------------------------------------------

    def set_mode(self, mode: str) -> None:
        if mode not in _VALID_MODES:
            logger.warning("Ignoring invalid mode %r", mode)
            return
        self.mode = mode
        with self._lock:
            self._active = False
        logger.debug("Hotkey mode set to %s", mode)

    def set_hotkey(self, hotkey: str) -> None:
        self.hotkey = hotkey
        self._required_modifiers, self._target_key = self._parse_hotkey(hotkey)
        with self._lock:
            self._active = False
            self._held_modifiers.clear()
        logger.debug("Hotkey set to %s", hotkey)

    # --- key matching -------------------------------------------------------

    def _is_main_key(self, key) -> bool:
        """True if `key` is the configured main (non-modifier) activation key."""
        if self._target_key is None:
            return False
        try:
            return key == self._target_key
        except Exception:
            return False

    def _modifiers_satisfied(self) -> bool:
        """True if every required modifier is currently held."""
        return self._required_modifiers.issubset(self._held_modifiers)

    # --- event handlers (pure, unit-tested directly) ------------------------

    def _on_press(self, key) -> None:
        # Track modifier state regardless of mode so combos can be detected.
        mod = self._modifier_name(key)
        if mod is not None:
            self._held_modifiers.add(mod)

        if self.mode == "wake_word" or not self._is_main_key(key):
            return
        if not self._modifiers_satisfied():
            return  # main key alone (or wrong combo) — don't fire
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
        # Stop tracking the modifier once released.
        mod = self._modifier_name(key)
        if mod is not None:
            self._held_modifiers.discard(mod)

        if self.mode != "push_to_talk" or not self._is_main_key(key):
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
