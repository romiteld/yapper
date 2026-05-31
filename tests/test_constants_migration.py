"""Tests for new Phase 1 settings keys and legacy migration."""
import json

from core.constants import DEFAULT_SETTINGS, SETTINGS_SCHEMA, HOTKEYS, VERSION


def test_new_keys_present_with_defaults():
    assert DEFAULT_SETTINGS["activation_mode"] == "push_to_talk"
    assert DEFAULT_SETTINGS["insertion_method"] == "paste"
    assert DEFAULT_SETTINGS["hotkey"] == "f8"


def test_new_keys_in_schema():
    assert "activation_mode" in SETTINGS_SCHEMA
    assert "insertion_method" in SETTINGS_SCHEMA


def test_activation_mode_validator():
    _type, validator, _desc = SETTINGS_SCHEMA["activation_mode"]
    assert validator("push_to_talk") is True
    assert validator("toggle") is True
    assert validator("wake_word") is True
    assert validator("nonsense") is False


def test_insertion_method_validator():
    _type, validator, _desc = SETTINGS_SCHEMA["insertion_method"]
    assert validator("paste") is True
    assert validator("type") is True
    assert validator("smoke") is False


def test_version_bumped():
    assert VERSION == "4.0.0"


def test_f6_hotkey_available():
    # Mac-friendly single F-keys must be selectable.
    assert "f6" in HOTKEYS
    assert "f7" in HOTKEYS


def test_legacy_always_listening_false_migrates_to_toggle(tmp_path):
    from core.config import Settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"always_listening": False, "api_key": "x"}))
    s = Settings(settings_path=path).load()
    assert s.get("activation_mode") == "toggle"


def test_legacy_always_listening_true_migrates_to_wake_word(tmp_path):
    from core.config import Settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"always_listening": True, "api_key": "x"}))
    s = Settings(settings_path=path).load()
    assert s.get("activation_mode") == "wake_word"


def test_explicit_activation_mode_not_overridden(tmp_path):
    from core.config import Settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps(
        {"always_listening": True, "activation_mode": "push_to_talk"}))
    s = Settings(settings_path=path).load()
    assert s.get("activation_mode") == "push_to_talk"
