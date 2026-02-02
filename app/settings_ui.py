#!/usr/bin/env python3
"""
Yapper Settings UI
==================
Modern graphical interface for configuring Yapper settings.
Cross-platform: Windows, macOS, Linux

Copyright (c) 2026 Cloudelipute
"""

import os
import sys
import webbrowser
from pathlib import Path

# Add app directory to path for imports
APP_DIR = Path(__file__).parent.resolve()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Check for customtkinter
try:
    import customtkinter as ctk
except ImportError:
    print("Installing customtkinter for modern UI...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "-q"])
    import customtkinter as ctk

# Try to import PIL for icon support
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Import core components
from core import (
    VERSION,
    COPYRIGHT,
    LANGUAGES,
    HOTKEYS,
    Settings,
    list_input_devices,
    setup_logging,
    get_logger,
)

# Initialize logging
setup_logging()
logger = get_logger("settings_ui")

# Icon file location
ICON_FILE = APP_DIR.parent / "yapper.ico"
if not ICON_FILE.exists():
    ICON_FILE = APP_DIR / "yapper.ico"


# =============================================================================
# MODERN SETTINGS UI
# =============================================================================

class SettingsApp(ctk.CTk):
    """Modern settings UI for Yapper."""

    def __init__(self):
        super().__init__()

        # Window setup
        self.title("Yapper Settings")
        self.geometry("520x750")
        self.resizable(False, False)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Try to set window icon
        if ICON_FILE.exists():
            try:
                self.iconbitmap(str(ICON_FILE))
            except Exception:
                pass

        # Load current settings
        self.settings = Settings()
        self.settings.load()
        self._data = self.settings.as_dict()

        # Build UI
        self._create_ui()

        # Center window
        self._center_window()

        logger.info("Settings UI opened")

    def _center_window(self):
        """Center the window on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _create_ui(self):
        """Create the settings UI."""
        # Main scrollable container
        main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # ===== HEADER =====
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        title_label = ctk.CTkLabel(
            header_frame,
            text=f"Yapper Settings v{VERSION}",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Configure your speech-to-text preferences",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle_label.pack(anchor="w")

        # ===== API KEY SECTION =====
        self._create_api_section(main_frame)

        # ===== HOTKEY SECTION =====
        self._create_hotkey_section(main_frame)

        # ===== AUDIO DEVICE SECTION =====
        self._create_device_section(main_frame)

        # ===== TRANSLATION SECTION =====
        self._create_translation_section(main_frame)

        # ===== OPTIONS SECTION =====
        self._create_options_section(main_frame)

        # ===== VAD SECTION =====
        self._create_vad_section(main_frame)

        # ===== BUTTONS =====
        self._create_buttons(main_frame)

        # ===== FOOTER =====
        footer_label = ctk.CTkLabel(
            main_frame,
            text=COPYRIGHT,
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        footer_label.pack(side="bottom", pady=(15, 0))

    def _create_api_section(self, parent):
        """Create API key section."""
        api_frame = ctk.CTkFrame(parent)
        api_frame.pack(fill="x", pady=(0, 12))

        api_header = ctk.CTkFrame(api_frame, fg_color="transparent")
        api_header.pack(fill="x", padx=12, pady=(12, 5))

        api_label = ctk.CTkLabel(
            api_header,
            text="OpenAI API Key",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        api_label.pack(side="left")

        api_link = ctk.CTkButton(
            api_header,
            text="Get API Key",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("dodgerblue", "deepskyblue"),
            width=80,
            height=22,
            command=lambda: webbrowser.open("https://platform.openai.com/api-keys")
        )
        api_link.pack(side="right")

        self.api_entry = ctk.CTkEntry(
            api_frame,
            placeholder_text="sk-...",
            font=ctk.CTkFont(size=13),
            height=36,
            show="*"
        )
        self.api_entry.pack(fill="x", padx=12, pady=(0, 8))
        if self._data.get("api_key"):
            self.api_entry.insert(0, self._data["api_key"])

        # Show/Hide toggle
        self.show_key = ctk.BooleanVar(value=False)
        show_check = ctk.CTkCheckBox(
            api_frame,
            text="Show API key",
            variable=self.show_key,
            command=self._toggle_api_visibility,
            font=ctk.CTkFont(size=11)
        )
        show_check.pack(anchor="w", padx=12, pady=(0, 12))

    def _create_hotkey_section(self, parent):
        """Create hotkey section."""
        hotkey_frame = ctk.CTkFrame(parent)
        hotkey_frame.pack(fill="x", pady=(0, 12))

        hotkey_label = ctk.CTkLabel(
            hotkey_frame,
            text="Recording Hotkey",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        hotkey_label.pack(anchor="w", padx=12, pady=(12, 5))

        hotkey_desc = ctk.CTkLabel(
            hotkey_frame,
            text="Press this key to start/stop recording",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        hotkey_desc.pack(anchor="w", padx=12, pady=(0, 8))

        self.hotkey_var = ctk.StringVar(value=self._data.get("hotkey", "f8"))
        self.hotkey_menu = ctk.CTkOptionMenu(
            hotkey_frame,
            values=HOTKEYS,
            variable=self.hotkey_var,
            font=ctk.CTkFont(size=13),
            height=36,
            width=180
        )
        self.hotkey_menu.pack(anchor="w", padx=12, pady=(0, 12))

    def _create_device_section(self, parent):
        """Create audio device selection section."""
        device_frame = ctk.CTkFrame(parent)
        device_frame.pack(fill="x", pady=(0, 12))

        device_label = ctk.CTkLabel(
            device_frame,
            text="Microphone",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        device_label.pack(anchor="w", padx=12, pady=(12, 5))

        device_desc = ctk.CTkLabel(
            device_frame,
            text="Select input device for recording",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        device_desc.pack(anchor="w", padx=12, pady=(0, 8))

        # Get available devices
        self._devices = list_input_devices()
        device_names = ["System Default"] + [d.name for d in self._devices]

        # Find current selection
        current_index = self._data.get("audio_device_index")
        if current_index is None:
            current_device = "System Default"
        else:
            current_device = next(
                (d.name for d in self._devices if d.index == current_index),
                "System Default"
            )

        self.device_var = ctk.StringVar(value=current_device)
        self.device_menu = ctk.CTkOptionMenu(
            device_frame,
            values=device_names,
            variable=self.device_var,
            font=ctk.CTkFont(size=13),
            height=36,
            width=300
        )
        self.device_menu.pack(anchor="w", padx=12, pady=(0, 12))

    def _create_translation_section(self, parent):
        """Create translation section."""
        translate_frame = ctk.CTkFrame(parent)
        translate_frame.pack(fill="x", pady=(0, 12))

        translate_label = ctk.CTkLabel(
            translate_frame,
            text="Translation",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        translate_label.pack(anchor="w", padx=12, pady=(12, 5))

        translate_desc = ctk.CTkLabel(
            translate_frame,
            text="Translate speech to another language",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        translate_desc.pack(anchor="w", padx=12, pady=(0, 8))

        # Get display name for current setting
        current_lang = self._data.get("translate_to", "")
        current_display = LANGUAGES.get(current_lang, "No Translation")

        self.translate_var = ctk.StringVar(value=current_display)
        self.translate_menu = ctk.CTkOptionMenu(
            translate_frame,
            values=list(LANGUAGES.values()),
            variable=self.translate_var,
            font=ctk.CTkFont(size=13),
            height=36,
            width=280
        )
        self.translate_menu.pack(anchor="w", padx=12, pady=(0, 12))

    def _create_options_section(self, parent):
        """Create options section."""
        options_frame = ctk.CTkFrame(parent)
        options_frame.pack(fill="x", pady=(0, 12))

        options_label = ctk.CTkLabel(
            options_frame,
            text="Options",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        options_label.pack(anchor="w", padx=12, pady=(12, 8))

        # Grammar correction toggle
        self.grammar_var = ctk.BooleanVar(value=self._data.get("fix_grammar", True))
        self.grammar_switch = ctk.CTkSwitch(
            options_frame,
            text="Grammar Correction (when not translating)",
            variable=self.grammar_var,
            font=ctk.CTkFont(size=12)
        )
        self.grammar_switch.pack(anchor="w", padx=12, pady=(0, 8))

        # Fuzzy wake word toggle
        self.wake_fuzzy_var = ctk.BooleanVar(value=self._data.get("wake_word_fuzzy", True))
        self.wake_fuzzy_switch = ctk.CTkSwitch(
            options_frame,
            text="Fuzzy Wake Word Detection",
            variable=self.wake_fuzzy_var,
            font=ctk.CTkFont(size=12)
        )
        self.wake_fuzzy_switch.pack(anchor="w", padx=12, pady=(0, 8))

        # Audio feedback toggle
        self.audio_feedback_var = ctk.BooleanVar(value=self._data.get("audio_feedback", True))
        self.audio_feedback_switch = ctk.CTkSwitch(
            options_frame,
            text="Audio Feedback Sounds",
            variable=self.audio_feedback_var,
            font=ctk.CTkFont(size=12)
        )
        self.audio_feedback_switch.pack(anchor="w", padx=12, pady=(0, 8))

        # Save history toggle
        self.history_var = ctk.BooleanVar(value=self._data.get("save_history", False))
        self.history_switch = ctk.CTkSwitch(
            options_frame,
            text="Save Transcription History",
            variable=self.history_var,
            font=ctk.CTkFont(size=12)
        )
        self.history_switch.pack(anchor="w", padx=12, pady=(0, 12))

    def _create_vad_section(self, parent):
        """Create VAD section."""
        vad_frame = ctk.CTkFrame(parent)
        vad_frame.pack(fill="x", pady=(0, 12))

        vad_header = ctk.CTkFrame(vad_frame, fg_color="transparent")
        vad_header.pack(fill="x", padx=12, pady=(12, 5))

        vad_label = ctk.CTkLabel(
            vad_header,
            text="Voice Activity Detection",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        vad_label.pack(side="left")

        # VAD enable toggle
        self.vad_var = ctk.BooleanVar(value=self._data.get("vad_enabled", True))
        self.vad_switch = ctk.CTkSwitch(
            vad_header,
            text="",
            variable=self.vad_var,
            command=self._on_vad_toggle,
            width=40
        )
        self.vad_switch.pack(side="right")

        vad_desc = ctk.CTkLabel(
            vad_frame,
            text="Skip API calls when no speech is detected (reduces costs)",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        vad_desc.pack(anchor="w", padx=12, pady=(0, 8))

        # VAD threshold slider
        threshold_frame = ctk.CTkFrame(vad_frame, fg_color="transparent")
        threshold_frame.pack(fill="x", padx=12, pady=(0, 12))

        threshold_label = ctk.CTkLabel(
            threshold_frame,
            text="Sensitivity:",
            font=ctk.CTkFont(size=12)
        )
        threshold_label.pack(side="left")

        current_threshold = self._data.get("vad_threshold_db", -35)
        self.threshold_label = ctk.CTkLabel(
            threshold_frame,
            text=f"{current_threshold} dB",
            font=ctk.CTkFont(size=12),
            width=60
        )
        self.threshold_label.pack(side="right")

        self.threshold_slider = ctk.CTkSlider(
            threshold_frame,
            from_=-60,
            to=-10,
            number_of_steps=50,
            command=self._on_threshold_change,
            width=200
        )
        self.threshold_slider.set(current_threshold)
        self.threshold_slider.pack(side="right", padx=(10, 10))

    def _create_buttons(self, parent):
        """Create action buttons."""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=(15, 0))

        save_btn = ctk.CTkButton(
            button_frame,
            text="Save Settings",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=45,
            command=self._save_settings
        )
        save_btn.pack(fill="x", pady=(0, 8))

        launch_btn = ctk.CTkButton(
            button_frame,
            text="Save & Launch Yapper",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=45,
            fg_color=("green", "darkgreen"),
            hover_color=("darkgreen", "green"),
            command=self._save_and_launch
        )
        launch_btn.pack(fill="x")

    def _toggle_api_visibility(self):
        """Toggle API key visibility."""
        if self.show_key.get():
            self.api_entry.configure(show="")
        else:
            self.api_entry.configure(show="*")

    def _on_vad_toggle(self):
        """Handle VAD toggle."""
        enabled = self.vad_var.get()
        state = "normal" if enabled else "disabled"
        self.threshold_slider.configure(state=state)

    def _on_threshold_change(self, value):
        """Handle threshold slider change."""
        self.threshold_label.configure(text=f"{int(value)} dB")

    def _get_language_code(self, display_name: str) -> str:
        """Get language code from display name."""
        for code, name in LANGUAGES.items():
            if name == display_name:
                return code
        return ""

    def _get_device_index(self, device_name: str):
        """Get device index from name."""
        if device_name == "System Default":
            return None
        for device in self._devices:
            if device.name == device_name:
                return device.index
        return None

    def _save_settings(self):
        """Save settings to file."""
        # Gather all settings
        self.settings.set("api_key", self.api_entry.get().strip())
        self.settings.set("hotkey", self.hotkey_var.get())
        self.settings.set("audio_device_index", self._get_device_index(self.device_var.get()))
        self.settings.set("translate_to", self._get_language_code(self.translate_var.get()))
        self.settings.set("language_hint", "en")  # Default to English input
        self.settings.set("fix_grammar", self.grammar_var.get())
        self.settings.set("wake_word_fuzzy", self.wake_fuzzy_var.get())
        self.settings.set("audio_feedback", self.audio_feedback_var.get())
        self.settings.set("save_history", self.history_var.get())
        self.settings.set("vad_enabled", self.vad_var.get())
        self.settings.set("vad_threshold_db", int(self.threshold_slider.get()))

        if self.settings.save():
            self._show_message("Settings saved successfully!")
            logger.info("Settings saved")
        else:
            self._show_message("Error saving settings!", error=True)

    def _save_and_launch(self):
        """Save settings and launch Yapper."""
        self._save_settings()

        # Launch yapper.py
        import subprocess
        yapper_path = APP_DIR / "yapper.py"

        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, str(yapper_path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Terminal", str(yapper_path)])
            else:
                subprocess.Popen([sys.executable, str(yapper_path)])

            # Close settings window
            self.after(500, self.destroy)
        except Exception as e:
            logger.error(f"Could not launch Yapper: {e}")
            self._show_message(f"Error: {e}", error=True)

    def _show_message(self, message: str, error: bool = False):
        """Show a temporary message."""
        msg_window = ctk.CTkToplevel(self)
        msg_window.title("Yapper")
        msg_window.geometry("300x100")
        msg_window.resizable(False, False)
        msg_window.transient(self)
        msg_window.grab_set()

        # Center on parent
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 150
        y = self.winfo_y() + (self.winfo_height() // 2) - 50
        msg_window.geometry(f"300x100+{x}+{y}")

        color = "red" if error else None
        label = ctk.CTkLabel(
            msg_window,
            text=message,
            font=ctk.CTkFont(size=15),
            text_color=color
        )
        label.pack(expand=True)

        # Auto-close after 1.5 seconds
        msg_window.after(1500, msg_window.destroy)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Launch the settings UI."""
    app = SettingsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
