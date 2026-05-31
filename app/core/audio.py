"""
Yapper Audio Recording
======================
16 kHz mono int16 capture on sounddevice (bundles portaudio in its wheels,
so no native build step and a real macOS wheel exists).

Public API is unchanged: start() -> bool, stop() -> str|None,
.is_recording, .frames (list[bytes]), .duration_seconds.

© 2026 Cloudelipute
"""

import tempfile
import threading
import wave
from typing import List, Optional

from .logger import get_logger

logger = get_logger("audio")

SAMPLE_RATE = 16000  # 16kHz - optimal for Whisper
CHANNELS = 1         # Mono
CHUNK_SIZE = 1024    # sounddevice blocksize
FORMAT_WIDTH = 2     # int16 = 2 bytes/sample


class AudioRecorder:
    """Records microphone audio to a temporary WAV file via sounddevice."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_size: int = CHUNK_SIZE,
        device_index: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device_index = device_index

        self._frames: List[bytes] = []
        self._is_recording = False
        self._stream = None
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def frames(self) -> List[bytes]:
        with self._lock:
            return self._frames.copy()

    @property
    def duration_seconds(self) -> float:
        with self._lock:
            total = sum(len(f) for f in self._frames)
        return total / (self.sample_rate * self.channels * FORMAT_WIDTH)

    def _load_sounddevice(self):
        """Lazy import so the module imports on headless CI without portaudio."""
        try:
            import sounddevice
            return sounddevice
        except Exception as e:
            logger.error("sounddevice not available: %s", e)
            return None

    def _callback(self, indata, frames, time_info, status) -> None:
        """sounddevice audio-thread callback; indata is an int16 ndarray."""
        if status:
            logger.debug("sounddevice status: %s", status)
        with self._lock:
            self._frames.append(bytes(indata))

    def start(self) -> bool:
        if self._is_recording:
            logger.warning("Already recording")
            return True

        sd = self._load_sounddevice()
        if sd is None:
            return False

        with self._lock:
            self._frames = []

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.chunk_size,
                device=self.device_index,
                callback=self._callback,
            )
            self._stream.start()
            self._is_recording = True
            logger.info("Recording started")
            return True
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            self._close_stream()
            self._is_recording = False
            return False

    def stop(self) -> Optional[str]:
        if not self._is_recording:
            logger.warning("Not currently recording")
            return None

        self._is_recording = False
        self._close_stream()

        with self._lock:
            if not self._frames:
                logger.warning("No audio frames recorded")
                return None
            frames_copy = self._frames.copy()

        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="yapper_")
            temp_path = tmp.name
            tmp.close()
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(FORMAT_WIDTH)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(frames_copy))
            logger.info("Recording stopped. Duration: %.1fs, File: %s",
                        self.duration_seconds, temp_path)
            return temp_path
        except (IOError, OSError) as e:
            logger.error("Failed to save audio file: %s", e)
            return None

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning("Error closing stream: %s", e)
            self._stream = None

    def cleanup(self) -> None:
        self._is_recording = False
        self._close_stream()

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
