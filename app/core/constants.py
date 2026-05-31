"""
Yapper Core Constants
=====================
Single source of truth for version, languages, hotkeys, and default settings.

© 2026 Cloudelipute
"""

from typing import Dict, List, Optional

# =============================================================================
# VERSION INFO
# =============================================================================

VERSION = "4.0.0"
COPYRIGHT = "© 2026 Cloudelipute"

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

# Available hotkey options - cross-platform compatible (single F-keys are
# Mac-safe; Ctrl/Alt combos are broken on macOS via pynput issue #297).
HOTKEYS: List[str] = [
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "pause",
    "scroll lock",
    "insert",
    "cmd+shift+space",
    "shift+space",
]

# =============================================================================
# OUTPUT MODES (faithful formatting)
# =============================================================================

# Output formatting modes for the faithful-formatting subsystem. Yapper is a
# general-purpose dictation tool (agent prompts, docs, everyday messaging),
# so the default keeps the user's own wording — it never paraphrases.
# clean     = (default) fix only caps/punctuation + remove fillers; keep the
#             user's exact words, tone, slang, and any jargon/code verbatim
# polished  = opt-in heavier rewrite into tidy prose
# verbatim  = no LLM cleanup at all
OUTPUT_MODES: List[str] = ["clean", "polished", "verbatim"]

# =============================================================================
# ENGINES & MODELS
# =============================================================================

# Transcription engine backends
ENGINES: List[str] = ["cloud", "local"]

# Activation modes (consumed by hotkeys.py in Phase 1)
ACTIVATION_MODES: List[str] = ["push_to_talk", "toggle", "wake_word"]

# Cloud speech-to-text models (gpt-4o-mini-transcribe default; whisper-1 kept
# for long-tail languages / timestamps).
CLOUD_STT_MODELS: List[str] = ["gpt-4o-mini-transcribe", "whisper-1"]

# Local on-device model sizes (mlx-whisper / faster-whisper).
LOCAL_STT_MODELS: List[str] = ["tiny", "base", "small", "medium", "large-v3"]

# Text post-processing / translation models.
# gpt-4.1-nano is DEPRECATED (shutdown 2026-10-23) and intentionally excluded.
TEXT_MODELS: List[str] = ["gpt-5-nano", "gpt-5.4-nano"]

# =============================================================================
# DEFAULT SETTINGS
# =============================================================================

DEFAULT_SETTINGS: Dict[str, any] = {
    # API Configuration
    "api_key": "",

    # Engine & models (Phase 2)
    "engine": "cloud",                            # cloud | local
    "cloud_stt_model": "gpt-4o-mini-transcribe",  # or whisper-1
    "local_stt_model": "base",                    # mlx/faster-whisper size
    "text_model": "gpt-5-nano",                   # post-processing/translation

    # Recording
    "hotkey": "f8",
    "audio_device_index": None,  # None = system default
    "audio_feedback": True,

    # Activation & insertion (v4)
    "activation_mode": "push_to_talk",  # push_to_talk | toggle | wake_word
    "insertion_method": "paste",        # paste | type

    # Transcription
    "language_hint": "",  # Input language hint for Whisper (empty = auto-detect)
    "translate_to": "",   # Target language (empty = no translation)
    "fix_grammar": True,  # Auto-correct grammar when not translating

    # Faithful formatting (Phase 3)
    "output_mode": "clean",           # clean | polished | verbatim
    "expand_spoken_symbols": True,    # expand "dash dash help" -> "--help"
    "vocabulary": [],                 # list of {said, typed} term dicts

    # Wake Word (Tray mode)
    "always_listening": True,
    "listen_interval": 3,  # seconds between wake word checks
    "wake_word_fuzzy": True,  # Fuzzy matching for wake words

    # Voice Activity Detection
    "vad_enabled": True,
    "vad_threshold_db": -45,  # Range: -60 to -10 (more negative = more sensitive)

    # History
    "save_history": True,

    # UI / HUD
    "show_hud": True,      # show the floating recording pill
    "reduce_motion": False, # disable HUD level animation
}

# =============================================================================
# SETTINGS SCHEMA
# =============================================================================

# Schema for settings validation
# Format: key -> (type, validator_func_or_None, description)
SETTINGS_SCHEMA: Dict[str, tuple] = {
    "api_key": (str, None, "OpenAI API key"),
    "engine": (str, lambda x: x in ENGINES, "Transcription engine"),
    "cloud_stt_model": (str, lambda x: x in CLOUD_STT_MODELS, "Cloud STT model"),
    "local_stt_model": (str, lambda x: x in LOCAL_STT_MODELS, "Local STT model"),
    "text_model": (str, lambda x: x in TEXT_MODELS, "Text post-processing model"),
    "hotkey": (str, lambda x: x in HOTKEYS, "Recording hotkey"),
    "activation_mode": (
        str,
        lambda x: x in ("push_to_talk", "toggle", "wake_word"),
        "How recording is triggered",
    ),
    "insertion_method": (
        str,
        lambda x: x in ("paste", "type"),
        "How text is inserted at cursor",
    ),
    "audio_device_index": ((int, type(None)), None, "Audio input device index"),
    "audio_feedback": (bool, None, "Enable audio feedback sounds"),
    "language_hint": (str, lambda x: x == "" or x in LANGUAGE_CODES, "Input language hint"),
    "translate_to": (str, lambda x: x == "" or x in LANGUAGE_CODES, "Target translation language"),
    "fix_grammar": (bool, None, "Auto-correct grammar"),
    "output_mode": (str, lambda x: x in OUTPUT_MODES, "Output formatting mode"),
    "expand_spoken_symbols": (bool, None, "Expand spoken symbols to characters"),
    "vocabulary": (
        list,
        lambda x: isinstance(x, list)
        and all(
            isinstance(t, str)
            or (isinstance(t, dict) and "typed" in t)
            for t in x
        ),
        "Custom vocabulary terms",
    ),
    "always_listening": (bool, None, "Enable wake word listening"),
    "listen_interval": (int, lambda x: 1 <= x <= 10, "Wake word check interval"),
    "wake_word_fuzzy": (bool, None, "Fuzzy wake word matching"),
    "vad_enabled": (bool, None, "Enable voice activity detection"),
    "vad_threshold_db": (int, lambda x: -60 <= x <= -10, "VAD threshold in dB"),
    "save_history": (bool, None, "Save transcription history"),
    "show_hud": (bool, None, "Show the floating recording HUD"),
    "reduce_motion": (bool, None, "Disable HUD level animation"),
}
