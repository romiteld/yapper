"""
Yapper Audio Recording
======================
Cross-platform audio recording using PyAudio.

Copyright (c) 2026 Cloudelipute
"""

import tempfile
import threading
import wave
from pathlib import Path
from typing import List, Optional

from .logger import get_logger

logger = get_logger("audio")

# Audio constants
SAMPLE_RATE = 16000  # 16kHz - optimal for Whisper
CHANNELS = 1         # Mono audio
CHUNK_SIZE = 1024    # Buffer size
FORMAT_WIDTH = 2     # 16-bit audio (2 bytes per sample)


class AudioRecorder:
    """
    Cross-platform audio recorder using PyAudio.

    Example:
        recorder = AudioRecorder()
        if recorder.start():
            # ... recording ...
            audio_path = recorder.stop()
            if audio_path:
                # Process audio file
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_size: int = CHUNK_SIZE,
        device_index: Optional[int] = None
    ):
        """
        Initialize the audio recorder.

        Args:
            sample_rate: Audio sample rate in Hz.
            channels: Number of audio channels.
            chunk_size: Buffer size for recording.
            device_index: Specific input device index (None = system default).
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device_index = device_index

        self._frames: List[bytes] = []
        self._is_recording = False
        self._stream = None
        self._audio = None
        self._record_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    @property
    def frames(self) -> List[bytes]:
        """Get recorded audio frames."""
        return self._frames.copy()

    @property
    def duration_seconds(self) -> float:
        """Get duration of recorded audio in seconds."""
        if not self._frames:
            return 0.0
        total_bytes = sum(len(f) for f in self._frames)
        return total_bytes / (self.sample_rate * self.channels * FORMAT_WIDTH)

    def start(self) -> bool:
        """
        Start recording audio from the microphone.

        Returns:
            True if recording started successfully, False otherwise.
        """
        if self._is_recording:
            logger.warning("Already recording")
            return True

        try:
            import pyaudio
            self._audio = pyaudio.PyAudio()
            self._frames = []
            self._is_recording = True

            # Build stream parameters
            stream_kwargs = {
                "format": pyaudio.paInt16,
                "channels": self.channels,
                "rate": self.sample_rate,
                "input": True,
                "frames_per_buffer": self.chunk_size,
            }

            # Add device index if specified
            if self.device_index is not None:
                stream_kwargs["input_device_index"] = self.device_index
                logger.debug(f"Using audio device index: {self.device_index}")

            self._stream = self._audio.open(**stream_kwargs)

            # Start recording thread
            self._record_thread = threading.Thread(
                target=self._record_loop,
                daemon=True,
                name="AudioRecorder"
            )
            self._record_thread.start()

            logger.info("Recording started")
            return True

        except ImportError:
            logger.error("PyAudio not installed. Install with: pip install pyaudio")
            self._is_recording = False
            return False

        except OSError as e:
            logger.error(f"Audio device error: {e}")
            self._cleanup_audio()
            return False

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self._cleanup_audio()
            return False

    def _record_loop(self) -> None:
        """Internal recording loop running in separate thread."""
        try:
            import pyaudio
        except ImportError:
            return

        while self._is_recording:
            try:
                if self._stream is None:
                    break
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                with self._lock:
                    self._frames.append(data)
            except OSError as e:
                logger.error(f"Recording error: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected recording error: {e}")
                break

    def stop(self) -> Optional[str]:
        """
        Stop recording and save to temporary WAV file.

        Returns:
            Path to the temporary WAV file, or None if no audio was recorded.
        """
        if not self._is_recording:
            logger.warning("Not currently recording")
            return None

        self._is_recording = False

        # Wait for recording thread to finish
        if self._record_thread is not None:
            self._record_thread.join(timeout=2.0)
            self._record_thread = None

        # Stop and close stream
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except OSError as e:
                logger.warning(f"Error closing stream: {e}")
            self._stream = None

        # Terminate PyAudio
        if self._audio is not None:
            try:
                self._audio.terminate()
            except OSError as e:
                logger.warning(f"Error terminating PyAudio: {e}")
            self._audio = None

        # Check if we have recorded frames
        with self._lock:
            if not self._frames:
                logger.warning("No audio frames recorded")
                return None
            frames_copy = self._frames.copy()

        # Save to temporary file
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                prefix="yapper_"
            )
            temp_path = temp_file.name
            temp_file.close()

            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(FORMAT_WIDTH)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(frames_copy))

            duration = self.duration_seconds
            logger.info(f"Recording stopped. Duration: {duration:.1f}s, File: {temp_path}")
            return temp_path

        except (IOError, OSError) as e:
            logger.error(f"Failed to save audio file: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up audio resources."""
        self._is_recording = False
        self._cleanup_audio()

    def _cleanup_audio(self) -> None:
        """Internal cleanup helper."""
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._audio is not None:
            try:
                self._audio.terminate()
            except Exception:
                pass
            self._audio = None

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()
