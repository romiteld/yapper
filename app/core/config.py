"""
Yapper Configuration Management
===============================
Unified settings loading, saving, and validation.

© 2026 Cloudelipute
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .constants import DEFAULT_SETTINGS, SETTINGS_SCHEMA, LANGUAGES, HOTKEYS
from .logger import get_logger

logger = get_logger("config")

# Default settings file location
_SETTINGS_FILE: Optional[Path] = None


def get_settings_path() -> Path:
    """Get the path to settings.json file."""
    global _SETTINGS_FILE
    if _SETTINGS_FILE is None:
        app_dir = Path(__file__).parent.parent.resolve()
        _SETTINGS_FILE = app_dir / "settings.json"
    return _SETTINGS_FILE


def set_settings_path(path: Path) -> None:
    """Override the settings file path."""
    global _SETTINGS_FILE
    _SETTINGS_FILE = path


class Settings:
    """
    Unified settings management with validation.

    Example:
        settings = Settings()
        settings.load()
        api_key = settings.get("api_key")
        settings.set("hotkey", "f9")
        settings.save()
    """

    def __init__(self, settings_path: Optional[Path] = None):
        """
        Initialize Settings instance.

        Args:
            settings_path: Optional custom path to settings file.
        """
        self._path = settings_path or get_settings_path()
        self._data: Dict[str, Any] = DEFAULT_SETTINGS.copy()
        self._extra_data: Dict[str, Any] = {}  # Preserve unknown keys (comments, etc.)

    @property
    def path(self) -> Path:
        """Path to the settings file."""
        return self._path

    def load(self) -> "Settings":
        """
        Load settings from file.

        Returns:
            Self for chaining.
        """
        if not self._path.exists():
            logger.info(f"Settings file not found at {self._path}, using defaults")
            self._create_default_file()
            return self

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                file_data = json.load(f)

            # Separate known and unknown keys
            for key, value in file_data.items():
                if key in DEFAULT_SETTINGS:
                    if key == "output_mode" and value in self._OUTPUT_MODE_RENAMES:
                        value = self._OUTPUT_MODE_RENAMES[value]
                    elif key == "cloud_stt_model" and value in self._STT_MODEL_RENAMES:
                        value = self._STT_MODEL_RENAMES[value]
                    # Validate and set known settings
                    validated_value = self._validate_setting(key, value)
                    if validated_value is not None:
                        self._data[key] = validated_value
                    else:
                        logger.warning(f"Invalid value for '{key}': {value}, using default")
                else:
                    # Preserve unknown keys (comments, help, etc.)
                    self._extra_data[key] = value

            self._migrate_legacy(file_data)
            logger.debug(f"Loaded settings from {self._path}")
            self.migrate()

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
        except IOError as e:
            logger.error(f"Could not read settings file: {e}")

        return self

    def save(self) -> bool:
        """
        Save current settings to file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Merge data with extra keys
            output_data = {**self._extra_data, **self._data}

            # Add helpful metadata
            output_data["_comment"] = "Yapper Settings - Edit via Settings UI or manually"
            output_data["_available_languages"] = {
                "info": "Use these codes for translate_to or language_hint",
                "languages": {k: v for k, v in LANGUAGES.items() if k}
            }
            output_data["_available_hotkeys"] = HOTKEYS

            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)

            logger.debug(f"Saved settings to {self._path}")
            return True

        except IOError as e:
            logger.error(f"Could not save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key.
            default: Default value if key not found (uses DEFAULT_SETTINGS if None).

        Returns:
            Setting value.
        """
        if default is None:
            default = DEFAULT_SETTINGS.get(key)
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value with validation.

        Args:
            key: Setting key.
            value: New value.

        Returns:
            True if value was valid and set, False otherwise.
        """
        # Reject None for keys whose schema does not permit None. Without this
        # guard set(key, None) would bypass validation for non-nullable keys
        # (e.g. api_key) because _validate_setting returns None for both
        # "invalid" and "valid None".
        if value is None and not self._allows_none(key):
            logger.warning(f"Invalid value for '{key}': None not allowed")
            return False
        validated = self._validate_setting(key, value)
        if validated is not None or value is None:
            self._data[key] = validated if validated is not None else value
            return True
        logger.warning(f"Invalid value for '{key}': {value}")
        return False

    @staticmethod
    def _allows_none(key: str) -> bool:
        """True if the schema for ``key`` permits a None value.

        Unknown keys are permissive (accepted as-is, matching _validate_setting).
        Known keys allow None only when ``type(None)`` is in the expected type.
        """
        if key not in SETTINGS_SCHEMA:
            return True
        expected_type, _, _ = SETTINGS_SCHEMA[key]
        if isinstance(expected_type, tuple):
            return type(None) in expected_type
        return False

    def validate(self) -> Tuple[bool, list]:
        """
        Validate all current settings.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []

        for key, value in self._data.items():
            if key in SETTINGS_SCHEMA:
                if self._validate_setting(key, value) is None and value is not None:
                    errors.append(f"Invalid value for '{key}': {value}")

        # Check required settings
        if not self._data.get("api_key"):
            errors.append("API key is required")

        return len(errors) == 0, errors

    def as_dict(self) -> Dict[str, Any]:
        """Return settings as a dictionary."""
        return self._data.copy()

    def _validate_setting(self, key: str, value: Any) -> Optional[Any]:
        """
        Validate a single setting value.

        Returns:
            Validated value or None if invalid.
        """
        if key not in SETTINGS_SCHEMA:
            # Unknown key, accept as-is
            return value

        expected_type, validator, _ = SETTINGS_SCHEMA[key]

        # Handle None values for optional settings
        if value is None:
            if type(None) in expected_type if isinstance(expected_type, tuple) else False:
                return None
            return None  # Invalid if None not allowed

        # Type check
        if isinstance(expected_type, tuple):
            if not isinstance(value, expected_type):
                return None
        else:
            if not isinstance(value, expected_type):
                # Try type coercion for common cases
                try:
                    if expected_type == bool:
                        if isinstance(value, bool):
                            pass  # already bool - handled by isinstance above
                        elif isinstance(value, str):
                            low = value.strip().lower()
                            if low in ("true", "1", "yes", "on"):
                                value = True
                            elif low in ("false", "0", "no", "off"):
                                value = False
                            else:
                                return None  # unrecognized -> reject, default used
                        else:
                            value = bool(value)  # ints/other: 0/1 semantics fine
                    elif expected_type == int:
                        value = int(value)
                    elif expected_type == str:
                        value = str(value)
                except (ValueError, TypeError):
                    return None

        # Custom validator
        if validator is not None:
            try:
                if not validator(value):
                    return None
            except Exception:
                return None

        return value

    def _migrate_legacy(self, file_data: Dict[str, Any]) -> None:
        """Map deprecated keys onto v4 keys when the new key is absent."""
        if "activation_mode" not in file_data and "always_listening" in file_data:
            legacy = file_data.get("always_listening")
            self._data["activation_mode"] = "wake_word" if legacy else "toggle"
            logger.info(
                "Migrated legacy 'always_listening'=%s -> activation_mode=%s",
                legacy, self._data["activation_mode"],
            )

        # Legacy output_mode names (technical/natural) get renamed even though
        # the new schema would reject them on validation. Read the raw file
        # value so the rename survives the validation step.
        raw_mode = file_data.get("output_mode")
        if raw_mode in self._OUTPUT_MODE_RENAMES:
            new_mode = self._OUTPUT_MODE_RENAMES[raw_mode]
            self._data["output_mode"] = new_mode
            logger.info(
                "Migrated legacy output_mode '%s' -> '%s'", raw_mode, new_mode
            )

        # Legacy cloud_stt_model names (gpt-4o-mini-transcribe / whisper-1)
        # migrate to ElevenLabs scribe_v2.
        raw_stt = file_data.get("cloud_stt_model")
        if raw_stt in self._STT_MODEL_RENAMES:
            new_stt = self._STT_MODEL_RENAMES[raw_stt]
            self._data["cloud_stt_model"] = new_stt
            logger.info(
                "Migrated legacy cloud_stt_model '%s' -> '%s'", raw_stt, new_stt
            )

        # Migrate elevenlabs_api_key -> api_key and drop deprecated keys.
        if "elevenlabs_api_key" in file_data:
            el_key = file_data.get("elevenlabs_api_key")
            if not self._data.get("api_key") and isinstance(el_key, str):
                self._data["api_key"] = el_key
            self._extra_data.pop("elevenlabs_api_key", None)

        # Replace legacy sk-proj-* keys with ELEVENLABS_API_KEY env var (or clear).
        current_key = self._data.get("api_key") or ""
        if isinstance(current_key, str) and current_key.startswith("sk-proj-"):
            env_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
            self._data["api_key"] = env_key
            logger.info("Migrated legacy sk-proj-* API key entry")

    def _create_default_file(self) -> None:
        """Create default settings file."""
        self._data = DEFAULT_SETTINGS.copy()
        self.save()
        logger.info(f"Created default settings file at {self._path}")

    # Legacy output_mode names -> current names (Phase 3 rename).
    _OUTPUT_MODE_RENAMES = {
        "technical": "clean",
        "natural": "polished",
    }

    # Legacy cloud STT model names -> ElevenLabs Scribe v2.
    _STT_MODEL_RENAMES = {
        "gpt-4o-mini-transcribe": "scribe_v2",
        "whisper-1": "scribe_v2",
    }

    def migrate(self) -> bool:
        """Backfill new keys onto legacy settings files.

        Returns True if any value was changed (caller may choose to save).
        Idempotent: running twice changes nothing.
        """
        changed = False

        # Backfill any DEFAULT_SETTINGS key missing from the loaded data.
        for key, default in DEFAULT_SETTINGS.items():
            if key not in self._data:
                self._data[key] = default
                changed = True

        # Rename legacy output_mode values (technical->clean, natural->polished).
        # clean/polished/verbatim are left as-is, so this is idempotent.
        current_mode = self._data.get("output_mode")
        if current_mode in self._OUTPUT_MODE_RENAMES:
            new_mode = self._OUTPUT_MODE_RENAMES[current_mode]
            self._data["output_mode"] = new_mode
            logger.info(
                "Migrated legacy output_mode '%s' -> '%s'", current_mode, new_mode
            )
            changed = True

        # Rename legacy cloud_stt_model values to scribe_v2.
        current_stt = self._data.get("cloud_stt_model")
        if current_stt in self._STT_MODEL_RENAMES:
            new_stt = self._STT_MODEL_RENAMES[current_stt]
            self._data["cloud_stt_model"] = new_stt
            logger.info(
                "Migrated legacy cloud_stt_model '%s' -> '%s'", current_stt, new_stt
            )
            changed = True

        if changed:
            logger.info("Migrated legacy settings: backfilled new keys")
        return changed


# Convenience function for backward compatibility
def load_settings() -> Dict[str, Any]:
    """Load and return settings as dictionary."""
    settings = Settings()
    settings.load()
    return settings.as_dict()


def save_settings(data: Dict[str, Any]) -> bool:
    """Save settings from dictionary."""
    settings = Settings()
    settings.load()  # Load existing to preserve extra data
    for key, value in data.items():
        if key in DEFAULT_SETTINGS:
            settings.set(key, value)
    return settings.save()
