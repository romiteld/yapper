"""Tests for AudioRecorder on sounddevice (hardware mocked)."""
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.audio import AudioRecorder, SAMPLE_RATE, CHANNELS


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
