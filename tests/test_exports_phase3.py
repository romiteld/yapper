"""Phase 3 public exports."""
import app.core as core


def test_vocabulary_exported():
    from app.core import Vocabulary
    assert Vocabulary is core.Vocabulary


def test_formatter_and_expand_exported():
    from app.core import Formatter, expand_spoken_symbols
    assert callable(expand_spoken_symbols)
    assert Formatter is core.Formatter
