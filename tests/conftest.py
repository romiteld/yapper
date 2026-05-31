"""Shared pytest fixtures for the Yapper suite.

Puts the repo root on ``sys.path`` so ``import app...`` works under any runner,
and provides an isolated temp settings path so tests never touch the real
``app/settings.json``.

© 2026 Cloudelipute
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def temp_settings_path(tmp_path, monkeypatch):
    """Point Settings at an isolated temp file for the duration of a test."""
    from app.core import config

    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "_SETTINGS_FILE", path, raising=False)
    return path
