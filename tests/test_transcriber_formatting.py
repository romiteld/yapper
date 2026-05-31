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


def _make_transcriber_with_formatter(raw_transcription, vocab, output_mode="technical"):
    """Build a Transcriber with a real Formatter (LLM echoes deterministic text)."""
    api = MagicMock()
    # Technical-mode LLM echoes the already-clean deterministic text.
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


def test_transcribe_runs_noslop_pipeline(tmp_path):
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
