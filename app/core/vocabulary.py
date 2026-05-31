"""
Yapper Vocabulary
=================
User term store that (a) builds the Whisper prompt bias before transcription
and (b) fuzzy-corrects mis-heard technical terms after transcription.

Each term is a dict: {"said": str | None, "typed": str}.
  - "typed": the canonical output spelling (e.g. "kubectl").
  - "said":  an optional phonetic alias the model tends to mis-hear
             (e.g. "cube cuttle"). None means correct toward "typed" only.

© 2026 Cloudelipute
"""

import csv
import re
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from .logger import get_logger

logger = get_logger("vocabulary")


# Small built-in developer starter pack. Aliases are common Whisper mis-hears.
DEV_STARTER_PACK: List[Dict[str, Optional[str]]] = [
    {"said": "cube cuttle", "typed": "kubectl"},
    {"said": "next J S", "typed": "Next.js"},
    {"said": "post gres", "typed": "PostgreSQL"},
    {"said": "engine x", "typed": "nginx"},
    {"said": None, "typed": "OAuth"},
    {"said": None, "typed": "JWT"},
    {"said": "p npm", "typed": "pnpm"},
    {"said": None, "typed": "async/await"},
    {"said": None, "typed": "TypeScript"},
    {"said": None, "typed": "GraphQL"},
    {"said": None, "typed": "Redis"},
    {"said": None, "typed": "Docker"},
]


class Vocabulary:
    """User vocabulary store + Whisper bias + fuzzy correction."""

    # Minimum fuzzy similarity (0-100) for a window to be replaced. High on
    # purpose: we only want confident mis-hear corrections, never paraphrase.
    CORRECT_THRESHOLD: float = 85.0

    def __init__(self, load_starter: bool = True):
        """
        Args:
            load_starter: Seed with the built-in dev starter pack.
        """
        self.terms: List[Dict[str, Optional[str]]] = []
        if load_starter:
            self.from_list([dict(t) for t in DEV_STARTER_PACK])

    def add(self, typed: str, said: Optional[str] = None) -> None:
        """Add or update a term keyed by ``typed`` (idempotent)."""
        typed = typed.strip()
        if not typed:
            return
        for term in self.terms:
            if term["typed"] == typed:
                if said is not None:
                    term["said"] = said.strip()
                return
        self.terms.append({"said": said.strip() if said else None, "typed": typed})

    def remove(self, typed: str) -> None:
        """Remove all terms whose ``typed`` equals ``typed``."""
        self.terms = [t for t in self.terms if t["typed"] != typed]

    def to_list(self) -> List[Dict[str, Optional[str]]]:
        """Serialize to a JSON-friendly list (for settings)."""
        return [dict(t) for t in self.terms]

    def from_list(self, data: List) -> None:
        """
        Load terms from a list. Accepts bare strings (treated as ``typed``)
        or dicts with at least a ``typed`` key.
        """
        self.terms = []
        for entry in data or []:
            if isinstance(entry, str):
                self.add(entry)
            elif isinstance(entry, dict) and entry.get("typed"):
                self.add(entry["typed"], said=entry.get("said"))
            else:
                logger.warning(f"Skipping malformed vocabulary entry: {entry!r}")

    def import_csv(self, path: str) -> None:
        """
        Import terms from a CSV file. Supports either:
          - two columns ``said,typed`` (optional header row), or
          - a single column treated as ``typed``.
        Empty ``said`` cells become None.
        """
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    cells = [c.strip() for c in row]
                    # Skip a header row.
                    if cells[0].lower() == "said" or (
                        len(cells) > 1 and cells[1].lower() == "typed"
                    ):
                        continue
                    if len(cells) == 1:
                        if cells[0]:
                            self.add(cells[0])
                    else:
                        said, typed = cells[0], cells[1]
                        if typed:
                            self.add(typed, said=said or None)
        except OSError as e:
            logger.error(f"Could not import vocabulary CSV '{path}': {e}")

    def whisper_prompt(self, max_chars: int = 800) -> str:
        """
        Build a Whisper ``prompt=`` bias string from the canonical ``typed``
        spellings. Priming Whisper with these counters its weakness on proper
        nouns. Bounded to ``max_chars`` (Whisper caps the prompt at ~224
        tokens).
        """
        typed_terms = [t["typed"] for t in self.terms if t["typed"]]
        if not typed_terms:
            return ""
        prompt = ""
        for term in typed_terms:
            candidate = f"{prompt}{term}, "
            if len(candidate.rstrip(", ")) > max_chars:
                break
            prompt = candidate
        return prompt.rstrip(", ")

    def _correction_targets(self) -> List[Tuple[str, str]]:
        """
        Yield (phrase_to_match, canonical_typed) pairs, longest phrase first
        so multi-word aliases are matched before single words.
        """
        targets: List[Tuple[str, str]] = []
        for term in self.terms:
            typed = term["typed"]
            if term["said"]:
                targets.append((term["said"], typed))
            # Also match the canonical spelling itself (catches near-misses).
            targets.append((typed, typed))
        # Longest phrase (by word count, then chars) first.
        targets.sort(key=lambda p: (len(p[0].split()), len(p[0])), reverse=True)
        return targets

    def correct(self, text: str) -> str:
        """
        Fuzzy-replace mis-heard windows with canonical ``typed`` spellings.

        For each target phrase, slide a same-word-length window across the
        text and replace the best-matching window whose similarity exceeds
        ``CORRECT_THRESHOLD``. Single-word targets that already equal the
        canonical spelling are skipped (nothing to fix).
        """
        if not self.terms or not text.strip():
            return text

        words = text.split()
        for phrase, typed in self._correction_targets():
            phrase_words = phrase.split()
            n = len(phrase_words)
            if n == 0 or n > len(words):
                continue
            i = 0
            while i + n <= len(words):
                window = " ".join(words[i : i + n])
                if window == typed:
                    i += 1
                    continue
                score = fuzz.ratio(window.lower(), phrase.lower())
                if score >= self.CORRECT_THRESHOLD:
                    words[i : i + n] = [typed]
                    logger.debug(
                        f"Vocab correct: '{window}' -> '{typed}' (score={score:.0f})"
                    )
                    # restart scan; lengths changed
                    i = 0
                    continue
                i += 1
        return " ".join(words)
