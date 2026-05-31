"""
Yapper Audio Devices
====================
Microphone enumeration via sounddevice.query_devices(). The AudioDevice
dataclass shape is unchanged so callers and settings keep working.

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
        marker = " (default)" if self.is_default else ""
        return f"[{self.index}] {self.name}{marker}"


def _load_sounddevice():
    try:
        import sounddevice
        return sounddevice
    except Exception as e:
        logger.error("sounddevice not available: %s", e)
        return None


def _default_input_index(sd) -> int:
    try:
        default = sd.default.device
        # sd.default.device is (input, output) or a single int.
        if isinstance(default, (list, tuple)):
            return int(default[0])
        return int(default)
    except Exception:
        return -1


def list_input_devices() -> List[AudioDevice]:
    """List available input devices (maxInputChannels > 0)."""
    sd = _load_sounddevice()
    if sd is None:
        return []

    devices: List[AudioDevice] = []
    try:
        default_index = _default_input_index(sd)
        for i, info in enumerate(sd.query_devices()):
            max_in = int(info.get("max_input_channels", 0))
            if max_in <= 0:
                continue
            devices.append(AudioDevice(
                index=i,
                name=info.get("name", f"Device {i}"),
                channels=max_in,
                sample_rate=int(info.get("default_samplerate", 16000)),
                is_default=(i == default_index),
            ))
    except Exception as e:
        logger.error("Error listing audio devices: %s", e)

    logger.info("Found %d input device(s)", len(devices))
    return devices


def get_device_by_index(index: int) -> Optional[AudioDevice]:
    for d in list_input_devices():
        if d.index == index:
            return d
    return None


def get_device_by_name(name: str, partial_match: bool = True) -> Optional[AudioDevice]:
    name_lower = name.lower()
    for d in list_input_devices():
        dn = d.name.lower()
        if (name_lower in dn) if partial_match else (name_lower == dn):
            return d
    return None


def get_default_device() -> Optional[AudioDevice]:
    devices = list_input_devices()
    for d in devices:
        if d.is_default:
            return d
    return devices[0] if devices else None


def test_device(device_index: int, duration: float = 0.5) -> bool:
    """Test if a device can record audio.

    Args:
        device_index: Device index to test.
        duration: Test duration in seconds.

    Returns:
        True if device works, False otherwise.
    """
    import time
    sd = _load_sounddevice()
    if sd is None:
        return False
    try:
        stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="int16",
            device=device_index,
        )
        stream.start()
        time.sleep(duration)
        stream.stop()
        stream.close()
        logger.debug("Device %d test passed", device_index)
        return True
    except Exception as e:
        logger.warning("Device %d test failed: %s", device_index, e)
        return False
