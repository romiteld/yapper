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
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import HOTKEYS, LANGUAGES, Settings, get_logger
from . import theme

logger = get_logger("settings_window")


def vocabulary_to_text(vocab_list: list) -> str:
    """Render a settings['vocabulary'] list as one term per line.

    Each term may be a bare string (typed-only) or a dict {typed, said}. The
    'said' aliases are shown after a '=' so users can edit both halves:
        kubectl
        Next.js = next js, nextjs
    """
    lines = []
    for entry in vocab_list or []:
        if isinstance(entry, str):
            lines.append(entry)
        elif isinstance(entry, dict) and entry.get("typed"):
            said = entry.get("said")
            lines.append(f"{entry['typed']} = {said}" if said else entry["typed"])
    return "\n".join(lines)


def text_to_vocabulary(text: str) -> list:
    """Parse one-term-per-line text back into a settings['vocabulary'] list.

    Inverse of vocabulary_to_text. Blank lines are ignored. A '=' splits the
    typed form from its spoken aliases.
    """
    out = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "=" in line:
            typed, said = line.split("=", 1)
            typed, said = typed.strip(), said.strip()
            if typed:
                out.append({"typed": typed, "said": said or None})
        else:
            out.append({"typed": line, "said": None})
    return out


class SettingsBinder:
    """Buffered read/write bridge between widgets and Settings.

    Edits are staged in ``_pending`` and only written to ``Settings`` (and
    persisted) on ``commit()`` — so closing/cancelling without Save leaves the
    in-memory Settings untouched. ``read`` reflects the pending value if one is
    staged, otherwise the live Settings value.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._pending: dict[str, Any] = {}

    def read(self, key: str) -> Any:
        if key in self._pending:
            return self._pending[key]
        return self.settings.get(key)

    def write(self, key: str, value: Any) -> None:
        # Stage the edit; do NOT mutate Settings until commit().
        self._pending[key] = value

    @property
    def dirty(self) -> bool:
        return bool(self._pending)

    def discard(self) -> None:
        """Drop all staged edits (Cancel/close without Save)."""
        self._pending.clear()

    def commit(self) -> bool:
        """Apply staged edits to Settings (validated) and persist."""
        for key, value in self._pending.items():
            # Settings.set validates; invalid values are silently skipped.
            self.settings.set(key, value)
        self._pending.clear()
        return self.settings.save()


class SettingsWindow(QWidget):
    settings_saved = Signal()
    open_history_requested = Signal()

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
            # Show human-readable language names; persist the language code.
            self._translate = self._lang_combo(lay, "Translate to", "translate_to")
        elif section == "Vocabulary":
            lay.addWidget(QLabel(
                "Custom terms, one per line. Use 'Typed = said, aliases' to map "
                "mis-hears (e.g. 'Next.js = next js, nextjs').",
                objectName="Muted"))
            self._vocab_edit = QPlainTextEdit()
            self._vocab_edit.setPlainText(
                vocabulary_to_text(self.binder.read("vocabulary")))
            self._vocab_edit.textChanged.connect(self._on_vocab_changed)
            lay.addWidget(self._vocab_edit, 1)
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
        elif section == "History":
            # Do NOT add a second "Save history" checkbox here — it would show
            # a stale state when toggled from the General section (both widgets
            # are built eagerly and there is no cross-widget sync). The single
            # checkbox in General is the canonical control.
            open_btn = QPushButton("Open history…")
            open_btn.clicked.connect(self.open_history_requested.emit)
            lay.addWidget(open_btn)
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

    def _lang_combo(self, lay, label, key) -> QComboBox:
        """A combo that displays LANGUAGES display names but stores the code."""
        lay.addWidget(QLabel(label, objectName="Muted"))
        cb = QComboBox()
        codes = list(LANGUAGES.keys())
        cb.addItems([LANGUAGES[c] for c in codes])
        current_code = str(self.binder.read(key) or "")
        if current_code in codes:
            cb.setCurrentIndex(codes.index(current_code))
        cb.currentIndexChanged.connect(
            lambda i, k=key, cs=codes: self.binder.write(k, cs[i]))
        lay.addWidget(cb)
        return cb

    def _on_vocab_changed(self) -> None:
        self.binder.write(
            "vocabulary", text_to_vocabulary(self._vocab_edit.toPlainText()))

    def _on_save(self) -> None:
        if self.binder.commit():
            self.settings_saved.emit()
            self.close()

    def closeEvent(self, event):  # noqa: N802 - Qt override
        # Closing without Save drops any staged edits (commit() already cleared
        # _pending, so this is a no-op after a successful save).
        self.binder.discard()
        super().closeEvent(event)
