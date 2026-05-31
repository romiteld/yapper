"""Tests for the Notifier wrapper (desktop-notifier mocked / absent)."""
from unittest.mock import MagicMock, patch

import pytest

from core.notifications import Notifier


def test_notify_sends_through_backend():
    backend = MagicMock()
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=backend):
        n.notify("Yapper", "Transcribed")
    backend.send.assert_called_once()
    kwargs = backend.send.call_args.kwargs
    assert kwargs.get("title") == "Yapper"
    assert kwargs.get("message") == "Transcribed"


def test_notify_is_noop_when_backend_unavailable():
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=None):
        # Must not raise.
        n.notify("Yapper", "no backend")


def test_notify_swallows_backend_errors():
    backend = MagicMock()
    backend.send.side_effect = RuntimeError("notification center down")
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=backend):
        # Must degrade gracefully, not raise.
        n.notify("Yapper", "boom")


def test_real_backend_is_desktop_notifier_sync_with_callable_send():
    """Construct the REAL backend (no mock) so a wrong class/method name fails.

    This is the regression guard for the v6 API: ``send_sync`` does not exist;
    only ``DesktopNotifierSync.send`` does. We don't actually dispatch a
    notification (no display server in CI), we only assert the backend object's
    shape so the call would succeed if a backend were present.
    """
    desktop_notifier = pytest.importorskip("desktop_notifier")
    DesktopNotifierSync = desktop_notifier.DesktopNotifierSync

    n = Notifier()
    backend = n._get_backend()
    if backend is None:
        pytest.skip("desktop-notifier has no working backend in this env")

    assert isinstance(backend, DesktopNotifierSync)
    assert callable(getattr(backend, "send", None))
    # The previously-used name must NOT exist on the real backend.
    assert not hasattr(backend, "send_sync")
