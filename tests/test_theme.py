"""Phase 4 Task 1: Theme tests."""
from ui import theme


def test_accent_is_pink():
    assert theme.ACCENT == "#ec2a8e"


def test_qss_is_nonempty_str_mentioning_accent():
    css = theme.qss()
    assert isinstance(css, str)
    assert theme.ACCENT in css
    assert "QWidget" in css


def test_state_colors_cover_all_states():
    for state in ("idle", "listening", "transcribing", "done"):
        assert state in theme.STATE_COLORS
        assert theme.STATE_COLORS[state].startswith("#")
