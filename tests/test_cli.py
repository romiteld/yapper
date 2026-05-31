"""Phase 4 Task 11: CLI single-shot path tests."""
from unittest.mock import MagicMock

import pytest

from core import Settings
from cli import run_once


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s


def test_run_once_invokes_pipeline(settings, monkeypatch):
    fake_controller = MagicMock()
    monkeypatch.setattr("cli._build_controller", lambda s: fake_controller)
    run_once(settings, duration=0.01)
    fake_controller.start_recording.assert_called_once()
    fake_controller.stop_recording.assert_called_once()


def test_run_once_requires_api_key(monkeypatch, tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()  # no api_key
    rc = run_once(s, duration=0.01)
    assert rc != 0
