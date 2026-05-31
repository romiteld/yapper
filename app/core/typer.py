"""
Yapper Text Typer
=================
Insert text at the current cursor position.

Primary method: clipboard paste (Cmd/Ctrl+V) — Unicode/emoji/CJK-safe — with
the original clipboard restored ~1.5 s later on a daemon thread so the paste
target has time to read it. Fallback method: pynput Controller().type().

On macOS, injection silently no-ops without Accessibility, so we check
permissions first and refuse rather than appear to succeed.

© 2026 Cloudelipute
"""

import threading
import time
from typing import Optional

from .logger import get_logger
from .platform import IS_MAC

logger = get_logger("typer")


class TextTyper:
    """Types text at the cursor via clipboard paste (default) or pynput type."""

    def __init__(
        self,
        delay_before_typing: float = 0.15,
        clipboard_restore_delay: float = 1.5,
    ):
        """
        Args:
            delay_before_typing: pause before injecting (lets focus settle).
            clipboard_restore_delay: seconds before the original clipboard is
                restored on a background daemon thread.
        """
        self.delay = delay_before_typing
        self.clipboard_restore_delay = clipboard_restore_delay

    # --- lazy imports (keep headless CI import-clean) -----------------------

    def _load_pyperclip(self):
        import pyperclip
        return pyperclip

    def _load_keyboard(self):
        from pynput import keyboard
        return keyboard

    # --- permission gate ----------------------------------------------------

    def _accessibility_ok(self) -> bool:
        from .permissions import accessibility_trusted
        return accessibility_trusted()

    # --- public API ---------------------------------------------------------

    def type_text(self, text: str, method: str = "paste") -> bool:
        """Insert `text` at the cursor.

        Args:
            text: text to insert.
            method: 'paste' (clipboard) or 'type' (pynput keystrokes).

        Returns:
            True on success, False otherwise.
        """
        if not text:
            logger.warning("No text to type")
            return False

        if IS_MAC and not self._accessibility_ok():
            logger.error(
                "Accessibility not granted; cannot inject text. "
                "Grant it in System Settings and relaunch Yapper."
            )
            return False

        preview = text[:60] + "..." if len(text) > 60 else text
        logger.info("Inserting (%s): %s", method, preview)

        if self.delay:
            time.sleep(self.delay)

        if method == "type":
            return self._type_via_pynput(text)
        if self._paste(text):
            return True
        logger.warning("Paste failed; falling back to pynput type")
        return self._type_via_pynput(text)

    # --- paste implementation ----------------------------------------------

    def _paste(self, text: str) -> bool:
        try:
            pyperclip = self._load_pyperclip()
            keyboard = self._load_keyboard()
        except Exception as e:
            logger.error("Paste deps unavailable: %s", e)
            return False

        try:
            original = pyperclip.paste()
        except Exception:
            original = None

        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error("Could not set clipboard: %s", e)
            return False

        try:
            controller = keyboard.Controller()
            modifier = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl
            controller.press(modifier)
            controller.press("v")
            controller.release("v")
            controller.release(modifier)
        except Exception as e:
            logger.error("Paste keystroke failed: %s", e)
            return False

        self._schedule_clipboard_restore(pyperclip, original)
        logger.debug("Pasted via clipboard")
        return True

    def _schedule_clipboard_restore(self, pyperclip, original) -> None:
        # Skip restore when the clipboard was empty/None: there's nothing worth
        # preserving, and re-copying "" ~1.5s later could clobber a fresh copy
        # the user made during the window.
        if not original:
            return

        def _restore():
            time.sleep(self.clipboard_restore_delay)
            try:
                pyperclip.copy(original)
            except Exception as e:
                logger.debug("Clipboard restore failed: %s", e)

        threading.Thread(target=_restore, daemon=True,
                         name="ClipboardRestore").start()

    # --- pynput fallback ----------------------------------------------------

    def _type_via_pynput(self, text: str) -> bool:
        try:
            keyboard = self._load_keyboard()
            keyboard.Controller().type(text)
            logger.debug("Typed via pynput Controller().type()")
            return True
        except Exception as e:
            logger.error("pynput type failed: %s", e)
            return False

    @staticmethod
    def type_text_static(text: str) -> bool:
        """Static method for simple one-off typing."""
        return TextTyper().type_text(text)
