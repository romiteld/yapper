"""
Yapper Transcription History
============================
Logging and retrieval of transcription records.

© 2026 Cloudelipute
"""

import json
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .logger import get_logger

logger = get_logger("history")


@dataclass
class TranscriptionRecord:
    """A single transcription record."""
    timestamp: str              # ISO format timestamp
    duration_seconds: float     # Recording duration
    text: str                   # Transcribed text
    was_translated: bool        # Whether translation was applied
    target_language: str        # Target language if translated
    was_grammar_fixed: bool     # Whether grammar was corrected
    source_language: str        # Detected/specified source language
    character_count: int        # Length of final text

    @classmethod
    def create(
        cls,
        text: str,
        duration: float,
        translated: bool = False,
        target_lang: str = "",
        grammar_fixed: bool = False,
        source_lang: str = ""
    ) -> "TranscriptionRecord":
        """
        Create a new transcription record with current timestamp.

        Args:
            text: Transcribed text.
            duration: Recording duration in seconds.
            translated: Whether translation was applied.
            target_lang: Target language code.
            grammar_fixed: Whether grammar was corrected.
            source_lang: Source language code.

        Returns:
            New TranscriptionRecord instance.
        """
        return cls(
            timestamp=datetime.now().isoformat(),
            duration_seconds=round(duration, 2),
            text=text,
            was_translated=translated,
            target_language=target_lang,
            was_grammar_fixed=grammar_fixed,
            source_language=source_lang,
            character_count=len(text)
        )


class TranscriptionHistory:
    """
    Manages transcription history storage and retrieval.

    Example:
        history = TranscriptionHistory()
        history.add(TranscriptionRecord.create("Hello world", 2.5))
        recent = history.get_recent(10)
    """

    DEFAULT_MAX_RECORDS = 1000
    HISTORY_FILENAME = "transcription_history.json"

    def __init__(
        self,
        history_dir: Optional[Path] = None,
        max_records: int = DEFAULT_MAX_RECORDS,
        enabled: bool = True
    ):
        """
        Initialize the transcription history.

        Args:
            history_dir: Directory to store history file.
            max_records: Maximum number of records to keep.
            enabled: Whether history saving is enabled.
        """
        self.enabled = enabled
        self.max_records = max_records

        if history_dir is None:
            # Default: logs/ directory in project root
            app_dir = Path(__file__).parent.parent.resolve()
            history_dir = app_dir.parent / "logs"

        self._history_dir = history_dir
        self._history_file = history_dir / self.HISTORY_FILENAME
        self._records: List[TranscriptionRecord] = []
        self._loaded = False
        # RLock so methods that call other locked methods (e.g. add -> _save)
        # don't deadlock, and so concurrent add()/clear()/_save() are serialised.
        self._lock = threading.RLock()

    def _ensure_loaded(self) -> None:
        """Load history from file if not already loaded."""
        with self._lock:
            if self._loaded:
                return

            self._loaded = True

            if not self._history_file.exists():
                logger.debug("No history file found, starting fresh")
                return

            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    for item in data:
                        try:
                            record = TranscriptionRecord(**item)
                            self._records.append(record)
                        except (TypeError, KeyError) as e:
                            logger.warning(f"Skipping invalid record: {e}")

                logger.debug(f"Loaded {len(self._records)} history records")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid history JSON: {e}")
            except IOError as e:
                logger.error(f"Could not read history file: {e}")

    def add(self, record: TranscriptionRecord) -> bool:
        """
        Add a new transcription record.

        Args:
            record: TranscriptionRecord to add.

        Returns:
            True if added successfully.
        """
        if not self.enabled:
            return False

        with self._lock:
            self._ensure_loaded()
            self._records.append(record)

            # Trim old records if exceeding max
            if len(self._records) > self.max_records:
                self._records = self._records[-self.max_records:]

            # Save to file
            return self._save()

    def get_recent(self, count: int = 10) -> List[TranscriptionRecord]:
        """
        Get the most recent transcription records.

        Args:
            count: Number of records to return.

        Returns:
            List of TranscriptionRecord objects (newest first).
        """
        with self._lock:
            self._ensure_loaded()
            if count <= 0:
                return []
            return list(reversed(self._records[-count:]))

    def get_all(self) -> List[TranscriptionRecord]:
        """
        Get all transcription records.

        Returns:
            List of all TranscriptionRecord objects (oldest first).
        """
        with self._lock:
            self._ensure_loaded()
            return self._records.copy()

    def get_by_date(self, date: datetime) -> List[TranscriptionRecord]:
        """
        Get records from a specific date.

        Args:
            date: Date to filter by.

        Returns:
            List of records from that date.
        """
        with self._lock:
            self._ensure_loaded()
            date_str = date.strftime("%Y-%m-%d")
            return [
                r for r in self._records
                if r.timestamp.startswith(date_str)
            ]

    def clear(self) -> bool:
        """
        Clear all history.

        Returns:
            True if cleared successfully.
        """
        with self._lock:
            self._records = []
            self._loaded = True
            return self._save()

    def get_stats(self) -> dict:
        """
        Get statistics about transcription history.

        Returns:
            Dictionary with stats.
        """
        with self._lock:
            self._ensure_loaded()

            if not self._records:
                return {
                    "total_records": 0,
                    "total_duration": 0,
                    "total_characters": 0,
                    "translations": 0,
                    "grammar_fixes": 0,
                }

            return {
                "total_records": len(self._records),
                "total_duration": sum(r.duration_seconds for r in self._records),
                "total_characters": sum(r.character_count for r in self._records),
                "translations": sum(1 for r in self._records if r.was_translated),
                "grammar_fixes": sum(1 for r in self._records if r.was_grammar_fixed),
            }

    def _save(self) -> bool:
        """Save history to file. Must be called with self._lock held."""
        try:
            self._history_dir.mkdir(parents=True, exist_ok=True)

            data = [asdict(r) for r in self._records]

            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved {len(self._records)} history records")
            return True

        except IOError as e:
            logger.error(f"Could not save history: {e}")
            return False
