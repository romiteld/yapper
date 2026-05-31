"""Tests for device enumeration on sounddevice (query mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from core.devices import (
    AudioDevice,
    list_input_devices,
    get_device_by_index,
    get_default_device,
)

FAKE_DEVICES = [
    {"name": "Built-in Mic", "max_input_channels": 2,
     "default_samplerate": 48000.0},
    {"name": "Loopback Out", "max_input_channels": 0,
     "default_samplerate": 44100.0},
    {"name": "USB Headset", "max_input_channels": 1,
     "default_samplerate": 16000.0},
]


def _patched_sd():
    sd = MagicMock()
    sd.query_devices.return_value = FAKE_DEVICES
    # default = (input_index, output_index)
    sd.default.device = [2, 1]
    return sd


def test_dataclass_shape_unchanged():
    d = AudioDevice(index=0, name="x", channels=1,
                    sample_rate=16000, is_default=True)
    assert "(default)" in str(d)


def test_lists_only_input_devices():
    sd = _patched_sd()
    with patch("core.devices._load_sounddevice", return_value=sd):
        devices = list_input_devices()
    names = [d.name for d in devices]
    assert names == ["Built-in Mic", "USB Headset"]
    assert all(d.channels > 0 for d in devices)


def test_marks_default_device():
    sd = _patched_sd()
    with patch("core.devices._load_sounddevice", return_value=sd):
        devices = list_input_devices()
    default = [d for d in devices if d.is_default]
    assert len(default) == 1
    assert default[0].index == 2


def test_get_device_by_index():
    sd = _patched_sd()
    with patch("core.devices._load_sounddevice", return_value=sd):
        d = get_device_by_index(2)
    assert d is not None
    assert d.name == "USB Headset"


def test_get_default_device_returns_marked_default():
    sd = _patched_sd()
    with patch("core.devices._load_sounddevice", return_value=sd):
        d = get_default_device()
    assert d.index == 2


def test_empty_when_sounddevice_missing():
    with patch("core.devices._load_sounddevice", return_value=None):
        assert list_input_devices() == []
