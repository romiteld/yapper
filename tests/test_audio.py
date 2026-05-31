"""Tests for AudioRecorder on sounddevice (hardware mocked)."""
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.audio import AudioRecorder, SAMPLE_RATE, CHANNELS, chunk_rms_level


class FakeStream:
    """Mimics sounddevice.InputStream as a context-managed callback source."""
    def __init__(self, *args, callback=None, **kwargs):
        self.callback = callback
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    def feed(self, n_frames):
        """Simulate the audio thread delivering int16 frames."""
        block = (np.ones((n_frames, CHANNELS), dtype="int16") * 1000)
        self.callback(block, n_frames, None, None)


def test_initial_state():
    r = AudioRecorder()
    assert r.is_recording is False
    assert r.frames == []
    assert r.duration_seconds == 0.0


def test_start_opens_stream_and_records():
    r = AudioRecorder()
    fake_sd = MagicMock()
    holder = {}

    def make_stream(**kwargs):
        holder["stream"] = FakeStream(**kwargs)
        return holder["stream"]

    fake_sd.InputStream.side_effect = make_stream
    with patch.object(r, "_load_sounddevice", return_value=fake_sd):
        assert r.start() is True
        assert r.is_recording is True
        holder["stream"].feed(16000)  # 1 second of audio
        assert len(r.frames) == 1


def test_stop_writes_wav_with_correct_format(tmp_path):
    r = AudioRecorder()
    fake_sd = MagicMock()
    holder = {}
    fake_sd.InputStream.side_effect = (
        lambda **k: holder.setdefault("s", FakeStream(**k)))
    with patch.object(r, "_load_sounddevice", return_value=fake_sd):
        r.start()
        holder["s"].feed(8000)  # 0.5 s
        path = r.stop()

    assert path is not None
    with wave.open(path, "rb") as wf:
        assert wf.getnchannels() == CHANNELS
        assert wf.getframerate() == SAMPLE_RATE
        assert wf.getsampwidth() == 2
        assert wf.getnframes() == 8000
    assert r.is_recording is False


def test_stop_returns_none_with_no_frames():
    r = AudioRecorder()
    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = lambda **k: FakeStream(**k)
    with patch.object(r, "_load_sounddevice", return_value=fake_sd):
        r.start()
        assert r.stop() is None


def test_start_returns_false_without_sounddevice():
    r = AudioRecorder()
    with patch.object(r, "_load_sounddevice", return_value=None):
        assert r.start() is False
        assert r.is_recording is False


def test_duration_seconds_tracks_frames():
    r = AudioRecorder()
    fake_sd = MagicMock()
    holder = {}
    fake_sd.InputStream.side_effect = (
        lambda **k: holder.setdefault("s", FakeStream(**k)))
    with patch.object(r, "_load_sounddevice", return_value=fake_sd):
        r.start()
        holder["s"].feed(SAMPLE_RATE)  # exactly 1 s
    assert abs(r.duration_seconds - 1.0) < 0.01


# ---- RMS level (HIGH-1: HUD ring) -----------------------------------------

def test_chunk_rms_level_silence_is_zero():
    block = np.zeros((1024, CHANNELS), dtype="int16")
    assert chunk_rms_level(block) == 0.0


def test_chunk_rms_level_loud_is_high():
    block = np.full((1024, CHANNELS), 32000, dtype="int16")
    level = chunk_rms_level(block)
    assert 0.9 < level <= 1.0


def test_chunk_rms_level_accepts_bytes():
    block = (np.ones((512, CHANNELS), dtype="int16") * 16000)
    level = chunk_rms_level(block.tobytes())
    assert 0.4 < level < 0.6


def test_chunk_rms_level_empty_is_zero():
    assert chunk_rms_level(np.zeros((0,), dtype="int16")) == 0.0
    assert chunk_rms_level(None) == 0.0


def test_recorder_invokes_on_level_per_chunk():
    levels = []
    r = AudioRecorder(on_level=levels.append)
    fake_sd = MagicMock()
    holder = {}
    fake_sd.InputStream.side_effect = (
        lambda **k: holder.setdefault("s", FakeStream(**k)))
    with patch.object(r, "_load_sounddevice", return_value=fake_sd):
        r.start()
        holder["s"].feed(1024)
        holder["s"].feed(1024)
    assert len(levels) == 2
    assert all(0.0 <= v <= 1.0 for v in levels)
    # Non-silent input (value 1000) yields a positive level.
    assert levels[0] > 0.0


def test_recorder_on_level_callback_error_does_not_crash_audio_thread():
    def boom(_):
        raise RuntimeError("ui exploded")

    r = AudioRecorder(on_level=boom)
    fake_sd = MagicMock()
    holder = {}
    fake_sd.InputStream.side_effect = (
        lambda **k: holder.setdefault("s", FakeStream(**k)))
    with patch.object(r, "_load_sounddevice", return_value=fake_sd):
        r.start()
        holder["s"].feed(1024)  # raising callback must be swallowed
        assert len(r.frames) == 1
