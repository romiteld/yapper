"""
Yapper Audio Feedback
=====================
Cross-platform audio feedback sounds.

© 2026 Cloudelipute
"""

import platform
import threading
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("sounds")


class SoundPlayer:
    """
    Cross-platform audio feedback player.

    Uses winsound on Windows, afplay on macOS, and aplay/paplay on Linux.
    Falls back to console bell if no audio system is available.

    Example:
        player = SoundPlayer()
        player.start_recording()  # Play start sound
        player.stop_recording()   # Play stop sound
    """

    # Default frequencies for generated beeps (Windows) - soft, subtle tones
    FREQ_START = 440     # Hz - gentle A4 note
    FREQ_STOP = 330      # Hz - soft E4 note
    FREQ_SUCCESS = 523   # Hz - pleasant C5 note
    FREQ_ERROR = 262     # Hz - low C4 note

    # Default durations in milliseconds - short and unobtrusive
    DURATION_SHORT = 50
    DURATION_MEDIUM = 75
    DURATION_LONG = 100

    def __init__(
        self,
        enabled: bool = True,
        sounds_dir: Optional[Path] = None
    ):
        """
        Initialize the sound player.

        Args:
            enabled: Whether audio feedback is enabled.
            sounds_dir: Optional directory containing custom WAV files.
        """
        self.enabled = enabled
        self._system = platform.system()
        self._sounds_dir = sounds_dir

        # Check for custom sound files
        self._custom_sounds = {}
        if sounds_dir and sounds_dir.exists():
            self._load_custom_sounds(sounds_dir)

    def _load_custom_sounds(self, sounds_dir: Path) -> None:
        """Load custom WAV files from directory."""
        sound_names = ["start", "stop", "success", "error"]
        for name in sound_names:
            wav_path = sounds_dir / f"{name}.wav"
            if wav_path.exists():
                self._custom_sounds[name] = wav_path
                logger.debug(f"Loaded custom sound: {wav_path}")

    def start_recording(self) -> None:
        """Play sound indicating recording has started."""
        self._play("start", self.FREQ_START, self.DURATION_SHORT)

    def stop_recording(self) -> None:
        """Play sound indicating recording has stopped."""
        self._play("stop", self.FREQ_STOP, self.DURATION_SHORT)

    def success(self) -> None:
        """Play success sound."""
        self._play("success", self.FREQ_SUCCESS, self.DURATION_MEDIUM)

    def error(self) -> None:
        """Play error sound."""
        self._play("error", self.FREQ_ERROR, self.DURATION_LONG)

    def _play(self, sound_name: str, frequency: int, duration: int) -> None:
        """
        Play a sound (custom file or generated beep).

        Args:
            sound_name: Name of the sound ('start', 'stop', 'success', 'error').
            frequency: Fallback frequency for generated beep (Hz).
            duration: Fallback duration for generated beep (ms).
        """
        if not self.enabled:
            return

        # Run in background thread to avoid blocking
        thread = threading.Thread(
            target=self._play_sound,
            args=(sound_name, frequency, duration),
            daemon=True
        )
        thread.start()

    def _play_sound(self, sound_name: str, frequency: int, duration: int) -> None:
        """Internal sound playing (runs in thread)."""
        try:
            # Try custom sound file first
            if sound_name in self._custom_sounds:
                self._play_wav(self._custom_sounds[sound_name])
                return

            # Fall back to system-specific beep
            if self._system == "Windows":
                self._play_windows_beep(frequency, duration)
            elif self._system == "Darwin":  # macOS
                self._play_macos_beep(frequency, duration)
            else:  # Linux
                self._play_linux_beep(frequency, duration)

        except Exception as e:
            logger.debug(f"Sound playback failed: {e}")
            # Silent fail - audio feedback is not critical

    def _play_wav(self, wav_path: Path) -> None:
        """Play a WAV file."""
        try:
            if self._system == "Windows":
                import winsound
                winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC)

            elif self._system == "Darwin":
                import subprocess
                subprocess.run(
                    ["afplay", str(wav_path)],
                    capture_output=True,
                    timeout=5
                )

            else:  # Linux
                import subprocess
                # Try different audio players; advance to the next on any failure.
                for player in ["paplay", "aplay", "play"]:
                    try:
                        subprocess.run(
                            [player, str(wav_path)],
                            capture_output=True,
                            timeout=5,
                            check=True,
                        )
                        break  # success
                    except FileNotFoundError:
                        continue  # player not installed
                    except subprocess.SubprocessError:
                        # CalledProcessError (non-zero exit) or TimeoutExpired
                        continue  # this player failed/hung, try the next

        except Exception as e:
            logger.debug(f"WAV playback failed: {e}")

    def _play_windows_beep(self, frequency: int, duration: int) -> None:
        """Play a beep on Windows using winsound."""
        try:
            import winsound
            winsound.Beep(frequency, duration)
        except Exception as e:
            logger.debug(f"Windows beep failed: {e}")
            self._play_console_bell()

    def _play_macos_beep(self, frequency: int, duration: int) -> None:
        """Play a beep on macOS using afplay or system sound."""
        try:
            import subprocess
            # Generate a simple tone using say command (always available)
            # or use the system beep
            subprocess.run(
                ["osascript", "-e", "beep"],
                capture_output=True,
                timeout=2
            )
        except Exception as e:
            logger.debug(f"macOS beep failed: {e}")
            self._play_console_bell()

    def _play_linux_beep(self, frequency: int, duration: int) -> None:
        """Play a beep on Linux."""
        try:
            import subprocess

            # Try speaker-test first (most reliable)
            try:
                subprocess.run(
                    ["speaker-test", "-t", "sine", "-f", str(frequency),
                     "-l", "1", "-p", str(duration // 1000 + 1)],
                    capture_output=True,
                    timeout=2
                )
                return
            except FileNotFoundError:
                pass

            # Try beep command
            try:
                subprocess.run(
                    ["beep", "-f", str(frequency), "-l", str(duration)],
                    capture_output=True,
                    timeout=2
                )
                return
            except FileNotFoundError:
                pass

            # Try paplay with generated sound
            try:
                # Use a simple audio file or the console bell
                subprocess.run(
                    ["paplay", "/usr/share/sounds/freedesktop/stereo/message.oga"],
                    capture_output=True,
                    timeout=2
                )
                return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Fall back to console bell
            self._play_console_bell()

        except Exception as e:
            logger.debug(f"Linux beep failed: {e}")
            self._play_console_bell()

    def _play_console_bell(self) -> None:
        """Play console bell as last resort."""
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass
