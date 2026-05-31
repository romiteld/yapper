"""Phase 4 Task 7: SetupWizard tests."""
import threading

import pytest
from PySide6.QtWidgets import QApplication

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


# ---- CRITICAL: mic-test result is marshaled to the GUI thread --------------

def test_mic_result_uses_queued_signal_not_direct_call(qtbot, settings):
    """on_result must emit a signal, never touch the QLabel directly.

    Emitting from a worker thread; with a queued connection the label is NOT
    updated synchronously — it only updates after the Qt event loop processes
    the queued slot on the main thread.
    """
    w = SetupWizard(settings, is_mac=False)
    qtbot.addWidget(w)
    # Build the "Hotkey & Voice" page so _mic_result exists.
    w.current_index = w.steps.index("Hotkey & Voice")
    w._refresh()
    assert hasattr(w, "_mic_result")

    main_thread = threading.current_thread()
    slot_thread = {}
    orig = w._set_mic_result

    def spy(text):
        slot_thread["thread"] = threading.current_thread()
        orig(text)

    w._set_mic_result = spy  # type: ignore[assignment]
    # Reconnect the spy through the queued signal.
    w._mic_result_ready.disconnect()
    from PySide6.QtCore import Qt as _Qt
    w._mic_result_ready.connect(spy, _Qt.ConnectionType.QueuedConnection)

    def worker():
        # Simulate the Controller worker thread delivering a result.
        w._on_mic_result("kubectl get pods")

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    # Queued: label not yet updated synchronously from the worker thread.
    assert w._mic_result.text() != "Heard: kubectl get pods"
    # Pump the event loop; the queued slot now runs on the main thread.
    qtbot.waitUntil(lambda: w._mic_result.text() == "Heard: kubectl get pods",
                    timeout=1000)
    assert slot_thread["thread"] is main_thread


def test_mic_test_stores_controller_reference(qtbot, settings, monkeypatch):
    """The mic-test Controller must be held on self so it isn't GC'd."""
    w = SetupWizard(settings, is_mac=False)
    qtbot.addWidget(w)
    w.current_index = w.steps.index("Hotkey & Voice")
    w._refresh()

    from ui import controller as controller_mod

    class FakeController:
        def __init__(self, *a, **kw):
            self.started = False

        def start_recording(self):
            self.started = True

        def stop_recording(self):
            pass

    monkeypatch.setattr(controller_mod, "Controller", FakeController)
    w._run_mic_test()
    assert isinstance(w._mic_controller, FakeController)
    assert w._mic_controller.started is True
