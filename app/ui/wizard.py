"""First-run setup wizard — sidebar steps.

© 2026 Cloudelipute
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import HOTKEYS, Settings, get_logger
from . import theme

logger = get_logger("wizard")


def wizard_steps(is_mac: bool) -> list[str]:
    """Ordered step titles; Permissions is mac-only."""
    steps = ["Welcome", "Engine", "Connect"]
    if is_mac:
        steps.append("Permissions")
    steps += ["Hotkey & Voice", "All set"]
    return steps


class SetupWizard(QWidget):
    finished_setup = Signal()

    def __init__(self, settings: Settings, is_mac: bool | None = None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.steps = wizard_steps(
            platform.system() == "Darwin" if is_mac is None else is_mac
        )
        self.current_index = 0

        self.setWindowTitle("Welcome to Yapper")
        self.setStyleSheet(theme.qss())
        self.resize(720, 460)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame(objectName="Sidebar")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 24, 16, 24)
        self._step_labels: list[QLabel] = []
        for name in self.steps:
            lbl = QLabel(name, objectName="Muted")
            self._step_labels.append(lbl)
            sb.addWidget(lbl)
        sb.addStretch(1)
        sidebar.setFixedWidth(200)
        root.addWidget(sidebar)

        right = QVBoxLayout()
        self._stack = QStackedWidget()
        for name in self.steps:
            self._stack.addWidget(self._build_page(name))
        right.addWidget(self._stack, 1)

        nav = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self.go_back)
        self._next_btn = QPushButton("Next", objectName="Primary")
        self._next_btn.clicked.connect(self.go_next)
        nav.addWidget(self._back_btn)
        nav.addStretch(1)
        nav.addWidget(self._next_btn)
        right.addLayout(nav)
        root.addLayout(right, 1)

        self._refresh()

    # -- page builders ---------------------------------------------------
    def _build_page(self, name: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 32, 32, 32)
        title = QLabel(name, objectName="Title")
        lay.addWidget(title)
        if name == "Welcome":
            lay.addWidget(QLabel(
                "Yapper turns your voice into text — anywhere you can type.\n\n"
                "Press Next to configure your setup.",
                objectName="Muted"))
        elif name == "Connect":
            lay.addWidget(QLabel("Paste your OpenAI API key:", objectName="Muted"))
            self._api_edit = QLineEdit()
            self._api_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._api_edit.setText(self.settings.get("api_key", ""))
            lay.addWidget(self._api_edit)
        elif name == "Engine":
            lay.addWidget(QLabel("Transcription engine:", objectName="Muted"))
            self._engine_combo = QComboBox()
            self._engine_combo.addItems(["cloud", "local"])
            self._engine_combo.setCurrentText(self.settings.get("engine", "cloud"))
            lay.addWidget(self._engine_combo)
        elif name == "Hotkey & Voice":
            lay.addWidget(QLabel("Activation hotkey:", objectName="Muted"))
            self._hotkey_combo = QComboBox()
            self._hotkey_combo.addItems(HOTKEYS)
            self._hotkey_combo.setCurrentText(self.settings.get("hotkey", "f8"))
            lay.addWidget(self._hotkey_combo)
            self._mic_test_btn = QPushButton("Test microphone")
            self._mic_test_btn.clicked.connect(self._run_mic_test)
            lay.addWidget(self._mic_test_btn)
            self._mic_result = QLabel("", objectName="Muted")
            lay.addWidget(self._mic_result)
        elif name == "Permissions":
            lay.addWidget(QLabel(
                "Grant Microphone, Accessibility, and Input Monitoring in "
                "System Settings, then quit & relaunch Yapper.", objectName="Muted"))
            self._perm_btn = QPushButton("Re-check permissions")
            self._perm_btn.clicked.connect(self._refresh_permissions)
            lay.addWidget(self._perm_btn)
            self._perm_label = QLabel("", objectName="Muted")
            lay.addWidget(self._perm_label)
        elif name == "All set":
            lay.addWidget(QLabel(
                "You're all set! Click Finish to start using Yapper.\n\n"
                "Yapper will appear in your system tray.",
                objectName="Muted"))
        lay.addStretch(1)
        return page

    # -- navigation ------------------------------------------------------
    def go_next(self) -> None:
        self._persist_current()
        if self.current_index >= len(self.steps) - 1:
            self.settings.save()
            self.finished_setup.emit()
            self.close()
            return
        self.current_index += 1
        self._refresh()

    def go_back(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._refresh()

    def _refresh(self) -> None:
        self._stack.setCurrentIndex(self.current_index)
        self._back_btn.setEnabled(self.current_index > 0)
        self._next_btn.setText(
            "Finish" if self.current_index == len(self.steps) - 1 else "Next"
        )
        for i, lbl in enumerate(self._step_labels):
            lbl.setObjectName("Title" if i == self.current_index else "Muted")
            lbl.setStyleSheet(theme.qss())

    def _persist_current(self) -> None:
        name = self.steps[self.current_index]
        if name == "Connect" and hasattr(self, "_api_edit"):
            self.settings.set("api_key", self._api_edit.text().strip())
        elif name == "Engine" and hasattr(self, "_engine_combo"):
            self.settings.set("engine", self._engine_combo.currentText())
        elif name == "Hotkey & Voice" and hasattr(self, "_hotkey_combo"):
            self.settings.set("hotkey", self._hotkey_combo.currentText())

    def _run_mic_test(self) -> None:
        # Real, short capture + transcription so the user gets a success moment.
        try:
            from .controller import Controller
            self._mic_result.setText("Recording 2s… speak now")
            # A lightweight one-shot using the same pipeline, fire-and-forget.
            c = Controller(self.settings, on_result=lambda t: self._mic_result.setText(
                f"Heard: {t[:48]}" if t else "No speech detected"))
            c.start_recording()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, c.stop_recording)
        except Exception as exc:  # noqa: BLE001
            self._mic_result.setText(f"Mic test failed: {exc}")

    def _refresh_permissions(self) -> None:
        from core.permissions import permission_status
        st = permission_status()
        self._perm_label.setText(
            f"mic={st.microphone}  accessibility={st.accessibility}  "
            f"input_monitoring={st.input_monitoring}")
