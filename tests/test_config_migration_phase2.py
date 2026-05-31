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


def test_legacy_file_backfills_new_keys(tmp_path):
    from core.config import Settings, set_settings_path
    legacy = {
        "api_key": "sk-legacy",
        "hotkey": "f8",
        "translate_to": "",
        "fix_grammar": True,
        "always_listening": True,  # legacy key, must be preserved
    }
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(legacy), encoding="utf-8")

    set_settings_path(p)
    s = Settings(p).load()

    # New keys present with sane defaults.
    assert s.get("engine") == "cloud"
    assert s.get("cloud_stt_model") == "gpt-4o-mini-transcribe"
    assert s.get("text_model") == "gpt-5-nano"
    # Legacy values preserved.
    assert s.get("api_key") == "sk-legacy"
    assert s.get("always_listening") is True


def test_migrate_is_idempotent(tmp_path):
    from core.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"api_key": "sk-x"}), encoding="utf-8")
    s = Settings(p).load()
    first = s.get("text_model")
    s.save()
    s2 = Settings(p).load()
    assert s2.get("text_model") == first == "gpt-5-nano"


# ---------------------------------------------------------------------------
# Phase 3: output_mode rename migration (technical->clean, natural->polished)
# ---------------------------------------------------------------------------

def test_legacy_output_mode_technical_migrates_to_clean(tmp_path):
    from core.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"api_key": "x", "output_mode": "technical"}))
    s = Settings(settings_path=p).load()
    assert s.get("output_mode") == "clean"


def test_legacy_output_mode_natural_migrates_to_polished(tmp_path):
    from core.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"api_key": "x", "output_mode": "natural"}))
    s = Settings(settings_path=p).load()
    assert s.get("output_mode") == "polished"


def test_current_output_modes_left_as_is(tmp_path):
    from core.config import Settings
    for mode in ("clean", "polished", "verbatim"):
        p = tmp_path / f"settings_{mode}.json"
        p.write_text(json.dumps({"api_key": "x", "output_mode": mode}))
        s = Settings(settings_path=p).load()
        assert s.get("output_mode") == mode


def test_output_mode_migration_idempotent(tmp_path):
    from core.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"api_key": "x", "output_mode": "technical"}))
    s = Settings(settings_path=p).load()
    assert s.get("output_mode") == "clean"
    s.save()
    s2 = Settings(settings_path=p).load()
    assert s2.get("output_mode") == "clean"  # stays clean, not re-migrated
