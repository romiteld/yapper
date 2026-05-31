"""
Yapper Transcriber
==================
Speech-to-text transcription with optional translation and grammar correction.

© 2026 Cloudelipute
"""

import os
import re
from typing import Optional

from .api import APIClient
from .logger import get_logger

logger = get_logger("transcriber")


class Transcriber:
    """
    Speech-to-text transcriber with translation and grammar correction.

    Example:
        transcriber = Transcriber(api_key="sk-...", translate_to="es")
        text = transcriber.transcribe("audio.wav")
    """

    # Wake word patterns to clean from transcriptions
    WAKE_WORD_PATTERNS = [
        r"\byapper[\s,]*start\b",
        r"\byapper[\s,]*stop\b",
        r"\byap\s*or\s*start\b",
        r"\byap\s*or\s*stop\b",
        r"\byap\s*er\s*start\b",
        r"\byap\s*er\s*stop\b",
    ]

    def __init__(
        self,
        api_key: str,
        language_hint: str = "",
        translate_to: str = "",
        fix_grammar: bool = True,
        clean_wake_words: bool = True
    ):
        """
        Initialize the transcriber.

        Args:
            api_key: OpenAI API key.
            language_hint: Optional language hint for Whisper (ISO code like 'en').
            translate_to: Target language for translation (empty = no translation).
            fix_grammar: Auto-correct grammar when not translating.
            clean_wake_words: Remove wake word phrases from transcription.
        """
        self._api_client = APIClient(api_key=api_key)
        self.language_hint = language_hint
        self.translate_to = translate_to
        self.fix_grammar = fix_grammar
        self.clean_wake_words = clean_wake_words

    def transcribe(
        self,
        audio_path: str,
        delete_audio: bool = True
    ) -> Optional[str]:
        """
        Transcribe audio file to text with optional post-processing.

        Args:
            audio_path: Path to the audio file.
            delete_audio: Whether to delete the audio file after transcription.

        Returns:
            Transcribed (and optionally processed) text, or None on failure.
        """
        logger.info(f"Transcribing: {audio_path}")

        # Step 1: Transcribe audio
        text = self._api_client.transcribe(
            audio_path=audio_path,
            language=self.language_hint if self.language_hint else None
        )

        # Clean up audio file
        if delete_audio:
            self._delete_audio_file(audio_path)

        if not text:
            logger.warning("Transcription returned empty result")
            return None

        logger.debug(f"Raw transcription: {text[:100]}...")

        # Step 2: Clean wake words if enabled
        if self.clean_wake_words:
            text = self._clean_wake_words(text)
            if not text:
                logger.warning("Text empty after removing wake words")
                return None

        # Step 3: Translation or grammar correction
        if self.translate_to:
            text = self._translate(text)
        elif self.fix_grammar:
            text = self._fix_grammar(text)

        logger.info(f"Final text ({len(text)} chars): {text[:50]}...")
        return text

    def transcribe_for_wake_word(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio specifically for wake word detection.
        No post-processing, just raw transcription.

        Args:
            audio_path: Path to audio file.

        Returns:
            Raw transcription text or None.
        """
        text = self._api_client.transcribe(
            audio_path=audio_path,
            language=self.language_hint if self.language_hint else None
        )

        self._delete_audio_file(audio_path)

        if text:
            return text.lower().strip()
        return None

    def _clean_wake_words(self, text: str) -> str:
        """Remove wake word phrases from text."""
        cleaned = text
        for pattern in self.WAKE_WORD_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Clean up multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)

        if cleaned != text:
            logger.debug(f"Cleaned wake words: '{text}' -> '{cleaned}'")

        return cleaned

    def _translate(self, text: str) -> str:
        """Translate text to target language."""
        logger.info(f"Translating to: {self.translate_to}")

        result = self._api_client.translate(text, self.translate_to)
        return result if result else text

    def _fix_grammar(self, text: str) -> str:
        """Fix grammar and punctuation."""
        logger.info("Fixing grammar")

        result = self._api_client.fix_grammar(text)
        return result if result else text

    def _delete_audio_file(self, audio_path: str) -> None:
        """Safely delete audio file."""
        try:
            os.unlink(audio_path)
            logger.debug(f"Deleted audio file: {audio_path}")
        except OSError as e:
            logger.warning(f"Could not delete audio file: {e}")
