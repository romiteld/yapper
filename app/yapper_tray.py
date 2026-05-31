"""
Yapper - System Tray Speech-to-Text
====================================
Speech-to-text that runs in your system tray.

HOW TO USE:
  1. Press F8 (or your configured hotkey) to start recording
  2. Speak your message
  3. Press F8 again to stop and transcribe

© 2026 Cloudelipute
"""

import os
import sys
import platform
import re
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

# Add app directory to path for imports
APP_DIR = Path(__file__).parent.resolve()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Import core components
from core import (
    VERSION,
    COPYRIGHT,
    LANGUAGES,
    Settings,
    AudioRecorder,
    Transcriber,
    TextTyper,
    SoundPlayer,
    VoiceActivityDetector,
    TranscriptionHistory,
    TranscriptionRecord,
    APIClient,
    setup_logging,
    get_logger,
    disable_console_logging,
)

# Icon file locations
ICON_FILE = APP_DIR.parent / "yapper.ico"
if not ICON_FILE.exists():
    ICON_FILE = APP_DIR / "yapper.ico"

# PNG icon for notifications (more reliable with Windows toasts)
ICON_PNG = APP_DIR.parent / "yapper_icon.png"
if not ICON_PNG.exists():
    ICON_PNG = ICON_FILE  # Fallback to ICO

# Initialize logging (disable console for tray mode)
setup_logging()
disable_console_logging()
logger = get_logger("tray")


# =============================================================================
# WAKE WORD LISTENER
# =============================================================================

class WakeWordListener:
    """
    Continuously listens for wake words in short intervals.

    If `fuzzy` is True, the listener uses fuzzy matching to detect the phrases
    "yapper start" and "yapper stop" allowing for mispronunciations.
    """

    def __init__(
        self,
        api_key: str,
        on_start_command,
        on_stop_command,
        interval: int = 3,
        fuzzy: bool = True,
        vad_enabled: bool = True,
        vad_threshold_db: int = -35
    ):
        """
        Initialize the wake word listener.

        Args:
            api_key: OpenAI API key.
            on_start_command: Callback when "Yapper start" is detected.
            on_stop_command: Callback when "Yapper stop" is detected.
            interval: Seconds between wake word checks.
            fuzzy: Enable fuzzy matching for wake words.
            vad_enabled: Enable voice activity detection.
            vad_threshold_db: VAD threshold in dB.
        """
        self.api_key = api_key
        self.on_start_command = on_start_command
        self.on_stop_command = on_stop_command
        self.interval = interval
        self.fuzzy = fuzzy

        # VAD for reducing API calls
        self.vad = VoiceActivityDetector(
            threshold_db=vad_threshold_db
        ) if vad_enabled else None

        self.is_listening = False
        self.is_paused = False
        self._listen_thread = None
        self._api_client = APIClient(api_key=api_key)

    def start(self):
        """Start listening for wake words."""
        if self.is_listening:
            return

        self.is_listening = True
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="WakeWordListener"
        )
        self._listen_thread.start()
        logger.info("Wake word listener started")

    def stop(self):
        """Stop listening for wake words."""
        self.is_listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
            self._listen_thread = None
        logger.info("Wake word listener stopped")

    def pause(self):
        """Pause listening (while recording)."""
        self.is_paused = True

    def resume(self):
        """Resume listening."""
        self.is_paused = False

    def _is_start_command(self, text: str) -> bool:
        """Check if text is a start command."""
        patterns = [
            r"\byapper[\s,]*start\b",
            r"\byap\s*or\s*start\b",
            r"\byap\s*er\s*start\b",
        ]
        for pat in patterns:
            if re.search(pat, text):
                return True

        if self.fuzzy:
            sanitized = re.sub(r"[^a-z]+", " ", text).strip()
            ratio = SequenceMatcher(None, sanitized, "yapper start").ratio()
            if ratio > 0.75:
                return True

        return False

    def _is_stop_command(self, text: str) -> bool:
        """Check if text is a stop command."""
        patterns = [
            r"\byapper[\s,]*stop\b",
            r"\byap\s*or\s*stop\b",
            r"\byap\s*er\s*stop\b",
        ]
        for pat in patterns:
            if re.search(pat, text):
                return True

        if self.fuzzy:
            sanitized = re.sub(r"[^a-z]+", " ", text).strip()
            ratio = SequenceMatcher(None, sanitized, "yapper stop").ratio()
            if ratio > 0.75:
                return True

        return False

    def _listen_loop(self):
        """Main listening loop."""
        while self.is_listening:
            if self.is_paused:
                time.sleep(0.5)
                continue

            try:
                # Record a short clip
                recorder = AudioRecorder()
                if not recorder.start():
                    time.sleep(1)
                    continue

                time.sleep(self.interval)
                audio_path = recorder.stop()

                if not audio_path:
                    continue

                # Check VAD before API call
                if self.vad and recorder.frames:
                    has_speech = self.vad.has_speech(recorder.frames)
                    if not has_speech:
                        logger.debug("No speech detected, skipping API call")
                        try:
                            os.unlink(audio_path)
                        except OSError:
                            pass
                        continue

                # Transcribe and check for wake words
                try:
                    text = self._api_client.transcribe(audio_path)

                    if text:
                        text_lower = text.lower().strip()
                        logger.debug(f"Wake word check: '{text_lower}'")

                        if self._is_start_command(text_lower):
                            logger.info("Start command detected")
                            self.on_start_command()
                        elif self._is_stop_command(text_lower):
                            logger.info("Stop command detected")
                            self.on_stop_command()

                except Exception as e:
                    logger.error(f"Transcription error in wake word: {e}")

                # Clean up
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass

            except Exception as e:
                logger.error(f"Wake word listener error: {e}")
                time.sleep(1)


# =============================================================================
# SYSTEM TRAY APPLICATION
# =============================================================================

class YapperTray:
    """System tray application for Yapper."""

    def __init__(self):
        """Initialize the tray application."""
        self.settings = Settings()
        self.settings.load()
        self._data = self.settings.as_dict()

        self.recorder = None
        self.transcriber = None
        self.sounds = SoundPlayer(enabled=self._data.get("audio_feedback", True))
        self.history = TranscriptionHistory(enabled=self._data.get("save_history", True))

        self.is_recording = False
        self.processing = False
        self.icon = None
        self._last_hotkey_time = 0  # Debounce for hotkey

        # Initialize transcriber if API key is set
        if self._data.get("api_key"):
            self._init_transcriber()

    def _init_transcriber(self):
        """Initialize the transcriber with current settings."""
        from core import Vocabulary
        # Start with the built-in starter pack, then layer the user's terms.
        vocab = Vocabulary()
        for entry in self._data.get("vocabulary", []) or []:
            if isinstance(entry, str):
                vocab.add(entry)
            elif isinstance(entry, dict) and entry.get("typed"):
                vocab.add(entry["typed"], said=entry.get("said"))
        self.transcriber = Transcriber(
            api_key=self._data["api_key"],
            language_hint=self._data.get("language_hint", ""),
            translate_to=self._data.get("translate_to", ""),
            fix_grammar=self._data.get("fix_grammar", True),
            output_mode=self._data.get("output_mode", "clean"),
            expand_spoken_symbols=self._data.get("expand_spoken_symbols", True),
            vocabulary=vocab,
            clean_wake_words=True  # Clean wake words in tray mode
        )

    def create_icon_image(self, state: str = "idle"):
        """
        Create tray icon image.

        Args:
            state: "idle", "listening", or "recording"

        Returns:
            PIL Image object.
        """
        try:
            from PIL import Image

            if ICON_FILE.exists():
                img = Image.open(str(ICON_FILE))
                img = img.resize((64, 64), Image.Resampling.LANCZOS)

                if state == "recording":
                    # Red tint for recording
                    img = img.convert("RGBA")
                    pixels = img.load()
                    for i in range(img.size[0]):
                        for j in range(img.size[1]):
                            r, g, b, a = pixels[i, j]
                            pixels[i, j] = (min(255, r + 100), g // 2, b // 2, a)

                return img
            else:
                colors = {
                    "idle": (0, 150, 255),
                    "listening": (0, 200, 100),
                    "recording": (255, 0, 0)
                }
                return Image.new('RGB', (64, 64), colors.get(state, (0, 150, 255)))

        except ImportError:
            from PIL import Image
            return Image.new('RGB', (64, 64), (0, 150, 255))
        except Exception as e:
            logger.error(f"Error creating icon: {e}")
            from PIL import Image
            return Image.new('RGB', (64, 64), (0, 150, 255))

    def start_recording(self):
        """Start recording audio."""
        if self.is_recording or self.processing:
            return

        if not self.transcriber:
            self.show_notification("No API Key", "Please set your API key")
            return

        self.is_recording = True
        self.recorder = AudioRecorder(
            device_index=self._data.get("audio_device_index")
        )
        self.sounds.start_recording()

        if self.recorder.start():
            self.update_icon("recording")
            self.show_notification("Recording", "Speak now... Press hotkey when done")
            logger.info("Recording started")
        else:
            self.is_recording = False
            self.sounds.error()
            self.show_notification("Error", "Could not start recording")
            logger.error("Failed to start recording")

    def stop_recording(self):
        """Stop recording and process audio."""
        if not self.is_recording:
            return

        self.is_recording = False
        self.processing = True
        self.sounds.stop_recording()
        self.update_icon("idle")

        audio_path = self.recorder.stop() if self.recorder else None
        logger.info(f"Recording stopped, audio: {audio_path}")

        if audio_path:
            # Check VAD before processing
            vad_enabled = self._data.get("vad_enabled", True)
            if vad_enabled and self.recorder and self.recorder.frames:
                vad = VoiceActivityDetector(
                    threshold_db=self._data.get("vad_threshold_db", -45)
                )
                if not vad.has_speech(self.recorder.frames):
                    logger.info("No speech detected, skipping")
                    self.show_notification("No Speech", "No speech detected")
                    self.processing = False
                    try:
                        os.unlink(audio_path)
                    except OSError:
                        pass
                    return

            thread = threading.Thread(
                target=self._process_audio,
                args=(audio_path,),
                daemon=True
            )
            thread.start()
        else:
            self.processing = False

    def _process_audio(self, audio_path: str):
        """Process recorded audio."""
        try:
            self.show_notification("Processing", "Transcribing audio...")
            text = self.transcriber.transcribe(audio_path)

            if text:
                typer = TextTyper()
                logger.info(f"About to type text: {text[:50]}...")
                success = typer.type_text(text)
                logger.info(f"Type result: {success}")

                if success:
                    self.sounds.success()
                    preview = text[:40] + "..." if len(text) > 40 else text
                    self.show_notification("Done", preview)
                    logger.info(f"Typed: {preview}")

                    # Save to history
                    if self.history.enabled and self.recorder:
                        record = TranscriptionRecord.create(
                            text=text,
                            duration=self.recorder.duration_seconds,
                            translated=bool(self._data.get("translate_to")),
                            target_lang=self._data.get("translate_to", ""),
                            grammar_fixed=self._data.get("fix_grammar", True),
                        )
                        self.history.add(record)
                else:
                    self.sounds.error()
                    self.show_notification("Type Failed", "Could not type text - check admin rights")
                    logger.error("TextTyper.type_text returned False")
            else:
                self.show_notification("Empty", "No speech detected")
                logger.warning("Empty transcription")

        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            self.sounds.error()
            self.show_notification("Error", str(e)[:50])

        finally:
            self.processing = False

    def toggle_recording(self):
        """Toggle recording on/off."""
        # Debounce - ignore if triggered within 500ms
        current_time = time.time()
        if current_time - self._last_hotkey_time < 0.5:
            logger.debug("Hotkey debounced")
            return
        self._last_hotkey_time = current_time

        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def update_icon(self, state: str = "idle"):
        """Update tray icon based on state."""
        if self.icon:
            try:
                self.icon.icon = self.create_icon_image(state)
                hotkey = self._data.get("hotkey", "F8").upper()
                titles = {
                    "idle": f"Yapper - Press {hotkey} to record",
                    "recording": f"Yapper - RECORDING (press {hotkey} to stop)",
                }
                self.icon.title = titles.get(state, "Yapper")
            except Exception as e:
                logger.error(f"Error updating icon: {e}")

    def show_notification(self, title: str, message: str):
        """Show a custom pink notification with white text."""
        logger.debug(f"Notification: {title} - {message}")
        try:
            if platform.system() == "Windows":
                import subprocess
                icon_path = str(ICON_PNG).replace("\\", "/")

                # Escape quotes in message for PowerShell
                safe_title = title.replace('"', '`"').replace("'", "''")
                safe_message = message.replace('"', '`"').replace("'", "''")

                # Custom Windows Forms notification - pink background, white text
                ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.BackColor = [System.Drawing.Color]::FromArgb(233, 30, 140)
$form.Size = New-Object System.Drawing.Size(340, 80)
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$form.TopMost = $true
$form.ShowInTaskbar = $false

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(($screen.Right - 350), ($screen.Bottom - 90))

try {{
    $icon = [System.Drawing.Image]::FromFile("{icon_path}")
    $picBox = New-Object System.Windows.Forms.PictureBox
    $picBox.Image = $icon
    $picBox.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
    $picBox.Size = New-Object System.Drawing.Size(50, 50)
    $picBox.Location = New-Object System.Drawing.Point(10, 15)
    $form.Controls.Add($picBox)
}} catch {{}}

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "{safe_title}"
$titleLabel.ForeColor = [System.Drawing.Color]::White
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$titleLabel.AutoSize = $true
$titleLabel.Location = New-Object System.Drawing.Point(70, 12)
$form.Controls.Add($titleLabel)

$msgLabel = New-Object System.Windows.Forms.Label
$msgLabel.Text = "{safe_message}"
$msgLabel.ForeColor = [System.Drawing.Color]::White
$msgLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$msgLabel.AutoSize = $true
$msgLabel.MaximumSize = New-Object System.Drawing.Size(250, 0)
$msgLabel.Location = New-Object System.Drawing.Point(70, 38)
$form.Controls.Add($msgLabel)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.Add_Tick({{ $form.Close() }})
$timer.Start()

$form.Add_Click({{ $form.Close() }})
$form.ShowDialog() | Out-Null
'''
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
                )
            elif self.icon:
                self.icon.notify(message, title)
        except Exception as e:
            logger.error(f"Notification error: {e}")
            # Fallback to tray notification
            if self.icon:
                try:
                    self.icon.notify(message, title)
                except Exception as e2:
                    logger.error(f"Fallback notification also failed: {e2}")

    def set_language(self, lang_code: str):
        """Set the translation language."""
        self._data["translate_to"] = lang_code
        self.settings.set("translate_to", lang_code)
        self.settings.save()

        if self.transcriber:
            self.transcriber.translate_to = lang_code

        lang_name = LANGUAGES.get(lang_code, "Off") if lang_code else "Off"
        self.show_notification("Language", f"Output: {lang_name}")
        self.rebuild_menu()
        logger.info(f"Language set to: {lang_code}")

    def toggle_grammar(self):
        """Toggle grammar correction."""
        current = bool(self._data.get("fix_grammar", True))
        new_value = not current

        self._data["fix_grammar"] = new_value
        self.settings.set("fix_grammar", new_value)
        self.settings.save()

        if self.transcriber:
            self.transcriber.fix_grammar = new_value

        state_text = "On" if new_value else "Off"
        self.show_notification("Grammar", f"Grammar correction: {state_text}")
        self.rebuild_menu()
        logger.info(f"Grammar correction: {state_text}")

    def toggle_vad(self):
        """Toggle voice activity detection."""
        current = bool(self._data.get("vad_enabled", True))
        new_val = not current

        self._data["vad_enabled"] = new_val
        self.settings.set("vad_enabled", new_val)
        self.settings.save()

        state_text = "On" if new_val else "Off"
        self.show_notification("VAD", f"Voice activity detection: {state_text}")
        self.rebuild_menu()
        logger.info(f"VAD: {state_text}")

    def rebuild_menu(self):
        """Rebuild the tray menu."""
        if self.icon:
            try:
                self.icon.menu = self.create_menu()
            except Exception as e:
                logger.error(f"Error rebuilding menu: {e}")

    def open_settings(self):
        """Open the settings UI."""
        import subprocess
        settings_path = APP_DIR / "settings_ui.py"

        if settings_path.exists():
            try:
                system = platform.system()
                if system == "Windows":
                    # Use pythonw to avoid console window, or python if not available
                    python_dir = Path(sys.executable).parent
                    pythonw = python_dir / "pythonw.exe"
                    if pythonw.exists():
                        subprocess.Popen([str(pythonw), str(settings_path)])
                    else:
                        subprocess.Popen([sys.executable, str(settings_path)])
                elif system == "Darwin":
                    subprocess.Popen([sys.executable, str(settings_path)])
                else:
                    subprocess.Popen([sys.executable, str(settings_path)])
                logger.info("Opened settings UI")
            except Exception as e:
                logger.error(f"Could not open settings: {e}")

    def reload_settings(self):
        """Reload settings from file."""
        self.settings.load()
        self._data = self.settings.as_dict()

        if self._data.get("api_key"):
            self._init_transcriber()
            self.show_notification("Reloaded", "Settings updated")
            self.setup_hotkey()

        # Update sound player
        self.sounds.enabled = self._data.get("audio_feedback", True)

        # Update history
        self.history.enabled = self._data.get("save_history", True)

        self.rebuild_menu()
        logger.info("Settings reloaded")

    def quit_app(self):
        """Quit the application."""
        logger.info("Quitting application")

        if self.recorder:
            self.recorder.cleanup()

        if self.icon:
            self.icon.stop()

    def setup_hotkey(self):
        """Setup the recording hotkey."""
        try:
            import keyboard
            keyboard.unhook_all()
            hotkey = self._data.get("hotkey", "f8")
            keyboard.on_press_key(hotkey, lambda _: self.toggle_recording())
            logger.info(f"Hotkey registered: {hotkey}")
        except ImportError:
            logger.warning("keyboard library not available")
        except Exception as e:
            logger.error(f"Could not setup hotkey: {e}")

    def create_menu(self):
        """Create the tray menu."""
        import pystray
        from pystray import MenuItem as item

        hotkey = self._data.get("hotkey", "f8").upper()
        current_lang = self._data.get("translate_to", "")

        def make_lang_setter(code):
            return lambda: self.set_language(code)

        def is_lang_checked(code):
            return lambda item: self._data.get("translate_to", "") == code

        lang_items = [
            item(name, make_lang_setter(code), checked=is_lang_checked(code))
            for code, name in LANGUAGES.items()
        ]

        def grammar_checked(_):
            return bool(self._data.get("fix_grammar", True))

        def fuzzy_checked(_):
            return bool(self._data.get("wake_word_fuzzy", True))

        def vad_checked(_):
            return bool(self._data.get("vad_enabled", True))

        return pystray.Menu(
            item(f'Start Recording ({hotkey})', lambda: self.start_recording()),
            item('Stop & Type', lambda: self.stop_recording()),
            pystray.Menu.SEPARATOR,
            item('Output Language', pystray.Menu(*lang_items)),
            item('Grammar Correction', lambda: self.toggle_grammar(), checked=grammar_checked),
            item('Voice Activity Detection', lambda: self.toggle_vad(), checked=vad_checked),
            pystray.Menu.SEPARATOR,
            item('View History', lambda: self.open_history()),
            item('Settings', lambda: self.open_settings()),
            item('Reload Settings', lambda: self.reload_settings()),
            pystray.Menu.SEPARATOR,
            item('Exit', lambda: self.quit_app())
        )

    def open_history(self):
        """Open the transcription history folder."""
        import subprocess
        history_dir = APP_DIR.parent / "logs"
        history_dir.mkdir(parents=True, exist_ok=True)

        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(history_dir)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(history_dir)])
        else:
            subprocess.Popen(["xdg-open", str(history_dir)])

    def run(self):
        """Run the tray application."""
        # Check for required packages
        try:
            import pystray
        except ImportError:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pystray", "-q"])
            import pystray

        try:
            from PIL import Image
        except ImportError:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])

        # First-time setup
        if not self._data.get("api_key"):
            self.first_time_setup()
            self.settings.load()
            self._data = self.settings.as_dict()

            if self._data.get("api_key"):
                self._init_transcriber()

        # Setup hotkey
        self.setup_hotkey()

        # Create tray icon
        hotkey = self._data.get("hotkey", "F8").upper()
        self.icon = pystray.Icon(
            "Yapper",
            self.create_icon_image("idle"),
            f"Yapper - Press {hotkey} to record",
            self.create_menu()
        )

        self.show_notification("Yapper Ready", f"Press {hotkey} to start recording")
        logger.info(f"Yapper Tray v{VERSION} started")
        self.icon.run()

    def first_time_setup(self):
        """Run first-time setup."""
        import subprocess
        settings_path = APP_DIR / "settings_console.py"

        if settings_path.exists():
            try:
                subprocess.run([sys.executable, str(settings_path)])
            except Exception as e:
                logger.error(f"First-time setup error: {e}")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    app = YapperTray()
    app.run()


if __name__ == "__main__":
    main()
