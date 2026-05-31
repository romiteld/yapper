"""Integration: Transcriber wires Vocabulary + Formatter (API mocked)."""
from unittest.mock import MagicMock, patch

from app.core.transcriber import Transcriber
from app.core.vocabulary import Vocabulary
from app.core.formatting import Formatter


def _make_engine(raw_transcription):
    """Create a mock TranscriptionEngine that returns a fixed transcription."""
    eng = MagicMock()
    eng.transcribe.return_value = raw_transcription
    return eng


def _make_transcriber_with_formatter(raw_transcription, vocab, output_mode="clean"):
    """Build a Transcriber with a real Formatter (LLM echoes deterministic text)."""
    api = MagicMock()
    # Clean-mode LLM echoes the already-clean deterministic text.
    api.chat.side_effect = lambda messages, **kw: messages[1]["content"]
    formatter = Formatter(api, vocab)
    eng = _make_engine(raw_transcription)
    t = Transcriber(
        engine=eng,
        output_mode=output_mode,
        expand_spoken_symbols=True,
        formatter=formatter,
        vocabulary=vocab,
        clean_wake_words=False,
    )
    return t, eng, api


def test_transcribe_runs_faithful_pipeline(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    vocab = Vocabulary(load_starter=False)
    vocab.add("kubectl", said="cube cuttle")
    t, eng, api = _make_transcriber_with_formatter(
        "cube cuttle apply dash f deployment dot yaml",
        vocab,
    )
    out = t.transcribe(str(wav), delete_audio=False)
    assert out == "kubectl apply -f deployment.yaml"


def test_transcribe_passes_vocab_prompt_bias_to_engine(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    vocab = Vocabulary(load_starter=False)
    vocab.add("kubectl", said="cube cuttle")
    t, eng, api = _make_transcriber_with_formatter("cube cuttle apply", vocab)
    t.transcribe(str(wav), delete_audio=False)
    # Vocab whisper_prompt is built and passed by Transcriber.
    # The engine.transcribe call should include the vocab prompt.
    call_kwargs = eng.transcribe.call_args
    # Prompt may be passed as positional or keyword; check both.
    prompt_arg = (
        call_kwargs.kwargs.get("prompt")
        if call_kwargs.kwargs
        else None
    )
    assert prompt_arg is not None and "kubectl" in prompt_arg


def test_verbatim_mode_skips_llm(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    vocab = Vocabulary(load_starter=False)
    vocab.add("kubectl", said="cube cuttle")
    api = MagicMock()
    formatter = Formatter(api, vocab)
    eng = _make_engine("cube cuttle apply")
    t = Transcriber(
        engine=eng,
        output_mode="verbatim",
        expand_spoken_symbols=True,
        formatter=formatter,
        vocabulary=vocab,
        clean_wake_words=False,
    )
    out = t.transcribe(str(wav), delete_audio=False)
    assert out == "kubectl apply"
    api.chat.assert_not_called()


def test_default_construction_uses_real_formatter_end_to_end(tmp_path):
    """A Transcriber built the NORMAL way (api_key, no explicit formatter)
    must use a real Formatter and actually apply output_mode + vocabulary.

    The internally-built text APIClient is patched so its chat() echoes the
    user content (clean-mode identity), proving the golden faithful case works
    end-to-end through Transcriber.transcribe()."""
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")

    vocab = Vocabulary(load_starter=False)
    vocab.add("kubectl", said="cube cuttle")
    eng = _make_engine("cube cuttle apply dash f deployment dot yaml")

    # Patch the APIClient used for the text/LLM path so no real call happens.
    with patch("app.core.transcriber.APIClient") as MockAPI:
        text_api = MockAPI.return_value
        text_api.chat.side_effect = lambda messages, **kw: messages[1]["content"]

        # NORMAL construction: api_key + vocabulary, NO explicit formatter.
        t = Transcriber(
            engine=eng,
            api_key="sk-test",
            vocabulary=vocab,
            output_mode="clean",
            expand_spoken_symbols=True,
            clean_wake_words=False,
        )
        # It must be a real Formatter, never the old passthrough.
        assert isinstance(t._formatter, Formatter)

        out = t.transcribe(str(wav), delete_audio=False)
        # Golden faithful case applied end-to-end.
        assert out == "kubectl apply -f deployment.yaml"
        # The LLM clean step actually ran (identity echo).
        text_api.chat.assert_called_once()


def test_default_construction_no_api_key_still_formats(tmp_path):
    """No API key -> real Formatter with api_client=None: deterministic stages
    (symbol expansion + vocab correction) still run, LLM step skipped."""
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")

    vocab = Vocabulary(load_starter=False)
    vocab.add("kubectl", said="cube cuttle")
    eng = _make_engine("cube cuttle apply dash f deployment dot yaml")

    # No api_key and no formatter -> Formatter(None, vocab).
    t = Transcriber(
        engine=eng,
        vocabulary=vocab,
        output_mode="clean",
        expand_spoken_symbols=True,
        clean_wake_words=False,
    )
    assert isinstance(t._formatter, Formatter)
    out = t.transcribe(str(wav), delete_audio=False)
    assert out == "kubectl apply -f deployment.yaml"


def test_transcriber_passes_text_model_to_formatter(tmp_path):
    """The configured text_model flows Transcriber -> Formatter -> chat()."""
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFfake")
    vocab = Vocabulary(load_starter=False)
    eng = _make_engine("hello world")

    with patch("app.core.transcriber.APIClient") as MockAPI:
        text_api = MockAPI.return_value
        text_api.chat.side_effect = lambda messages, **kw: messages[1]["content"]
        t = Transcriber(
            engine=eng,
            api_key="sk-test",
            vocabulary=vocab,
            output_mode="clean",
            text_model="gpt-5.4-nano",
            clean_wake_words=False,
        )
        t.transcribe(str(wav), delete_audio=False)
        assert text_api.chat.call_args.kwargs.get("model") == "gpt-5.4-nano"
