"""
Yapper Faithful Formatting Subsystem
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

# Common words that, when they precede "dash <letter>", indicate ordinary prose
# rather than a CLI short flag. The single-letter dash rule is suppressed after
# any of these (it also requires a positive CLI cue to fire — see
# _expand_single_dash).
_DASH_PROSE_PRECEDERS = frozenset({
    # Articles, prepositions, and determiners.
    "a", "an", "the", "of", "in", "that", "this", "his", "her", "your",
    # Common verbs/words that appear in prose "X dash <letter>" patterns.
    "made", "was", "is", "are", "be", "been", "had", "has", "have",
    "plan", "score", "mark", "note", "long", "mad", "em", "quick", "straight",
    "even", "odd", "just",
})

# Narrow prose blacklist for the "dash dash <word>" (--flag) rule. Because
# "dash dash" is a near-unambiguous CLI cue, this rule CONVERTS BY DEFAULT and
# only suppresses these clearly-prose preceders. It deliberately EXCLUDES words
# like "set"/"config"/"install"/"get" that are legitimate CLI subcommands, so
# real commands ("npm set --global", "git config --global") still convert.
_DASH_DASH_PROSE_PRECEDERS = frozenset({
    # Articles, prepositions, determiners.
    "a", "an", "the", "of", "in", "that", "this", "his", "her", "your",
    # Linking/auxiliary verbs that read as prose before "dash dash".
    "was", "were", "is", "are", "be", "been", "had", "has", "have", "made",
    # Adjectives/adverbs that read as prose before "dash dash".
    "long", "mad", "em", "quick", "straight", "even", "odd", "just",
    # Common everyday nouns that are NOT CLI subcommands.
    "plan", "score", "mark", "note", "dash",
})

# If the letter after "dash" is itself a standalone English word/article, the
# phrase reads as prose ("grade dash a", "... dash i ...") — not a CLI flag.
_DASH_PROSE_LETTERS = frozenset({"a", "i"})

# Positive-evidence CLI verbs/commands/subcommands. The dash rules fire when
# the preceding token is one of these (or when there is no preceding word, i.e.
# the flag appears at the start of the utterance). This prevents "she dash B",
# "plan dash B", "vitamin dash C" from being mangled while still converting real
# CLI commands like "npm set --global", "git config --global".
_DASH_CLI_VERBS = frozenset({
    # shell/CLI verbs and common subcommands
    "run", "use", "with", "exec", "flag", "apply", "commit", "push", "pull",
    "build", "test", "install", "uninstall", "deploy", "serve", "start", "stop",
    "add", "remove", "create", "delete", "update", "upgrade", "init", "clone",
    "checkout", "merge", "rebase", "fetch", "diff", "log", "status", "reset",
    "config", "set", "get", "list", "show", "save", "publish", "link", "unlink",
    "restart", "exec", "logs", "describe", "scale", "rollout", "expose",
    "config", "login", "logout", "search", "info", "audit", "format", "lint",
    # common CLI binaries
    "git", "kubectl", "docker", "npm", "yarn", "pnpm", "pip", "python", "python3",
    "ls", "cp", "mv", "rm", "cat", "grep", "find", "curl", "ssh", "scp",
    "tar", "rsync", "make", "cmake", "go", "cargo", "rustc", "java", "mvn",
    "uv", "pipx", "brew", "apt", "yum", "dnf", "pacman", "helm", "terraform",
    "gradle", "node", "deno", "bun", "gcloud", "aws", "az",
})


def _expand_single_dash(match: "re.Match") -> str:
    """Replace "dash <letter>" -> "-<letter>" only in a clear CLI context.

    The rule fires when:
      - There is no preceding word (flag at the start of the utterance), OR
      - The preceding word is a known CLI command/verb (_DASH_CLI_VERBS).

    It is suppressed when:
      - The preceding word is a prose word (_DASH_PROSE_PRECEDERS), OR
      - The preceding word is NOT a recognized CLI cue (default-safe), OR
      - The flag letter is a standalone English article (a / i).
    """
    preceder = (match.group("pre") or "").lower()
    letter = match.group("letter")

    # Prose letter guard: "grade dash a" / "plan dash i" -> untouched.
    if letter.lower() in _DASH_PROSE_LETTERS:
        return match.group(0)

    # No preceding word -> flag at start of utterance; convert.
    if not preceder:
        return f"-{letter}"

    # Preceding word is a known prose word -> leave untouched.
    if preceder in _DASH_PROSE_PRECEDERS:
        return match.group(0)

    # Preceding word is a recognized CLI command/verb -> convert.
    if preceder in _DASH_CLI_VERBS:
        prefix = match.group("pre")
        space = match.group("presp") or ""
        return f"{prefix}{space}-{letter}"

    # Default: unknown preceding word — do NOT convert (avoids "she dash B",
    # "plan dash B", "vitamin dash C", "grade dash B", etc.).
    return match.group(0)


def _expand_double_dash(match: "re.Match") -> str:
    """Replace "dash dash <word>" -> "--<word>".

    "dash dash" is a near-unambiguous long-flag cue (saying "dash dash" out loud
    in casual prose is rare), so we CONVERT BY DEFAULT and only suppress when the
    preceding word is a clear prose word (_DASH_DASH_PROSE_PRECEDERS). This keeps
    real CLI commands working even when a subcommand/argument noun precedes the
    flag — e.g. "npm set --global", "git config --global", "kubectl get pods
    --all", "git commit --amend" — while leaving contrived prose like "the score
    was dash dash even" / "plan dash dash backup" / "a long dash dash mark"
    untouched.

    NOTE: this uses a narrower prose blacklist than the single-dash rule, NOT a
    CLI verb whitelist, precisely because the preceding token is often a CLI
    noun/argument ("pods", "image", "config") that no whitelist could enumerate.
    Erring toward conversion is correct here (see the bug #22 re-verification).
    """
    pre = (match.group("pre") or "").lower()
    word = match.group("word")

    # Only suppress for clearly-prose preceders that are NOT plausible CLI
    # commands/subcommands/arguments. (Words like "set"/"config"/"install" are
    # deliberately excluded — they are real CLI subcommands.)
    if pre and pre in _DASH_DASH_PROSE_PRECEDERS:
        return match.group(0)  # prose — leave untouched

    prefix = match.group("pre")
    space = match.group("presp") or ""
    return f"{prefix}{space}--{word}" if prefix else f"--{word}"


# Prose words that, when they immediately follow "press enter" or
# "insert new line", indicate the phrase is prose rather than a dictation
# command (e.g. "press enter to continue", "I press enter the room").
_NEWLINE_PROSE_FOLLOWERS = frozenset({
    "to", "the", "a", "an", "your", "my", "his", "her",
    "this", "that", "key", "button",
})


def _expand_newline(match: "re.Match") -> str:
    """Replace "press enter" / "insert new line" with \\n unless prose follows.

    Prose guard: if the next word is in _NEWLINE_PROSE_FOLLOWERS (e.g.
    "press enter to continue", "press enter the room") the phrase is left
    unchanged.  When converting, any captured following word is preserved so
    it is not swallowed (e.g. "first line press enter second" -> "first line\\nsecond").
    """
    follower = (match.group("after") or "").strip()
    if follower.lower() in _NEWLINE_PROSE_FOLLOWERS:
        return match.group(0)  # prose: leave untouched
    if follower:
        return f"\n{follower}"
    return "\n"


# Ordered, conservative spoken-symbol rules. Each is (compiled_pattern,
# replacement) where replacement is a string or a callable. Order matters —
# longer/structural cues are matched before single tokens. Every rule fires
# ONLY on an unambiguous cue so ordinary prose is never corrupted.
_DASH_DASH_RE = re.compile(
    r"(?:(?P<pre>\w+)(?P<presp>\s+))?\bdash dash (?P<word>\w+)\b",
    re.IGNORECASE,
)
_SYMBOL_RULES: List[Tuple[re.Pattern, Union[str, Callable]]] = [
    # Long flags: "dash dash help" -> "--help", guarded against prose by
    # inspecting the preceding word (see _expand_double_dash).
    (_DASH_DASH_RE, _expand_double_dash),
    # Short flags: "dash f" -> "-f" (single letter), only in a CLI context
    # (preceding word must be a known command/verb, see _expand_single_dash).
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
    # Requires BOTH backtick cues, so a lone "backtick" in prose is safe.
    # (The single-backtick rule was removed: it mangled "the backtick of doom"
    # and was fully redundant with this paired rule.)
    (re.compile(r"\bbacktick (\w+(?:\s+\w+){0,4}) backtick\b", re.IGNORECASE), r"`\1`"),
    # Parentheses — require a MATCHED pair of "open paren" / "close paren"
    # cues in the same utterance so standalone cues in prose are safe.
    (
        re.compile(r"\bopen paren\b(.*?)\bclose paren\b", re.IGNORECASE | re.DOTALL),
        r"(\1)",
    ),
    # Newline — ONLY on an explicit standalone trigger, never the bare
    # "new line" (which mangles "a new line of thinking"). "press enter" and
    # "insert new line" are dictation commands, but they are suppressed when
    # followed by a prose word like "to", "the", "a", etc.
    (
        re.compile(
            r"\b(?:press enter|insert new line)\b(?:\s+(?P<after>\w+))?",
            re.IGNORECASE,
        ),
        _expand_newline,
    ),
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
    Output formatter for the faithful formatting pipeline.

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
        Run the faithful formatting pipeline.

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
