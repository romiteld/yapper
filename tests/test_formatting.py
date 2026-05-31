"""Tests for the no-slop formatting subsystem."""
from app.core.formatting import expand_spoken_symbols


def test_dash_dash_flag():
    assert expand_spoken_symbols("run dash dash help now") == "run --help now"


def test_single_dash_flag():
    assert expand_spoken_symbols("apply dash f file") == "apply -f file"


def test_dot_extension_py():
    assert expand_spoken_symbols("open deployment dot yaml") == "open deployment.yaml"
    assert expand_spoken_symbols("edit main dot py") == "edit main.py"


def test_backtick_word():
    assert expand_spoken_symbols("wrap backtick code backtick here") == "wrap `code` here"


def test_open_close_paren():
    assert expand_spoken_symbols("call open paren x close paren") == "call (x)"


def test_new_line():
    assert expand_spoken_symbols("line one new line line two") == "line one\nline two"


def test_does_not_corrupt_prose():
    # 'dash' as a normal word without a following token stays untouched
    text = "I went for a quick dash to the store"
    assert expand_spoken_symbols(text) == text


def test_idempotent_on_plain_prose():
    text = "the quick brown fox jumps over the lazy dog"
    assert expand_spoken_symbols(text) == text
