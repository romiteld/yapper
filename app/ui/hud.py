"""Recording HUD — frameless translucent always-on-top pill.

© 2026 Cloudelipute
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget

from core import get_logger
from . import theme

logger = get_logger("hud")

_STATES = ("idle", "listening", "transcribing", "done")
_LABELS = {
    "idle": "Yapper",
    "listening": "Listening…",
    "transcribing": "Transcribing…",
    "done": "Done",
}


class RecordingHUD(QWidget):
    """A small floating status pill with a live audio level ring."""

    WIDTH = 190
    HEIGHT = 56

    def __init__(self, reduce_motion: bool = False, parent=None):
        super().__init__(parent)
        self.state = "idle"
        self.reduce_motion = reduce_motion
        self._level = 0.0
        self._displayed_level = 0.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Click-through so the pill never steals focus from the editor.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        # Smooth the displayed level toward the target unless reduce_motion.
        self._anim = QTimer(self)
        self._anim.setInterval(33)  # ~30 fps
        self._anim.timeout.connect(self._tick)

        # Stored, cancellable hide timer: activated on 'done', cancelled on
        # re-activation ('listening'/'transcribing') so a rapid back-to-back
        # dictation does not hide the HUD mid-recording.
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        # The macOS NSWindow shim needs a native window handle, which only
        # exists after the widget is first shown — applied in showEvent.
        self._macos_behavior_applied = False

    # -- public API ------------------------------------------------------
    def set_state(self, state: str) -> None:
        if state not in _STATES:
            raise ValueError(f"Unknown HUD state: {state!r}")
        self.state = state
        if state == "listening" and not self.reduce_motion:
            if not self._anim.isActive():
                self._anim.start()
        else:
            self._anim.stop()
            self._displayed_level = 0.0
        if state in ("listening", "transcribing"):
            # Cancel any pending auto-hide from the previous 'done' transition.
            self._hide_timer.stop()
        elif state == "done":
            # Arm the auto-hide; do NOT stop on 'idle' because the controller
            # emits IDLE right after DONE — stopping there would kill the timer.
            self._hide_timer.start(900)
        self.update()

    def update_level(self, rms: float) -> None:
        self._level = max(0.0, min(1.0, float(rms)))
        if self.reduce_motion:
            self._displayed_level = 0.0
        self.update()

    # -- internals -------------------------------------------------------
    def _tick(self) -> None:
        # Ease displayed level toward target.
        self._displayed_level += (self._level - self._displayed_level) * 0.35
        self.update()

    def show_centered_bottom(self) -> None:
        # Cancel any pending auto-hide before re-showing.
        self._hide_timer.stop()
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            x = geom.center().x() - self.WIDTH // 2
            y = geom.bottom() - self.HEIGHT - 60
            self.move(x, y)
        self.show()

    def showEvent(self, event):  # noqa: N802 - Qt override
        # Apply the macOS NSWindow collection behavior once the native handle
        # exists (winId() is only valid after the first show).
        super().showEvent(event)
        if not self._macos_behavior_applied:
            self._macos_behavior_applied = True
            self._apply_macos_collection_behavior()

    def _apply_macos_collection_behavior(self) -> None:
        if platform.system() != "Darwin":
            return
        try:  # pragma: no cover - mac-only path
            from AppKit import (
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorFullScreenAuxiliary,
                NSWindowCollectionBehaviorStationary,
            )
            import objc  # noqa: F401
            win = objc.objc_object(c_void_p=int(self.winId()))
            win.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
                | NSWindowCollectionBehaviorStationary
            )
            win.setLevel_(1000)  # floating panel level
        except Exception as exc:  # noqa: BLE001 - shim is best-effort
            logger.debug(f"macOS HUD collection behavior unavailable: {exc}")

    def paintEvent(self, event):  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(2, 2, -2, -2), 24, 24)
        p.fillPath(path, QColor(theme.BG_RAISED))
        ring = QColor(theme.STATE_COLORS[self.state])
        pen_w = 2 + int(self._displayed_level * 5)
        pen = p.pen()
        pen.setColor(ring)
        pen.setWidth(pen_w)
        p.setPen(pen)
        p.drawPath(path)
        p.setPen(QColor(theme.FG))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _LABELS[self.state])
        p.end()
