"""Phase 2: new engine/model settings keys + legacy migration."""
import json

from core.constants import (
    DEFAULT_SETTINGS,
    SETTINGS_SCHEMA,
    ENGINES,
    CLOUD_STT_MODELS,
    TEXT_MODELS,
)


def test_new_keys_have_defaults():
    assert DEFAULT_SETTINGS["engine"] == "cloud"
    assert DEFAULT_SETTINGS["cloud_stt_model"] == "gpt-4o-mini-transcribe"
    assert DEFAULT_SETTINGS["local_stt_model"] == "base"
    assert DEFAULT_SETTINGS["text_model"] == "gpt-5-nano"


def test_new_keys_in_schema():
    for key in ("engine", "cloud_stt_model", "local_stt_model", "text_model"):
        assert key in SETTINGS_SCHEMA


def test_option_lists_present():
    assert "cloud" in ENGINES and "local" in ENGINES
    assert "gpt-4o-mini-transcribe" in CLOUD_STT_MODELS
    assert "whisper-1" in CLOUD_STT_MODELS
    assert "gpt-5-nano" in TEXT_MODELS
    assert "gpt-4.1-nano" not in TEXT_MODELS  # deprecated, must be gone


def test_engine_schema_rejects_bad_value():
    typ, validator, _ = SETTINGS_SCHEMA["engine"]
    assert typ is str
    assert validator("cloud") is True
    assert validator("bogus") is False
