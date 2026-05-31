"""Tests for the no-slop formatting subsystem."""
from app.core.formatting import expand_spoken_symbols


def test_dash_dash_flag():
    assert expand_spoken_symbols("run dash dash help now") == "run --help now"


def test_single_dash_flag():
    assert expand_spoken_symbols("apply dash f file") == "apply -f file"


def test_dot_extension_py():
    assert expand_spoken_symbols("open deployment dot yaml") == "open deployment.yaml"
    assert expand_spoken_symbols("edit main dot py") == "edit main.py"


def test_backtick_word():
    assert expand_spoken_symbols("wrap backtick code backtick here") == "wrap `code` here"


def test_open_close_paren():
    assert expand_spoken_symbols("call open paren x close paren") == "call (x)"


def test_bare_new_line_is_not_expanded():
    # The bare "new line" cue is DROPPED (it mangled "a new line of thinking").
    # Newlines now require an explicit standalone trigger.
    assert (
        expand_spoken_symbols("line one new line line two")
        == "line one new line line two"
    )


def test_explicit_newline_triggers():
    assert expand_spoken_symbols("first line press enter second line") == (
        "first line\nsecond line"
    )
    assert expand_spoken_symbols("para one insert new line para two") == (
        "para one\npara two"
    )


def test_does_not_corrupt_prose():
    # 'dash' as a normal word without a following token stays untouched
    text = "I went for a quick dash to the store"
    assert expand_spoken_symbols(text) == text


def test_idempotent_on_plain_prose():
    text = "the quick brown fox jumps over the lazy dog"
    assert expand_spoken_symbols(text) == text


# ---------------------------------------------------------------------------
# Task 7: Formatter verbatim mode (no LLM)
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock

from app.core.formatting import Formatter
from app.core.vocabulary import Vocabulary


def _vocab():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    return v


def test_verbatim_runs_no_llm():
    api = MagicMock()
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply dash f deploy",
        mode="verbatim",
        expand_symbols=True,
        translate_to=None,
    )
    assert out == "kubectl apply -f deploy"
    api.chat.assert_not_called()


def test_verbatim_can_skip_symbol_expansion():
    api = MagicMock()
    fmt = Formatter(api, Vocabulary(load_starter=False))
    out = fmt.format(
        "run dash dash help",
        mode="verbatim",
        expand_symbols=False,
        translate_to=None,
    )
    assert out == "run dash dash help"
    api.chat.assert_not_called()


# ---------------------------------------------------------------------------
# Task 8: Clean & polished mode LLM cleanup (mocked)
# ---------------------------------------------------------------------------

def test_clean_mode_calls_llm_with_protected_tokens():
    api = MagicMock()
    api.chat.return_value = "kubectl apply -f deployment.yaml then check the pod logs"
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply dash f deployment dot yaml then check the pod logs",
        mode="clean",
        expand_symbols=True,
        translate_to=None,
    )
    assert out == "kubectl apply -f deployment.yaml then check the pod logs"
    # LLM was called once.
    api.chat.assert_called_once()
    messages = api.chat.call_args.kwargs.get("messages") or api.chat.call_args.args[0]
    system = messages[0]["content"]
    user = messages[1]["content"]
    # System prompt must preserve the user's voice and forbid rephrasing,
    # and must NOT be a code-only / engineer-only prompt.
    sys_lower = system.lower()
    assert "do not rephrase" in sys_lower or "do not reword" in sys_lower
    assert "tone" in sys_lower and "slang" in sys_lower  # preserve voice
    assert "filler" in sys_lower  # remove fillers
    assert "software engineer" not in sys_lower  # not engineer-branded
    assert "kubectl" in system  # protected token from vocabulary still passed
    # The deterministic text (already corrected/expanded) is what we send.
    assert "kubectl apply -f deployment.yaml" in user
    # gpt-5-nano with minimal reasoning effort.
    assert api.chat.call_args.kwargs.get("model") == "gpt-5-nano"
    assert api.chat.call_args.kwargs.get("reasoning_effort") == "minimal"


def test_polished_mode_uses_grammar_prompt():
    api = MagicMock()
    api.chat.return_value = "I think we should deploy now."
    fmt = Formatter(api, Vocabulary(load_starter=False))
    out = fmt.format(
        "um i think we should like deploy now",
        mode="polished",
        expand_symbols=False,
        translate_to=None,
    )
    assert out == "I think we should deploy now."
    system = api.chat.call_args.kwargs.get("messages")[0]["content"]
    assert "grammar" in system.lower()


def test_polished_mode_preserves_code_and_identifiers():
    # Polished must carry the same code/identifier/CLI-flag/path preservation
    # constraint as clean, so it never paraphrases `kubectl apply -f`.
    api = MagicMock()
    api.chat.return_value = "ok"
    fmt = Formatter(api, _vocab())
    fmt.format("kubectl apply -f x", mode="polished",
               expand_symbols=False, translate_to=None)
    system = api.chat.call_args.kwargs.get("messages")[0]["content"].lower()
    assert "cli flag" in system
    assert "file path" in system
    assert "never paraphrase" in system or "paraphrase" in system
    assert "kubectl" in api.chat.call_args.kwargs.get("messages")[0]["content"]


def test_text_model_defaults_to_gpt_5_nano():
    api = MagicMock()
    api.chat.return_value = "x"
    fmt = Formatter(api, Vocabulary(load_starter=False))
    fmt.format("hello", mode="clean", expand_symbols=False, translate_to=None)
    assert api.chat.call_args.kwargs.get("model") == "gpt-5-nano"


def test_text_model_is_configurable():
    api = MagicMock()
    api.chat.return_value = "x"
    fmt = Formatter(api, Vocabulary(load_starter=False), text_model="gpt-5.4-nano")
    fmt.format("hello", mode="clean", expand_symbols=False, translate_to=None)
    assert api.chat.call_args.kwargs.get("model") == "gpt-5.4-nano"


def test_text_model_used_for_translation_too():
    api = MagicMock()
    api.chat.return_value = "hola"
    fmt = Formatter(api, Vocabulary(load_starter=False), text_model="gpt-5.4-nano")
    fmt.format("hello", mode="clean", expand_symbols=False, translate_to="es")
    assert api.chat.call_args.kwargs.get("model") == "gpt-5.4-nano"


def test_llm_failure_falls_back_to_deterministic_text():
    api = MagicMock()
    api.chat.return_value = None  # simulate API failure
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply",
        mode="clean",
        expand_symbols=True,
        translate_to=None,
    )
    assert out == "kubectl apply"  # deterministic result, no crash


def test_no_api_client_skips_llm_but_runs_deterministic():
    # With api_client=None (no API key), the LLM step is skipped but the
    # deterministic stages (symbol expansion + vocab correction) still run.
    fmt = Formatter(None, _vocab())
    out = fmt.format(
        "cube cuttle apply dash f deployment dot yaml",
        mode="clean",
        expand_symbols=True,
        translate_to=None,
    )
    assert out == "kubectl apply -f deployment.yaml"


def test_no_api_client_skips_translation():
    fmt = Formatter(None, _vocab())
    out = fmt.format(
        "cube cuttle apply",
        mode="clean",
        expand_symbols=True,
        translate_to="es",
    )
    # No API client -> translation skipped, deterministic result returned.
    assert out == "kubectl apply"


# ---------------------------------------------------------------------------
# Task 9: Translation step (mocked)
# ---------------------------------------------------------------------------

def test_translation_replaces_cleanup_and_keeps_code():
    api = MagicMock()
    api.chat.return_value = "ejecuta kubectl apply -f deployment.yaml"
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply dash f deployment dot yaml",
        mode="clean",
        expand_symbols=True,
        translate_to="es",
    )
    assert out == "ejecuta kubectl apply -f deployment.yaml"
    system = api.chat.call_args.kwargs.get("messages")[0]["content"]
    assert "Spanish" in system  # resolved from language code
    assert "untranslated" in system.lower() or "do not translate" in system.lower()


def test_translation_failure_falls_back_to_deterministic_text():
    api = MagicMock()
    api.chat.return_value = None
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply",
        mode="clean",
        expand_symbols=True,
        translate_to="es",
    )
    assert out == "kubectl apply"
