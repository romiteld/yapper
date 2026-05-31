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
from typing import Callable, List, Optional, Tuple, Union

from .logger import get_logger

logger = get_logger("formatting")

TEXT_MODEL = "gpt-5-nano"

# Whitelist of suffixes for the "<name> dot <ext>" rule: common file
# extensions + TLDs only. Restricting to this set keeps ordinary prose like
# "the dot product" / "polka dot" untouched while still handling
# "main dot py" -> "main.py" and "example dot com" -> "example.com".
_DOT_SUFFIXES = [
    # file extensions
    "py", "js", "ts", "tsx", "jsx", "json", "yaml", "yml", "md", "txt",
    "sh", "toml", "go", "rs",
    # TLDs
    "com", "org", "net", "io", "dev",
]
_DOT_SUFFIX_RE = "|".join(sorted(_DOT_SUFFIXES, key=len, reverse=True))

# Common words that, when they precede "dash <letter>", indicate ordinary
# prose ("a dash of salt", "he made a dash", "grade dash a") rather than a CLI
# flag. The single-letter dash rule is suppressed after any of these.
_DASH_PROSE_PRECEDERS = frozenset({
    "a", "an", "the", "of", "in", "made", "that", "this", "his", "her", "your",
})

# If the letter after "dash" is itself a standalone English word/article, the
# phrase reads as prose ("grade dash a", "... dash i ...") — not a CLI flag.
_DASH_PROSE_LETTERS = frozenset({"a", "i"})


def _expand_single_dash(match: "re.Match") -> str:
    """Replace "dash <letter>" -> "-<letter>" unless it reads as prose.

    ``match`` captures an optional preceding word so we can suppress the
    conversion right after an article/preposition/common prose word, or when
    the flag "letter" is itself a standalone English article (a / i).
    """
    preceder = (match.group("pre") or "").lower()
    letter = match.group("letter")
    if preceder in _DASH_PROSE_PRECEDERS or letter.lower() in _DASH_PROSE_LETTERS:
        return match.group(0)  # leave untouched
    prefix = match.group("pre")
    space = match.group("presp") or ""
    return f"{prefix}{space}-{letter}" if prefix else f"-{letter}"


# Ordered, conservative spoken-symbol rules. Each is (compiled_pattern,
# replacement) where replacement is a string or a callable. Order matters —
# longer/structural cues are matched before single tokens. Every rule fires
# ONLY on an unambiguous cue so ordinary prose is never corrupted.
_SYMBOL_RULES: List[Tuple[re.Pattern, Union[str, Callable]]] = [
    # Long flags: "dash dash help" -> "--help" (unambiguous: double "dash").
    (re.compile(r"\bdash dash (\w+)\b", re.IGNORECASE), r"--\1"),
    # Short flags: "dash f" -> "-f" (single letter), guarded against prose by
    # inspecting the preceding word (see _expand_single_dash).
    (
        re.compile(
            r"(?:(?P<pre>\w+)(?P<presp>\s+))?\bdash\s+(?P<letter>[a-zA-Z])\b",
            re.IGNORECASE,
        ),
        _expand_single_dash,
    ),
    # File extensions / TLDs: "deployment dot yaml" -> "deployment.yaml".
    # Whitelisted suffixes only, so "the dot product" is untouched.
    (
        re.compile(
            rf"\b(\w+) dot ({_DOT_SUFFIX_RE})\b",
            re.IGNORECASE,
        ),
        r"\1.\2",
    ),
    # Backtick pair: "backtick <word(s)> backtick" -> "`<word(s)>`".
    # Requires both backtick cues, so prose is safe.
    (re.compile(r"\bbacktick (\w+(?:\s+\w+){0,4}) backtick\b", re.IGNORECASE), r"`\1`"),
    # Single standalone backtick cue (explicit word "backtick").
    (re.compile(r"\bbacktick\b", re.IGNORECASE), "`"),
    # Parentheses — require the explicit word "paren".
    (re.compile(r"\bopen paren\b", re.IGNORECASE), "("),
    (re.compile(r"\bclose paren\b", re.IGNORECASE), ")"),
    # Newline — ONLY on an explicit standalone trigger, never the bare
    # "new line" (which mangles "a new line of thinking"). "press enter" and
    # "insert new line" are unambiguous dictation commands.
    (re.compile(r"\b(?:press enter|insert new line)\b", re.IGNORECASE), "\n"),
]


def expand_spoken_symbols(text: str) -> str:
    """
    Expand spoken-symbol cues to their characters.

    Conservative by design: every rule fires only on an unambiguous cue, so
    ordinary prose is left untouched. Specifically:
      - "dash dash <word>" -> "--word"; "dash <letter>" -> "-<letter>" only
        when not preceded by a prose word (a/an/the/of/...).
      - "<name> dot <ext>" -> "<name>.<ext>" for whitelisted extensions/TLDs
        only ("main dot py", "example dot com"); "the dot product" is safe.
      - "backtick ... backtick" -> "`...`"; "open/close paren" -> "(" / ")".
      - newline ONLY via explicit "press enter" / "insert new line".

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

    def __init__(self, api_client, vocabulary, text_model: str = TEXT_MODEL):
        """
        Args:
            api_client: APIClient with a ``chat(messages, ...)`` method, or
                None to skip all LLM cleanup/translation steps.
            vocabulary: Vocabulary used for correction and protected tokens.
            text_model: Chat model used for the LLM cleanup/translation steps
                (default ``gpt-5-nano``).
        """
        self._api = api_client
        self._vocab = vocabulary
        self._text_model = text_model or TEXT_MODEL

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
            model=self._text_model,
            reasoning_effort="minimal",
        )
        return result.strip() if result else text

    def _polished_cleanup(self, text: str) -> str:
        system = (
            "You polish dictated prose. Fix grammar and punctuation, remove "
            "filler words (um, uh, like, you know), and produce clean, natural "
            "sentences while preserving the original meaning and tone. "
            "Preserve all technical terms, code, identifiers, CamelCase, CLI "
            "flags, and file paths exactly — never paraphrase or alter code "
            "tokens (e.g. keep `kubectl apply -f` verbatim). "
            "Output ONLY the cleaned text, nothing else."
        )
        protected = self._protected_tokens()
        if protected:
            system += f"\nProtected tokens (keep exactly as written): {protected}."
        result = self._api.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            model=self._text_model,
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
            model=self._text_model,
            reasoning_effort="minimal",
        )
        return result.strip() if result else text
