"""Phase 4 Task 8: HistoryWindow tests."""
from core import TranscriptionHistory, TranscriptionRecord
from ui.history_window import HistoryWindow, filter_records


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
