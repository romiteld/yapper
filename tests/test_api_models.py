"""Phase 2: APIClient passes correct ElevenLabs Scribe models/params; retry preserved."""
from unittest.mock import MagicMock
from core.api import APIClient, APIRateLimitError


def _make_client():
    return APIClient(api_key="sk_test")


def test_transcribe_default_model_and_params(mock_elevenlabs, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    client = _make_client()

    out = client.transcribe(str(wav), language="en", prompt="kubectl Next.js")

    assert out == "hello world"
    call = mock_elevenlabs.post.call_args
    assert call.args[0] == "/speech-to-text"
    data = call.kwargs["data"]
    assert data["model_id"] == "scribe_v2"
    assert data["tag_audio_events"] == "false"
    assert data["language_code"] == "en"
    assert data["keyterms"] == ["kubectl", "Next.js"]


def test_transcribe_honors_explicit_model(mock_elevenlabs, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    client = _make_client()

    client.transcribe(str(wav), model="scribe_v1")
    call = mock_elevenlabs.post.call_args
    assert call.kwargs["data"]["model_id"] == "scribe_v1"


def test_transcribe_omits_empty_prompt_and_language(mock_elevenlabs, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    client = _make_client()

    client.transcribe(str(wav))
    data = mock_elevenlabs.post.call_args.kwargs["data"]
    assert "language_code" not in data
    assert "keyterms" not in data


def test_chat_uses_gpt5nano_and_reasoning_effort(mock_elevenlabs):
    client = _make_client()
    client._client = mock_elevenlabs
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "cleaned text"
    kwargs = mock_elevenlabs.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-5-nano"
    assert kwargs["reasoning_effort"] == "minimal"
    # Reasoning models: legacy sampling args must NOT be sent.
    assert "temperature" not in kwargs
    assert "max_tokens" not in kwargs


def test_fix_grammar_default_model(mock_elevenlabs):
    client = _make_client()
    client._client = mock_elevenlabs
    client.fix_grammar("teh cat")
    assert mock_elevenlabs.chat.completions.create.call_args.kwargs["model"] == "gpt-5-nano"


def test_translate_default_model(mock_elevenlabs):
    client = _make_client()
    client._client = mock_elevenlabs
    client.translate("hello", target_language="es")
    assert mock_elevenlabs.chat.completions.create.call_args.kwargs["model"] == "gpt-5-nano"


def test_no_deprecated_model_referenced():
    import inspect
    import core.api as api_mod
    src = inspect.getsource(api_mod)
    assert "gpt-4.1-nano" not in src


class _RateLimitError(Exception):
    """Stand-in named to match _is_retryable_error allow-list."""
    def __init__(self):
        super().__init__("rate limited")
_RateLimitError.__name__ = "RateLimitError"


def test_transcribe_retries_then_succeeds(mock_elevenlabs, tmp_path, monkeypatch):
    monkeypatch.setattr("core.api.time.sleep", lambda *_: None)  # no real waiting
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    second_resp = MagicMock()
    second_resp.status_code = 200
    second_resp.json.return_value = {"text": "second try"}
    mock_elevenlabs.post.side_effect = [
        APIRateLimitError("rate limited"),
        second_resp,
    ]
    client = APIClient(api_key="sk_test")
    out = client.transcribe(str(wav))
    assert out == "second try"
    assert mock_elevenlabs.post.call_count == 2


def test_chat_gives_up_after_max_retries(mock_elevenlabs, monkeypatch):
    monkeypatch.setattr("core.api.time.sleep", lambda *_: None)
    mock_elevenlabs.chat.completions.create.side_effect = _RateLimitError()
    client = APIClient(api_key="sk_test")
    client._client = mock_elevenlabs
    out = client.chat([{"role": "user", "content": "x"}])
    assert out is None
    assert mock_elevenlabs.chat.completions.create.call_count == 3  # MAX_RETRIES
