"""First-run setup wizard — sidebar steps.

© 2026 Cloudelipute
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, QTimer, Signal, Slot
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
    # Emitted (possibly from the Controller's worker thread) with the mic-test
    # result text. Connected with a queued connection to a Qt-main-thread slot
    # so QLabel is never mutated off the GUI thread.
    _mic_result_ready = Signal(str)

    def __init__(self, settings: Settings, is_mac: bool | None = None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.steps = wizard_steps(
            platform.system() == "Darwin" if is_mac is None else is_mac
        )
        self.current_index = 0
        # Hold a reference so the mic-test Controller isn't GC'd mid-recording.
        self._mic_controller = None
        # Queued connection guarantees the slot runs on the GUI thread even when
        # emitted from the Controller worker thread.
        self._mic_result_ready.connect(
            self._set_mic_result, Qt.ConnectionType.QueuedConnection)

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
            lay.addWidget(QLabel("Paste your ElevenLabs API key:", objectName="Muted"))
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

    @Slot(str)
    def _set_mic_result(self, text: str) -> None:
        """GUI-thread slot that updates the mic-test label."""
        if hasattr(self, "_mic_result"):
            self._mic_result.setText(text)

    def _on_mic_result(self, text: str) -> None:
        """Controller on_result callback — may run on the worker thread.

        Routes the text to the GUI thread via a queued signal instead of
        touching the QLabel directly (Qt widgets are not thread-safe).
        """
        self._mic_result_ready.emit(
            f"Heard: {text[:48]}" if text else "No speech detected")

    def _mic_error(self, message: str) -> None:
        """Controller on_error callback — may run on the worker thread."""
        self._mic_result_ready.emit(f"Mic test failed: {message}")

    def _mic_fallback(self) -> None:
        """Fallback timer slot: surface a message if no result arrived yet."""
        if hasattr(self, "_mic_result") and \
                self._mic_result.text() == "Recording 2s… speak now":
            self._mic_result.setText("No result — check mic and API key")

    def _run_mic_test(self) -> None:
        # Real, short capture + transcription so the user gets a success moment.
        # Uses dry_run=True so the result is NOT typed into the user's active field.
        try:
            from .controller import Controller
            self._mic_result.setText("Recording 2s… speak now")
            # A lightweight one-shot using the same pipeline. Keep a reference
            # on self so it isn't garbage-collected mid-recording, route the
            # worker-thread result through a queued signal (thread-safe), and
            # wire on_error so missing-key / API failures surface to the UI.
            self._mic_controller = Controller(
                self.settings,
                on_result=self._on_mic_result,
                on_error=self._mic_error,
                dry_run=True,  # do NOT type the transcription into the focused field
            )
            self._mic_controller.start_recording()
            QTimer.singleShot(2000, self._mic_controller.stop_recording)
            # Fallback: if neither on_result nor on_error fired (e.g. silence /
            # empty transcription that returns IDLE silently), surface a message.
            QTimer.singleShot(6000, self._mic_fallback)
        except Exception as exc:  # noqa: BLE001
            self._mic_result.setText(f"Mic test failed: {exc}")

    def _refresh_permissions(self) -> None:
        from core.permissions import permission_status
        st = permission_status()
        self._perm_label.setText(
            f"mic={st.microphone}  accessibility={st.accessibility}  "
            f"input_monitoring={st.input_monitoring}")
