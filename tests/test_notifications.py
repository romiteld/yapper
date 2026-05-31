"""Tests for the Notifier wrapper (desktop-notifier mocked / absent)."""
from unittest.mock import MagicMock, patch

from core.notifications import Notifier


def test_notify_sends_through_backend():
    backend = MagicMock()
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=backend):
        n.notify("Yapper", "Transcribed")
    backend.send_sync.assert_called_once()
    kwargs = backend.send_sync.call_args.kwargs
    assert kwargs.get("title") == "Yapper"
    assert kwargs.get("message") == "Transcribed"


def test_notify_is_noop_when_backend_unavailable():
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=None):
        # Must not raise.
        n.notify("Yapper", "no backend")


def test_notify_swallows_backend_errors():
    backend = MagicMock()
    backend.send_sync.side_effect = RuntimeError("notification center down")
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=backend):
        # Must degrade gracefully, not raise.
        n.notify("Yapper", "boom")
