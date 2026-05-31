"""Phase 2: APIClient passes correct OpenAI 2.x models/params; retry preserved."""
from unittest.mock import mock_open, patch

import pytest

from core.api import APIClient


def _make_client():
    return APIClient(api_key="sk-test")


def test_transcribe_default_model_and_params(mock_openai, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    client = _make_client()

    out = client.transcribe(str(wav), language="en", prompt="kubectl Next.js")

    assert out == "hello world"
    call = mock_openai.audio.transcriptions.create.call_args
    assert call.kwargs["model"] == "gpt-4o-mini-transcribe"
    assert call.kwargs["response_format"] == "text"
    assert call.kwargs["language"] == "en"
    assert call.kwargs["prompt"] == "kubectl Next.js"


def test_transcribe_honors_explicit_model(mock_openai, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    client = _make_client()

    client.transcribe(str(wav), model="whisper-1")
    call = mock_openai.audio.transcriptions.create.call_args
    assert call.kwargs["model"] == "whisper-1"


def test_transcribe_omits_empty_prompt_and_language(mock_openai, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    client = _make_client()

    client.transcribe(str(wav))
    kwargs = mock_openai.audio.transcriptions.create.call_args.kwargs
    assert "language" not in kwargs
    assert "prompt" not in kwargs
