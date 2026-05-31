# Phase 1: Cross-Platform Core Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the platform-abstraction foundation (hotkeys, permissions, text insertion, audio capture, device enumeration, notifications, OS helpers) that every later phase depends on, fully headless-testable on Linux CI.
**Architecture:** Each module isolates one cross-platform concern behind a thin, stable public API; macOS-specific behavior (pynput combo workarounds, TCC permission detection, Accessibility-gated injection) is guarded by `core/platform.py` flags and lazy imports so the code imports and tests run with zero native deps on Linux. All modules log via `core.logger.get_logger` and read config via the existing `core.config.Settings`.
**Tech Stack:** `pynput>=1.8.2` (capture + injection), `sounddevice` + `numpy` (audio), `pyperclip` (clipboard), `desktop-notifier` (notifications), `pyobjc-framework-ApplicationServices` (mac TCC, lazy), `pytest` + `unittest.mock` (TDD).

---

## File Structure

**Create**
- `app/core/platform.py` — OS detection (`IS_MAC`/`IS_WIN`/`IS_LINUX`), per-OS default hotkey, open-System-Settings deep links, open-folder helper.
- `app/core/permissions.py` — `PermissionStatus` dataclass + `microphone_ok`/`accessibility_trusted`/`input_monitoring_ok`/`permission_status`; all `True` off-mac.
- `app/core/hotkeys.py` — `HotkeyManager` on pynput: push_to_talk / toggle / wake_word, with PTT auto-repeat guard.
- `app/core/notifications.py` — `Notifier` over `desktop-notifier`, graceful no-op degrade.
- `tests/conftest.py` — adds `app/` to `sys.path` and registers a `temp_settings` fixture (created here if Phase 0 did not).
- `tests/test_platform.py`, `tests/test_permissions.py`, `tests/test_hotkeys.py`, `tests/test_typer.py`, `tests/test_audio.py`, `tests/test_devices.py`, `tests/test_notifications.py` — unit tests.

**Modify**
- `app/core/typer.py` — `TextTyper` reworked: clipboard-paste primary (daemon-thread ~1.5 s restore), pynput `Controller().type()` fallback, drop `isascii()` branch, mac Accessibility gate, new `type_text(text, method='paste')` signature.
- `app/core/audio.py` — `AudioRecorder` reimplemented on `sounddevice` (same public API).
- `app/core/devices.py` — `list_input_devices()` etc. via `sounddevice.query_devices()` (same `AudioDevice` shape).
- `app/core/constants.py` — add Phase-1-relevant settings keys (`activation_mode`, `insertion_method`, OS default `hotkey`) + schema; expand `HOTKEYS`; bump `VERSION` to `4.0.0`.
- `app/core/config.py` — migrate legacy `always_listening` → `activation_mode`.
- `app/core/__init__.py` — export the new symbols.

---

## Tasks

### Task 1: Test scaffolding (conftest + path)

**Files:**
- Test: `tests/conftest.py` (Create)

**Steps:**
- [ ] Create `tests/conftest.py` so every test can import `core.*` and get a temp settings file. If Phase 0 already created this file, instead append the `temp_settings` fixture to it (check first with a quick read). Write:
```python
"""Shared pytest fixtures for Yapper tests."""
import sys
from pathlib import Path

import pytest

# Make `import core...` work from the app/ package.
APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture
def temp_settings(tmp_path, monkeypatch):
    """A Settings instance backed by a throwaway JSON file."""
    from core.config import Settings

    path = tmp_path / "settings.json"
    return Settings(settings_path=path)
```
- [ ] Verify the harness collects tests and the import path works:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/ -q --collect-only 2>&1 | tail -5
```
  Expected: no `ModuleNotFoundError`; collection succeeds (0 or more items, no errors).
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/conftest.py && git commit -m "test: add conftest with app path + temp_settings fixture"
```

---

### Task 2: `core/platform.py` — OS helpers

**Files:**
- Create: `app/core/platform.py`
- Test: `tests/test_platform.py`

**Steps:**
- [ ] Write the failing test `tests/test_platform.py`:
```python
"""Tests for core.platform OS helpers."""
import importlib
from unittest.mock import patch

import pytest


def _reload_platform(system: str):
    """Reload core.platform with platform.system() mocked to `system`."""
    with patch("platform.system", return_value=system):
        import core.platform as p
        return importlib.reload(p)


def test_flags_mac():
    p = _reload_platform("Darwin")
    assert p.IS_MAC is True
    assert p.IS_WIN is False
    assert p.IS_LINUX is False


def test_flags_windows():
    p = _reload_platform("Windows")
    assert p.IS_WIN is True
    assert p.IS_MAC is False


def test_default_hotkey_per_os():
    assert _reload_platform("Darwin").default_hotkey() == "f8"
    assert _reload_platform("Windows").default_hotkey() == "f8"


def test_open_settings_pane_runs_open_on_mac():
    p = _reload_platform("Darwin")
    with patch("subprocess.run") as run:
        p.open_settings_pane("accessibility")
    run.assert_called_once()
    args = run.call_args[0][0]
    assert args[0] == "open"
    assert "Privacy_Accessibility" in args[1]


def test_open_settings_pane_noop_off_mac():
    p = _reload_platform("Windows")
    with patch("subprocess.run") as run:
        result = p.open_settings_pane("accessibility")
    run.assert_not_called()
    assert result is False


def test_open_folder_invokes_opener(tmp_path):
    p = _reload_platform("Linux")
    with patch("subprocess.run") as run:
        p.open_folder(str(tmp_path))
    run.assert_called_once()
    assert run.call_args[0][0][0] == "xdg-open"


def teardown_module(module):
    # Restore module to the real OS state for other test files.
    _reload_platform(__import__("platform").system())
```
- [ ] Run it (expect FAIL — module does not exist):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_platform.py -q
```
  Expected: `ModuleNotFoundError: No module named 'core.platform'` / errors.
- [ ] Create `app/core/platform.py`:
```python
"""
Yapper Platform Helpers
=======================
OS detection, default hotkey per OS, and OS deep-link / folder helpers.

© 2026 Cloudelipute
"""

import platform as _platform
import subprocess
from typing import Final

from .logger import get_logger

logger = get_logger("platform")

_SYSTEM: Final[str] = _platform.system()

IS_MAC: Final[bool] = _SYSTEM == "Darwin"
IS_WIN: Final[bool] = _SYSTEM == "Windows"
IS_LINUX: Final[bool] = _SYSTEM == "Linux"

# macOS System Settings deep links (Ventura+ "x-apple.systempreferences" URLs).
_MAC_SETTINGS_PANES = {
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


def default_hotkey() -> str:
    """Return the default activation key for the current OS.

    A single F-key is used everywhere: pynput Ctrl/Alt *combos* are broken on
    macOS (pynput issue #297), and F8 is safe and unused on Win/Mac/Linux.
    """
    return "f8"


def open_settings_pane(pane: str) -> bool:
    """Open a macOS System Settings privacy pane. No-op (False) off macOS.

    Args:
        pane: one of 'accessibility', 'input_monitoring', 'microphone'.
    """
    if not IS_MAC:
        return False
    url = _MAC_SETTINGS_PANES.get(pane)
    if not url:
        logger.warning("Unknown settings pane: %s", pane)
        return False
    try:
        subprocess.run(["open", url], check=False)
        return True
    except OSError as e:
        logger.error("Failed to open settings pane %s: %s", pane, e)
        return False


def open_folder(path: str) -> bool:
    """Reveal a folder in the OS file manager. Returns True on success."""
    try:
        if IS_MAC:
            subprocess.run(["open", path], check=False)
        elif IS_WIN:
            subprocess.run(["explorer", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except OSError as e:
        logger.error("Failed to open folder %s: %s", path, e)
        return False
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_platform.py -q
```
  Expected: all tests pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/platform.py tests/test_platform.py && git commit -m "feat(core): add platform helpers (IS_MAC/IS_WIN, default hotkey, deep links)"
```

---

### Task 3: `core/constants.py` + `config.py` migration — new settings keys

**Files:**
- Modify: `app/core/constants.py`
- Modify: `app/core/config.py`
- Test: `tests/test_constants_migration.py` (Create)

**Steps:**
- [ ] Write the failing test `tests/test_constants_migration.py`:
```python
"""Tests for new Phase 1 settings keys and legacy migration."""
import json

from core.constants import DEFAULT_SETTINGS, SETTINGS_SCHEMA, HOTKEYS, VERSION


def test_new_keys_present_with_defaults():
    assert DEFAULT_SETTINGS["activation_mode"] == "push_to_talk"
    assert DEFAULT_SETTINGS["insertion_method"] == "paste"
    assert DEFAULT_SETTINGS["hotkey"] == "f8"


def test_new_keys_in_schema():
    assert "activation_mode" in SETTINGS_SCHEMA
    assert "insertion_method" in SETTINGS_SCHEMA


def test_activation_mode_validator():
    _type, validator, _desc = SETTINGS_SCHEMA["activation_mode"]
    assert validator("push_to_talk") is True
    assert validator("toggle") is True
    assert validator("wake_word") is True
    assert validator("nonsense") is False


def test_insertion_method_validator():
    _type, validator, _desc = SETTINGS_SCHEMA["insertion_method"]
    assert validator("paste") is True
    assert validator("type") is True
    assert validator("smoke") is False


def test_version_bumped():
    assert VERSION == "4.0.0"


def test_f6_hotkey_available():
    # Mac-friendly single F-keys must be selectable.
    assert "f6" in HOTKEYS
    assert "f7" in HOTKEYS


def test_legacy_always_listening_false_migrates_to_toggle(tmp_path):
    from core.config import Settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"always_listening": False, "api_key": "x"}))
    s = Settings(settings_path=path).load()
    assert s.get("activation_mode") == "toggle"


def test_legacy_always_listening_true_migrates_to_wake_word(tmp_path):
    from core.config import Settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"always_listening": True, "api_key": "x"}))
    s = Settings(settings_path=path).load()
    assert s.get("activation_mode") == "wake_word"


def test_explicit_activation_mode_not_overridden(tmp_path):
    from core.config import Settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps(
        {"always_listening": True, "activation_mode": "push_to_talk"}))
    s = Settings(settings_path=path).load()
    assert s.get("activation_mode") == "push_to_talk"
```
- [ ] Run it (expect FAIL — keys/migration absent):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_constants_migration.py -q
```
  Expected: KeyError / assertion failures.
- [ ] In `app/core/constants.py`, bump version:
```python
VERSION = "4.0.0"
```
- [ ] In `app/core/constants.py`, replace the `HOTKEYS` list with one that includes Mac-friendly single F-keys:
```python
HOTKEYS: List[str] = [
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "pause",
    "scroll lock",
    "insert",
    "cmd+shift+space",
    "shift+space",
]
```
- [ ] In `app/core/constants.py`, add the Phase 1 keys to `DEFAULT_SETTINGS` (insert after the `"hotkey": "f8",` line, inside the dict):
```python
    # Activation & insertion (v4)
    "activation_mode": "push_to_talk",  # push_to_talk | toggle | wake_word
    "insertion_method": "paste",        # paste | type
```
- [ ] In `app/core/constants.py`, add to `SETTINGS_SCHEMA` (inside the dict, near `"hotkey"`):
```python
    "activation_mode": (
        str,
        lambda x: x in ("push_to_talk", "toggle", "wake_word"),
        "How recording is triggered",
    ),
    "insertion_method": (
        str,
        lambda x: x in ("paste", "type"),
        "How text is inserted at cursor",
    ),
```
- [ ] In `app/core/config.py`, add a private migration method to the `Settings` class (place it right above `_create_default_file`):
```python
    def _migrate_legacy(self, file_data: Dict[str, Any]) -> None:
        """Map deprecated keys onto v4 keys when the new key is absent."""
        if "activation_mode" not in file_data and "always_listening" in file_data:
            legacy = file_data.get("always_listening")
            self._data["activation_mode"] = "wake_word" if legacy else "toggle"
            logger.info(
                "Migrated legacy 'always_listening'=%s -> activation_mode=%s",
                legacy, self._data["activation_mode"],
            )
```
- [ ] In `app/core/config.py`, call the migration at the end of `load()`. Change the final `return self` of the `load()` method's `try` path so that immediately before `return self` (after the for-loop that splits known/unknown keys, inside the `try`), it runs migration. Replace:
```python
            logger.debug(f"Loaded settings from {self._path}")

        except json.JSONDecodeError as e:
```
  with:
```python
            self._migrate_legacy(file_data)
            logger.debug(f"Loaded settings from {self._path}")

        except json.JSONDecodeError as e:
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_constants_migration.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/constants.py app/core/config.py tests/test_constants_migration.py && git commit -m "feat(core): add activation_mode/insertion_method keys + legacy migration; bump to 4.0.0"
```

---

### Task 4: `core/permissions.py` — macOS TCC detection

**Files:**
- Create: `app/core/permissions.py`
- Test: `tests/test_permissions.py`

**Steps:**
- [ ] Write the failing test `tests/test_permissions.py`:
```python
"""Tests for core.permissions (macOS TCC detection, no-op off-mac)."""
from unittest.mock import MagicMock, patch

from core.permissions import (
    PermissionStatus,
    microphone_ok,
    accessibility_trusted,
    input_monitoring_ok,
    permission_status,
)


def test_dataclass_shape():
    s = PermissionStatus(microphone=True, accessibility=False, input_monitoring=True)
    assert s.microphone is True
    assert s.accessibility is False
    assert s.input_monitoring is True


def test_all_true_off_mac():
    with patch("core.permissions.IS_MAC", False):
        assert microphone_ok() is True
        assert accessibility_trusted() is True
        assert input_monitoring_ok() is True
        st = permission_status()
        assert st == PermissionStatus(True, True, True)


def test_accessibility_uses_axis_process_trusted_on_mac():
    fake_hi = MagicMock()
    fake_hi.AXIsProcessTrusted.return_value = True
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert accessibility_trusted() is True
    fake_hi.AXIsProcessTrusted.return_value = False
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert accessibility_trusted() is False


def test_accessibility_false_when_pyobjc_missing_on_mac():
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=None):
        assert accessibility_trusted() is False


def test_input_monitoring_uses_listener_is_trusted_on_mac():
    fake_listener = MagicMock()
    fake_listener.IS_TRUSTED = True
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._keyboard_listener_cls", return_value=fake_listener):
        assert input_monitoring_ok() is True
    fake_listener.IS_TRUSTED = False
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._keyboard_listener_cls", return_value=fake_listener):
        assert input_monitoring_ok() is False


def test_microphone_probe_true_when_stream_opens_on_mac():
    fake_sd = MagicMock()
    fake_sd.check_input_settings.return_value = None  # no exception => ok
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_sounddevice", return_value=fake_sd):
        assert microphone_ok() is True


def test_microphone_probe_false_when_stream_raises_on_mac():
    fake_sd = MagicMock()
    fake_sd.PortAudioError = Exception
    fake_sd.check_input_settings.side_effect = Exception("denied")
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_sounddevice", return_value=fake_sd):
        assert microphone_ok() is False


def test_permission_status_aggregates_on_mac():
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions.microphone_ok", return_value=True), \
         patch("core.permissions.accessibility_trusted", return_value=False), \
         patch("core.permissions.input_monitoring_ok", return_value=True):
        st = permission_status()
    assert st == PermissionStatus(True, False, True)
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_permissions.py -q
```
  Expected: `ModuleNotFoundError`.
- [ ] Create `app/core/permissions.py`:
```python
"""
Yapper Permissions
==================
macOS TCC permission detection (Accessibility, Input Monitoring, Microphone).
On Windows/Linux every check returns True (no per-permission gating needed).

macOS only re-reads TCC at process launch, so a False here means the user must
grant the permission and *relaunch* the app. pynput injection fails silently
without Accessibility, so we never rely on exceptions — we probe up front.

© 2026 Cloudelipute
"""

from dataclasses import dataclass

from .logger import get_logger
from .platform import IS_MAC

logger = get_logger("permissions")


@dataclass
class PermissionStatus:
    """Aggregated permission state for the wizard / HUD to act on."""
    microphone: bool
    accessibility: bool
    input_monitoring: bool

    @property
    def all_granted(self) -> bool:
        return self.microphone and self.accessibility and self.input_monitoring


def _load_hiservices():
    """Return the pyobjc HIServices module, or None if unavailable."""
    try:
        import HIServices  # type: ignore
        return HIServices
    except Exception:  # pragma: no cover - import path only on mac
        try:
            from ApplicationServices import HIServices  # type: ignore
            return HIServices
        except Exception:
            logger.debug("HIServices (pyobjc) not available")
            return None


def _keyboard_listener_cls():
    """Return pynput's keyboard Listener class, or None if unavailable."""
    try:
        from pynput import keyboard  # type: ignore
        return keyboard.Listener
    except Exception:
        logger.debug("pynput not available for input-monitoring probe")
        return None


def _load_sounddevice():
    """Return the sounddevice module, or None if unavailable."""
    try:
        import sounddevice  # type: ignore
        return sounddevice
    except Exception:
        logger.debug("sounddevice not available for mic probe")
        return None


def accessibility_trusted() -> bool:
    """True if the process may inject keystrokes (mac Accessibility)."""
    if not IS_MAC:
        return True
    hi = _load_hiservices()
    if hi is None:
        return False
    try:
        return bool(hi.AXIsProcessTrusted())
    except Exception as e:
        logger.error("AXIsProcessTrusted failed: %s", e)
        return False


def input_monitoring_ok() -> bool:
    """True if the process may observe global key events (mac Input Monitoring)."""
    if not IS_MAC:
        return True
    listener_cls = _keyboard_listener_cls()
    if listener_cls is None:
        return False
    try:
        return bool(getattr(listener_cls, "IS_TRUSTED", True))
    except Exception as e:
        logger.error("Listener.IS_TRUSTED check failed: %s", e)
        return False


def microphone_ok() -> bool:
    """True if an input stream can be opened (mac Microphone)."""
    if not IS_MAC:
        return True
    sd = _load_sounddevice()
    if sd is None:
        return False
    try:
        sd.check_input_settings()
        return True
    except Exception as e:
        logger.warning("Microphone probe failed: %s", e)
        return False


def permission_status() -> PermissionStatus:
    """Snapshot all three permissions."""
    if not IS_MAC:
        return PermissionStatus(True, True, True)
    return PermissionStatus(
        microphone=microphone_ok(),
        accessibility=accessibility_trusted(),
        input_monitoring=input_monitoring_ok(),
    )
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_permissions.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/permissions.py tests/test_permissions.py && git commit -m "feat(core): add permissions module (mac TCC detection, no-op off-mac)"
```

---

### Task 5: `core/hotkeys.py` — `HotkeyManager` on pynput

**Files:**
- Create: `app/core/hotkeys.py`
- Test: `tests/test_hotkeys.py`

**Steps:**
- [ ] Write the failing test `tests/test_hotkeys.py`. It exercises the pure state machine via the manager's private `_on_press` / `_on_release` handlers with a fake key, so no real listener thread is needed:
```python
"""Tests for core.hotkeys HotkeyManager state machine (pynput mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from core.hotkeys import HotkeyManager


class FakeKey:
    """Stand-in for a pynput key with a usable name attribute."""
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return isinstance(other, FakeKey) and other.name == self.name
    def __hash__(self):
        return hash(self.name)


def _make(mode="push_to_talk", hotkey="f8"):
    on_start = MagicMock()
    on_stop = MagicMock()
    mgr = HotkeyManager(mode=mode, hotkey=hotkey,
                        on_start=on_start, on_stop=on_stop)
    # Force the matcher to recognise our FakeKey("f8").
    mgr._target_key = FakeKey("f8")
    return mgr, on_start, on_stop


def test_ptt_press_starts_release_stops():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f8"))
    on_start.assert_called_once()
    on_stop.assert_not_called()
    mgr._on_release(FakeKey("f8"))
    on_stop.assert_called_once()


def test_ptt_autorepeat_guarded():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f8"))
    mgr._on_press(FakeKey("f8"))   # OS key auto-repeat
    mgr._on_press(FakeKey("f8"))
    assert on_start.call_count == 1  # guarded by _active flag


def test_ptt_ignores_other_keys():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f9"))
    on_start.assert_not_called()


def test_toggle_alternates_on_press_only():
    mgr, on_start, on_stop = _make("toggle")
    mgr._on_press(FakeKey("f8"))
    on_start.assert_called_once()
    mgr._on_release(FakeKey("f8"))   # release is a no-op in toggle
    on_stop.assert_not_called()
    mgr._on_press(FakeKey("f8"))
    on_stop.assert_called_once()
    mgr._on_press(FakeKey("f8"))
    assert on_start.call_count == 2


def test_set_mode_resets_active_state():
    mgr, on_start, on_stop = _make("push_to_talk")
    mgr._on_press(FakeKey("f8"))      # _active True
    mgr.set_mode("toggle")
    assert mgr._active is False
    mgr._on_press(FakeKey("f8"))      # toggle -> start
    assert on_start.call_count == 2


def test_set_hotkey_reparses_target():
    mgr, _, _ = _make("push_to_talk", "f8")
    with patch.object(mgr, "_parse_hotkey", return_value="PARSED") as parse:
        mgr.set_hotkey("f9")
    parse.assert_called_once_with("f9")
    assert mgr._target_key == "PARSED"


def test_start_creates_and_runs_listener():
    mgr, _, _ = _make("push_to_talk")
    fake_listener = MagicMock()
    fake_keyboard = MagicMock()
    fake_keyboard.Listener.return_value = fake_listener
    with patch.object(mgr, "_load_keyboard", return_value=fake_keyboard):
        mgr.start()
    fake_listener.start.assert_called_once()


def test_stop_stops_listener():
    mgr, _, _ = _make("push_to_talk")
    fake_listener = MagicMock()
    mgr._listener = fake_listener
    mgr.stop()
    fake_listener.stop.assert_called_once()
    assert mgr._listener is None


def test_wake_word_mode_does_not_react_to_keys():
    mgr, on_start, on_stop = _make("wake_word")
    mgr._on_press(FakeKey("f8"))
    mgr._on_release(FakeKey("f8"))
    on_start.assert_not_called()
    on_stop.assert_not_called()
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_hotkeys.py -q
```
  Expected: `ModuleNotFoundError`.
- [ ] Create `app/core/hotkeys.py`:
```python
"""
Yapper Hotkey Manager
=====================
Cross-platform activation key capture via pynput. Supports push-to-talk,
toggle, and a wake-word bridge (key handling disabled; the wake-word listener
drives start/stop elsewhere).

PTT key auto-repeat is guarded by an internal `_active` flag so a held key only
fires on_start once. Ctrl/Alt *combos* are broken on macOS (pynput #297), so the
default activation is a single F-key.

© 2026 Cloudelipute
"""

import threading
from typing import Callable, Optional

from .logger import get_logger

logger = get_logger("hotkeys")

_VALID_MODES = ("push_to_talk", "toggle", "wake_word")


class HotkeyManager:
    """Owns a pynput keyboard.Listener and maps key events to start/stop."""

    def __init__(
        self,
        mode: str,
        hotkey: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ):
        if mode not in _VALID_MODES:
            logger.warning("Unknown mode %r, defaulting to push_to_talk", mode)
            mode = "push_to_talk"
        self.mode = mode
        self.hotkey = hotkey
        self._on_start = on_start
        self._on_stop = on_stop

        self._active = False          # PTT held / toggle currently recording
        self._lock = threading.Lock()
        self._listener = None
        self._target_key = self._parse_hotkey(hotkey)

    # --- listener lifecycle -------------------------------------------------

    def _load_keyboard(self):
        """Lazy import so the module imports on headless CI without pynput."""
        from pynput import keyboard
        return keyboard

    def _parse_hotkey(self, hotkey: str):
        """Resolve a hotkey string to a pynput Key/KeyCode, or None if unknown."""
        try:
            keyboard = self._load_keyboard()
        except Exception:
            logger.debug("pynput unavailable; hotkey parsing deferred")
            return None
        token = hotkey.strip().lower().split("+")[-1]  # ignore combo prefixes
        special = getattr(keyboard.Key, token, None)
        if special is not None:
            return special
        try:
            return keyboard.KeyCode.from_char(token)
        except Exception:
            logger.warning("Could not parse hotkey %r", hotkey)
            return None

    def start(self) -> None:
        """Begin listening for the activation key on a background thread."""
        if self._listener is not None:
            return
        try:
            keyboard = self._load_keyboard()
        except Exception as e:
            logger.error("Cannot start hotkeys (pynput missing): %s", e)
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        logger.info("Hotkey listener started (mode=%s, key=%s)",
                    self.mode, self.hotkey)

    def stop(self) -> None:
        """Stop the listener and reset state."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as e:
                logger.warning("Error stopping listener: %s", e)
            self._listener = None
        self._active = False

    # --- runtime reconfiguration -------------------------------------------

    def set_mode(self, mode: str) -> None:
        if mode not in _VALID_MODES:
            logger.warning("Ignoring invalid mode %r", mode)
            return
        self.mode = mode
        self._active = False
        logger.debug("Hotkey mode set to %s", mode)

    def set_hotkey(self, hotkey: str) -> None:
        self.hotkey = hotkey
        self._target_key = self._parse_hotkey(hotkey)
        self._active = False
        logger.debug("Hotkey set to %s", hotkey)

    # --- key matching -------------------------------------------------------

    def _matches(self, key) -> bool:
        if self._target_key is None:
            return False
        try:
            return key == self._target_key
        except Exception:
            return False

    # --- event handlers (pure, unit-tested directly) ------------------------

    def _on_press(self, key) -> None:
        if self.mode == "wake_word" or not self._matches(key):
            return
        with self._lock:
            if self.mode == "push_to_talk":
                if self._active:
                    return  # auto-repeat guard
                self._active = True
                fire_start = True
                fire_stop = False
            else:  # toggle
                self._active = not self._active
                fire_start = self._active
                fire_stop = not self._active
        if fire_start:
            self._safe(self._on_start)
        if fire_stop:
            self._safe(self._on_stop)

    def _on_release(self, key) -> None:
        if self.mode != "push_to_talk" or not self._matches(key):
            return
        with self._lock:
            if not self._active:
                return
            self._active = False
        self._safe(self._on_stop)

    @staticmethod
    def _safe(callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception as e:  # never let a callback kill the listener thread
            logger.error("Hotkey callback raised: %s", e)
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_hotkeys.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/hotkeys.py tests/test_hotkeys.py && git commit -m "feat(core): add HotkeyManager (pynput PTT/toggle/wake_word with auto-repeat guard)"
```

---

### Task 6: `core/typer.py` — clipboard-paste rework

**Files:**
- Modify: `app/core/typer.py`
- Test: `tests/test_typer.py`

**Steps:**
- [ ] Write the failing test `tests/test_typer.py`:
```python
"""Tests for the reworked TextTyper (clipboard-paste primary, pynput fallback)."""
from unittest.mock import MagicMock, patch

import pytest

from core.typer import TextTyper


def _typer():
    t = TextTyper(delay_before_typing=0.0, clipboard_restore_delay=0.0)
    return t


def test_empty_text_returns_false():
    assert _typer().type_text("") is False


def test_paste_sets_clipboard_and_sends_shortcut(monkeypatch):
    fake_clip = MagicMock()
    fake_clip.paste.return_value = "ORIGINAL"
    fake_kb = MagicMock()
    controller = MagicMock()
    fake_kb.Controller.return_value = controller
    fake_kb.Key.cmd = "CMD"
    fake_kb.Key.ctrl = "CTRL"

    t = _typer()
    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", False):
        ok = t.type_text("hello.py --help", method="paste")

    assert ok is True
    fake_clip.copy.assert_any_call("hello.py --help")
    controller.press.assert_called()      # Ctrl held
    controller.release.assert_called()


def test_paste_restores_clipboard_on_daemon_thread(monkeypatch):
    fake_clip = MagicMock()
    fake_clip.paste.return_value = "ORIGINAL"
    fake_kb = MagicMock()
    fake_kb.Controller.return_value = MagicMock()
    fake_kb.Key.ctrl = "CTRL"

    t = TextTyper(delay_before_typing=0.0, clipboard_restore_delay=0.0)
    started = {}

    real_thread = __import__("threading").Thread

    def capture_thread(*args, **kwargs):
        started["daemon"] = kwargs.get("daemon")
        th = real_thread(*args, **kwargs)
        return th

    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", False), \
         patch("core.typer.threading.Thread", side_effect=capture_thread):
        t.type_text("x", method="paste")

    # restore must happen off the main thread (daemon=True)
    assert started.get("daemon") is True


def test_type_method_uses_controller_type():
    fake_kb = MagicMock()
    controller = MagicMock()
    fake_kb.Controller.return_value = controller
    t = _typer()
    with patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True):
        ok = t.type_text("café 🚀 中文", method="type")
    assert ok is True
    controller.type.assert_called_once_with("café 🚀 中文")


def test_unicode_not_routed_through_isascii_branch():
    # Regression: the old isascii() ASCII/non-ASCII split must be gone.
    import inspect
    src = inspect.getsource(TextTyper)
    assert "isascii" not in src


def test_blocked_when_accessibility_missing_on_mac():
    t = _typer()
    with patch("core.typer.IS_MAC", True), \
         patch.object(t, "_accessibility_ok", return_value=False):
        assert t.type_text("hi", method="paste") is False


def test_paste_uses_cmd_on_mac():
    fake_clip = MagicMock()
    fake_clip.paste.return_value = ""
    fake_kb = MagicMock()
    controller = MagicMock()
    fake_kb.Controller.return_value = controller
    fake_kb.Key.cmd = "CMD"
    t = _typer()
    with patch.object(t, "_load_pyperclip", return_value=fake_clip), \
         patch.object(t, "_load_keyboard", return_value=fake_kb), \
         patch.object(t, "_accessibility_ok", return_value=True), \
         patch("core.typer.IS_MAC", True):
        t.type_text("z", method="paste")
    # the modifier pressed must be Cmd on mac
    controller.press.assert_any_call("CMD")
```
- [ ] Run it (expect FAIL — new signature/behavior absent):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_typer.py -q
```
  Expected: failures (old `type_text(text)` signature, `keyboard`/`pyautogui` imports, `isascii` present).
- [ ] Replace the entire contents of `app/core/typer.py` with:
```python
"""
Yapper Text Typer
=================
Insert text at the current cursor position.

Primary method: clipboard paste (Cmd/Ctrl+V) — Unicode/emoji/CJK-safe — with
the original clipboard restored ~1.5 s later on a daemon thread so the paste
target has time to read it. Fallback method: pynput Controller().type().

On macOS, injection silently no-ops without Accessibility, so we check
permissions first and refuse rather than appear to succeed.

© 2026 Cloudelipute
"""

import threading
import time
from typing import Optional

from .logger import get_logger
from .platform import IS_MAC

logger = get_logger("typer")


class TextTyper:
    """Types text at the cursor via clipboard paste (default) or pynput type."""

    def __init__(
        self,
        delay_before_typing: float = 0.15,
        clipboard_restore_delay: float = 1.5,
    ):
        """
        Args:
            delay_before_typing: pause before injecting (lets focus settle).
            clipboard_restore_delay: seconds before the original clipboard is
                restored on a background daemon thread.
        """
        self.delay = delay_before_typing
        self.clipboard_restore_delay = clipboard_restore_delay

    # --- lazy imports (keep headless CI import-clean) -----------------------

    def _load_pyperclip(self):
        import pyperclip
        return pyperclip

    def _load_keyboard(self):
        from pynput import keyboard
        return keyboard

    # --- permission gate ----------------------------------------------------

    def _accessibility_ok(self) -> bool:
        from .permissions import accessibility_trusted
        return accessibility_trusted()

    # --- public API ---------------------------------------------------------

    def type_text(self, text: str, method: str = "paste") -> bool:
        """Insert `text` at the cursor.

        Args:
            text: text to insert.
            method: 'paste' (clipboard) or 'type' (pynput keystrokes).

        Returns:
            True on success, False otherwise.
        """
        if not text:
            logger.warning("No text to type")
            return False

        if IS_MAC and not self._accessibility_ok():
            logger.error(
                "Accessibility not granted; cannot inject text. "
                "Grant it in System Settings and relaunch Yapper."
            )
            return False

        preview = text[:60] + "..." if len(text) > 60 else text
        logger.info("Inserting (%s): %s", method, preview)

        if self.delay:
            time.sleep(self.delay)

        if method == "type":
            return self._type_via_pynput(text)
        if self._paste(text):
            return True
        logger.warning("Paste failed; falling back to pynput type")
        return self._type_via_pynput(text)

    # --- paste implementation ----------------------------------------------

    def _paste(self, text: str) -> bool:
        try:
            pyperclip = self._load_pyperclip()
            keyboard = self._load_keyboard()
        except Exception as e:
            logger.error("Paste deps unavailable: %s", e)
            return False

        try:
            original = pyperclip.paste()
        except Exception:
            original = None

        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error("Could not set clipboard: %s", e)
            return False

        try:
            controller = keyboard.Controller()
            modifier = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl
            controller.press(modifier)
            controller.press("v")
            controller.release("v")
            controller.release(modifier)
        except Exception as e:
            logger.error("Paste keystroke failed: %s", e)
            return False

        self._schedule_clipboard_restore(pyperclip, original)
        logger.debug("Pasted via clipboard")
        return True

    def _schedule_clipboard_restore(self, pyperclip, original) -> None:
        if original is None:
            return

        def _restore():
            time.sleep(self.clipboard_restore_delay)
            try:
                pyperclip.copy(original)
            except Exception as e:
                logger.debug("Clipboard restore failed: %s", e)

        threading.Thread(target=_restore, daemon=True,
                         name="ClipboardRestore").start()

    # --- pynput fallback ----------------------------------------------------

    def _type_via_pynput(self, text: str) -> bool:
        try:
            keyboard = self._load_keyboard()
            keyboard.Controller().type(text)
            logger.debug("Typed via pynput Controller().type()")
            return True
        except Exception as e:
            logger.error("pynput type failed: %s", e)
            return False
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_typer.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/typer.py tests/test_typer.py && git commit -m "feat(core): rework TextTyper to clipboard-paste primary + pynput fallback, mac a11y gate"
```

---

### Task 7: `core/audio.py` — sounddevice reimplementation

**Files:**
- Modify: `app/core/audio.py`
- Test: `tests/test_audio.py`

**Steps:**
- [ ] Write the failing test `tests/test_audio.py`. It mocks `sounddevice.InputStream` so the recorder works with no audio hardware:
```python
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
```
- [ ] Run it (expect FAIL — still PyAudio-based):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_audio.py -q
```
  Expected: failures (`_load_sounddevice` missing, `start()` tries PyAudio).
- [ ] Replace the entire contents of `app/core/audio.py` with:
```python
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
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_audio.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/audio.py tests/test_audio.py && git commit -m "feat(core): reimplement AudioRecorder on sounddevice (same public API)"
```

---

### Task 8: `core/devices.py` — sounddevice enumeration

**Files:**
- Modify: `app/core/devices.py`
- Test: `tests/test_devices.py`

**Steps:**
- [ ] Write the failing test `tests/test_devices.py`:
```python
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
```
- [ ] Run it (expect FAIL — still PyAudio-based):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_devices.py -q
```
  Expected: failures (`_load_sounddevice` missing).
- [ ] Replace the entire contents of `app/core/devices.py` with:
```python
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
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_devices.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/devices.py tests/test_devices.py && git commit -m "feat(core): enumerate input devices via sounddevice.query_devices()"
```

---

### Task 9: `core/notifications.py` — desktop-notifier wrapper

**Files:**
- Create: `app/core/notifications.py`
- Test: `tests/test_notifications.py`

**Steps:**
- [ ] Write the failing test `tests/test_notifications.py`:
```python
"""Tests for the Notifier wrapper (desktop-notifier mocked / absent)."""
from unittest.mock import MagicMock, patch

from core.notifications import Notifier


def test_notify_sends_through_backend():
    backend = MagicMock()
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=backend):
        n.notify("Yapper", "Transcribed")
    backend.send_sync.assert_called_once()
    kwargs = backend.send_sync.call_args.kwargs
    assert kwargs.get("title") == "Yapper"
    assert kwargs.get("message") == "Transcribed"


def test_notify_is_noop_when_backend_unavailable():
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=None):
        # Must not raise.
        n.notify("Yapper", "no backend")


def test_notify_swallows_backend_errors():
    backend = MagicMock()
    backend.send_sync.side_effect = RuntimeError("notification center down")
    n = Notifier()
    with patch.object(n, "_get_backend", return_value=backend):
        # Must degrade gracefully, not raise.
        n.notify("Yapper", "boom")
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_notifications.py -q
```
  Expected: `ModuleNotFoundError`.
- [ ] Create `app/core/notifications.py`:
```python
"""
Yapper Notifications
====================
Thin wrapper over desktop-notifier. Degrades to a no-op when notifications are
unavailable (e.g. an unsigned macOS build with no Notification Center access);
the recording HUD remains the primary feedback channel.

© 2026 Cloudelipute
"""

from typing import Optional

from .logger import get_logger

logger = get_logger("notifications")


class Notifier:
    """Sends desktop notifications, silently no-op'ing when unsupported."""

    def __init__(self, app_name: str = "Yapper"):
        self.app_name = app_name
        self._backend = None
        self._tried = False

    def _get_backend(self):
        """Lazily build a DesktopNotifier, or None if it can't be created."""
        if self._tried:
            return self._backend
        self._tried = True
        try:
            from desktop_notifier import DesktopNotifier
            self._backend = DesktopNotifier(app_name=self.app_name)
        except Exception as e:
            logger.info("Notifications unavailable (%s); using HUD only", e)
            self._backend = None
        return self._backend

    def notify(self, title: str, message: str) -> None:
        backend = self._get_backend()
        if backend is None:
            return
        try:
            backend.send_sync(title=title, message=message)
        except Exception as e:
            logger.debug("Notification failed: %s", e)
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_notifications.py -q
```
  Expected: all pass.
  // verify against docs: desktop-notifier 6.x exposes async `send()`; `send_sync()` is the blocking helper used here.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/notifications.py tests/test_notifications.py && git commit -m "feat(core): add Notifier over desktop-notifier with graceful degrade"
```

---

### Task 10: Wire new modules into `core/__init__.py`

**Files:**
- Modify: `app/core/__init__.py`
- Test: `tests/test_core_exports.py` (Create)

**Steps:**
- [ ] Write the failing test `tests/test_core_exports.py`:
```python
"""The new Phase 1 symbols must be importable from the core package."""
import core


def test_new_symbols_exported():
    from core import (
        HotkeyManager,
        TextTyper,
        AudioRecorder,
        AudioDevice,
        Notifier,
        PermissionStatus,
        permission_status,
    )
    assert HotkeyManager is not None
    assert Notifier is not None
    assert callable(permission_status)


def test_platform_flags_exported():
    from core import IS_MAC, IS_WIN
    assert isinstance(IS_MAC, bool)
    assert isinstance(IS_WIN, bool)


def test_all_lists_new_symbols():
    for name in ("HotkeyManager", "Notifier", "PermissionStatus",
                 "permission_status", "IS_MAC", "IS_WIN"):
        assert name in core.__all__
```
- [ ] Run it (expect FAIL — not exported):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_core_exports.py -q
```
  Expected: `ImportError`.
- [ ] In `app/core/__init__.py`, add new imports immediately after the existing `from .typer import TextTyper` line:
```python
# Platform
from .platform import IS_MAC, IS_WIN, IS_LINUX, default_hotkey, open_settings_pane, open_folder

# Permissions
from .permissions import (
    PermissionStatus,
    permission_status,
    microphone_ok,
    accessibility_trusted,
    input_monitoring_ok,
)

# Hotkeys
from .hotkeys import HotkeyManager

# Notifications
from .notifications import Notifier
```
- [ ] In `app/core/__init__.py`, extend `__all__`. Insert these entries right after the `"TextTyper",` line inside the `__all__` list:
```python
    # Platform
    "IS_MAC",
    "IS_WIN",
    "IS_LINUX",
    "default_hotkey",
    "open_settings_pane",
    "open_folder",
    # Permissions
    "PermissionStatus",
    "permission_status",
    "microphone_ok",
    "accessibility_trusted",
    "input_monitoring_ok",
    # Hotkeys
    "HotkeyManager",
    # Notifications
    "Notifier",
```
- [ ] Run the test (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_core_exports.py -q
```
  Expected: all pass.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/__init__.py tests/test_core_exports.py && git commit -m "feat(core): export platform/permissions/hotkeys/notifications from core package"
```

---

### Task 11: Full Phase 1 suite green + lint gate

**Files:**
- Test: all of `tests/` (no new files)

**Steps:**
- [ ] Run the entire Phase 1 test suite (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_platform.py tests/test_permissions.py tests/test_hotkeys.py tests/test_typer.py tests/test_audio.py tests/test_devices.py tests/test_notifications.py tests/test_constants_migration.py tests/test_core_exports.py -q
```
  Expected: all tests pass, no errors.
- [ ] Confirm no legacy Windows-only typing libs remain referenced in the reworked typer (regression guard):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -rnE "import keyboard|import pyautogui|isascii" app/core/typer.py app/core/audio.py app/core/devices.py || echo "CLEAN: no legacy libs"
```
  Expected: `CLEAN: no legacy libs`.
- [ ] Confirm the whole `core` package imports cleanly on this headless Linux box (no pynput/sounddevice/pyobjc installed):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && PYTHONPATH=app python -c "import core; print('core import OK', core.__version__)"
```
  Expected: `core import OK 4.0.0`.
- [ ] Commit any final formatting/no-op tidy (skip if nothing changed):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add -A && git commit -m "test: green Phase 1 cross-platform core suite" --allow-empty
```

---

## Done criteria for Phase 1

- [ ] `core/platform.py`, `core/permissions.py`, `core/hotkeys.py`, `core/notifications.py` exist with the exact signatures in the shared interface contracts.
- [ ] `core/typer.py` uses `type_text(text, method='paste')`, clipboard-paste primary with daemon-thread restore, pynput fallback, mac Accessibility gate, and contains no `isascii` branch and no `keyboard`/`pyautogui` imports.
- [ ] `core/audio.py` and `core/devices.py` run on `sounddevice` with their original public APIs intact.
- [ ] `constants.py` has `activation_mode='push_to_talk'` and `insertion_method='paste'` (plus schema validators), `VERSION='4.0.0'`, and Mac-friendly single F-keys; `config.py` migrates legacy `always_listening`.
- [ ] Every module imports and every test passes headless on Linux with pynput/sounddevice/pyobjc/desktop-notifier absent (all lazily imported and mocked in tests).
