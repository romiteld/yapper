"""Shared pytest fixtures for the Yapper suite.

Puts the repo root on ``sys.path`` so ``import app...`` works under any runner,
and also puts ``app/`` on ``sys.path`` so Phase 1+ tests can use bare
``import core.*`` imports. Provides an isolated temp settings path so tests
never touch the real ``app/settings.json``.

© 2026 Cloudelipute
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
def mock_elevenlabs(monkeypatch):
    """Patch ``httpx.Client`` so no network call happens during APIClient tests.

    Returns the mock *client instance* (httpx.Client(...) return value).
    """
    client = MagicMock(name="ElevenLabsHttpClient")

    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {"text": "hello world", "language_code": "en"}
    post_resp.text = '{"text":"hello world"}'
    client.post.return_value = post_resp

    get_resp = MagicMock()
    get_resp.status_code = 200
    client.get.return_value = get_resp

    chat_resp = MagicMock()
    chat_resp.choices = [MagicMock()]
    chat_resp.choices[0].message.content = "cleaned text"
    client.chat.completions.create.return_value = chat_resp

    factory = MagicMock(name="HttpxClientFactory", return_value=client)
    import httpx
    monkeypatch.setattr(httpx, "Client", factory)
    client._factory = factory
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
