"""Settings window — sidebar nav bound to core.Settings.

© 2026 Cloudelipute
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import HOTKEYS, LANGUAGES, Settings, get_logger
from . import theme

logger = get_logger("settings_window")


class SettingsBinder:
    """Headless read/write bridge between widgets and Settings (validated)."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def read(self, key: str) -> Any:
        return self.settings.get(key)

    def write(self, key: str, value: Any) -> None:
        # Settings.set validates; silently ignore invalid values.
        self.settings.set(key, value)

    def commit(self) -> bool:
        return self.settings.save()


class SettingsWindow(QWidget):
    settings_saved = Signal()

    SECTIONS = [
        "General", "Engine & Models", "Vocabulary", "Formatting",
        "Hotkeys", "Audio", "History", "About",
    ]

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.binder = SettingsBinder(settings)
        self.setWindowTitle("Yapper — Settings")
        self.setStyleSheet(theme.qss())
        self.resize(760, 540)

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        self._nav = QListWidget()
        self._nav.addItems(self.SECTIONS)
        self._nav.setFixedWidth(190)
        self._nav.currentRowChanged.connect(lambda i: self._stack.setCurrentIndex(i))
        body.addWidget(self._nav)

        self._stack = QStackedWidget()
        for section in self.SECTIONS:
            self._stack.addWidget(self._build_section(section))
        body.addWidget(self._stack, 1)
        root.addLayout(body, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        save = QPushButton("Save", objectName="Primary")
        save.clicked.connect(self._on_save)
        bar.addWidget(save)
        root.addLayout(bar)
        self._nav.setCurrentRow(0)

    def _build_section(self, section: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel(section, objectName="Title"))
        if section == "Engine & Models":
            self._engine = self._combo(lay, "Engine", ["cloud", "local"], "engine")
            self._cloud_model = self._combo(
                lay, "Cloud STT model",
                ["gpt-4o-mini-transcribe", "whisper-1"], "cloud_stt_model")
            self._text_model = self._combo(
                lay, "Text model", ["gpt-5-nano", "gpt-5.4-nano"], "text_model")
        elif section == "Formatting":
            # Output modes: Clean / Polished / Verbatim (general-purpose framing)
            # Clean = fix mechanics, keep your words (default)
            # Polished = tidy-prose rewrite
            # Verbatim = raw, no LLM cleanup
            self._mode = self._combo(
                lay, "Output mode", ["clean", "polished", "verbatim"], "output_mode")
            self._expand = self._check(lay, "Expand spoken symbols", "expand_spoken_symbols")
            self._translate = self._combo(
                lay, "Translate to", list(LANGUAGES.keys()), "translate_to")
        elif section == "Hotkeys":
            self._mode_act = self._combo(
                lay, "Activation", ["push_to_talk", "toggle", "wake_word"], "activation_mode")
            self._hotkey = self._combo(lay, "Hotkey", HOTKEYS, "hotkey")
        elif section == "Audio":
            self._insertion = self._combo(
                lay, "Insertion method", ["paste", "type"], "insertion_method")
            self._feedback = self._check(lay, "Audio feedback", "audio_feedback")
        elif section == "General":
            self._hud = self._check(lay, "Show recording HUD", "show_hud")
            self._reduce = self._check(lay, "Reduce motion", "reduce_motion")
            self._save_hist = self._check(lay, "Save history", "save_history")
        elif section == "About":
            lay.addWidget(QLabel("© 2026 Cloudelipute", objectName="Muted"))
        lay.addStretch(1)
        return page

    # -- widget helpers (write straight to binder on change) -------------
    def _combo(self, lay, label, items, key) -> QComboBox:
        lay.addWidget(QLabel(label, objectName="Muted"))
        cb = QComboBox()
        cb.addItems([str(i) for i in items])
        current = str(self.binder.read(key))
        if current in [str(i) for i in items]:
            cb.setCurrentText(current)
        cb.currentTextChanged.connect(lambda v, k=key: self.binder.write(k, v))
        lay.addWidget(cb)
        return cb

    def _check(self, lay, label, key) -> QCheckBox:
        cx = QCheckBox(label)
        cx.setChecked(bool(self.binder.read(key)))
        cx.toggled.connect(lambda v, k=key: self.binder.write(k, v))
        lay.addWidget(cx)
        return cx

    def _on_save(self) -> None:
        if self.binder.commit():
            self.settings_saved.emit()
            self.close()
