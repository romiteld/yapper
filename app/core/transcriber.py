"""
Yapper Transcriber
==================
Thin orchestrator: engine.transcribe() -> wake-word clean -> formatting.

The real formatting subsystem lands in Phase 3 (core/formatting.Formatter).
Until then, a passthrough formatter is used by default.

© 2026 Cloudelipute
"""

import os
import re
from typing import Optional

from .engines.base import TranscriptionEngine
from .logger import get_logger

logger = get_logger("transcriber")


class _PassthroughFormatter:
    """No-op stand-in for the Phase 3 Formatter; returns text unchanged."""

    def format(
        self,
        raw_text: str,
        *,
        mode: str,
        expand_symbols: bool,
        translate_to: Optional[str],
    ) -> str:
        return raw_text


class Transcriber:
    """Orchestrates transcription over a TranscriptionEngine + a Formatter.

    Example:
        eng = get_engine(settings)
        t = Transcriber(engine=eng, output_mode="technical")
        text = t.transcribe("audio.wav")
    """

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
        engine: Optional[TranscriptionEngine] = None,
        *,
        api_key: str = "",
        language_hint: str = "",
        translate_to: str = "",
        output_mode: str = "technical",
        expand_spoken_symbols: bool = True,
        formatter: Optional[object] = None,
        clean_wake_words: bool = True,
        # Legacy compat (Phase 1/old callers); folded into output_mode.
        fix_grammar: bool = True,
    ):
        if engine is None:
            # Backward-compat: build a CloudEngine from an api_key.
            from .api import APIClient
            from .engines.cloud import CloudEngine
            engine = CloudEngine(api_client=APIClient(api_key=api_key))
        self._engine = engine
        self.language_hint = language_hint
        self.translate_to = translate_to
        self.output_mode = output_mode
        self.expand_spoken_symbols = expand_spoken_symbols
        self.clean_wake_words = clean_wake_words
        self._formatter = formatter or _PassthroughFormatter()

    def transcribe(
        self,
        audio_path: str,
        delete_audio: bool = True,
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Transcribe + clean + format an audio file."""
        logger.info(f"Transcribing: {audio_path}")

        text = self._engine.transcribe(
            audio_path,
            language=self.language_hint or None,
            prompt=prompt,
        )

        if delete_audio:
            self._delete_audio_file(audio_path)

        if not text:
            logger.warning("Transcription returned empty result")
            return None

        logger.debug(f"Raw transcription: {text[:100]}...")

        if self.clean_wake_words:
            text = self._clean_wake_words(text)
            if not text:
                logger.warning("Text empty after removing wake words")
                return None

        text = self._formatter.format(
            text,
            mode=self.output_mode,
            expand_symbols=self.expand_spoken_symbols,
            translate_to=self.translate_to or None,
        )

        logger.info(f"Final text ({len(text)} chars): {text[:50]}...")
        return text

    def transcribe_for_wake_word(self, audio_path: str) -> Optional[str]:
        """Raw transcription for wake-word detection (no formatting)."""
        text = self._engine.transcribe(
            audio_path, language=self.language_hint or None
        )
        self._delete_audio_file(audio_path)
        if text:
            return text.lower().strip()
        return None

    def _clean_wake_words(self, text: str) -> str:
        cleaned = text
        for pattern in self.WAKE_WORD_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned != text:
            logger.debug(f"Cleaned wake words: '{text}' -> '{cleaned}'")
        return cleaned

    def _delete_audio_file(self, audio_path: str) -> None:
        try:
            os.unlink(audio_path)
            logger.debug(f"Deleted audio file: {audio_path}")
        except OSError as e:
            logger.warning(f"Could not delete audio file: {e}")
