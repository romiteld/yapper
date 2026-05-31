"""Smoke tests: the package imports, reports the v4 version, and Settings load.

© 2026 Cloudelipute
"""


def test_version_is_4():
    from app.core.constants import VERSION

    assert VERSION == "4.0.0"


def test_core_package_imports():
    import app.core as core

    assert core.__version__ == "4.0.0"
    assert core.COPYRIGHT == "© 2026 Cloudelipute"
    # Public surface that later phases extend must already be importable.
    assert hasattr(core, "Settings")
    assert hasattr(core, "DEFAULT_SETTINGS")
    assert hasattr(core, "get_logger")


def test_settings_load_creates_defaults(temp_settings_path):
    from app.core.config import Settings

    settings = Settings(settings_path=temp_settings_path).load()

    # Defaults present and the file was materialized.
    assert temp_settings_path.exists()
    assert settings.get("audio_feedback") is True
    assert settings.get("api_key") == ""


def test_entrypoint_main_returns_zero(capsys):
    from app.__main__ import main

    rc = main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "Yapper 4.0.0" in out
    assert "© 2026 Cloudelipute" in out
