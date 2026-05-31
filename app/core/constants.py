"""
Yapper Core Constants
=====================
Single source of truth for version, languages, hotkeys, and default settings.

Copyright (c) 2026 Cloudelipute
"""

from typing import Dict, List

# =============================================================================
# VERSION INFO
# =============================================================================

VERSION = "4.0.0"
COPYRIGHT = "Copyright (c) 2026 Cloudelipute"

# =============================================================================
# LANGUAGES
# =============================================================================

# Unified language dictionary - used for both translation and language hints
# Format: code -> display name
LANGUAGES: Dict[str, str] = {
    "": "No Translation",
    "en": "English",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
    "nl": "Dutch (Nederlands)",
    "pl": "Polish (Polski)",
    "ru": "Russian (Русский)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "zh": "Chinese (中文)",
    "ar": "Arabic (العربية)",
    "hi": "Hindi (हिन्दी)",
    "tr": "Turkish (Türkçe)",
    "vi": "Vietnamese (Tiếng Việt)",
    "th": "Thai (ไทย)",
    "sv": "Swedish (Svenska)",
    "da": "Danish (Dansk)",
    "fi": "Finnish (Suomi)",
    "no": "Norwegian (Norsk)",
    "uk": "Ukrainian (Українська)",
    "cs": "Czech (Čeština)",
    "el": "Greek (Ελληνικά)",
    "he": "Hebrew (עברית)",
    "id": "Indonesian (Bahasa)",
    "ms": "Malay (Bahasa Melayu)",
    "ro": "Romanian (Română)",
    "hu": "Hungarian (Magyar)",
    "bg": "Bulgarian (Български)",
    "hr": "Croatian (Hrvatski)",
    "sk": "Slovak (Slovenčina)",
    "sl": "Slovenian (Slovenščina)",
    "et": "Estonian (Eesti)",
    "lv": "Latvian (Latviešu)",
    "lt": "Lithuanian (Lietuvių)",
    "ca": "Catalan (Català)",
    "af": "Afrikaans",
    "sw": "Swahili (Kiswahili)",
}

# Language code to name mapping (without "No Translation")
LANGUAGE_CODES: Dict[str, str] = {k: v for k, v in LANGUAGES.items() if k}

# =============================================================================
# HOTKEYS
# =============================================================================

# Available hotkey options - cross-platform compatible
HOTKEYS: List[str] = [
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "pause",
    "scroll lock",
    "insert",
    "ctrl+shift+r",
    "ctrl+shift+d",
    "ctrl+alt+v",
]

# =============================================================================
# DEFAULT SETTINGS
# =============================================================================

DEFAULT_SETTINGS: Dict[str, any] = {
    # API Configuration
    "api_key": "",

    # Recording
    "hotkey": "f8",
    "audio_device_index": None,  # None = system default
    "audio_feedback": True,

    # Transcription
    "language_hint": "",  # Input language hint for Whisper (empty = auto-detect)
    "translate_to": "",   # Target language (empty = no translation)
    "fix_grammar": True,  # Auto-correct grammar when not translating

    # Wake Word (Tray mode)
    "always_listening": True,
    "listen_interval": 3,  # seconds between wake word checks
    "wake_word_fuzzy": True,  # Fuzzy matching for wake words

    # Voice Activity Detection
    "vad_enabled": True,
    "vad_threshold_db": -45,  # Range: -60 to -10 (more negative = more sensitive)

    # History
    "save_history": True,
}

# =============================================================================
# SETTINGS SCHEMA
# =============================================================================

# Schema for settings validation
# Format: key -> (type, validator_func_or_None, description)
SETTINGS_SCHEMA: Dict[str, tuple] = {
    "api_key": (str, None, "OpenAI API key"),
    "hotkey": (str, lambda x: x in HOTKEYS, "Recording hotkey"),
    "audio_device_index": ((int, type(None)), None, "Audio input device index"),
    "audio_feedback": (bool, None, "Enable audio feedback sounds"),
    "language_hint": (str, lambda x: x == "" or x in LANGUAGE_CODES, "Input language hint"),
    "translate_to": (str, lambda x: x == "" or x in LANGUAGE_CODES, "Target translation language"),
    "fix_grammar": (bool, None, "Auto-correct grammar"),
    "always_listening": (bool, None, "Enable wake word listening"),
    "listen_interval": (int, lambda x: 1 <= x <= 10, "Wake word check interval"),
    "wake_word_fuzzy": (bool, None, "Fuzzy wake word matching"),
    "vad_enabled": (bool, None, "Enable voice activity detection"),
    "vad_threshold_db": (int, lambda x: -60 <= x <= -10, "VAD threshold in dB"),
    "save_history": (bool, None, "Save transcription history"),
}
