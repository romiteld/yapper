"""
Local on-device transcription engine.
=====================================
Lazy-imports mlx_whisper (macOS Apple Silicon) or faster_whisper (Windows).
Requires the optional install extra:  uv sync --extra local

© 2026 Cloudelipute
"""

import sys
from typing import Any, Optional

from ..logger import get_logger
from .base import TranscriptionEngine

logger = get_logger("engines.local")

IS_MAC = sys.platform == "darwin"


class LocalEngineUnavailable(RuntimeError):
    """Raised when the [local] extra (mlx/faster-whisper) is not installed."""


class LocalEngine(TranscriptionEngine):
    """On-device speech-to-text via mlx-whisper (mac) / faster-whisper (win)."""

    def __init__(self, model: str = "base"):
        self._model = model
        self._backend: Optional[Any] = None

    def _load_backend(self) -> Any:
        """Lazily import and build the platform backend.

        Returns an object exposing `.transcribe(wav_path, language=...) -> dict`
        with a 'text' key. Raises LocalEngineUnavailable if the extra is absent.
        """
        if IS_MAC:
            try:
                import mlx_whisper  # noqa: F401
            except ImportError as e:
                raise LocalEngineUnavailable(
                    "mlx-whisper not installed. Run: uv sync --extra local"
                ) from e
            return _MlxBackend(self._model)

        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise LocalEngineUnavailable(
                "faster-whisper not installed. Run: uv sync --extra local"
            ) from e
        return _FasterWhisperBackend(WhisperModel(self._model))

    def transcribe(
        self,
        wav_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        if self._backend is None:
            self._backend = self._load_backend()
        result = self._backend.transcribe(wav_path, language=language)
        text = result.get("text") if isinstance(result, dict) else result
        return text.strip() if text else None


class _MlxBackend:
    """Thin adapter so mlx_whisper matches the dict-returning contract."""

    def __init__(self, model: str):
        self._model = model

    def transcribe(self, wav_path: str, language: Optional[str] = None) -> dict:
        import mlx_whisper
        repo = f"mlx-community/whisper-{self._model}"
        return mlx_whisper.transcribe(
            wav_path, path_or_hf_repo=repo, language=language
        )


class _FasterWhisperBackend:
    """Adapter joining faster-whisper's segment generator into a dict."""

    def __init__(self, model: Any):
        self._model = model

    def transcribe(self, wav_path: str, language: Optional[str] = None) -> dict:
        segments, _info = self._model.transcribe(wav_path, language=language)
        text = "".join(seg.text for seg in segments)
        return {"text": text}
