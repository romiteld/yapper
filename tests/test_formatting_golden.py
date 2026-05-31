"""Golden faithful cases for the full formatting pipeline (LLM mocked identity)."""
from unittest.mock import MagicMock

import pytest

from app.core.formatting import Formatter, expand_spoken_symbols
from app.core.vocabulary import Vocabulary


def _identity_api():
    api = MagicMock()
    # Clean-mode LLM only fixes caps/punctuation; here the deterministic
    # output is already clean, so the LLM echoes it back unchanged.
    api.chat.side_effect = lambda messages, **kw: messages[1]["content"]
    return api


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "cube cuttle apply dash f deployment dot yaml then check the pod logs",
            "kubectl apply -f deployment.yaml then check the pod logs",
        ),
        (
            # "dash namespaces" stays as-is: the single-letter-only dash rule
            # won't fire on multi-char words. This is the correct conservative
            # behavior — update deliberately if a future rule handles it.
            "run cube cuttle get pods dash dash all dash namespaces",
            "run kubectl get pods --all dash namespaces",
        ),
        (
            "open main dot py and import FastAPI",
            "open main.py and import FastAPI",
        ),
    ],
)
def test_golden_clean_pipeline_technical(raw, expected):
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    fmt = Formatter(_identity_api(), v)
    out = fmt.format(
        raw, mode="clean", expand_symbols=True, translate_to=None
    )
    assert out == expected


@pytest.mark.parametrize(
    "raw",
    [
        # Everyday/social messaging must NOT be mangled by the deterministic
        # stages. The Clean-mode LLM would later strip "um"/filler "like", but
        # the deterministic pipeline must leave casual prose untouched.
        "um so like i'll be there in ten",
        "hey wanna grab lunch later today",
        "lol that movie was so good you have to see it",
        "ok cool i'll send you the link in a sec",
    ],
)
def test_golden_casual_text_not_mangled_by_deterministic_stages(raw):
    # With the starter pack loaded (real-world config), casual prose passes
    # through expand_spoken_symbols + Vocabulary.correct unchanged.
    v = Vocabulary()  # loads dev starter pack (kubectl, nginx, etc.)
    assert expand_spoken_symbols(raw) == raw
    assert v.correct(raw) == raw


def test_golden_casual_text_clean_mode_identity_llm():
    # Full pipeline with an identity LLM (echoes input): casual text survives
    # the deterministic stages and is handed to the LLM unchanged.
    raw = "um so like i'll be there in ten"
    v = Vocabulary()  # starter pack
    fmt = Formatter(_identity_api(), v)
    out = fmt.format(raw, mode="clean", expand_symbols=True, translate_to=None)
    assert out == raw
