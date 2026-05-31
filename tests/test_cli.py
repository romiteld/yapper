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
    monkeypatch.setattr("cli._build_controller", lambda s, on_error=None: fake_controller)
    rc = run_once(settings, duration=0.01)
    fake_controller.start_recording.assert_called_once()
    fake_controller.stop_recording.assert_called_once()
    assert rc == 0


def test_run_once_requires_api_key(monkeypatch, tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()  # no api_key
    rc = run_once(s, duration=0.01)
    assert rc == 2


def test_run_once_returns_nonzero_on_pipeline_error(settings, monkeypatch):
    # A controller whose pipeline reports an error must yield exit code 1.
    def fake_build(s, on_error=None):
        c = MagicMock()
        # Simulate the controller surfacing an error during start/stop.
        c.start_recording.side_effect = lambda: on_error and on_error("mic failed")
        return c

    monkeypatch.setattr("cli._build_controller", fake_build)
    rc = run_once(settings, duration=0.01)
    assert rc == 1
