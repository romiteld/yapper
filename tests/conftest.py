"""Shared pytest fixtures for the Yapper suite.

Puts the repo root on ``sys.path`` so ``import app...`` works under any runner,
and also puts ``app/`` on ``sys.path`` so Phase 1+ tests can use bare
``import core.*`` imports. Provides an isolated temp settings path so tests
never touch the real ``app/settings.json``.

© 2026 Cloudelipute
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Make `import core.*` work for Phase 1+ tests.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture
def temp_settings_path(tmp_path, monkeypatch):
    """Point Settings at an isolated temp file for the duration of a test."""
    from app.core import config

    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "_SETTINGS_FILE", path, raising=False)
    return path


@pytest.fixture
def temp_settings(tmp_path):
    """A Settings instance backed by a throwaway JSON file (Phase 1+ fixture)."""
    from core.config import Settings

    path = tmp_path / "settings.json"
    return Settings(settings_path=path)


@pytest.fixture
def mock_openai(monkeypatch):
    """Patch `openai.OpenAI` so no network call happens.

    Returns the mock *client instance* (openai.OpenAI(...) return value).
    Configure: mock_openai.audio.transcriptions.create.return_value = "..."
               mock_openai.chat.completions.create.return_value = <obj>
    """
    client = MagicMock(name="OpenAIClient")
    # Default transcription returns a plain string (response_format='text').
    client.audio.transcriptions.create.return_value = "hello world"

    # Default chat returns an object shaped like the SDK response.
    chat_resp = MagicMock()
    chat_resp.choices = [MagicMock()]
    chat_resp.choices[0].message.content = "cleaned text"
    client.chat.completions.create.return_value = chat_resp

    factory = MagicMock(name="OpenAIFactory", return_value=client)
    # `core.api` does `from openai import OpenAI` inside _get_client.
    import openai
    monkeypatch.setattr(openai, "OpenAI", factory)
    client._factory = factory  # expose for assertions on constructor args
    return client


@pytest.fixture
def fake_local_backend():
    """A stand-in local whisper backend exposing a `transcribe(...)` callable."""
    backend = MagicMock(name="LocalBackend")
    backend.transcribe.return_value = {"text": " local transcript "}
    return backend


@pytest.fixture
def settings_factory():
    """Build a core.config.Settings with overrides, no file I/O."""
    from core.config import Settings

    def _make(**overrides):
        s = Settings.__new__(Settings)
        from core.constants import DEFAULT_SETTINGS
        s._path = Path("/tmp/yapper-test-settings.json")
        s._data = {**DEFAULT_SETTINGS, **overrides}
        s._extra_data = {}
        return s

    return _make
