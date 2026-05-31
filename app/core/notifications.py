"""
Yapper Notifications
====================
Thin wrapper over desktop-notifier. Degrades to a no-op when notifications are
unavailable (e.g. an unsigned macOS build with no Notification Center access);
the recording HUD remains the primary feedback channel.

© 2026 Cloudelipute
"""

from typing import Optional

from .logger import get_logger

logger = get_logger("notifications")


class Notifier:
    """Sends desktop notifications, silently no-op'ing when unsupported."""

    def __init__(self, app_name: str = "Yapper"):
        self.app_name = app_name
        self._backend = None
        self._tried = False

    def _get_backend(self):
        """Lazily build a DesktopNotifierSync, or None if it can't be created.

        desktop-notifier v6 exposes the async ``DesktopNotifier`` plus a
        blocking ``DesktopNotifierSync`` whose ``send(title=, message=)`` runs
        the event loop for us — that's the one we want from a sync callsite.
        """
        if self._tried:
            return self._backend
        self._tried = True
        try:
            from desktop_notifier import DesktopNotifierSync
            self._backend = DesktopNotifierSync(app_name=self.app_name)
        except Exception as e:
            logger.info("Notifications unavailable (%s); using HUD only", e)
            self._backend = None
        return self._backend

    def notify(self, title: str, message: str) -> None:
        backend = self._get_backend()
        if backend is None:
            return
        try:
            backend.send(title=title, message=message)
        except Exception as e:
            logger.debug("Notification failed: %s", e)
