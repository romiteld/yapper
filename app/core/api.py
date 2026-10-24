"""
Yapper API Client
=================
ElevenLabs Speech-to-Text API client with retry logic and error handling.

© 2026 Cloudelipute
"""

import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx

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
    ElevenLabs API client with automatic retry logic.

    Example:
        client = APIClient(api_key="sk_...")
        text = client.transcribe("audio.wav", language="en")
    """

    BASE_URL = "https://api.elevenlabs.io/v1"
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
            api_key: ElevenLabs API key.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = None

    def _get_client(self) -> httpx.Client:
        """Lazily initialize the ElevenLabs HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                headers={"xi-api-key": self._api_key},
                timeout=self._timeout,
            )
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
        for attempt in range(self._max_retries):
            try:
                result = operation()
                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                return result

            except Exception as e:
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
        if isinstance(error, (APIRateLimitError, APIConnectionError, httpx.TransportError, httpx.TimeoutException)):
            return True

        error_type = type(error).__name__
        retryable_errors = [
            "RateLimitError",
            "APIRateLimitError",
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "ServiceUnavailableError",
            "ConnectError",
            "ReadTimeout",
            "WriteTimeout",
            "PoolTimeout",
        ]

        if error_type in retryable_errors:
            return True

        # Check for network errors
        msg = str(error).lower()
        if "connection" in msg or "timeout" in msg or "rate limit" in msg or "429" in msg:
            return True

        return False

    @staticmethod
    def _parse_keyterms(prompt: str) -> List[str]:
        """Convert a vocabulary prompt string into ElevenLabs Scribe v2 keyterms."""
        if not prompt or not prompt.strip():
            return []
        if "," in prompt:
            raw_terms = [t.strip() for t in prompt.split(",")]
        else:
            raw_terms = [t.strip() for t in re.split(r"\s+", prompt.strip())]
        terms: List[str] = []
        for term in raw_terms:
            if term and len(term) <= 50 and len(term.split()) <= 5 and term not in terms:
                terms.append(term)
            if len(terms) >= 100:
                break
        return terms

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        model: str = "scribe_v2",
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Transcribe audio file to text via ElevenLabs Scribe.

        Args:
            audio_path: Path to audio file.
            language: Optional language hint (ISO code).
            model: STT model (default scribe_v2; scribe_v1 selectable).
            prompt: Optional vocabulary bias passed as keyterms on scribe_v2.

        Returns:
            Transcribed text or None on failure.
        """
        def _do_transcribe() -> str:
            client = self._get_client()
            path_obj = Path(audio_path)

            with open(path_obj, "rb") as audio_file:
                data: Dict[str, Any] = {
                    "model_id": model,
                    "tag_audio_events": "false",
                }
                if language:
                    data["language_code"] = language
                if prompt and model == "scribe_v2":
                    keyterms = self._parse_keyterms(prompt)
                    if keyterms:
                        data["keyterms"] = keyterms

                files = {
                    "file": (path_obj.name, audio_file, "audio/wav"),
                }

                response = client.post(
                    "/speech-to-text",
                    data=data,
                    files=files,
                )

                if response.status_code == 429:
                    raise APIRateLimitError(f"HTTP 429: {response.text}")
                if response.status_code >= 500:
                    raise APIConnectionError(f"HTTP {response.status_code}: {response.text}")
                if response.status_code >= 400:
                    raise APIError(f"HTTP {response.status_code}: {response.text}")

                payload = response.json()
                if isinstance(payload, str):
                    return payload.strip()
                if isinstance(payload, dict):
                    return str(payload.get("text", "")).strip()
                return str(payload).strip()

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
        Optional chat completion hook for post-processing.

        When backed by an injected chat client (e.g. in tests), delegates to
        ``_client.chat.completions.create``. When backed only by the ElevenLabs
        STT HTTP client, returns None so callers use deterministic formatting.
        """
        if self._client is None or not hasattr(self._client, "chat"):
            logger.debug("Chat completion unavailable on STT-only client; using deterministic path")
            return None

        def _do_chat() -> str:
            response = self._client.chat.completions.create(
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
        Translate text to target language if a chat backend is available.
        """
        from .constants import LANGUAGE_CODES

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

        logger.warning("Translation unavailable or failed, returning original text")
        return text

    def fix_grammar(
        self,
        text: str,
        model: str = "gpt-5-nano",
    ) -> Optional[str]:
        """
        Fix grammar and punctuation in text if a chat backend is available.
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

        logger.warning("Grammar correction unavailable or failed, returning original text")
        return text

    def is_valid(self) -> bool:
        """Check if ElevenLabs API key is valid by making a test request."""
        try:
            client = self._get_client()
            resp = client.get("/user")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False
