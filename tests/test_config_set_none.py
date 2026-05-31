"""Phase 4 review item 10: Settings.set must reject None for non-nullable keys.

set(key, None) previously bypassed validation because _validate_setting returns
None for both "invalid" and "valid None" — so a non-nullable key like api_key
could be clobbered with None. Nullable keys (audio_device_index) still accept None.
"""
import pytest

from core import Settings


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    return s


def test_set_none_rejected_for_non_nullable_key(settings):
    settings.set("api_key", "sk-real")
    ok = settings.set("api_key", None)
    assert ok is False
    # Prior value is preserved, not clobbered to None.
    assert settings.get("api_key") == "sk-real"


def test_set_none_rejected_for_string_enum_key(settings):
    settings.set("output_mode", "clean")
    assert settings.set("output_mode", None) is False
    assert settings.get("output_mode") == "clean"


def test_set_none_allowed_for_nullable_key(settings):
    # audio_device_index schema is (int, type(None)) — None means system default.
    assert settings.set("audio_device_index", None) is True
    assert settings.get("audio_device_index") is None


def test_set_none_rejected_for_bool_key(settings):
    settings.set("audio_feedback", True)
    assert settings.set("audio_feedback", None) is False
    assert settings.get("audio_feedback") is True
