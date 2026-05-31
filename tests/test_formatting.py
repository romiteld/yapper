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


def test_new_line():
    assert expand_spoken_symbols("line one new line line two") == "line one\nline two"


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
# Task 8: Technical & natural mode LLM cleanup (mocked)
# ---------------------------------------------------------------------------

def test_technical_mode_calls_llm_with_protected_tokens():
    api = MagicMock()
    api.chat.return_value = "kubectl apply -f deployment.yaml then check the pod logs"
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply dash f deployment dot yaml then check the pod logs",
        mode="technical",
        expand_symbols=True,
        translate_to=None,
    )
    assert out == "kubectl apply -f deployment.yaml then check the pod logs"
    # LLM was called once.
    api.chat.assert_called_once()
    messages = api.chat.call_args.kwargs.get("messages") or api.chat.call_args.args[0]
    system = messages[0]["content"]
    user = messages[1]["content"]
    # System prompt must forbid paraphrasing and list protected tokens.
    assert "never paraphrase" in system.lower()
    assert "kubectl" in system  # protected token from vocabulary
    # The deterministic text (already corrected/expanded) is what we send.
    assert "kubectl apply -f deployment.yaml" in user
    # gpt-5-nano with minimal reasoning effort.
    assert api.chat.call_args.kwargs.get("model") == "gpt-5-nano"
    assert api.chat.call_args.kwargs.get("reasoning_effort") == "minimal"


def test_natural_mode_uses_grammar_prompt():
    api = MagicMock()
    api.chat.return_value = "I think we should deploy now."
    fmt = Formatter(api, Vocabulary(load_starter=False))
    out = fmt.format(
        "um i think we should like deploy now",
        mode="natural",
        expand_symbols=False,
        translate_to=None,
    )
    assert out == "I think we should deploy now."
    system = api.chat.call_args.kwargs.get("messages")[0]["content"]
    assert "grammar" in system.lower()


def test_llm_failure_falls_back_to_deterministic_text():
    api = MagicMock()
    api.chat.return_value = None  # simulate API failure
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply",
        mode="technical",
        expand_symbols=True,
        translate_to=None,
    )
    assert out == "kubectl apply"  # deterministic result, no crash


# ---------------------------------------------------------------------------
# Task 9: Translation step (mocked)
# ---------------------------------------------------------------------------

def test_translation_replaces_cleanup_and_keeps_code():
    api = MagicMock()
    api.chat.return_value = "ejecuta kubectl apply -f deployment.yaml"
    fmt = Formatter(api, _vocab())
    out = fmt.format(
        "cube cuttle apply dash f deployment dot yaml",
        mode="technical",
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
        mode="technical",
        expand_symbols=True,
        translate_to="es",
    )
    assert out == "kubectl apply"
