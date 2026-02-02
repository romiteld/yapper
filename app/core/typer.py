"""
Yapper Text Typer
=================
Cross-platform text typing at cursor position.

Copyright (c) 2026 Cloudelipute
"""

import platform
import time
from typing import Optional

from .logger import get_logger

logger = get_logger("typer")


class TextTyper:
    """
    Types text at the current cursor position.

    Uses the keyboard library on Windows/Linux, or pyautogui as fallback on macOS.

    Example:
        typer = TextTyper()
        success = typer.type_text("Hello, world!")
    """

    def __init__(self, delay_before_typing: float = 0.15):
        """
        Initialize the text typer.

        Args:
            delay_before_typing: Delay in seconds before typing starts.
        """
        self.delay = delay_before_typing
        self._system = platform.system()
        self._keyboard_available = False
        self._pyautogui_available = False

        # Check available libraries
        self._check_libraries()

    def _check_libraries(self) -> None:
        """Check which typing libraries are available."""
        try:
            import keyboard
            self._keyboard_available = True
            logger.debug("keyboard library available")
        except ImportError:
            logger.debug("keyboard library not available")

        try:
            import pyautogui
            self._pyautogui_available = True
            logger.debug("pyautogui library available")
        except ImportError:
            logger.debug("pyautogui library not available")

    def type_text(self, text: str) -> bool:
        """
        Type the given text at the current cursor position.

        Args:
            text: Text to type.

        Returns:
            True if successful, False otherwise.
        """
        if not text:
            logger.warning("No text to type")
            return False

        # Preview for logging
        preview = text[:60] + "..." if len(text) > 60 else text
        logger.info(f"Typing: {preview}")

        # Small delay to ensure focus is on target window
        time.sleep(self.delay)

        # Try keyboard library first (best for Windows/Linux)
        if self._keyboard_available:
            try:
                import keyboard
                keyboard.write(text)
                logger.debug("Typed using keyboard library")
                return True
            except Exception as e:
                logger.warning(f"keyboard.write failed: {e}")
                # Fall through to try other methods

        # Try pyautogui (works on all platforms, especially macOS)
        if self._pyautogui_available:
            try:
                import pyautogui
                # pyautogui.write() doesn't work well with special chars
                # Use typewrite for ASCII, then clipboard for non-ASCII
                if text.isascii():
                    pyautogui.write(text, interval=0.01)
                else:
                    # For non-ASCII, use clipboard
                    self._type_via_clipboard(text)
                logger.debug("Typed using pyautogui")
                return True
            except Exception as e:
                logger.warning(f"pyautogui failed: {e}")

        # Last resort: clipboard paste
        try:
            return self._type_via_clipboard(text)
        except Exception as e:
            logger.error(f"All typing methods failed: {e}")
            return False

    def _type_via_clipboard(self, text: str) -> bool:
        """
        Type text by copying to clipboard and pasting.

        Args:
            text: Text to type.

        Returns:
            True if successful.
        """
        try:
            import pyperclip

            # Save current clipboard
            try:
                original = pyperclip.paste()
            except Exception:
                original = None

            # Copy text to clipboard
            pyperclip.copy(text)

            # Paste using keyboard shortcut
            if self._system == "Darwin":  # macOS
                self._press_hotkey("command", "v")
            else:  # Windows/Linux
                self._press_hotkey("ctrl", "v")

            # Restore original clipboard after a short delay
            if original is not None:
                time.sleep(0.1)
                try:
                    pyperclip.copy(original)
                except Exception:
                    pass

            logger.debug("Typed via clipboard")
            return True

        except ImportError:
            logger.error("pyperclip not available for clipboard typing")
            return False
        except Exception as e:
            logger.error(f"Clipboard typing failed: {e}")
            return False

    def _press_hotkey(self, *keys: str) -> None:
        """Press a keyboard hotkey combination."""
        if self._keyboard_available:
            import keyboard
            keyboard.press_and_release("+".join(keys))
        elif self._pyautogui_available:
            import pyautogui
            pyautogui.hotkey(*keys)

    @staticmethod
    def type_text_static(text: str) -> bool:
        """
        Static method for simple one-off typing.

        Args:
            text: Text to type.

        Returns:
            True if successful.
        """
        return TextTyper().type_text(text)
