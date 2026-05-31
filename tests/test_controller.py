"""Phase 4 Tasks 2-5: Controller state machine tests."""
from unittest.mock import MagicMock

import pytest

from core import Settings
from ui.controller import Controller, ControllerState


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s


# ---- Task 2: state machine ------------------------------------------------

def test_initial_state_is_idle(settings):
    c = Controller(settings)
    assert c.state == ControllerState.IDLE


def test_state_changes_emit_callback(settings):
    seen = []
    c = Controller(settings, on_state=seen.append)
    c._set_state(ControllerState.LISTENING)
    c._set_state(ControllerState.TRANSCRIBING)
    assert seen == [ControllerState.LISTENING, ControllerState.TRANSCRIBING]


def test_duplicate_state_not_re_emitted(settings):
    seen = []
    c = Controller(settings, on_state=seen.append)
    c._set_state(ControllerState.LISTENING)
    c._set_state(ControllerState.LISTENING)
    assert seen == [ControllerState.LISTENING]


# ---- Task 3: start recording ----------------------------------------------

def test_start_recording_sets_listening_and_calls_recorder(settings):
    fake_rec = MagicMock()
    fake_rec.start.return_value = True
    seen = []
    c = Controller(settings, on_state=seen.append)
    c._recorder_factory = lambda **kw: fake_rec
    c.start_recording()
    assert c.state == ControllerState.LISTENING
    fake_rec.start.assert_called_once()
    assert seen[-1] == ControllerState.LISTENING


def test_start_recording_failure_emits_error(settings):
    fake_rec = MagicMock()
    fake_rec.start.return_value = False
    errors = []
    c = Controller(settings, on_error=errors.append)
    c._recorder_factory = lambda **kw: fake_rec
    c.start_recording()
    assert c.state == ControllerState.IDLE
    assert errors and "record" in errors[0].lower()


def test_start_recording_ignored_when_already_listening(settings):
    fake_rec = MagicMock()
    fake_rec.start.return_value = True
    c = Controller(settings)
    c._recorder_factory = lambda **kw: fake_rec
    c.start_recording()
    c.start_recording()
    fake_rec.start.assert_called_once()


# ---- HIGH-1: on_level wiring (HUD ring) ------------------------------------

def test_recorder_factory_receives_on_level(settings):
    captured = {}

    def factory(**kw):
        captured.update(kw)
        rec = MagicMock()
        rec.start.return_value = True
        return rec

    c = Controller(settings)
    c._recorder_factory = factory
    c.start_recording()
    assert "on_level" in captured
    assert callable(captured["on_level"])


def test_level_callback_forwarded_while_listening(settings):
    levels = []
    fake_rec = MagicMock()
    fake_rec.start.return_value = True
    c = Controller(settings, on_level=levels.append)
    c._recorder_factory = lambda **kw: fake_rec
    c.start_recording()
    # Simulate the audio thread emitting RMS chunks.
    c._emit_level(0.5)
    c._emit_level(0.8)
    assert levels == [0.5, 0.8]


def test_level_callback_suppressed_when_not_listening(settings):
    levels = []
    c = Controller(settings, on_level=levels.append)
    # idle -> a stray late callback must not animate the HUD.
    c._emit_level(0.9)
    assert levels == []


# ---- Task 4: full pipeline ------------------------------------------------

def _wired_controller(settings, raw="raw text", formatted="kubectl get pods"):
    fake_rec = MagicMock()
    fake_rec.start.return_value = True
    fake_rec.stop.return_value = "/tmp/yapper_x.wav"
    fake_rec.frames = [b"\x00\x01" * 800]
    fake_rec.duration_seconds = 1.3

    fake_engine = MagicMock()
    fake_engine.transcribe.return_value = raw
    fake_formatter = MagicMock()
    fake_formatter.format.return_value = formatted
    fake_typer = MagicMock()
    fake_typer.type_text.return_value = True

    # Keep history writes inside the test's temp dir, never the real logs/.
    from core import TranscriptionHistory
    hist = TranscriptionHistory(history_dir=settings.path.parent, enabled=True)
    c = Controller(settings, history=hist)
    c._recorder_factory = lambda **kw: fake_rec
    c._engine_factory = lambda: fake_engine
    c._formatter_factory = lambda: fake_formatter
    c._typer_factory = lambda: fake_typer
    # Defeat VAD gating for deterministic tests.
    c._has_speech = lambda frames: True
    return c, fake_rec, fake_engine, fake_formatter, fake_typer


def test_full_pipeline_types_formatted_text(settings):
    results = []
    c, rec, engine, fmt, typer = _wired_controller(settings)
    c._on_result = results.append
    c.start_recording()
    c.stop_recording()
    c._await_processing()  # blocks until the worker thread finishes
    engine.transcribe.assert_called_once()
    fmt.format.assert_called_once()
    typer.type_text.assert_called_once_with("kubectl get pods", method="paste")
    assert results == ["kubectl get pods"]
    assert c.state == ControllerState.IDLE


def test_pipeline_passes_vocabulary_prompt_to_engine(settings):
    c, rec, engine, fmt, typer = _wired_controller(settings)
    c.start_recording()
    c.stop_recording()
    c._await_processing()
    # engine.transcribe(wav_path, language=..., prompt=...)
    _, kwargs = engine.transcribe.call_args
    assert "prompt" in kwargs
    assert "language" in kwargs


def test_pipeline_skips_when_no_speech(settings):
    c, rec, engine, fmt, typer = _wired_controller(settings)
    c._has_speech = lambda frames: False
    c.start_recording()
    c.stop_recording()
    c._await_processing()
    engine.transcribe.assert_not_called()
    assert c.state == ControllerState.IDLE


def test_pipeline_records_history(settings):
    c, rec, engine, fmt, typer = _wired_controller(settings)
    c.history.add = MagicMock(return_value=True)
    c.start_recording()
    c.stop_recording()
    c._await_processing()
    c.history.add.assert_called_once()


# ---- Task 5: hotkey wiring + reload settings ------------------------------

def test_toggle_handler_starts_then_stops(settings):
    c, rec, engine, fmt, typer = _wired_controller(settings)
    assert c.state == ControllerState.IDLE
    c.on_hotkey_start()        # PTT down / toggle on
    assert c.state == ControllerState.LISTENING
    c.on_hotkey_stop()         # PTT up / toggle off
    c._await_processing()
    assert c.state == ControllerState.IDLE


def test_reload_settings_updates_sound_and_history(settings):
    c = Controller(settings)
    settings.set("audio_feedback", False)
    settings.set("save_history", False)
    c.reload_settings()
    assert c.sounds.enabled is False
    assert c.history.enabled is False
