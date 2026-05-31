"""Phase 4 Task 6: RecordingHUD tests."""
import pytest

from ui.hud import RecordingHUD


def test_hud_constructs(qtbot):
    hud = RecordingHUD()
    qtbot.addWidget(hud)
    assert hud.state == "idle"


def test_set_state_updates_state_and_repaints(qtbot):
    hud = RecordingHUD()
    qtbot.addWidget(hud)
    for state in ("listening", "transcribing", "done", "idle"):
        hud.set_state(state)
        assert hud.state == state


def test_set_state_rejects_unknown(qtbot):
    hud = RecordingHUD()
    qtbot.addWidget(hud)
    with pytest.raises(ValueError):
        hud.set_state("bogus")


def test_update_level_clamps(qtbot):
    hud = RecordingHUD()
    qtbot.addWidget(hud)
    hud.update_level(5.0)
    assert hud._level == 1.0
    hud.update_level(-1.0)
    assert hud._level == 0.0


def test_reduce_motion_disables_level_animation(qtbot):
    hud = RecordingHUD(reduce_motion=True)
    qtbot.addWidget(hud)
    hud.set_state("listening")
    # With reduce_motion the level ring stays flat regardless of input.
    hud.update_level(0.9)
    assert hud._displayed_level == 0.0
