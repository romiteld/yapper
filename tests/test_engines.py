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


from core.engines.local import LocalEngine, LocalEngineUnavailable


def test_local_engine_is_engine():
    assert issubclass(LocalEngine, TranscriptionEngine)


def test_local_engine_uses_injected_backend(fake_local_backend):
    eng = LocalEngine(model="base")
    eng._backend = fake_local_backend  # bypass lazy load
    out = eng.transcribe("/tmp/x.wav", language="en", prompt="ignored")
    assert out == "local transcript"  # stripped from fixture's " local transcript "
    fake_local_backend.transcribe.assert_called_once()


def test_local_engine_lazy_loads_once(monkeypatch, fake_local_backend):
    eng = LocalEngine(model="base")
    calls = {"n": 0}

    def _fake_load():
        calls["n"] += 1
        return fake_local_backend

    monkeypatch.setattr(eng, "_load_backend", _fake_load)
    eng.transcribe("/tmp/x.wav")
    eng.transcribe("/tmp/y.wav")
    assert calls["n"] == 1  # backend cached after first call


def test_local_engine_missing_extra_raises(monkeypatch):
    eng = LocalEngine(model="base")

    def _boom():
        raise LocalEngineUnavailable("install the [local] extra")

    monkeypatch.setattr(eng, "_load_backend", _boom)
    with pytest.raises(LocalEngineUnavailable):
        eng.transcribe("/tmp/x.wav")


from core.engines import get_engine


def test_get_engine_cloud_default(settings_factory):
    s = settings_factory(api_key="sk-x", engine="cloud")
    eng = get_engine(s)
    assert isinstance(eng, CloudEngine)
    assert eng._model == "gpt-4o-mini-transcribe"


def test_get_engine_cloud_honors_model(settings_factory):
    s = settings_factory(api_key="sk-x", engine="cloud", cloud_stt_model="whisper-1")
    eng = get_engine(s)
    assert isinstance(eng, CloudEngine)
    assert eng._model == "whisper-1"


def test_get_engine_local(settings_factory):
    s = settings_factory(engine="local", local_stt_model="small")
    eng = get_engine(s)
    assert isinstance(eng, LocalEngine)
    assert eng._model == "small"


def test_get_engine_exported_from_core():
    import core
    assert hasattr(core, "get_engine")
    assert hasattr(core, "TranscriptionEngine")
