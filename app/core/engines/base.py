"""
Transcription engine abstraction.
===============================
Defines the contract every STT backend (cloud, local) must satisfy.

© 2026 Cloudelipute
"""

from abc import ABC, abstractmethod
from typing import Optional


class TranscriptionEngine(ABC):
    """Abstract base for speech-to-text engines."""

    @abstractmethod
    def transcribe(
        self,
        wav_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Transcribe a 16 kHz mono WAV file to text.

        Args:
            wav_path: Path to the WAV file.
            language: Optional ISO language hint.
            prompt: Optional vocabulary bias.

        Returns:
            Transcribed text, or None on failure / empty audio.
        """
        raise NotImplementedError
