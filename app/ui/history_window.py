"""History window — searchable transcription history with row actions.

© 2026 Cloudelipute
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import (
    Settings,
    TextTyper,
    TranscriptionHistory,
    TranscriptionRecord,
    get_logger,
)
from . import theme

logger = get_logger("history_window")


def filter_records(records: List[TranscriptionRecord], query: str) -> List[TranscriptionRecord]:
    """Case-insensitive substring filter over record text."""
    q = query.strip().lower()
    if not q:
        return records
    return [r for r in records if q in r.text.lower()]


def reprocess_text(text: str, settings: Settings) -> str:
    """Re-run stored text through the Formatter with the CURRENT settings.

    Reuses the no-slop pipeline (spoken-symbol expansion, vocabulary, mode
    cleanup, translation) so a user can re-clean or re-translate a past
    transcription without re-recording. Returns the original text unchanged if
    formatting fails (e.g. no API key) — never raises to the UI.
    """
    try:
        from core import APIClient
        from core.formatting import Formatter
        from core.vocabulary import Vocabulary
        vocab = Vocabulary(load_starter=False)
        vocab.from_list(settings.get("vocabulary", []))
        client = APIClient(api_key=settings.get("api_key"))
        formatter = Formatter(client, vocab)
        return formatter.format(
            text,
            mode=settings.get("output_mode", "clean"),
            expand_symbols=bool(settings.get("expand_spoken_symbols", True)),
            translate_to=settings.get("translate_to") or None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"reprocess failed: {exc}")
        return text


class HistoryWindow(QWidget):
    def __init__(self, history: TranscriptionHistory,
                 settings: Optional[Settings] = None, parent=None):
        super().__init__(parent)
        self.history = history
        self.settings = settings or Settings().load()
        self.setWindowTitle("Yapper — History")
        self.setStyleSheet(theme.qss())
        self.resize(640, 520)

        root = QVBoxLayout(self)
        self._search = QLineEdit(placeholderText="Search transcriptions…")
        self._search.textChanged.connect(self._apply_filter)
        root.addWidget(self._search)

        self._list = QListWidget()
        root.addWidget(self._list, 1)

        row = QHBoxLayout()
        for text, slot in (
            ("Copy", self._copy_selected),
            ("Re-insert", self._reinsert_selected),
            ("Reprocess", self._reprocess_selected),
            ("Export", self._export),
            ("Clear", self._clear),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        root.addLayout(row)
        root.addWidget(QLabel("© 2026 Cloudelipute", objectName="Muted"))

        self._reload()

    def _reload(self) -> None:
        self._records = list(reversed(self.history.get_all()))
        self._apply_filter()

    def _apply_filter(self) -> None:
        self._list.clear()
        for rec in filter_records(self._records, self._search.text()):
            item = QListWidgetItem(f"{rec.timestamp[:19]}  ·  {rec.text}")
            item.setData(256, rec.text)  # Qt.UserRole == 256
            self._list.addItem(item)

    def _selected_text(self) -> str | None:
        item = self._list.currentItem()
        return item.data(256) if item else None

    def _copy_selected(self) -> None:
        text = self._selected_text()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)

    def _reinsert_selected(self) -> None:
        text = self._selected_text()
        if text:
            TextTyper().type_text(text, method="paste")

    def _reprocess_selected(self) -> None:
        """Re-run the selected text through the Formatter with current settings,
        then insert the reprocessed result at the cursor."""
        text = self._selected_text()
        if not text:
            return
        result = reprocess_text(text, self.settings)
        TextTyper().type_text(result, method="paste")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export history", "history.json", "JSON (*.json)")
        if path:
            data = [r.__dict__ for r in self.history.get_all()]
            Path(path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _clear(self) -> None:
        self.history.clear()
        self._reload()
