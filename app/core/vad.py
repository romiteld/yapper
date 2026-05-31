"""
Yapper Voice Activity Detection
===============================
Energy-based voice activity detection to reduce unnecessary API calls.

© 2026 Cloudelipute
"""

import math
import struct
from typing import List, Optional, Tuple

from .logger import get_logger

logger = get_logger("vad")


class VoiceActivityDetector:
    """
    Energy-based voice activity detector.

    Analyzes audio frames to determine if speech is present,
    helping to avoid unnecessary API calls for silent recordings.

    Example:
        vad = VoiceActivityDetector(threshold_db=-35)
        if vad.has_speech(audio_frames):
            # Process the audio
            transcribe(audio_frames)
        else:
            # Skip - no speech detected
            pass
    """

    # Default settings
    DEFAULT_THRESHOLD_DB = -35  # dB threshold for speech detection
    DEFAULT_MIN_SPEECH_FRAMES = 3  # Minimum frames above threshold to count as speech
    DEFAULT_SAMPLE_RATE = 16000
    DEFAULT_SAMPLE_WIDTH = 2  # 16-bit audio

    def __init__(
        self,
        threshold_db: float = DEFAULT_THRESHOLD_DB,
        min_speech_frames: int = DEFAULT_MIN_SPEECH_FRAMES,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        sample_width: int = DEFAULT_SAMPLE_WIDTH
    ):
        """
        Initialize the voice activity detector.

        Args:
            threshold_db: Energy threshold in dB. Audio above this is considered speech.
                         Typical values: -50 (very sensitive) to -20 (less sensitive).
            min_speech_frames: Minimum number of frames that must exceed threshold.
            sample_rate: Audio sample rate in Hz.
            sample_width: Bytes per sample (2 for 16-bit audio).
        """
        self.threshold_db = threshold_db
        self.min_speech_frames = min_speech_frames
        self.sample_rate = sample_rate
        self.sample_width = sample_width

        # Calculate reference value for dB calculation (16-bit audio max)
        self._reference = 32768.0 if sample_width == 2 else 128.0

        logger.debug(
            f"VAD initialized: threshold={threshold_db}dB, "
            f"min_frames={min_speech_frames}"
        )

    def calculate_energy_db(self, audio_data: bytes) -> float:
        """
        Calculate the energy level of audio data in decibels.

        Args:
            audio_data: Raw audio bytes (16-bit PCM).

        Returns:
            Energy level in dB (typically -60 to 0).
        """
        if not audio_data:
            return -100.0

        try:
            # Unpack audio samples
            if self.sample_width == 2:
                # 16-bit audio
                num_samples = len(audio_data) // 2
                if num_samples == 0:
                    return -100.0
                samples = struct.unpack(f"<{num_samples}h", audio_data[:num_samples * 2])
            else:
                # 8-bit audio
                samples = list(audio_data)

            # Calculate RMS (Root Mean Square) energy
            sum_squares = sum(s * s for s in samples)
            rms = math.sqrt(sum_squares / len(samples))

            # Convert to decibels
            if rms > 0:
                db = 20 * math.log10(rms / self._reference)
            else:
                db = -100.0

            return db

        except (struct.error, ZeroDivisionError, ValueError) as e:
            logger.warning(f"Error calculating energy: {e}")
            return -100.0

    def is_speech_frame(self, audio_data: bytes) -> bool:
        """
        Check if a single frame contains speech.

        Args:
            audio_data: Raw audio bytes for one frame.

        Returns:
            True if energy is above threshold.
        """
        energy_db = self.calculate_energy_db(audio_data)
        return energy_db > self.threshold_db

    def has_speech(self, audio_frames: List[bytes]) -> bool:
        """
        Check if audio frames contain speech.

        Args:
            audio_frames: List of audio frame bytes.

        Returns:
            True if speech is detected in enough frames.
        """
        if not audio_frames:
            logger.debug("No audio frames to analyze")
            return False

        speech_frame_count = 0
        total_frames = len(audio_frames)
        max_energy = -100.0

        for frame in audio_frames:
            energy_db = self.calculate_energy_db(frame)
            max_energy = max(max_energy, energy_db)

            if energy_db > self.threshold_db:
                speech_frame_count += 1

                # Early exit if we've found enough speech frames
                if speech_frame_count >= self.min_speech_frames:
                    logger.debug(
                        f"Speech detected: {speech_frame_count}/{total_frames} frames "
                        f"above {self.threshold_db}dB (max: {max_energy:.1f}dB)"
                    )
                    return True

        logger.debug(
            f"No speech detected: {speech_frame_count}/{total_frames} frames "
            f"above {self.threshold_db}dB (max: {max_energy:.1f}dB)"
        )
        return False

    def analyze_frames(self, audio_frames: List[bytes]) -> Tuple[bool, dict]:
        """
        Analyze audio frames and return detailed results.

        Args:
            audio_frames: List of audio frame bytes.

        Returns:
            Tuple of (has_speech, analysis_dict).
        """
        if not audio_frames:
            return False, {
                "has_speech": False,
                "total_frames": 0,
                "speech_frames": 0,
                "speech_ratio": 0.0,
                "max_energy_db": -100.0,
                "avg_energy_db": -100.0,
            }

        energies = [self.calculate_energy_db(frame) for frame in audio_frames]
        speech_frames = sum(1 for e in energies if e > self.threshold_db)
        total_frames = len(audio_frames)

        has_speech = speech_frames >= self.min_speech_frames

        return has_speech, {
            "has_speech": has_speech,
            "total_frames": total_frames,
            "speech_frames": speech_frames,
            "speech_ratio": speech_frames / total_frames if total_frames > 0 else 0.0,
            "max_energy_db": max(energies) if energies else -100.0,
            "avg_energy_db": sum(energies) / len(energies) if energies else -100.0,
            "threshold_db": self.threshold_db,
        }

    def get_speech_segments(
        self,
        audio_frames: List[bytes],
        min_segment_frames: int = 5
    ) -> List[Tuple[int, int]]:
        """
        Find continuous segments of speech in audio.

        Args:
            audio_frames: List of audio frame bytes.
            min_segment_frames: Minimum frames for a segment to be counted.

        Returns:
            List of (start_index, end_index) tuples for speech segments.
        """
        segments = []
        in_speech = False
        segment_start = 0

        for i, frame in enumerate(audio_frames):
            is_speech = self.is_speech_frame(frame)

            if is_speech and not in_speech:
                # Start of speech segment
                in_speech = True
                segment_start = i
            elif not is_speech and in_speech:
                # End of speech segment
                in_speech = False
                segment_length = i - segment_start
                if segment_length >= min_segment_frames:
                    segments.append((segment_start, i))

        # Handle case where speech continues to end
        if in_speech:
            segment_length = len(audio_frames) - segment_start
            if segment_length >= min_segment_frames:
                segments.append((segment_start, len(audio_frames)))

        return segments

    def calibrate(
        self,
        silence_frames: List[bytes],
        margin_db: float = 10.0
    ) -> float:
        """
        Calibrate threshold based on silence samples.

        Args:
            silence_frames: Audio frames of ambient noise/silence.
            margin_db: Safety margin above noise floor.

        Returns:
            Suggested threshold in dB.
        """
        if not silence_frames:
            return self.threshold_db

        energies = [self.calculate_energy_db(frame) for frame in silence_frames]
        noise_floor = max(energies)  # Use max to be safe
        suggested_threshold = noise_floor + margin_db

        logger.info(
            f"Calibration: noise_floor={noise_floor:.1f}dB, "
            f"suggested_threshold={suggested_threshold:.1f}dB"
        )

        return suggested_threshold
