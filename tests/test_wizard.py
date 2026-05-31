"""Phase 4 Task 7: SetupWizard tests."""
import pytest

from core import Settings
from ui.wizard import SetupWizard, wizard_steps


def test_steps_include_permissions_on_mac():
    steps = wizard_steps(is_mac=True)
    assert steps == ["Welcome", "Engine", "Connect", "Permissions",
                     "Hotkey & Voice", "All set"]


def test_steps_skip_permissions_on_windows():
    steps = wizard_steps(is_mac=False)
    assert "Permissions" not in steps
    assert steps[0] == "Welcome" and steps[-1] == "All set"


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    return s


def test_wizard_constructs_and_starts_on_first_step(qtbot, settings):
    w = SetupWizard(settings)
    qtbot.addWidget(w)
    assert w.current_index == 0
    assert w.steps[0] == "Welcome"


def test_wizard_next_advances(qtbot, settings):
    w = SetupWizard(settings)
    qtbot.addWidget(w)
    w.go_next()
    assert w.current_index == 1


def test_wizard_finish_emits_signal(qtbot, settings):
    w = SetupWizard(settings)
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.finished_setup, timeout=1000):
        w.current_index = len(w.steps) - 1
        w.go_next()  # from last step -> finish
