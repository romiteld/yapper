"""
Yapper Audio Devices
====================
Cross-platform microphone enumeration and selection.

© 2026 Cloudelipute
"""

from dataclasses import dataclass
from typing import List, Optional

from .logger import get_logger

logger = get_logger("devices")


@dataclass
class AudioDevice:
    """Represents an audio input device."""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_default: bool

    def __str__(self) -> str:
        default_marker = " (default)" if self.is_default else ""
        return f"[{self.index}] {self.name}{default_marker}"


def list_input_devices() -> List[AudioDevice]:
    """
    List all available audio input devices.

    Returns:
        List of AudioDevice objects representing available microphones.
    """
    devices = []

    try:
        import pyaudio
        audio = pyaudio.PyAudio()

        try:
            # Get default input device info
            default_info = audio.get_default_input_device_info()
            default_index = default_info.get("index", -1)
        except (IOError, OSError):
            default_index = -1
            logger.warning("Could not determine default input device")

        # Enumerate all devices
        device_count = audio.get_device_count()

        for i in range(device_count):
            try:
                info = audio.get_device_info_by_index(i)

                # Only include input devices (maxInputChannels > 0)
                max_input_channels = int(info.get("maxInputChannels", 0))
                if max_input_channels > 0:
                    device = AudioDevice(
                        index=i,
                        name=info.get("name", f"Device {i}"),
                        channels=max_input_channels,
                        sample_rate=int(info.get("defaultSampleRate", 16000)),
                        is_default=(i == default_index)
                    )
                    devices.append(device)
                    logger.debug(f"Found input device: {device}")

            except (IOError, OSError) as e:
                logger.warning(f"Error getting info for device {i}: {e}")
                continue

        audio.terminate()

    except ImportError:
        logger.error("PyAudio not installed. Install with: pip install pyaudio")
    except Exception as e:
        logger.error(f"Error listing audio devices: {e}")

    logger.info(f"Found {len(devices)} input device(s)")
    return devices


def get_device_by_index(index: int) -> Optional[AudioDevice]:
    """
    Get a specific audio device by index.

    Args:
        index: Device index.

    Returns:
        AudioDevice if found, None otherwise.
    """
    devices = list_input_devices()
    for device in devices:
        if device.index == index:
            return device
    return None


def get_device_by_name(name: str, partial_match: bool = True) -> Optional[AudioDevice]:
    """
    Find an audio device by name.

    Args:
        name: Device name to search for.
        partial_match: If True, match partial names (case-insensitive).

    Returns:
        First matching AudioDevice, or None if not found.
    """
    devices = list_input_devices()
    name_lower = name.lower()

    for device in devices:
        device_name_lower = device.name.lower()
        if partial_match:
            if name_lower in device_name_lower:
                return device
        else:
            if name_lower == device_name_lower:
                return device

    return None


def get_default_device() -> Optional[AudioDevice]:
    """
    Get the default audio input device.

    Returns:
        Default AudioDevice, or None if not found.
    """
    devices = list_input_devices()
    for device in devices:
        if device.is_default:
            return device

    # Return first device if no default found
    if devices:
        return devices[0]

    return None


def test_device(device_index: int, duration: float = 0.5) -> bool:
    """
    Test if a device can record audio.

    Args:
        device_index: Device index to test.
        duration: Test duration in seconds.

    Returns:
        True if device works, False otherwise.
    """
    try:
        import pyaudio
        import time

        audio = pyaudio.PyAudio()

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )

            # Try to read some data
            time.sleep(duration)
            data = stream.read(1024, exception_on_overflow=False)

            stream.stop_stream()
            stream.close()
            audio.terminate()

            # Check if we got actual data
            if len(data) > 0:
                logger.debug(f"Device {device_index} test passed")
                return True

        except (IOError, OSError) as e:
            logger.warning(f"Device {device_index} test failed: {e}")
            audio.terminate()
            return False

    except ImportError:
        logger.error("PyAudio not installed")
        return False
    except Exception as e:
        logger.error(f"Device test error: {e}")
        return False

    return False
