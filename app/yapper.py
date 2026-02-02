#!/usr/bin/env python3
"""
Yapper - Speech-to-Text Tool (Console Mode)
============================================
A cross-platform speech-to-text application that transcribes your voice
and types the text wherever your cursor is positioned.

Features:
    - Press hotkey to start/stop recording
    - Excellent grammar and spelling with OpenAI Whisper
    - Translate your speech to any language
    - Voice activity detection to reduce API costs
    - Easy configuration via settings.json

Copyright (c) 2026 Cloudelipute
"""

import os
import sys
import platform
import threading
from pathlib import Path

# Add app directory to path for imports
APP_DIR = Path(__file__).parent.resolve()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# =============================================================================
# DEPENDENCY CHECK
# =============================================================================

def check_dependencies():
    """Check and provide guidance for missing dependencies."""
    missing = []

    try:
        import pyaudio
    except ImportError:
        missing.append("pyaudio")

    try:
        import keyboard
    except ImportError:
        missing.append("keyboard")

    try:
        import openai
    except ImportError:
        missing.append("openai")

    if missing:
        print("\n  Missing dependencies. Please install them:")
        print(f"    pip install {' '.join(missing)}")
        if "pyaudio" in missing:
            system = platform.system()
            if system == "Windows":
                print("\n  For PyAudio on Windows, you may need:")
                print("    pip install pipwin")
                print("    pipwin install pyaudio")
            elif system == "Darwin":
                print("\n  For PyAudio on macOS:")
                print("    brew install portaudio")
                print("    pip install pyaudio")
            else:
                print("\n  For PyAudio on Linux, first install:")
                print("    sudo apt-get install python3-pyaudio portaudio19-dev")
        sys.exit(1)

check_dependencies()

# Now import core components
from core import (
    VERSION,
    COPYRIGHT,
    Settings,
    AudioRecorder,
    Transcriber,
    TextTyper,
    SoundPlayer,
    VoiceActivityDetector,
    TranscriptionHistory,
    TranscriptionRecord,
    setup_logging,
    get_logger,
)

import keyboard

# Initialize logging
setup_logging()
logger = get_logger("main")


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class Yapper:
    """Main console application class."""

    def __init__(self, settings: Settings):
        """
        Initialize Yapper with settings.

        Args:
            settings: Loaded Settings instance.
        """
        self.settings = settings
        self._data = settings.as_dict()

        # Core components
        self.recorder = AudioRecorder(
            device_index=self._data.get("audio_device_index")
        )
        self.transcriber = Transcriber(
            api_key=self._data["api_key"],
            language_hint=self._data.get("language_hint", ""),
            translate_to=self._data.get("translate_to", ""),
            fix_grammar=self._data.get("fix_grammar", True),
            clean_wake_words=False  # Console mode doesn't use wake words
        )
        self.typer = TextTyper()

        # Optional components
        self.sounds = SoundPlayer(
            enabled=self._data.get("audio_feedback", True)
        )
        self.vad = VoiceActivityDetector(
            threshold_db=self._data.get("vad_threshold_db", -35)
        ) if self._data.get("vad_enabled", True) else None

        self.history = TranscriptionHistory(
            enabled=self._data.get("save_history", False)
        )

        # State
        self.is_recording = False
        self.processing = False

    def toggle_recording(self):
        """Toggle recording on/off."""
        if self.processing:
            print("  ... Still processing previous recording...")
            return

        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        """Start recording audio."""
        self.is_recording = True
        self.sounds.start_recording()

        if self.recorder.start():
            hotkey = self._data["hotkey"].upper()
            print(f"\n  Recording... (Press {hotkey} to stop)")
        else:
            print("  Error: Could not start recording")
            self.sounds.error()
            self.is_recording = False

    def _stop_recording(self):
        """Stop recording and process audio."""
        self.is_recording = False
        self.processing = True
        self.sounds.stop_recording()

        audio_path = self.recorder.stop()

        if audio_path:
            # Check for voice activity if VAD is enabled
            if self.vad and self.recorder.frames:
                has_speech = self.vad.has_speech(self.recorder.frames)
                if not has_speech:
                    print("  No speech detected, skipping API call")
                    self.processing = False
                    try:
                        os.unlink(audio_path)
                    except OSError:
                        pass
                    return

            # Process in background thread
            thread = threading.Thread(
                target=self._process_audio,
                args=(audio_path,),
                daemon=True
            )
            thread.start()
        else:
            print("  Warning: No audio recorded")
            self.processing = False

    def _process_audio(self, audio_path: str):
        """Process recorded audio (transcribe and type)."""
        try:
            print("  Transcribing...")
            text = self.transcriber.transcribe(audio_path)

            if text:
                # Type the text
                preview = text[:60] + "..." if len(text) > 60 else text
                print(f"  Typing: {preview}")

                if self.typer.type_text(text):
                    self.sounds.success()
                    print("  Done!")

                    # Save to history
                    if self.history.enabled:
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
                    print("  Error: Could not type text")
            else:
                print("  Warning: Transcription returned empty result")

        except Exception as e:
            logger.error(f"Processing error: {e}")
            self.sounds.error()
            print(f"  Error: {e}")

        finally:
            self.processing = False

    def run(self):
        """Run the Yapper application."""
        self._print_banner()

        # Register hotkey
        hotkey = self._data["hotkey"]
        keyboard.on_press_key(hotkey, lambda _: self.toggle_recording())
        logger.info(f"Registered hotkey: {hotkey}")

        # Register settings hotkey
        keyboard.on_press_key('s', lambda _: self._open_settings())

        # Keep running until Escape or Ctrl+C
        print(f"\n  Ready! Press {hotkey.upper()} to start recording...")
        print("  Press S to open settings, ESC to exit\n")

        try:
            keyboard.wait('escape')
        except KeyboardInterrupt:
            pass

        print("\n  Shutting down Yapper...")
        self.recorder.cleanup()
        print(f"  Goodbye!\n")

    def _open_settings(self):
        """Open the settings UI."""
        import subprocess
        settings_path = APP_DIR / "settings_ui.py"

        if settings_path.exists():
            print("\n  Opening settings...")
            try:
                subprocess.Popen([sys.executable, str(settings_path)])
            except Exception as e:
                logger.error(f"Could not open settings: {e}")

    def _print_banner(self):
        """Print the application banner."""
        hotkey = self._data["hotkey"].upper()
        translate_to = self._data.get("translate_to", "")

        if translate_to:
            translate_info = f"Translate to: {translate_to.upper()}"
        else:
            translate_info = "No translation (same language)"

        vad_status = "On" if self._data.get("vad_enabled", True) else "Off"

        banner = f"""
  ╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐
  ╚╦╝├─┤├─┘├─┘├┤ ├┬┘
   ╩ ┴ ┴┴  ┴  └─┘┴└─  v{VERSION}

  ─────────────────────────────────────────
  Speech-to-Text | Speak → Type Anywhere
  ─────────────────────────────────────────

  HOTKEY:      {hotkey} (press to start/stop)
  TRANSLATION: {translate_info}
  VAD:         {vad_status}
  SETTINGS:    Edit settings.json to configure

  HOW TO USE:
    1. Click where you want to type
    2. Press {hotkey} to start recording
    3. Speak clearly into your microphone
    4. Press {hotkey} again to stop & transcribe

  ─────────────────────────────────────────
  {COPYRIGHT}
  ─────────────────────────────────────────
"""
        print(banner)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    print(f"""
  ╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐
  ╚╦╝├─┤├─┘├─┘├┤ ├┬┘
   ╩ ┴ ┴┴  ┴  └─┘┴└─

  Loading...""")

    # Load settings
    settings = Settings()
    settings.load()
    data = settings.as_dict()

    # Check for API key
    api_key = data.get("api_key", "").strip()
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not api_key:
        print("""
  Warning: No API key found!

  Opening Settings to configure your API key...
""")
        import subprocess
        settings_path = APP_DIR / "settings_console.py"
        if settings_path.exists():
            try:
                print("  Please enter your API key in the Settings window.")
                print("  Get your API key at: https://platform.openai.com/api-keys")
                print()
                subprocess.run([sys.executable, str(settings_path)])
                print()
                print("  Settings closed. Run Yapper again to start!")
                print(f"  {COPYRIGHT}")
            except Exception as e:
                print(f"  Error: Could not open Settings: {e}")
        sys.exit(0)

    # Update settings with resolved API key
    settings.set("api_key", api_key)

    # Check for root/admin on Linux (needed for keyboard library)
    if platform.system() == "Linux" and os.geteuid() != 0:
        print(f"""
  Note: On Linux, Yapper needs root privileges
        for global hotkey support.

  Please run with sudo:
      sudo -E python3 {sys.argv[0]}

  The -E flag preserves your environment variables.

  {COPYRIGHT}
""")
        sys.exit(1)

    app = Yapper(settings)
    app.run()


if __name__ == "__main__":
    main()
