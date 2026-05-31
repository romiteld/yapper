"""
Yapper No-Slop Formatting Subsystem
===================================
Spoken-symbol expansion and output-mode cleanup for a general-purpose
dictation tool. Types what the user actually said — their wording, voice,
slang, AND any jargon/code/CLI flags/paths — fixing only mechanics, never
paraphrasing. Works the same for casual messaging and technical text.

© 2026 Cloudelipute
"""

import re
from typing import List, Optional, Tuple

from .logger import get_logger

logger = get_logger("formatting")

TEXT_MODEL = "gpt-5-nano"

# Ordered, conservative spoken-symbol rules: (compiled_pattern, replacement).
# Order matters — longer/structural cues are matched before single tokens so
# that e.g. "dash dash help" beats "dash". Each rule only fires on a clear cue
# to avoid corrupting ordinary prose.
_SYMBOL_RULES: List[Tuple[re.Pattern, str]] = [
    # Long flags: "dash dash help" -> "--help"
    (re.compile(r"\bdash dash (\w+)\b", re.IGNORECASE), r"--\1"),
    # Short flags: "dash f" -> "-f" (single letter only, to avoid prose)
    (re.compile(r"\bdash ([a-zA-Z])\b", re.IGNORECASE), r"-\1"),
    # File extensions: "deployment dot yaml" -> "deployment.yaml"
    (
        re.compile(
            r"\b(\w+) dot (py|yaml|yml|json|js|ts|tsx|jsx|md|txt|sh|toml|cfg|ini|env|go|rs|rb|java|c|cpp|h)\b",
            re.IGNORECASE,
        ),
        r"\1.\2",
    ),
    # Backtick pair: "backtick <word(s)> backtick" -> "`<word(s)>`"
    # Match up to 5 words between the two backtick cues.
    (re.compile(r"\bbacktick (\w+(?:\s+\w+){0,4}) backtick\b", re.IGNORECASE), r"`\1`"),
    # Single standalone backtick cue (fallback).
    (re.compile(r"\bbacktick\b", re.IGNORECASE), "`"),
    # Parentheses
    (re.compile(r"\bopen paren\b", re.IGNORECASE), "("),
    (re.compile(r"\bclose paren\b", re.IGNORECASE), ")"),
    # New line
    (re.compile(r"\bnew line\b", re.IGNORECASE), "\n"),
]


def expand_spoken_symbols(text: str) -> str:
    """
    Expand spoken-symbol cues to their characters.

    Conservative: only fires on clear cues (e.g. "dash dash <word>",
    "<name> dot py", "backtick", "open/close paren", "new line"). Ordinary
    prose is left untouched.

    Args:
        text: Raw transcription text.

    Returns:
        Text with spoken symbols expanded.
    """
    result = text
    for pattern, replacement in _SYMBOL_RULES:
        result = pattern.sub(replacement, result)

    # Paren replacements leave doubled spaces inside; collapse them.
    result = re.sub(r"\(\s+", "(", result)
    result = re.sub(r"\s+\)", ")", result)
    # Collapse any doubled spaces left after newline insertion.
    result = re.sub(r" *\n *", "\n", result)
    return result


class Formatter:
    """
    Output formatter for the no-slop pipeline.

    Pipeline order (after raw transcription, wake-word stripping happens
    upstream):
      1. spoken-symbol expansion (optional)
      2. canonical vocabulary correction
      3. mode cleanup (LLM) — clean | polished ; verbatim skips the LLM
      4. translation (replaces mode cleanup when a target language is set)

    The LLM steps (3 and 4) require an ``api_client``. When ``api_client`` is
    None (e.g. no API key configured), those steps are skipped and the
    deterministic result from steps 1-2 is returned — so a user with no key
    still gets spoken-symbol expansion and vocabulary correction.
    """

    def __init__(self, api_client, vocabulary):
        """
        Args:
            api_client: APIClient with a ``chat(messages, ...)`` method, or
                None to skip all LLM cleanup/translation steps.
            vocabulary: Vocabulary used for correction and protected tokens.
        """
        self._api = api_client
        self._vocab = vocabulary

    def format(
        self,
        raw_text: str,
        *,
        mode: str,
        expand_symbols: bool,
        translate_to: Optional[str],
    ) -> str:
        """
        Run the no-slop pipeline.

        Args:
            raw_text: Raw transcription text.
            mode: 'clean' | 'polished' | 'verbatim'.
            expand_symbols: Whether to run spoken-symbol expansion.
            translate_to: Target language code, or None/"" for no translation.

        Returns:
            Final formatted text.
        """
        text = raw_text.strip()
        if not text:
            return text

        # 1. Spoken-symbol expansion (deterministic).
        if expand_symbols:
            text = expand_spoken_symbols(text)

        # 2. Canonical vocabulary correction (deterministic).
        text = self._vocab.correct(text)

        # Verbatim: no LLM step at all.
        if mode == "verbatim" and not translate_to:
            return text

        # Without an API client we can't run the LLM steps; return the
        # deterministic result so symbol/vocab help still works offline.
        if self._api is None:
            return text

        # 4. Translation replaces mode cleanup when a target language is set.
        if translate_to:
            return self._translate(text, translate_to)

        # 3. Mode cleanup (LLM).
        if mode == "polished":
            return self._polished_cleanup(text)
        # default / clean
        return self._clean_cleanup(text)

    def _protected_tokens(self) -> str:
        tokens = [t["typed"] for t in self._vocab.terms if t["typed"]]
        return ", ".join(tokens)

    def _clean_cleanup(self, text: str) -> str:
        system = (
            "You clean up dictated speech. Fix capitalization and punctuation "
            "and remove filler words (um, uh, 'like'/'you know' used as "
            "fillers). Do NOT rephrase, reword, summarize, translate, or change "
            "the user's wording, tone, slang, or voice. Preserve all technical "
            "terms, code, identifiers, CamelCase, CLI flags, and file paths "
            "exactly. Return only the user's cleaned words."
        )
        protected = self._protected_tokens()
        if protected:
            system += f"\nProtected tokens (keep exactly as written): {protected}."
        result = self._api.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            model=TEXT_MODEL,
            reasoning_effort="minimal",
        )
        return result.strip() if result else text

    def _polished_cleanup(self, text: str) -> str:
        system = (
            "You polish dictated prose. Fix grammar and punctuation, remove "
            "filler words (um, uh, like, you know), and produce clean, natural "
            "sentences while preserving the original meaning and tone. "
            "Output ONLY the cleaned text, nothing else."
        )
        result = self._api.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            model=TEXT_MODEL,
            reasoning_effort="minimal",
        )
        return result.strip() if result else text

    def _translate(self, text: str, translate_to: str) -> str:
        from .constants import LANGUAGE_CODES

        lang_name = LANGUAGE_CODES.get(translate_to, translate_to)
        system = (
            f"You are a translator. Translate the user's text to {lang_name}. "
            "Leave code, identifiers, CLI flags, file paths, and URLs "
            "untranslated and verbatim. Do not translate technical tokens. "
            "Output ONLY the translation, nothing else."
        )
        protected = self._protected_tokens()
        if protected:
            system += f"\nKeep these tokens exactly as written: {protected}."
        result = self._api.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            model=TEXT_MODEL,
            reasoning_effort="minimal",
        )
        return result.strip() if result else text
