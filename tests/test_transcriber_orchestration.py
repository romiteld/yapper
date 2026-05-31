"""Phase 2/3: Transcriber orchestrates engine + the real faithful Formatter."""
from unittest.mock import MagicMock

from core.transcriber import Transcriber
from core.formatting import Formatter


def _engine_returning(text):
    eng = MagicMock()
    eng.transcribe.return_value = text
    return eng


def test_transcriber_calls_injected_engine(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning("hello world")
    t = Transcriber(engine=eng, language_hint="en", clean_wake_words=False)

    out = t.transcribe(str(wav), delete_audio=False)

    assert out == "hello world"
    eng.transcribe.assert_called_once()
    assert eng.transcribe.call_args.kwargs["language"] == "en"


def test_transcriber_passes_prompt_bias(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning("ok")
    t = Transcriber(engine=eng, clean_wake_words=False)
    t.transcribe(str(wav), delete_audio=False, prompt="kubectl Next.js")
    assert eng.transcribe.call_args.kwargs["prompt"] == "kubectl Next.js"


def test_transcriber_cleans_wake_words(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning("yapper start deploy the app")
    t = Transcriber(engine=eng, clean_wake_words=True)
    out = t.transcribe(str(wav), delete_audio=False)
    assert "yapper" not in out.lower()
    assert "deploy the app" in out


def test_transcriber_uses_formatter(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning("raw text")
    fmt = MagicMock()
    fmt.format.return_value = "FORMATTED"
    t = Transcriber(engine=eng, formatter=fmt, clean_wake_words=False)
    out = t.transcribe(str(wav), delete_audio=False)
    assert out == "FORMATTED"
    assert fmt.format.call_args.kwargs["mode"] == "clean"


def test_transcriber_defaults_to_real_formatter(tmp_path):
    # With no explicit formatter and no API key, prod must still use the real
    # Formatter (never a no-op passthrough): deterministic stages run, LLM is
    # cleanly skipped (api_client is None).
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning("apply dash f file")
    t = Transcriber(engine=eng, clean_wake_words=False)
    assert isinstance(t._formatter, Formatter)
    out = t.transcribe(str(wav), delete_audio=False)
    # Spoken-symbol expansion (deterministic) applied even with no API key.
    assert out == "apply -f file"


def test_transcriber_empty_engine_result_returns_none(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning(None)
    t = Transcriber(engine=eng)
    assert t.transcribe(str(wav), delete_audio=False) is None


def test_transcriber_stores_fix_grammar():
    eng = _engine_returning("ok")
    assert Transcriber(engine=eng, fix_grammar=False).fix_grammar is False
    assert Transcriber(engine=eng, fix_grammar=True).fix_grammar is True


def test_transcribe_for_wake_word_lowercases_and_strips(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning("  Yapper START  ")
    t = Transcriber(engine=eng, language_hint="en")

    out = t.transcribe_for_wake_word(str(wav))

    assert out == "yapper start"
    eng.transcribe.assert_called_once_with(str(wav), language="en")


def test_transcribe_for_wake_word_returns_none_on_empty(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng = _engine_returning(None)
    t = Transcriber(engine=eng)
    assert t.transcribe_for_wake_word(str(wav)) is None
