"""
Yapper Core Package
===================
Shared components for the Yapper speech-to-text application.

© 2026 Cloudelipute
"""

# Version and metadata
from .constants import VERSION, COPYRIGHT

# Constants
from .constants import (
    LANGUAGES,
    LANGUAGE_CODES,
    HOTKEYS,
    DEFAULT_SETTINGS,
    SETTINGS_SCHEMA,
    ENGINES,
    OUTPUT_MODES,
    CLOUD_STT_MODELS,
    LOCAL_STT_MODELS,
    TEXT_MODELS,
    ACTIVATION_MODES,
)

# Logging
from .logger import (
    setup_logging,
    get_logger,
    set_console_level,
    disable_console_logging,
    enable_console_logging,
)

# Configuration
from .config import (
    Settings,
    load_settings,
    save_settings,
    get_settings_path,
    set_settings_path,
)

# Audio
from .audio import AudioRecorder, SAMPLE_RATE, CHANNELS, CHUNK_SIZE

# API
from .api import APIClient, APIError, APIConnectionError, APIRateLimitError

# Transcription
from .transcriber import Transcriber

# No-slop formatting subsystem
from .vocabulary import Vocabulary
from .formatting import Formatter, expand_spoken_symbols

# Engines
from .engines import (
    TranscriptionEngine,
    CloudEngine,
    LocalEngine,
    LocalEngineUnavailable,
    get_engine,
)

# Text Typing
from .typer import TextTyper

# Platform
from .platform import IS_MAC, IS_WIN, IS_LINUX, default_hotkey, open_settings_pane, open_folder

# Permissions
from .permissions import (
    PermissionStatus,
    permission_status,
    microphone_ok,
    accessibility_trusted,
    input_monitoring_ok,
)

# Hotkeys
from .hotkeys import HotkeyManager

# Notifications
from .notifications import Notifier

# Devices
from .devices import (
    AudioDevice,
    list_input_devices,
    get_device_by_index,
    get_device_by_name,
    get_default_device,
    test_device,
)

# Audio Feedback
from .sounds import SoundPlayer

# History
from .history import TranscriptionRecord, TranscriptionHistory

# Voice Activity Detection
from .vad import VoiceActivityDetector

# Package version
__version__ = VERSION
__all__ = [
    # Version
    "VERSION",
    "COPYRIGHT",
    "__version__",
    # Constants
    "LANGUAGES",
    "LANGUAGE_CODES",
    "HOTKEYS",
    "DEFAULT_SETTINGS",
    "SETTINGS_SCHEMA",
    "ENGINES",
    "OUTPUT_MODES",
    "CLOUD_STT_MODELS",
    "LOCAL_STT_MODELS",
    "TEXT_MODELS",
    "ACTIVATION_MODES",
    # Logging
    "setup_logging",
    "get_logger",
    "set_console_level",
    "disable_console_logging",
    "enable_console_logging",
    # Configuration
    "Settings",
    "load_settings",
    "save_settings",
    "get_settings_path",
    "set_settings_path",
    # Audio
    "AudioRecorder",
    "SAMPLE_RATE",
    "CHANNELS",
    "CHUNK_SIZE",
    # API
    "APIClient",
    "APIError",
    "APIConnectionError",
    "APIRateLimitError",
    # Transcription
    "Transcriber",
    # No-slop formatting
    "Vocabulary",
    "Formatter",
    "expand_spoken_symbols",
    # Engines
    "TranscriptionEngine",
    "CloudEngine",
    "LocalEngine",
    "LocalEngineUnavailable",
    "get_engine",
    # Text Typing
    "TextTyper",
    # Platform
    "IS_MAC",
    "IS_WIN",
    "IS_LINUX",
    "default_hotkey",
    "open_settings_pane",
    "open_folder",
    # Permissions
    "PermissionStatus",
    "permission_status",
    "microphone_ok",
    "accessibility_trusted",
    "input_monitoring_ok",
    # Hotkeys
    "HotkeyManager",
    # Notifications
    "Notifier",
    # Devices
    "AudioDevice",
    "list_input_devices",
    "get_device_by_index",
    "get_device_by_name",
    "get_default_device",
    "test_device",
    # Audio Feedback
    "SoundPlayer",
    # History
    "TranscriptionRecord",
    "TranscriptionHistory",
    # VAD
    "VoiceActivityDetector",
]
