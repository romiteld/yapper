"""
Cloud transcription engine (ElevenLabs).
========================================
Wraps APIClient; default model scribe_v2.

© 2026 Cloudelipute
"""

from typing import Optional

from ..api import APIClient
from ..logger import get_logger
from .base import TranscriptionEngine

logger = get_logger("engines.cloud")


class CloudEngine(TranscriptionEngine):
    """ElevenLabs-backed speech-to-text engine."""

    def __init__(
        self,
        api_client: APIClient,
        model: str = "scribe_v2",
    ):
        self._api = api_client
        self._model = model

    def transcribe(
        self,
        wav_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        logger.debug(f"CloudEngine.transcribe model={self._model}")
        return self._api.transcribe(
            wav_path,
            language=language,
            model=self._model,
            prompt=prompt,
        )
