"""Golden no-slop cases for the full formatting pipeline (LLM mocked identity)."""
from unittest.mock import MagicMock

import pytest

from app.core.formatting import Formatter
from app.core.vocabulary import Vocabulary


def _identity_api():
    api = MagicMock()
    # Technical-mode LLM only fixes caps/punctuation; here the deterministic
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
def test_golden_technical_pipeline(raw, expected):
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    fmt = Formatter(_identity_api(), v)
    out = fmt.format(
        raw, mode="technical", expand_symbols=True, translate_to=None
    )
    assert out == expected
