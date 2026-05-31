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


# Small built-in developer starter pack.
#
# Two roles, kept strictly separate:
#   - Every "typed" term seeds the Whisper prompt bias (whisper_prompt()),
#     priming the model so it spells proper nouns right in the FIRST place.
#   - Only terms with an explicit "said" alias participate in post-transcription
#     correct(). A "said" alias is a DISTINCTIVE phrase Whisper genuinely
#     mis-hears (e.g. "cube cuttle" for kubectl); it is never an intentional
#     casual form. Terms with said=None NEVER rewrite the user's words — so
#     "just docker it", "redis is fast", "lets use postgres" stay as dictated.
#
# Aliases may be a single string or a list of strings (multiple mis-hears).
DEV_STARTER_PACK: List[Dict[str, object]] = [
    {"said": ["cube cuttle", "cube cuddle", "kube control"], "typed": "kubectl"},
    {"said": ["next J S"], "typed": "Next.js"},
    {"said": ["engine x"], "typed": "nginx"},
    {"said": ["graph QL"], "typed": "GraphQL"},
    # Deliberately NO alias for the intentional short form "postgres" — only
    # the genuine mis-hear "postgre sql". "lets use postgres" is left alone.
    {"said": ["postgre sql"], "typed": "PostgreSQL"},
    # Prompt-bias only (no correction): these are spelled fine by Whisper and
    # have common intentional casual forms we must not rewrite.
    {"said": None, "typed": "OAuth"},
    {"said": None, "typed": "JWT"},
    {"said": None, "typed": "pnpm"},
    {"said": None, "typed": "async/await"},
    {"said": None, "typed": "TypeScript"},
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

    def add(self, typed: str, said=None) -> None:
        """Add or update a term keyed by ``typed`` (idempotent).

        ``said`` may be None, a single alias string, or a list of alias
        strings. Aliases are distinctive mis-hear phrases used by ``correct``;
        ``None`` means the term contributes to Whisper bias only.
        """
        typed = typed.strip()
        if not typed:
            return
        normalized = self._normalize_said(said)
        for term in self.terms:
            if term["typed"] == typed:
                if normalized is not None:
                    term["said"] = normalized
                return
        self.terms.append({"said": normalized, "typed": typed})

    @staticmethod
    def _normalize_said(said) -> Optional[str]:
        """Normalize a ``said`` value to None or a single string.

        Accepts None, a string, or a list/tuple of strings. A list is stored
        as a comma-separated string so the serialized term stays JSON/CSV
        friendly ({said: str|None, typed: str}); ``_aliases`` splits it back.
        """
        if said is None:
            return None
        if isinstance(said, (list, tuple)):
            parts = [str(s).strip() for s in said if str(s).strip()]
            return ", ".join(parts) if parts else None
        text = str(said).strip()
        return text or None

    def remove(self, typed: str) -> None:
        """Remove all terms whose ``typed`` equals ``typed``."""
        self.terms = [t for t in self.terms if t["typed"] != typed]

    def to_list(self) -> List[Dict[str, Optional[str]]]:
        """Serialize to a JSON-friendly list (for settings)."""
        return [dict(t) for t in self.terms]

    def from_list(self, data: List) -> None:
        """
        Replace all terms from a list. Accepts bare strings (treated as
        ``typed``) or dicts with at least a ``typed`` key.
        """
        self.terms = []
        self.add_from_list(data)

    def add_from_list(self, data: List) -> None:
        """
        Append terms from a list WITHOUT clearing existing terms (e.g. layer a
        user's custom vocabulary on top of the built-in starter pack). Accepts
        bare strings (treated as ``typed``) or dicts with a ``typed`` key.
        """
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

    # An explicit mis-hear alias must be DISTINCTIVE enough that it cannot
    # collide with intentional casual usage: at least this many words OR this
    # many characters. (e.g. "cube cuttle" = 2 words; "postgre sql" = 2 words.)
    MIN_ALIAS_WORDS: int = 2
    MIN_ALIAS_CHARS: int = 6

    @staticmethod
    def _aliases(said: Optional[str]) -> List[str]:
        """Split a stored ``said`` value into individual alias phrases."""
        if not said:
            return []
        return [a.strip() for a in said.split(",") if a.strip()]

    def _correction_targets(self) -> List[Tuple[str, str]]:
        """
        Yield (alias_phrase, canonical_typed) pairs to fuzzy-correct.

        ONLY explicit ``said`` mis-hear aliases participate — terms with
        said=None contribute to the Whisper prompt bias only and NEVER rewrite
        the user's words. Each alias must clear the distinctiveness backstop
        (>= MIN_ALIAS_WORDS words OR >= MIN_ALIAS_CHARS chars) so it can't
        false-match short casual words. Longest phrase first so multi-word
        aliases win.
        """
        targets: List[Tuple[str, str]] = []
        for term in self.terms:
            typed = term["typed"]
            for alias in self._aliases(term["said"]):
                words = alias.split()
                if len(words) < self.MIN_ALIAS_WORDS and len(alias) < self.MIN_ALIAS_CHARS:
                    logger.debug(
                        f"Skipping non-distinctive alias {alias!r} for {typed!r}"
                    )
                    continue
                targets.append((alias, typed))
        # Longest phrase (by word count, then chars) first.
        targets.sort(key=lambda p: (len(p[0].split()), len(p[0])), reverse=True)
        return targets

    def correct(self, text: str) -> str:
        """
        Fuzzy-replace mis-heard windows with canonical ``typed`` spellings.

        Only EXPLICIT ``said`` mis-hear aliases are applied. For each alias,
        slide a same-word-length window across the text and replace the
        best-matching window whose similarity exceeds ``CORRECT_THRESHOLD``.
        Intentional casual usage of bare terms (e.g. "just docker it",
        "redis is fast", "lets use postgres") is left untouched.
        """
        if not self.terms or not text.strip():
            return text

        targets = self._correction_targets()
        if not targets:
            return text

        words = text.split()
        for phrase, typed in targets:
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
