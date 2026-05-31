# [Phase 4: UI Overhaul (PySide6)] Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Replace the retired tray/console/customtkinter entry points with a single PySide6 Qt app — tray, recording HUD, setup wizard, settings window, and history window — driven by a headless, fully-tested `Controller` that wires `HotkeyManager → AudioRecorder → get_engine() → Formatter → TextTyper → HUD`.

**Architecture:** Qt owns the one event loop. A pure-Python `Controller` (no Qt imports) holds all dictation orchestration and is unit-tested with mocks. The pynput-thread `HotkeyManager` callbacks are marshaled into Qt through a `_Bridge(QObject)` with Signals, so all UI mutation happens on the Qt main thread. Widgets are thin; their logic lives in testable controller/helper functions, and widget construction is smoke-tested with `pytest-qt` (`qtbot`).

**Tech Stack:** PySide6 (Qt6 widgets, `QSystemTrayIcon`, `QWidget`, `Signal`/`Slot`, `QTimer`), pytest + pytest-qt + unittest.mock, existing `core` package (`Settings`, `AudioRecorder`, `TextTyper`, `TranscriptionHistory`, `SoundPlayer`, `Notifier`, `HotkeyManager`, `get_engine`, `Formatter`, `Vocabulary`, `permission_status`), pyobjc (mac-only NSWindow shim, lazy-imported).

---

## File Structure

**Create:**
- `app/ui/__init__.py` — UI package marker; re-exports `YapperApp`, `main`.
- `app/ui/theme.py` — `ACCENT='#ec2a8e'`, `qss()` returns the dark QSS string; `STATE_COLORS` dict for tray/HUD.
- `app/ui/controller.py` — `Controller` (no Qt): pure orchestration `record→engine→format→type→history`, state machine, callbacks. **This is the TDD heart of the phase.**
- `app/ui/hud.py` — `RecordingHUD(QWidget)` frameless translucent pill; `set_state`, `update_level`; mac click-through shim.
- `app/ui/wizard.py` — `SetupWizard(QWidget)` sidebar steps; non-Qt `wizard_steps(is_mac)` helper for testability.
- `app/ui/settings_window.py` — `SettingsWindow(QWidget)` sidebar nav bound to `Settings`; non-Qt `SettingsBinder` helper.
- `app/ui/history_window.py` — `HistoryWindow(QWidget)` searchable list; non-Qt `filter_records()` helper.
- `app/ui/app.py` — `YapperApp` (QApplication + `QSystemTrayIcon` + `Controller`), `_Bridge(QObject)`, `main()`.
- `app/__main__.py` — `python -m app` entry: parses `--once`, calls `ui.app.main()` or `run_once()`.
- `app/cli.py` — `run_once(settings)` single-shot record→transcribe→type (no Qt loop) for `--once`.
- `tests/__init__.py`, `tests/conftest.py` — pytest fixtures (`qapp`, `tmp_settings`).
- `tests/test_controller.py`, `tests/test_theme.py`, `tests/test_hud.py`, `tests/test_wizard.py`, `tests/test_settings_window.py`, `tests/test_history_window.py`, `tests/test_app.py`, `tests/test_cli.py`.
- `docs/MANUAL_SMOKE_PHASE4.md` — honest manual smoke checklist (mac + win).

**Modify:**
- `pyproject.toml` — add `pytest-qt` to dev deps; add `[project.scripts] yapper = "app.__main__:cli_main"`; add `qt_api` pytest config.
- `app/core/__init__.py` — no change required; UI imports `from core import ...`.

**Delete (retire at end, Task 13):**
- `app/yapper_tray.py`, `app/yapper.py`, `app/settings_ui.py`, `app/settings_console.py`.

---

## Tasks

### Task 0: Test scaffolding, pytest-qt dep, conftest fixtures

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_imports.py`

- [ ] Add `pytest-qt>=4.4` to the dev dependency group and configure the Qt API in `pyproject.toml`. Append/merge:
```toml
[dependency-groups]
dev = ["pytest>=8.0", "pytest-qt>=4.4"]

[tool.pytest.ini_options]
testpaths = ["tests"]
qt_api = "pyside6"
addopts = "-q"
```
- [ ] Install dev deps and PySide6 into the venv: run
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv sync --group dev && uv add PySide6
```
  Expected: `uv` resolves and installs `PySide6` and `pytest-qt` without error.
- [ ] Create `tests/__init__.py` as an empty file (one newline).
- [ ] Create `tests/conftest.py`:
```python
"""Shared pytest fixtures for the Yapper UI test suite."""
import sys
from pathlib import Path

import pytest

# Make `core`, `app`, and `ui` importable exactly as the runtime does.
APP_DIR = Path(__file__).resolve().parent.parent / "app"
ROOT_DIR = APP_DIR.parent
for p in (str(APP_DIR), str(ROOT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def tmp_settings(tmp_path):
    """A Settings instance backed by a throwaway file."""
    from core import Settings
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s
```
- [ ] Create the failing smoke test `tests/test_imports.py`:
```python
def test_pyside6_and_pytestqt_importable(qtbot):
    import PySide6  # noqa: F401
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    qtbot.addWidget(w)
    assert w is not None
```
- [ ] Run it: `cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest tests/test_imports.py -q`. Expected: **1 passed** (PySide6 + pytest-qt installed). If it fails on the `qtbot` fixture, re-run the install step.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add pyproject.toml tests/__init__.py tests/conftest.py tests/test_imports.py && git commit -m "test(ui): add pytest-qt scaffolding and conftest fixtures"
```

---

### Task 1: Theme — accent, QSS, state colors

**Files:**
- Create: `app/ui/__init__.py`, `app/ui/theme.py`
- Test: `tests/test_theme.py`

- [ ] Write failing test `tests/test_theme.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_theme.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui'`).
- [ ] Create `app/ui/__init__.py`:
```python
"""Yapper PySide6 UI package.

Copyright (c) 2026 Cloudelipute
"""
from .app import YapperApp, main  # noqa: F401

__all__ = ["YapperApp", "main"]
```
  Note: this import will only resolve once `app/ui/app.py` exists (Task 9). Until then, import `theme` directly via `from ui import theme` which triggers `__init__`. To avoid a chicken-and-egg failure now, **temporarily** make `__init__.py` lazy:
```python
"""Yapper PySide6 UI package.

Copyright (c) 2026 Cloudelipute
"""

__all__ = ["YapperApp", "main"]


def __getattr__(name):  # PEP 562 lazy attribute access
    if name in ("YapperApp", "main"):
        from .app import YapperApp, main
        return {"YapperApp": YapperApp, "main": main}[name]
    raise AttributeError(name)
```
- [ ] Create `app/ui/theme.py`:
```python
"""Yapper UI theme — dark QSS + Cloudelipute pink accent.

Copyright (c) 2026 Cloudelipute
"""

ACCENT = "#ec2a8e"
ACCENT_DIM = "#b81f6f"
BG = "#16131a"
BG_RAISED = "#211c29"
BG_INPUT = "#2c2533"
FG = "#f2eef6"
FG_MUTED = "#9b90a8"
BORDER = "#3a3142"

# Recording state -> indicator color (tray icon dot + HUD pill glow).
STATE_COLORS = {
    "idle": "#6b6275",
    "listening": ACCENT,
    "transcribing": "#f4b740",
    "done": "#3ddc84",
}


def qss() -> str:
    """Return the shared dark stylesheet for all Yapper windows."""
    return f"""
    QWidget {{
        background-color: {BG};
        color: {FG};
        font-family: "Segoe UI", -apple-system, "Helvetica Neue", sans-serif;
        font-size: 13px;
    }}
    QFrame#Sidebar {{
        background-color: {BG_RAISED};
        border-right: 1px solid {BORDER};
    }}
    QLabel#Title {{ font-size: 20px; font-weight: 600; }}
    QLabel#Muted {{ color: {FG_MUTED}; }}
    QPushButton {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 7px 14px;
    }}
    QPushButton:hover {{ border-color: {ACCENT}; }}
    QPushButton#Primary {{
        background-color: {ACCENT};
        border: none;
        color: white;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background-color: {ACCENT_DIM}; }}
    QPushButton#NavItem {{
        text-align: left;
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 9px 12px;
    }}
    QPushButton#NavItem:checked {{
        background-color: {ACCENT};
        color: white;
    }}
    QLineEdit, QComboBox, QPlainTextEdit, QSpinBox, QListWidget {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px 9px;
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border-color: {ACCENT};
    }}
    QCheckBox::indicator:checked {{ background-color: {ACCENT}; }}
    """
```
- [ ] Run: `uv run pytest tests/test_theme.py -q`. Expected: **3 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/__init__.py app/ui/theme.py tests/test_theme.py && git commit -m "feat(ui): add dark theme QSS with Cloudelipute pink accent"
```

---

### Task 2: Controller — state machine (no recording yet)

The `Controller` is plain Python (no Qt) so it is fully unit-testable. It emits state via a `on_state(state)` callback that `YapperApp` later routes into Qt signals.

**Files:**
- Create: `app/ui/controller.py`
- Test: `tests/test_controller.py`

- [ ] Write failing test `tests/test_controller.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui.controller'`).
- [ ] Create `app/ui/controller.py`:
```python
"""Yapper dictation controller — pure orchestration, no Qt.

Wires hotkeys -> record -> engine -> format -> type -> history. UI layers
(YapperApp, HUD) subscribe via plain callbacks so this stays headless-testable.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

import enum
import os
import threading
from typing import Callable, Optional

from core import (
    AudioRecorder,
    Settings,
    SoundPlayer,
    TextTyper,
    TranscriptionHistory,
    TranscriptionRecord,
    VoiceActivityDetector,
    get_logger,
)

logger = get_logger("controller")


class ControllerState(str, enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    DONE = "done"


class Controller:
    """Headless dictation orchestrator."""

    def __init__(
        self,
        settings: Settings,
        on_state: Optional[Callable[[ControllerState], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
        on_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.settings = settings
        self._on_state = on_state
        self._on_level = on_level
        self._on_result = on_result
        self._on_error = on_error

        self.state = ControllerState.IDLE
        self._recorder: Optional[AudioRecorder] = None
        self._lock = threading.Lock()

        self.sounds = SoundPlayer(enabled=settings.get("audio_feedback", True))
        self.history = TranscriptionHistory(enabled=settings.get("save_history", True))

    # -- state -----------------------------------------------------------
    def _set_state(self, state: ControllerState) -> None:
        if state == self.state:
            return
        self.state = state
        logger.debug(f"state -> {state.value}")
        if self._on_state:
            self._on_state(state)

    def _emit_error(self, message: str) -> None:
        logger.error(message)
        self.sounds.error()
        if self._on_error:
            self._on_error(message)
        self._set_state(ControllerState.IDLE)
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **3 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/controller.py tests/test_controller.py && git commit -m "feat(ui): add Controller state machine"
```

---

### Task 3: Controller — start/stop recording with injected recorder

**Files:**
- Modify: `app/ui/controller.py`
- Test: `tests/test_controller.py`

- [ ] Append failing tests to `tests/test_controller.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **FAIL** (`AttributeError: 'Controller' object has no attribute 'start_recording'`).
- [ ] Add to `Controller` in `app/ui/controller.py` (after `_emit_error`):
```python
    # -- recording -------------------------------------------------------
    def _recorder_factory(self, **kwargs) -> AudioRecorder:
        return AudioRecorder(**kwargs)

    def start_recording(self) -> None:
        with self._lock:
            if self.state in (ControllerState.LISTENING, ControllerState.TRANSCRIBING):
                return
        if not self.settings.get("api_key"):
            self._emit_error("No API key set. Open Settings to add one.")
            return
        self._recorder = self._recorder_factory(
            device_index=self.settings.get("audio_device_index")
        )
        self.sounds.start_recording()
        if self._recorder.start():
            self._set_state(ControllerState.LISTENING)
        else:
            self._recorder = None
            self._emit_error("Could not start recording (microphone error).")
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **6 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/controller.py tests/test_controller.py && git commit -m "feat(ui): Controller.start_recording with injectable recorder"
```

---

### Task 4: Controller — stop_recording → engine → formatter → typer → history

This is the full happy path. Everything external is injected (recorder factory, engine, formatter, typer) so we test the pipeline ordering deterministically with no API/audio.

**Files:**
- Modify: `app/ui/controller.py`
- Test: `tests/test_controller.py`

- [ ] Append failing tests to `tests/test_controller.py`:
```python
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

    c = Controller(settings)
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
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **FAIL** (`AttributeError: stop_recording`).
- [ ] Add the rest of the pipeline to `Controller` in `app/ui/controller.py`:
```python
    # -- factories (overridable in tests) --------------------------------
    def _engine_factory(self):
        from core.engines import get_engine
        return get_engine(self.settings)

    def _formatter_factory(self):
        from core import APIClient
        from core.formatting import Formatter
        from core.vocabulary import Vocabulary
        vocab = Vocabulary.from_list(self.settings.get("vocabulary", []))
        client = APIClient(api_key=self.settings.get("api_key"))
        return Formatter(client, vocab)

    def _typer_factory(self) -> TextTyper:
        return TextTyper()

    def _has_speech(self, frames) -> bool:
        if not self.settings.get("vad_enabled", True):
            return True
        vad = VoiceActivityDetector(
            threshold_db=self.settings.get("vad_threshold_db", -45)
        )
        return vad.has_speech(frames)

    def _vocab_prompt(self) -> Optional[str]:
        from core.vocabulary import Vocabulary
        vocab = Vocabulary.from_list(self.settings.get("vocabulary", []))
        prompt = vocab.whisper_prompt()
        return prompt or None

    # -- stop + process --------------------------------------------------
    def stop_recording(self) -> None:
        if self.state != ControllerState.LISTENING or self._recorder is None:
            return
        self.sounds.stop_recording()
        recorder = self._recorder
        wav_path = recorder.stop()
        if not wav_path:
            self._recorder = None
            self._set_state(ControllerState.IDLE)
            return
        if not self._has_speech(recorder.frames):
            logger.info("No speech detected; skipping transcription")
            self._cleanup_wav(wav_path)
            self._recorder = None
            self._set_state(ControllerState.IDLE)
            return
        self._set_state(ControllerState.TRANSCRIBING)
        self._worker = threading.Thread(
            target=self._process, args=(wav_path, recorder.duration_seconds),
            daemon=True, name="ControllerProcess",
        )
        self._worker.start()

    def _await_processing(self, timeout: float = 5.0) -> None:
        """Test helper: block until the worker thread completes."""
        worker = getattr(self, "_worker", None)
        if worker is not None:
            worker.join(timeout)

    def _process(self, wav_path: str, duration: float) -> None:
        try:
            engine = self._engine_factory()
            raw = engine.transcribe(
                wav_path,
                language=self.settings.get("language_hint") or None,
                prompt=self._vocab_prompt(),
            )
            self._cleanup_wav(wav_path)
            if not raw:
                self._set_state(ControllerState.IDLE)
                return
            formatter = self._formatter_factory()
            translate_to = self.settings.get("translate_to") or None
            final = formatter.format(
                raw,
                mode=self.settings.get("output_mode", "technical"),
                expand_symbols=bool(self.settings.get("expand_spoken_symbols", True)),
                translate_to=translate_to,
            )
            method = self.settings.get("insertion_method", "paste")
            typer = self._typer_factory()
            if typer.type_text(final, method=method):
                self.sounds.success()
                self._set_state(ControllerState.DONE)
                if self._on_result:
                    self._on_result(final)
                self._record_history(final, duration, translate_to)
            else:
                self._emit_error("Could not insert text. Check Accessibility permission.")
                return
        except Exception as exc:  # noqa: BLE001 - surface to UI, never crash loop
            self._emit_error(f"Transcription failed: {exc}")
            return
        finally:
            self._recorder = None
        # Settle back to idle so the next press starts clean.
        self._set_state(ControllerState.IDLE)

    def _record_history(self, text: str, duration: float, translate_to) -> None:
        if not self.history.enabled:
            return
        try:
            self.history.add(TranscriptionRecord.create(
                text=text,
                duration=duration,
                translated=bool(translate_to),
                target_lang=translate_to or "",
                grammar_fixed=self.settings.get("output_mode") == "natural",
                source_lang=self.settings.get("language_hint", ""),
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"history.add failed: {exc}")

    @staticmethod
    def _cleanup_wav(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **10 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/controller.py tests/test_controller.py && git commit -m "feat(ui): Controller full record->engine->format->type->history pipeline"
```

---

### Task 5: Controller — hotkey wiring + live settings reload

**Files:**
- Modify: `app/ui/controller.py`
- Test: `tests/test_controller.py`

- [ ] Append failing tests to `tests/test_controller.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **FAIL** (`AttributeError: on_hotkey_start`).
- [ ] Add to `Controller` in `app/ui/controller.py`:
```python
    # -- hotkey entry points (called from HotkeyManager via _Bridge) -----
    def on_hotkey_start(self) -> None:
        self.start_recording()

    def on_hotkey_stop(self) -> None:
        self.stop_recording()

    def reload_settings(self) -> None:
        self.settings.load()
        self.sounds.enabled = self.settings.get("audio_feedback", True)
        self.history.enabled = self.settings.get("save_history", True)
        logger.info("Controller settings reloaded")
```
- [ ] Run: `uv run pytest tests/test_controller.py -q`. Expected: **12 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/controller.py tests/test_controller.py && git commit -m "feat(ui): Controller hotkey entry points and live settings reload"
```

---

### Task 6: Recording HUD (PySide6 widget)

Frameless translucent always-on-top pill. `set_state` and `update_level` are smoke-tested with `qtbot`; the mac click-through shim is guarded and only invoked on Darwin.

**Files:**
- Create: `app/ui/hud.py`
- Test: `tests/test_hud.py`

- [ ] Write failing test `tests/test_hud.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_hud.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui.hud'`).
- [ ] Create `app/ui/hud.py`:
```python
"""Recording HUD — frameless translucent always-on-top pill.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget

from core import get_logger
from . import theme

logger = get_logger("hud")

_STATES = ("idle", "listening", "transcribing", "done")
_LABELS = {
    "idle": "Yapper",
    "listening": "Listening…",
    "transcribing": "Transcribing…",
    "done": "Done",
}


class RecordingHUD(QWidget):
    """A small floating status pill with a live audio level ring."""

    WIDTH = 190
    HEIGHT = 56

    def __init__(self, reduce_motion: bool = False, parent=None):
        super().__init__(parent)
        self.state = "idle"
        self.reduce_motion = reduce_motion
        self._level = 0.0
        self._displayed_level = 0.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Click-through so the pill never steals focus from the editor.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        # Smooth the displayed level toward the target unless reduce_motion.
        self._anim = QTimer(self)
        self._anim.setInterval(33)  # ~30 fps
        self._anim.timeout.connect(self._tick)

        self._apply_macos_collection_behavior()

    # -- public API ------------------------------------------------------
    def set_state(self, state: str) -> None:
        if state not in _STATES:
            raise ValueError(f"Unknown HUD state: {state!r}")
        self.state = state
        if state == "listening" and not self.reduce_motion:
            if not self._anim.isActive():
                self._anim.start()
        else:
            self._anim.stop()
            self._displayed_level = 0.0
        if state == "done":
            QTimer.singleShot(900, self.hide)
        self.update()

    def update_level(self, rms: float) -> None:
        self._level = max(0.0, min(1.0, float(rms)))
        if self.reduce_motion:
            self._displayed_level = 0.0
        self.update()

    # -- internals -------------------------------------------------------
    def _tick(self) -> None:
        # Ease displayed level toward target.
        self._displayed_level += (self._level - self._displayed_level) * 0.35
        self.update()

    def show_centered_bottom(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.WIDTH // 2
        y = screen.bottom() - self.HEIGHT - 60
        self.move(x, y)
        self.show()

    def _apply_macos_collection_behavior(self) -> None:
        if platform.system() != "Darwin":
            return
        try:  # pragma: no cover - mac-only path
            from AppKit import (
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorFullScreenAuxiliary,
                NSWindowCollectionBehaviorStationary,
            )
            import objc  # noqa: F401
            win = objc.objc_object(c_void_p=int(self.winId()))
            win.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
                | NSWindowCollectionBehaviorStationary
            )
            win.setLevel_(1000)  # floating panel level
        except Exception as exc:  # noqa: BLE001 - shim is best-effort
            logger.debug(f"macOS HUD collection behavior unavailable: {exc}")

    def paintEvent(self, event):  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(2, 2, -2, -2), 24, 24)
        p.fillPath(path, QColor(theme.BG_RAISED))
        ring = QColor(theme.STATE_COLORS[self.state])
        pen_w = 2 + int(self._displayed_level * 5)
        pen = p.pen()
        pen.setColor(ring)
        pen.setWidth(pen_w)
        p.setPen(pen)
        p.drawPath(path)
        p.setPen(QColor(theme.FG))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _LABELS[self.state])
        p.end()
```
- [ ] Run: `uv run pytest tests/test_hud.py -q`. Expected: **5 passed**. (If running headless CI without a display, prefix the run with `QT_QPA_PLATFORM=offscreen`; document this in conftest below.)
- [ ] If the HUD test fails to construct due to no display, add this to the top of `tests/conftest.py` (before `import pytest` effects), then re-run:
```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/hud.py tests/test_hud.py tests/conftest.py && git commit -m "feat(ui): add RecordingHUD frameless pill with state + level"
```

---

### Task 7: Setup wizard (steps logic + widget smoke)

The step list (with mac-only Permissions) lives in a non-Qt helper so it is unit-tested without Qt; the widget itself gets a construction smoke test.

**Files:**
- Create: `app/ui/wizard.py`
- Test: `tests/test_wizard.py`

- [ ] Write failing test `tests/test_wizard.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_wizard.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui.wizard'`).
- [ ] Create `app/ui/wizard.py`:
```python
"""First-run setup wizard — sidebar steps.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import HOTKEYS, Settings, get_logger
from . import theme

logger = get_logger("wizard")


def wizard_steps(is_mac: bool) -> list[str]:
    """Ordered step titles; Permissions is mac-only."""
    steps = ["Welcome", "Engine", "Connect"]
    if is_mac:
        steps.append("Permissions")
    steps += ["Hotkey & Voice", "All set"]
    return steps


class SetupWizard(QWidget):
    finished_setup = Signal()

    def __init__(self, settings: Settings, is_mac: bool | None = None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.steps = wizard_steps(
            platform.system() == "Darwin" if is_mac is None else is_mac
        )
        self.current_index = 0

        self.setWindowTitle("Welcome to Yapper")
        self.setStyleSheet(theme.qss())
        self.resize(720, 460)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame(objectName="Sidebar")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 24, 16, 24)
        self._step_labels: list[QLabel] = []
        for name in self.steps:
            lbl = QLabel(name, objectName="Muted")
            self._step_labels.append(lbl)
            sb.addWidget(lbl)
        sb.addStretch(1)
        sidebar.setFixedWidth(200)
        root.addWidget(sidebar)

        right = QVBoxLayout()
        self._stack = QStackedWidget()
        for name in self.steps:
            self._stack.addWidget(self._build_page(name))
        right.addWidget(self._stack, 1)

        nav = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self.go_back)
        self._next_btn = QPushButton("Next", objectName="Primary")
        self._next_btn.clicked.connect(self.go_next)
        nav.addWidget(self._back_btn)
        nav.addStretch(1)
        nav.addWidget(self._next_btn)
        right.addLayout(nav)
        root.addLayout(right, 1)

        self._refresh()

    # -- page builders ---------------------------------------------------
    def _build_page(self, name: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 32, 32, 32)
        title = QLabel(name, objectName="Title")
        lay.addWidget(title)
        if name == "Connect":
            lay.addWidget(QLabel("Paste your OpenAI API key:", objectName="Muted"))
            self._api_edit = QLineEdit()
            self._api_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._api_edit.setText(self.settings.get("api_key", ""))
            lay.addWidget(self._api_edit)
        elif name == "Engine":
            lay.addWidget(QLabel("Transcription engine:", objectName="Muted"))
            self._engine_combo = QComboBox()
            self._engine_combo.addItems(["cloud", "local"])
            self._engine_combo.setCurrentText(self.settings.get("engine", "cloud"))
            lay.addWidget(self._engine_combo)
        elif name == "Hotkey & Voice":
            lay.addWidget(QLabel("Activation hotkey:", objectName="Muted"))
            self._hotkey_combo = QComboBox()
            self._hotkey_combo.addItems(HOTKEYS)
            self._hotkey_combo.setCurrentText(self.settings.get("hotkey", "f8"))
            lay.addWidget(self._hotkey_combo)
            self._mic_test_btn = QPushButton("Test microphone")
            self._mic_test_btn.clicked.connect(self._run_mic_test)
            lay.addWidget(self._mic_test_btn)
            self._mic_result = QLabel("", objectName="Muted")
            lay.addWidget(self._mic_result)
        elif name == "Permissions":
            lay.addWidget(QLabel(
                "Grant Microphone, Accessibility, and Input Monitoring in "
                "System Settings, then quit & relaunch Yapper.", objectName="Muted"))
            self._perm_btn = QPushButton("Re-check permissions")
            self._perm_btn.clicked.connect(self._refresh_permissions)
            lay.addWidget(self._perm_btn)
            self._perm_label = QLabel("", objectName="Muted")
            lay.addWidget(self._perm_label)
        lay.addStretch(1)
        return page

    # -- navigation ------------------------------------------------------
    def go_next(self) -> None:
        self._persist_current()
        if self.current_index >= len(self.steps) - 1:
            self.settings.save()
            self.finished_setup.emit()
            self.close()
            return
        self.current_index += 1
        self._refresh()

    def go_back(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._refresh()

    def _refresh(self) -> None:
        self._stack.setCurrentIndex(self.current_index)
        self._back_btn.setEnabled(self.current_index > 0)
        self._next_btn.setText(
            "Finish" if self.current_index == len(self.steps) - 1 else "Next"
        )
        for i, lbl in enumerate(self._step_labels):
            lbl.setObjectName("Title" if i == self.current_index else "Muted")
            lbl.setStyleSheet(theme.qss())

    def _persist_current(self) -> None:
        name = self.steps[self.current_index]
        if name == "Connect" and hasattr(self, "_api_edit"):
            self.settings.set("api_key", self._api_edit.text().strip())
        elif name == "Engine" and hasattr(self, "_engine_combo"):
            self.settings.set("engine", self._engine_combo.currentText())
        elif name == "Hotkey & Voice" and hasattr(self, "_hotkey_combo"):
            self.settings.set("hotkey", self._hotkey_combo.currentText())

    def _run_mic_test(self) -> None:
        # Real, short capture + transcription so the user gets a success moment.
        try:
            from .controller import Controller, ControllerState  # local import
            self._mic_result.setText("Recording 2s… speak now")
            # A lightweight one-shot using the same pipeline, fire-and-forget.
            c = Controller(self.settings, on_result=lambda t: self._mic_result.setText(
                f"Heard: {t[:48]}" if t else "No speech detected"))
            c.start_recording()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, c.stop_recording)
        except Exception as exc:  # noqa: BLE001
            self._mic_result.setText(f"Mic test failed: {exc}")

    def _refresh_permissions(self) -> None:
        from core.permissions import permission_status
        st = permission_status()
        self._perm_label.setText(
            f"mic={st.microphone}  accessibility={st.accessibility}  "
            f"input_monitoring={st.input_monitoring}")
```
- [ ] Run: `uv run pytest tests/test_wizard.py -q`. Expected: **5 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/wizard.py tests/test_wizard.py && git commit -m "feat(ui): add SetupWizard with mac-only Permissions step"
```

---

### Task 8: History window (filter logic + widget smoke)

`filter_records()` is a pure function (unit-tested); the widget is smoke-tested.

**Files:**
- Create: `app/ui/history_window.py`
- Test: `tests/test_history_window.py`

- [ ] Write failing test `tests/test_history_window.py`:
```python
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
```
- [ ] Run: `uv run pytest tests/test_history_window.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui.history_window'`).
- [ ] Create `app/ui/history_window.py`:
```python
"""History window — searchable transcription history with row actions.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

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

from core import TextTyper, TranscriptionHistory, TranscriptionRecord, get_logger
from . import theme

logger = get_logger("history_window")


def filter_records(records: List[TranscriptionRecord], query: str) -> List[TranscriptionRecord]:
    """Case-insensitive substring filter over record text."""
    q = query.strip().lower()
    if not q:
        return records
    return [r for r in records if q in r.text.lower()]


class HistoryWindow(QWidget):
    def __init__(self, history: TranscriptionHistory, parent=None):
        super().__init__(parent)
        self.history = history
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
            ("Export", self._export),
            ("Clear", self._clear),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        root.addLayout(row)
        root.addWidget(QLabel(theme.ACCENT and "© 2026 Cloudelipute", objectName="Muted"))

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

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export history", "history.json", "JSON (*.json)")
        if path:
            data = [r.__dict__ for r in self.history.get_all()]
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _clear(self) -> None:
        self.history.clear()
        self._reload()
```
- [ ] Run: `uv run pytest tests/test_history_window.py -q`. Expected: **5 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/history_window.py tests/test_history_window.py && git commit -m "feat(ui): add searchable HistoryWindow with copy/reinsert/export/clear"
```

---

### Task 9: Settings window (binder logic + widget smoke)

A non-Qt `SettingsBinder` does the read/write between widget values and `Settings`; the window wires widgets to it. The binder is unit-tested; the window is smoke-tested.

**Files:**
- Create: `app/ui/settings_window.py`
- Test: `tests/test_settings_window.py`

- [ ] Write failing test `tests/test_settings_window.py`:
```python
import pytest

from core import Settings
from ui.settings_window import SettingsWindow, SettingsBinder


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    return s


def test_binder_reads_default(settings):
    b = SettingsBinder(settings)
    assert b.read("output_mode") == "technical"


def test_binder_writes_and_saves(settings):
    b = SettingsBinder(settings)
    b.write("output_mode", "natural")
    b.commit()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("output_mode") == "natural"


def test_binder_rejects_unknown_value_silently(settings):
    b = SettingsBinder(settings)
    # invalid hotkey not in HOTKEYS should not crash; value left at prior.
    b.write("hotkey", "not-a-key")
    assert b.read("hotkey") in (settings.get("hotkey"), "f8")


def test_settings_window_constructs_with_nav_sections(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    assert win.SECTIONS == [
        "General", "Engine & Models", "Vocabulary", "Formatting",
        "Hotkeys", "Audio", "History", "About",
    ]
    assert win._nav.count() == len(win.SECTIONS)


def test_settings_window_save_persists(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win.binder.write("expand_spoken_symbols", False)
    win._on_save()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("expand_spoken_symbols") is False
```
- [ ] Run: `uv run pytest tests/test_settings_window.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui.settings_window'`).
- [ ] Create `app/ui/settings_window.py`:
```python
"""Settings window — sidebar nav bound to core.Settings.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import HOTKEYS, LANGUAGES, Settings, get_logger
from . import theme

logger = get_logger("settings_window")


class SettingsBinder:
    """Headless read/write bridge between widgets and Settings (validated)."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def read(self, key: str) -> Any:
        return self.settings.get(key)

    def write(self, key: str, value: Any) -> None:
        # Settings.set validates; silently ignore invalid values.
        self.settings.set(key, value)

    def commit(self) -> bool:
        return self.settings.save()


class SettingsWindow(QWidget):
    settings_saved = Signal()

    SECTIONS = [
        "General", "Engine & Models", "Vocabulary", "Formatting",
        "Hotkeys", "Audio", "History", "About",
    ]

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.binder = SettingsBinder(settings)
        self.setWindowTitle("Yapper — Settings")
        self.setStyleSheet(theme.qss())
        self.resize(760, 540)

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        self._nav = QListWidget()
        self._nav.addItems(self.SECTIONS)
        self._nav.setFixedWidth(190)
        self._nav.currentRowChanged.connect(lambda i: self._stack.setCurrentIndex(i))
        body.addWidget(self._nav)

        self._stack = QStackedWidget()
        for section in self.SECTIONS:
            self._stack.addWidget(self._build_section(section))
        body.addWidget(self._stack, 1)
        root.addLayout(body, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        save = QPushButton("Save", objectName="Primary")
        save.clicked.connect(self._on_save)
        bar.addWidget(save)
        root.addLayout(bar)
        self._nav.setCurrentRow(0)

    def _build_section(self, section: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel(section, objectName="Title"))
        if section == "Engine & Models":
            self._engine = self._combo(lay, "Engine", ["cloud", "local"], "engine")
            self._cloud_model = self._combo(
                lay, "Cloud STT model",
                ["gpt-4o-mini-transcribe", "whisper-1"], "cloud_stt_model")
            self._text_model = self._combo(
                lay, "Text model", ["gpt-5-nano", "gpt-5.4-nano"], "text_model")
        elif section == "Formatting":
            self._mode = self._combo(
                lay, "Output mode", ["technical", "natural", "verbatim"], "output_mode")
            self._expand = self._check(lay, "Expand spoken symbols", "expand_spoken_symbols")
            self._translate = self._combo(
                lay, "Translate to", list(LANGUAGES.keys()), "translate_to")
        elif section == "Hotkeys":
            self._mode_act = self._combo(
                lay, "Activation", ["push_to_talk", "toggle", "wake_word"], "activation_mode")
            self._hotkey = self._combo(lay, "Hotkey", HOTKEYS, "hotkey")
        elif section == "Audio":
            self._insertion = self._combo(
                lay, "Insertion method", ["paste", "type"], "insertion_method")
            self._feedback = self._check(lay, "Audio feedback", "audio_feedback")
        elif section == "General":
            self._hud = self._check(lay, "Show recording HUD", "show_hud")
            self._reduce = self._check(lay, "Reduce motion", "reduce_motion")
            self._save_hist = self._check(lay, "Save history", "save_history")
        elif section == "About":
            lay.addWidget(QLabel("© 2026 Cloudelipute", objectName="Muted"))
        lay.addStretch(1)
        return page

    # -- widget helpers (write straight to binder on change) -------------
    def _combo(self, lay, label, items, key) -> QComboBox:
        lay.addWidget(QLabel(label, objectName="Muted"))
        cb = QComboBox()
        cb.addItems([str(i) for i in items])
        cb.setCurrentText(str(self.binder.read(key)))
        cb.currentTextChanged.connect(lambda v, k=key: self.binder.write(k, v))
        lay.addWidget(cb)
        return cb

    def _check(self, lay, label, key) -> QCheckBox:
        cx = QCheckBox(label)
        cx.setChecked(bool(self.binder.read(key)))
        cx.toggled.connect(lambda v, k=key: self.binder.write(k, v))
        lay.addWidget(cx)
        return cx

    def _on_save(self) -> None:
        if self.binder.commit():
            self.settings_saved.emit()
            self.close()
```
- [ ] Run: `uv run pytest tests/test_settings_window.py -q`. Expected: **5 passed**. (Note: this requires the new settings keys `output_mode`, `engine`, `expand_spoken_symbols`, `show_hud`, `reduce_motion`, `activation_mode`, `insertion_method`, `text_model`, `cloud_stt_model` to exist in `DEFAULT_SETTINGS`/`SETTINGS_SCHEMA` — added in Phase 0/3. If a test fails because a key is missing, that is a Phase-dependency gap, not this widget's bug.)
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/settings_window.py tests/test_settings_window.py && git commit -m "feat(ui): add SettingsWindow with sidebar nav bound to Settings"
```

---

### Task 10: YapperApp — tray + _Bridge + main()

`_Bridge(QObject)` marshals pynput-thread callbacks into Qt. The tray icon is state-colored. Construction + signal smoke is tested with `qtbot`; `HotkeyManager` and `Notifier` are mocked so no real listener/notification starts.

**Files:**
- Create: `app/ui/app.py`
- Test: `tests/test_app.py`

- [ ] Write failing test `tests/test_app.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from core import Settings
from ui.controller import ControllerState


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s


def test_bridge_relays_state_on_qt_thread(qtbot):
    from ui.app import _Bridge
    bridge = _Bridge()
    received = []
    bridge.state_changed.connect(lambda s: received.append(s))
    bridge.state_changed.emit("listening")
    assert received == ["listening"]


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_yapperapp_constructs_tray(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    assert app.tray is not None
    assert app.controller is not None
    # Tray icon was given a context menu.
    assert app.tray.contextMenu() is not None


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_controller_state_drives_tray_tooltip(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=False)
    app._bridge.state_changed.emit(ControllerState.LISTENING.value)
    qtbot.wait(10)
    assert "isten" in app.tray.toolTip() or app.tray.toolTip() != ""


@patch("ui.app.HotkeyManager")
@patch("ui.app.Notifier")
def test_start_listener_builds_hotkey_manager(mock_notifier, mock_hk, qtbot, settings):
    from ui.app import YapperApp
    app = YapperApp(settings=settings, start_listener=True)
    mock_hk.assert_called_once()
    _, kwargs = mock_hk.call_args
    assert kwargs["mode"] == settings.get("activation_mode", "push_to_talk")
    app.hotkeys.start.assert_called_once()
```
- [ ] Run: `uv run pytest tests/test_app.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'ui.app'`).
- [ ] Create `app/ui/app.py`:
```python
"""YapperApp — QApplication + QSystemTrayIcon + Controller, with a thread bridge.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core import (
    HotkeyManager,
    Notifier,
    Settings,
    TranscriptionHistory,
    VERSION,
    get_logger,
    setup_logging,
)
from . import theme
from .controller import Controller, ControllerState

logger = get_logger("app")

APP_DIR = Path(__file__).resolve().parent.parent


class _Bridge(QObject):
    """Marshals pynput-listener-thread callbacks into the Qt main thread."""

    hotkey_start = Signal()
    hotkey_stop = Signal()
    state_changed = Signal(str)   # ControllerState value
    level = Signal(float)
    result = Signal(str)
    error = Signal(str)


def _state_icon(state: str) -> QIcon:
    """A 32px dot tinted by the recording state color."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(QColor(theme.STATE_COLORS.get(state, theme.STATE_COLORS["idle"])))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(4, 4, 24, 24)
    p.end()
    return QIcon(pix)


class YapperApp:
    """Owns the Qt loop, tray, controller, HUD, and hotkey bridge."""

    def __init__(self, settings: Settings | None = None, start_listener: bool = True):
        self.qapp = QApplication.instance() or QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.setStyleSheet(theme.qss())

        self.settings = settings or Settings().load()
        self.notifier = Notifier()
        self.history = TranscriptionHistory(enabled=self.settings.get("save_history", True))

        self._bridge = _Bridge()
        self.controller = Controller(
            self.settings,
            on_state=lambda s: self._bridge.state_changed.emit(s.value),
            on_level=lambda v: self._bridge.level.emit(v),
            on_result=lambda t: self._bridge.result.emit(t),
            on_error=lambda m: self._bridge.error.emit(m),
        )

        # Connect bridge signals to Qt slots (run on main thread).
        self._bridge.hotkey_start.connect(self.controller.on_hotkey_start)
        self._bridge.hotkey_stop.connect(self.controller.on_hotkey_stop)
        self._bridge.state_changed.connect(self._on_state)
        self._bridge.result.connect(self._on_result)
        self._bridge.error.connect(self._on_error)

        self._hud = None
        if self.settings.get("show_hud", True):
            from .hud import RecordingHUD
            self._hud = RecordingHUD(reduce_motion=self.settings.get("reduce_motion", False))
            self._bridge.level.connect(self._hud.update_level)

        self.tray = self._build_tray()
        self._wizard = None
        self._settings_win = None
        self._history_win = None

        self.hotkeys = None
        if start_listener:
            self._start_hotkeys()

    # -- tray ------------------------------------------------------------
    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(_state_icon("idle"))
        tray.setToolTip(f"Yapper v{VERSION}")
        menu = QMenu()
        for text, slot in (
            ("Settings…", self.open_settings),
            ("History…", self.open_history),
        ):
            act = QAction(text, menu)
            act.triggered.connect(slot)
            menu.addAction(act)
        menu.addSeparator()
        quit_act = QAction("Quit Yapper", menu)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)
        tray.setContextMenu(menu)
        tray.show()
        return tray

    def _start_hotkeys(self) -> None:
        self.hotkeys = HotkeyManager(
            mode=self.settings.get("activation_mode", "push_to_talk"),
            hotkey=self.settings.get("hotkey", "f8"),
            on_start=self._bridge.hotkey_start.emit,
            on_stop=self._bridge.hotkey_stop.emit,
        )
        self.hotkeys.start()

    # -- slots -----------------------------------------------------------
    @Slot(str)
    def _on_state(self, state: str) -> None:
        self.tray.setIcon(_state_icon(state))
        labels = {
            "idle": f"Yapper v{VERSION}",
            "listening": "Yapper — Listening…",
            "transcribing": "Yapper — Transcribing…",
            "done": "Yapper — Done",
        }
        self.tray.setToolTip(labels.get(state, "Yapper"))
        if self._hud is not None:
            if state == "listening":
                self._hud.show_centered_bottom()
            self._hud.set_state(state)

    @Slot(str)
    def _on_result(self, text: str) -> None:
        self.notifier.notify("Yapper", text[:60])

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.notifier.notify("Yapper", message[:80])

    # -- windows ---------------------------------------------------------
    def open_settings(self) -> None:
        from .settings_window import SettingsWindow
        self._settings_win = SettingsWindow(self.settings)
        self._settings_win.settings_saved.connect(self._on_settings_saved)
        self._settings_win.show()

    def open_history(self) -> None:
        from .history_window import HistoryWindow
        self._history_win = HistoryWindow(self.history)
        self._history_win.show()

    def _on_settings_saved(self) -> None:
        self.controller.reload_settings()
        if self.hotkeys is not None:
            self.hotkeys.set_mode(self.settings.get("activation_mode", "push_to_talk"))
            self.hotkeys.set_hotkey(self.settings.get("hotkey", "f8"))

    def quit(self) -> None:
        if self.hotkeys is not None:
            self.hotkeys.stop()
        self.tray.hide()
        self.qapp.quit()

    def run(self) -> int:
        return self.qapp.exec()


def main() -> int:
    setup_logging()
    settings = Settings().load()
    app = YapperApp(settings=settings, start_listener=True)
    if not settings.get("api_key"):
        from .wizard import SetupWizard
        app._wizard = SetupWizard(settings)
        app._wizard.finished_setup.connect(app._on_settings_saved)
        app._wizard.show()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
```
- [ ] Run: `uv run pytest tests/test_app.py -q`. Expected: **4 passed**.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/app.py tests/test_app.py && git commit -m "feat(ui): add YapperApp tray + _Bridge thread marshaling + main()"
```

---

### Task 11: `--once` CLI path + `python -m app` entry

A non-Qt single-shot path for scripted use. It records for a fixed window, transcribes, and types — reusing `Controller` for the pipeline but without the Qt loop or hotkeys.

**Files:**
- Create: `app/cli.py`, `app/__main__.py`
- Test: `tests/test_cli.py`

- [ ] Write failing test `tests/test_cli.py`:
```python
from unittest.mock import MagicMock

import pytest

from core import Settings
from app_cli_helpers import run_once  # see note below


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s


def test_run_once_invokes_pipeline(settings, monkeypatch):
    fake_controller = MagicMock()
    monkeypatch.setattr("cli._build_controller", lambda s: fake_controller)
    run_once(settings, duration=0.01)
    fake_controller.start_recording.assert_called_once()
    fake_controller.stop_recording.assert_called_once()
```
  Note: the import line above is a deliberate placeholder to force you to wire imports correctly — replace it with `from cli import run_once` once `app/` is on `sys.path` (it already is via `conftest.py`). Use the corrected test below.
- [ ] Replace the test body with the correct imports in `tests/test_cli.py`:
```python
from unittest.mock import MagicMock

import pytest

from core import Settings
from cli import run_once


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    s.set("api_key", "sk-test")
    return s


def test_run_once_invokes_pipeline(settings, monkeypatch):
    fake_controller = MagicMock()
    monkeypatch.setattr("cli._build_controller", lambda s: fake_controller)
    run_once(settings, duration=0.01)
    fake_controller.start_recording.assert_called_once()
    fake_controller.stop_recording.assert_called_once()


def test_run_once_requires_api_key(monkeypatch, tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()  # no api_key
    rc = run_once(s, duration=0.01)
    assert rc != 0
```
- [ ] Run: `uv run pytest tests/test_cli.py -q`. Expected: **FAIL** (`ModuleNotFoundError: No module named 'cli'`).
- [ ] Create `app/cli.py`:
```python
"""Single-shot CLI dictation path (`python -m app --once`). No Qt loop.

Copyright (c) 2026 Cloudelipute
"""

from __future__ import annotations

import time

from core import Settings, get_logger, setup_logging
from ui.controller import Controller

logger = get_logger("cli")


def _build_controller(settings: Settings) -> Controller:
    return Controller(settings)


def run_once(settings: Settings, duration: float = 5.0) -> int:
    """Record for `duration` seconds, transcribe, and type once. Returns exit code."""
    if not settings.get("api_key"):
        logger.error("No API key set. Run `python -m app` to configure.")
        return 2
    controller = _build_controller(settings)
    controller.start_recording()
    time.sleep(duration)
    controller.stop_recording()
    controller._await_processing(timeout=60.0)
    return 0


def cli_main(argv: list[str] | None = None) -> int:
    import argparse
    setup_logging()
    parser = argparse.ArgumentParser(prog="yapper")
    parser.add_argument("--once", action="store_true", help="Single-shot record+type, no tray")
    parser.add_argument("--seconds", type=float, default=5.0, help="Recording window for --once")
    args = parser.parse_args(argv)
    settings = Settings().load()
    if args.once:
        return run_once(settings, duration=args.seconds)
    from ui.app import main as ui_main
    return ui_main()
```
- [ ] Create `app/__main__.py`:
```python
"""`python -m app` entry point.

Copyright (c) 2026 Cloudelipute
"""

import sys
from pathlib import Path

# Ensure `app/` (this dir) is importable as the source root.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from cli import cli_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(cli_main())
```
- [ ] Delete the placeholder first test version if it remains; ensure `tests/test_cli.py` only contains the corrected version.
- [ ] Run: `uv run pytest tests/test_cli.py -q`. Expected: **2 passed**.
- [ ] Add the console-script entry to `pyproject.toml` under `[project]`:
```toml
[project.scripts]
yapper = "app.cli:cli_main"
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/cli.py app/__main__.py tests/test_cli.py pyproject.toml && git commit -m "feat(cli): add --once single-shot path and python -m app entry"
```

---

### Task 12: Full suite green + offscreen verification

**Files:**
- Test: all of `tests/`

- [ ] Run the entire suite headless: `cd /home/romiteld/Development/Desktop_Apps/yapper-portable && QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q`. Expected: **all tests pass** (theme 3, controller 12, hud 5, wizard 5, history 5, settings 5, app 4, cli 2, imports 1 = ~42 passed). If any Qt test errors with `could not connect to display`, confirm `QT_QPA_PLATFORM=offscreen` is exported (already defaulted in `conftest.py`).
- [ ] Verify the module imports cleanly end-to-end (no circular import between `ui/__init__.py` and `ui/app.py`):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && QT_QPA_PLATFORM=offscreen uv run python -c "import sys; sys.path.insert(0,'app'); import ui; from ui.app import YapperApp, main; from ui.controller import Controller; print('imports OK')"
```
  Expected output: `imports OK`.
- [ ] Commit (if conftest/offscreen tweak needed): no code change expected; skip commit if working tree clean. Otherwise:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add -A && git commit -m "test(ui): full suite green under offscreen Qt platform"
```

---

### Task 13: Retire legacy entry points + manual smoke checklist

Only after the Qt app and `--once` path are proven do we delete the old files, so the repo never has a window with zero working entry point.

**Files:**
- Delete: `app/yapper_tray.py`, `app/yapper.py`, `app/settings_ui.py`, `app/settings_console.py`
- Create: `docs/MANUAL_SMOKE_PHASE4.md`

- [ ] Confirm nothing in the new code imports the legacy modules:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -rn "yapper_tray\|settings_ui\|settings_console\|import yapper\b" app/ui app/cli.py app/__main__.py tests/ || echo "NO_LEGACY_REFS"
```
  Expected: `NO_LEGACY_REFS`.
- [ ] Delete the retired files:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git rm app/yapper_tray.py app/yapper.py app/settings_ui.py app/settings_console.py
```
- [ ] Re-run the suite to prove nothing depended on them: `cd /home/romiteld/Development/Desktop_Apps/yapper-portable && QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q`. Expected: **all tests still pass**.
- [ ] Create `docs/MANUAL_SMOKE_PHASE4.md` (honest about what GUI automation cannot cover):
```markdown
# Phase 4 Manual Smoke Checklist (mac + Windows)

GUI automation covers construction and signal wiring only. The items below
require a human on real hardware. Run `python -m app`.

## Both platforms
- [ ] First launch with no API key shows the SetupWizard at the Welcome step.
- [ ] Wizard: Engine -> Connect (paste key) -> Hotkey & Voice -> "Test microphone"
      records ~2s and shows "Heard: …". Finish closes the wizard.
- [ ] Tray icon appears; right-click shows Settings…, History…, Quit Yapper.
- [ ] Push-to-talk: hold the hotkey -> HUD shows "Listening…" with a moving ring;
      release -> "Transcribing…" -> text pastes at the cursor -> HUD "Done" fades.
- [ ] Tray icon dot color changes idle(grey) -> listening(pink) -> transcribing(amber) -> done(green).
- [ ] Toggle mode (Settings -> Hotkeys -> Activation=toggle): one press starts, next stops.
- [ ] Settings -> Formatting -> output_mode=verbatim: no LLM cleanup; technical: identifiers preserved.
- [ ] History window: search filters rows; Copy, Re-insert, Export, Clear all work.
- [ ] Reduce motion ON: HUD ring stays flat (no level animation).
- [ ] Paste into: code editor, browser address bar, terminal, Slack — Unicode/emoji intact.

## macOS only
- [ ] Without Accessibility granted, paste fails silently; wizard Permissions step
      flags accessibility=False and tells user to quit & relaunch after granting.
- [ ] After granting Accessibility + Input Monitoring and relaunching, PTT + paste work.
- [ ] HUD floats over a full-screen Space and is click-through (clicks pass to app beneath).

## Windows only
- [ ] Wizard skips the Permissions step entirely.
- [ ] F-key hotkeys (f8–f12) capture and inject without admin elevation where possible.
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add docs/MANUAL_SMOKE_PHASE4.md && git commit -m "chore(ui): retire legacy entry points; add Phase 4 manual smoke checklist"
```

---

### Task 14: Finalize `ui/__init__.py` eager export

Now that `ui/app.py` exists, replace the lazy `__getattr__` shim with eager imports so `from ui import YapperApp, main` works directly and there is no PEP-562 surprise.

**Files:**
- Modify: `app/ui/__init__.py`
- Test: `tests/test_imports.py`

- [ ] Append to `tests/test_imports.py`:
```python
def test_ui_package_exports_app_symbols():
    import ui
    assert hasattr(ui, "YapperApp")
    assert callable(ui.main)
```
- [ ] Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/test_imports.py -q`. Expected: **PASS** already (the lazy shim resolves it), confirming the contract before refactor.
- [ ] Replace the body of `app/ui/__init__.py` with the eager version:
```python
"""Yapper PySide6 UI package.

Copyright (c) 2026 Cloudelipute
"""
from .app import YapperApp, main

__all__ = ["YapperApp", "main"]
```
- [ ] Run the full suite once more: `cd /home/romiteld/Development/Desktop_Apps/yapper-portable && QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q`. Expected: **all pass** with no circular-import error (eager import of `app` triggers importing `controller`, `theme`, `hud` lazily inside functions — safe).
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/__init__.py tests/test_imports.py && git commit -m "refactor(ui): eager-export YapperApp/main from ui package"
```

---

## Phase 4 Done When
- `uv run pytest tests/` is fully green under `QT_QPA_PLATFORM=offscreen` (~43 tests).
- `python -m app` launches the Qt tray app (wizard on first run); `python -m app --once` does a single-shot dictation.
- `app/yapper_tray.py`, `app/yapper.py`, `app/settings_ui.py`, `app/settings_console.py` are deleted.
- The `Controller` pipeline, theme, HUD, wizard, settings, and history are unit/smoke tested; the manual GUI/permission items are enumerated honestly in `docs/MANUAL_SMOKE_PHASE4.md` for the Phase 6 hardware pass.
