"""
Yapper API Client
=================
OpenAI API client with retry logic and error handling.

© 2026 Cloudelipute
"""

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .logger import get_logger

logger = get_logger("api")

T = TypeVar("T")


class APIError(Exception):
    """Base exception for API errors."""
    pass


class APIConnectionError(APIError):
    """Connection to API failed."""
    pass


class APIRateLimitError(APIError):
    """Rate limit exceeded."""
    pass


class APIClient:
    """
    OpenAI API client with automatic retry logic.

    Example:
        client = APIClient(api_key="sk-...")
        text = client.transcribe("audio.wav", language="en")
        response = client.chat([{"role": "user", "content": "Hello"}])
    """

    DEFAULT_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # exponential backoff in seconds

    def __init__(
        self,
        api_key: str,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize the API client.

        Args:
            api_key: OpenAI API key.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = None

    def _get_client(self):
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    timeout=self._timeout
                )
            except ImportError:
                logger.error("OpenAI package not installed. Install with: pip install openai")
                raise APIError("OpenAI package not installed")
        return self._client

    def _with_retry(
        self,
        operation: Callable[[], T],
        operation_name: str
    ) -> Optional[T]:
        """
        Execute an operation with retry logic.

        Args:
            operation: Function to execute.
            operation_name: Name for logging purposes.

        Returns:
            Operation result or None on failure.
        """
        last_error = None

        for attempt in range(self._max_retries):
            try:
                result = operation()
                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                return result

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # Check if error is retryable
                retryable = self._is_retryable_error(e)

                if retryable and attempt < self._max_retries - 1:
                    delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self._max_retries}): "
                        f"{error_type}: {e}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed: {error_type}: {e}")
                    break

        return None

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        error_type = type(error).__name__

        # OpenAI specific errors
        retryable_errors = [
            "RateLimitError",
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "ServiceUnavailableError",
        ]

        if error_type in retryable_errors:
            return True

        # Check for network errors
        if "connection" in str(error).lower() or "timeout" in str(error).lower():
            return True

        return False

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        model: str = "gpt-4o-mini-transcribe",
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file.
            language: Optional language hint (ISO code).
            model: STT model (default gpt-4o-mini-transcribe; whisper-1 selectable).
            prompt: Optional vocabulary bias passed to the model.

        Returns:
            Transcribed text or None on failure.
        """
        def _do_transcribe() -> str:
            client = self._get_client()

            with open(audio_path, "rb") as audio_file:
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "file": audio_file,
                    "response_format": "text",
                }
                if language:
                    kwargs["language"] = language
                if prompt:
                    kwargs["prompt"] = prompt

                result = client.audio.transcriptions.create(**kwargs)

                # response_format='text' returns a plain str; guard for objects.
                if isinstance(result, str):
                    return result.strip()
                return result.text.strip()

        logger.debug(f"Transcribing: {audio_path} (model={model})")
        text = self._with_retry(_do_transcribe, "Transcription")

        if text:
            logger.debug(f"Transcribed {len(text)} characters")

        return text

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-nano",
        reasoning_effort: str = "minimal",
    ) -> Optional[str]:
        """
        Send a chat completion request to a reasoning model.

        Args:
            messages: List of message dicts.
            model: Text model (default gpt-5-nano).
            reasoning_effort: 'minimal' for fast, low-latency post-processing.

        Returns:
            Response text or None on failure.
        """
        def _do_chat() -> str:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                reasoning_effort=reasoning_effort,
            )
            msg = response.choices[0].message
            content = msg.content
            if not content:
                finish = response.choices[0].finish_reason
                if finish in ("length", "content_filter"):
                    logger.warning(
                        "Chat response truncated/filtered (finish_reason=%s)", finish)
            return content.strip() if content else ""

        logger.debug(f"Chat request ({model}) with {len(messages)} messages")
        return self._with_retry(_do_chat, "Chat")

    def translate(
        self,
        text: str,
        target_language: str,
        model: str = "gpt-5-nano",
    ) -> Optional[str]:
        """
        Translate text to target language.

        Args:
            text: Text to translate.
            target_language: Target language name or code.
            model: Model to use for translation.

        Returns:
            Translated text or original text on failure.
        """
        from .constants import LANGUAGE_CODES

        # Get full language name
        lang_name = LANGUAGE_CODES.get(target_language, target_language)

        messages = [
            {
                "role": "system",
                "content": f"You are a translator. Translate the following text to {lang_name}. "
                          "Only output the translation, nothing else. Preserve the tone and meaning."
            },
            {"role": "user", "content": text}
        ]

        logger.debug(f"Translating to {lang_name}")
        result = self.chat(messages, model=model)

        if result:
            return result

        logger.warning("Translation failed, returning original text")
        return text

    def fix_grammar(
        self,
        text: str,
        model: str = "gpt-5-nano",
    ) -> Optional[str]:
        """
        Fix grammar and punctuation in text.

        Args:
            text: Text to correct.
            model: Model to use.

        Returns:
            Corrected text or original text on failure.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that improves grammar and punctuation. "
                    "Please correct any grammatical errors in the user's text while preserving "
                    "the original meaning and tone. Return only the corrected text."
                )
            },
            {"role": "user", "content": text}
        ]

        logger.debug("Fixing grammar")
        result = self.chat(messages, model=model)

        if result:
            return result

        logger.warning("Grammar correction failed, returning original text")
        return text

    def is_valid(self) -> bool:
        """Check if API key is valid by making a test request."""
        try:
            client = self._get_client()
            # Make a minimal request to verify the key
            client.models.list()
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False
