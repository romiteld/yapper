"""Phase 4 Task 8: HistoryWindow tests."""
from unittest.mock import MagicMock

import pytest

from core import Settings, TranscriptionHistory, TranscriptionRecord
from ui.history_window import HistoryWindow, filter_records, reprocess_text


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    return s


def _recs():
    return [
        TranscriptionRecord.create("kubectl get pods", 1.0),
        TranscriptionRecord.create("hello world", 0.8),
        TranscriptionRecord.create("Next.js routing", 1.2),
    ]


def test_filter_empty_query_returns_all():
    recs = _recs()
    assert filter_records(recs, "") == recs


def test_filter_is_case_insensitive_substring():
    recs = _recs()
    out = filter_records(recs, "NEXT")
    assert len(out) == 1 and out[0].text == "Next.js routing"


def test_filter_no_match_returns_empty():
    assert filter_records(_recs(), "zzz") == []


def test_history_window_constructs(qtbot, tmp_path):
    hist = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    hist.add(TranscriptionRecord.create("kubectl get pods", 1.0))
    win = HistoryWindow(hist)
    qtbot.addWidget(win)
    assert win._list.count() == 1


def test_history_window_search_filters_list(qtbot, tmp_path):
    hist = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    hist.add(TranscriptionRecord.create("kubectl get pods", 1.0))
    hist.add(TranscriptionRecord.create("hello world", 0.8))
    win = HistoryWindow(hist)
    qtbot.addWidget(win)
    win._search.setText("kubectl")
    win._apply_filter()
    assert win._list.count() == 1


# ---- HIGH-4: Reprocess action ----------------------------------------------

def test_reprocess_text_expands_spoken_symbols(settings):
    # verbatim mode skips the LLM, so reprocessing is deterministic; with
    # expand_spoken_symbols the spoken token is expanded.
    settings.set("output_mode", "verbatim")
    settings.set("expand_spoken_symbols", True)
    settings.set("api_key", "")  # no LLM calls
    out = reprocess_text("git commit dash dash amend", settings)
    assert "--amend" in out


def test_reprocess_text_never_raises_returns_original(settings):
    # Force a failure path: a settings object whose get explodes.
    broken = MagicMock()
    broken.get.side_effect = RuntimeError("boom")
    assert reprocess_text("hello", broken) == "hello"


def test_history_window_reprocess_inserts_via_typer(qtbot, tmp_path, settings, monkeypatch):
    """Reprocess runs off the GUI thread and delivers the result via a queued
    signal.  We call the private _on_reprocess_done slot directly to verify
    that it types the text — the threading/signal wiring is exercised by the
    _reprocess_selected test below."""
    settings.set("output_mode", "verbatim")
    settings.set("expand_spoken_symbols", True)
    settings.set("api_key", "")
    hist = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    hist.add(TranscriptionRecord.create("dash dash help", 1.0))
    win = HistoryWindow(hist, settings=settings)
    qtbot.addWidget(win)

    typed = {}
    import ui.history_window as hw

    class FakeTyper:
        def type_text(self, text, method="paste"):
            typed["text"] = text
            typed["method"] = method
            return True

    monkeypatch.setattr(hw, "TextTyper", FakeTyper)
    # Call the GUI-thread slot directly (the slot is what does the typing).
    win._on_reprocess_done("--help expanded")
    assert typed["method"] == "paste"
    assert "--help" in typed["text"]


def test_history_window_reprocess_selected_spawns_thread(qtbot, tmp_path, settings, monkeypatch):
    """_reprocess_selected() disables the button and emits the result via a
    worker thread + queued signal rather than blocking the GUI thread."""
    import threading
    settings.set("output_mode", "verbatim")
    settings.set("expand_spoken_symbols", True)
    settings.set("api_key", "")
    hist = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    hist.add(TranscriptionRecord.create("dash dash help", 1.0))
    win = HistoryWindow(hist, settings=settings)
    qtbot.addWidget(win)
    win._list.setCurrentRow(0)

    typed = {}
    import ui.history_window as hw

    class FakeTyper:
        def type_text(self, text, method="paste"):
            typed["text"] = text
            typed["method"] = method
            return True

    monkeypatch.setattr(hw, "TextTyper", FakeTyper)

    win._reprocess_selected()
    # Button should be disabled immediately (while the thread runs).
    assert not win._reprocess_btn.isEnabled()
    # Wait for the worker thread to finish and the queued signal to be processed.
    qtbot.waitUntil(lambda: win._reprocess_btn.isEnabled(), timeout=3000)
    assert "method" in typed
    assert typed["method"] == "paste"
    assert "--help" in typed["text"]


def test_history_window_has_reprocess_button(qtbot, tmp_path, settings):
    hist = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    win = HistoryWindow(hist, settings=settings)
    qtbot.addWidget(win)
    from PySide6.QtWidgets import QPushButton
    labels = {b.text() for b in win.findChildren(QPushButton)}
    assert {"Copy", "Re-insert", "Reprocess", "Export", "Clear"} <= labels
