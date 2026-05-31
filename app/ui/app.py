"""YapperApp — QApplication + QSystemTrayIcon + Controller, with a thread bridge.

© 2026 Cloudelipute
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core import (
    ENGINES,
    HotkeyManager,
    LANGUAGES,
    Notifier,
    OUTPUT_MODES,
    Settings,
    TranscriptionHistory,
    VERSION,
    get_logger,
    setup_logging,
)
from . import theme
from .controller import Controller, ControllerState

logger = get_logger("app")

APP_DIR = Path(__file__).resolve().parent.parent


class _Bridge(QObject):
    """Marshals pynput-listener-thread callbacks into the Qt main thread."""

    hotkey_start = Signal()
    hotkey_stop = Signal()
    state_changed = Signal(str)   # ControllerState value
    level = Signal(float)
    result = Signal(str)
    error = Signal(str)


def _state_icon(state: str) -> QIcon:
    """A 32px dot tinted by the recording state color."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(QColor(theme.STATE_COLORS.get(state, theme.STATE_COLORS["idle"])))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(4, 4, 24, 24)
    p.end()
    return QIcon(pix)


class YapperApp:
    """Owns the Qt loop, tray, controller, HUD, and hotkey bridge."""

    def __init__(self, settings: Settings | None = None, start_listener: bool = True):
        self.qapp = QApplication.instance() or QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.setStyleSheet(theme.qss())

        self.settings = settings or Settings().load()
        self.notifier = Notifier()
        # ONE shared history: the controller writes to it during dictation and
        # the HistoryWindow reads the same instance, so it never shows stale data.
        self.history = TranscriptionHistory(enabled=self.settings.get("save_history", True))

        self._bridge = _Bridge()
        self.controller = Controller(
            self.settings,
            on_state=lambda s: self._bridge.state_changed.emit(s.value),
            on_level=lambda v: self._bridge.level.emit(v),
            on_result=lambda t: self._bridge.result.emit(t),
            on_error=lambda m: self._bridge.error.emit(m),
            history=self.history,
        )

        # Connect bridge signals to Qt slots (run on main thread).
        self._bridge.hotkey_start.connect(self.controller.on_hotkey_start)
        self._bridge.hotkey_stop.connect(self.controller.on_hotkey_stop)
        self._bridge.state_changed.connect(self._on_state)
        self._bridge.result.connect(self._on_result)
        self._bridge.error.connect(self._on_error)

        self._hud = None
        if self.settings.get("show_hud", True):
            from .hud import RecordingHUD
            self._hud = RecordingHUD(reduce_motion=self.settings.get("reduce_motion", False))
            self._bridge.level.connect(self._hud.update_level)

        self.tray = self._build_tray()
        self._wizard = None
        self._settings_win = None
        self._history_win = None

        self.hotkeys = None
        if start_listener:
            self._start_hotkeys()

    # -- tray ------------------------------------------------------------
    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(_state_icon("idle"))
        tray.setToolTip(f"Yapper v{VERSION}")
        # Keep a Python reference to the menu (and via parenting, its submenus)
        # so it isn't garbage-collected after this method returns.
        self._tray_menu = self._build_tray_menu()
        tray.setContextMenu(self._tray_menu)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # No system tray (some Linux/headless/locked-down desktops). Don't
            # leave the user with no entry point: log and open Settings so the
            # app is still usable.
            logger.warning(
                "System tray unavailable; opening Settings as a fallback entry point.")
            QTimer.singleShot(0, self.open_settings)
            return tray
        tray.show()
        return tray

    def _build_tray_menu(self) -> QMenu:
        """Build the tray context menu, including live quick-toggle submenus."""
        menu = QMenu()
        # Retain submenu/group references so their C++ objects aren't collected
        # (Qt parenting alone isn't enough to keep the PySide wrappers alive).
        self._submenus: list = []
        self._action_groups: list = []
        # Quick toggles that update settings live + persist.
        self._engine_group = self._add_choice_submenu(
            menu, "Engine", ENGINES, "engine")
        self._mode_group = self._add_choice_submenu(
            menu, "Output mode", OUTPUT_MODES, "output_mode",
            labels={"clean": "Clean", "polished": "Polished", "verbatim": "Verbatim"})
        # Language: code -> display name; "" is "No Translation".
        lang_codes = list(LANGUAGES.keys())
        self._lang_group = self._add_choice_submenu(
            menu, "Language", lang_codes, "translate_to",
            labels={c: LANGUAGES[c] for c in lang_codes})
        menu.addSeparator()
        for text, slot in (
            ("Settings…", self.open_settings),
            ("History…", self.open_history),
        ):
            act = QAction(text, menu)
            act.triggered.connect(slot)
            menu.addAction(act)
        menu.addSeparator()
        quit_act = QAction("Quit Yapper", menu)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)
        return menu

    def _add_choice_submenu(self, menu: QMenu, title: str, values: list,
                            key: str, labels: dict | None = None) -> QActionGroup:
        """Add an exclusive checkable submenu that sets ``key`` live on click."""
        sub = QMenu(title, menu)
        menu.addMenu(sub)
        self._submenus.append(sub)  # keep the wrapper alive
        group = QActionGroup(sub)
        group.setExclusive(True)
        self._action_groups.append(group)
        current = self.settings.get(key)
        for value in values:
            label = labels.get(value, value) if labels else value
            act = QAction(label or "No Translation", sub)
            act.setCheckable(True)
            act.setData(value)
            act.setChecked(value == current)
            act.triggered.connect(
                lambda _checked=False, v=value, k=key: self._on_quick_toggle(k, v))
            group.addAction(act)
            sub.addAction(act)
        return group

    def _on_quick_toggle(self, key: str, value) -> None:
        """Apply a tray quick-toggle: set + persist + reload runtime state."""
        self.settings.set(key, value)
        self.settings.save()
        self.controller.reload_settings()
        logger.info("Tray quick-toggle: %s = %r", key, value)

    def _start_hotkeys(self) -> None:
        self.hotkeys = HotkeyManager(
            mode=self.settings.get("activation_mode", "push_to_talk"),
            hotkey=self.settings.get("hotkey", "f8"),
            on_start=self._bridge.hotkey_start.emit,
            on_stop=self._bridge.hotkey_stop.emit,
        )
        self.hotkeys.start()

    # -- slots -----------------------------------------------------------
    @Slot(str)
    def _on_state(self, state: str) -> None:
        self.tray.setIcon(_state_icon(state))
        labels = {
            "idle": f"Yapper v{VERSION}",
            "listening": "Yapper — Listening…",
            "transcribing": "Yapper — Transcribing…",
            "done": "Yapper — Done",
        }
        self.tray.setToolTip(labels.get(state, "Yapper"))
        if self._hud is not None:
            if state == "listening":
                self._hud.show_centered_bottom()
            self._hud.set_state(state)

    @Slot(str)
    def _on_result(self, text: str) -> None:
        self.notifier.notify("Yapper", text[:60])

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.notifier.notify("Yapper", message[:80])

    # -- windows ---------------------------------------------------------
    def open_settings(self) -> None:
        from .settings_window import SettingsWindow
        self._settings_win = SettingsWindow(self.settings)
        self._settings_win.settings_saved.connect(self._on_settings_saved)
        self._settings_win.open_history_requested.connect(self.open_history)
        self._settings_win.show()

    def open_history(self) -> None:
        from .history_window import HistoryWindow
        self._history_win = HistoryWindow(self.history, settings=self.settings)
        self._history_win.show()

    def _on_settings_saved(self) -> None:
        self.controller.reload_settings()
        if self.hotkeys is not None:
            self.hotkeys.set_mode(self.settings.get("activation_mode", "push_to_talk"))
            self.hotkeys.set_hotkey(self.settings.get("hotkey", "f8"))

    def quit(self) -> None:
        if self.hotkeys is not None:
            self.hotkeys.stop()
        self.tray.hide()
        self.qapp.quit()

    def run(self) -> int:
        return self.qapp.exec()


def main() -> int:
    setup_logging()
    settings = Settings().load()
    app = YapperApp(settings=settings, start_listener=True)
    if not settings.get("api_key"):
        from .wizard import SetupWizard
        app._wizard = SetupWizard(settings)
        app._wizard.finished_setup.connect(app._on_settings_saved)
        app._wizard.show()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
