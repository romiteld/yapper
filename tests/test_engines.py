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


from unittest.mock import MagicMock

from core.engines.cloud import CloudEngine


def test_cloud_engine_is_engine():
    assert issubclass(CloudEngine, TranscriptionEngine)


def test_cloud_engine_delegates_to_api_client():
    api = MagicMock()
    api.transcribe.return_value = "hi there"
    eng = CloudEngine(api_client=api, model="gpt-4o-mini-transcribe")

    out = eng.transcribe("/tmp/x.wav", language="en", prompt="kubectl")

    assert out == "hi there"
    api.transcribe.assert_called_once_with(
        "/tmp/x.wav",
        language="en",
        model="gpt-4o-mini-transcribe",
        prompt="kubectl",
    )


def test_cloud_engine_default_model():
    api = MagicMock()
    api.transcribe.return_value = "ok"
    eng = CloudEngine(api_client=api)
    eng.transcribe("/tmp/x.wav")
    assert api.transcribe.call_args.kwargs["model"] == "gpt-4o-mini-transcribe"
