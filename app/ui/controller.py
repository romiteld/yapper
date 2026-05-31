"""Yapper dictation controller — pure orchestration, no Qt.

Wires hotkeys -> record -> engine -> format -> type -> history. UI layers
(YapperApp, HUD) subscribe via plain callbacks so this stays headless-testable.

© 2026 Cloudelipute
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

    # -- factories (overridable in tests) --------------------------------
    def _engine_factory(self):
        from core.engines import get_engine
        return get_engine(self.settings)

    def _formatter_factory(self):
        from core import APIClient
        from core.formatting import Formatter
        from core.vocabulary import Vocabulary
        vocab = Vocabulary(load_starter=False)
        vocab.from_list(self.settings.get("vocabulary", []))
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
        vocab = Vocabulary(load_starter=False)
        vocab.from_list(self.settings.get("vocabulary", []))
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
                mode=self.settings.get("output_mode", "clean"),
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
                grammar_fixed=self.settings.get("output_mode") == "clean",
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

    # -- hotkey entry points (called from HotkeyManager via _Bridge) -----
    def on_hotkey_start(self) -> None:
        self.start_recording()

    def on_hotkey_stop(self) -> None:
        self.stop_recording()

    def reload_settings(self) -> None:
        """Sync runtime state from the current Settings values.

        Does NOT reload from disk — call settings.load() explicitly before
        this if you want to re-read the file (YapperApp._on_settings_saved
        handles that after Settings.save()).
        """
        self.sounds.enabled = self.settings.get("audio_feedback", True)
        self.history.enabled = self.settings.get("save_history", True)
        logger.info("Controller settings reloaded")
