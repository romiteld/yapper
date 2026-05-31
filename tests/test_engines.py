"""Phase 2: engine abstraction (ABC, cloud, local, selection)."""
import inspect
from abc import ABC

import pytest

from core.engines.base import TranscriptionEngine


def test_base_is_abstract():
    assert issubclass(TranscriptionEngine, ABC)
    with pytest.raises(TypeError):
        TranscriptionEngine()  # cannot instantiate abstract class


def test_transcribe_signature():
    sig = inspect.signature(TranscriptionEngine.transcribe)
    params = list(sig.parameters)
    assert params == ["self", "wav_path", "language", "prompt"]
    assert sig.parameters["language"].default is None
    assert sig.parameters["prompt"].default is None
