# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Yapper is a **cross-platform** (macOS Apple Silicon + Windows) push-to-talk speech-to-text app for engineers. It records your voice, transcribes it (cloud or on-device), cleans it up **without "AI slop"** (technical terms/code/identifiers preserved verbatim), and pastes it at the cursor. Clone-first and `uv`-managed — no embedded runtime.

- **Transcription:** cloud `gpt-4o-mini-transcribe` (default) or on-device `mlx-whisper`/`faster-whisper`, behind a `TranscriptionEngine` interface.
- **Text cleanup / translation:** `gpt-5-nano` with `reasoning_effort='minimal'` (the old `gpt-4.1-nano` is deprecated, shutting down 2026-10-23).
- **Activation:** push-to-talk (default), toggle, or wake word.

> **Active reimagining (v4).** The app is being rebuilt to the design in
> [`docs/superpowers/specs/2026-05-30-yapper-reimagining-design.md`](docs/superpowers/specs/2026-05-30-yapper-reimagining-design.md),
> executed phase-by-phase via the plans in [`docs/superpowers/plans/`](docs/superpowers/plans/)
> (index: `2026-05-30-yapper-v4-implementation.md`). Phase 0 (repo hygiene) is done.
> The legacy entry points (`app/yapper_tray.py`, `app/yapper.py`, `app/settings_ui.py`,
> `app/settings_console.py`) still exist but are **retired in Phase 4** when the PySide6 app lands.

## Running the Application

```bash
# First-time setup (creates .venv, installs deps via uv)
./setup            # POSIX (macOS/Linux); setup.bat on Windows

# Run the application
./run.sh           # macOS/Linux; run.command (macOS double-click); run.bat (Windows)

# Run directly / for testing
uv run python -m app        # the app (Phase 0: prints version; PySide6 app lands in Phase 4)
uv run pytest               # run the test suite
uv sync --extra local       # add on-device transcription engines
```

## Architecture (target v4)

```
[Hotkey: PTT/toggle] → [AudioRecorder] → [TranscriptionEngine] → [Formatter] → [TextTyper]
   (pynput)              (sounddevice + VAD)   (cloud / on-device)   (no-slop)    (clipboard-paste)
                                                                        │
                                              vocabulary → Whisper prompt bias
```

PySide6/Qt owns one event loop for the tray (`QSystemTrayIcon`), first-run wizard, settings,
recording HUD, and history window. Platform differences are isolated behind thin abstractions
(`hotkeys`, `permissions`, `typer`, `notifications`).

**Key classes (in `app/core/` + `app/ui/`):**
- `AudioRecorder` (`core/audio.py`) - sounddevice capture at 16 kHz mono
- `HotkeyManager` (`core/hotkeys.py`) - pynput global push-to-talk / toggle / wake word
- `TranscriptionEngine` (`core/engines/`) - `CloudEngine` (OpenAI) + `LocalEngine` (mlx/faster-whisper)
- `Formatter` + `Vocabulary` (`core/formatting.py`, `core/vocabulary.py`) - the no-slop pipeline (Technical/Natural/Verbatim modes, spoken symbols, vocabulary bias)
- `TextTyper` (`core/typer.py`) - clipboard-paste (⌘/Ctrl+V) primary, pynput type fallback
- `RecordingHUD` (`app/ui/hud.py`) - frameless always-on-top pill with live waveform

## Dependencies

Managed via `uv` / `pyproject.toml`:
- `openai` (2.x) - transcription + text models
- `pynput` - global hotkeys **and** keystroke/paste injection (cross-platform)
- `sounddevice` - audio capture (bundles portaudio; replaces PyAudio)
- `pyperclip` - clipboard (for paste insertion)
- `PySide6` - Qt UI (settings, wizard, HUD, tray)
- `desktop-notifier` - cross-platform notifications
- `rapidfuzz` - fuzzy vocabulary correction
- `Pillow` - icons
- `[local]` extra: `mlx-whisper` (macOS arm64) / `faster-whisper` (Windows/Linux)
- `[macos]` extra: `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices` (TCC permission checks)
- `dev` extra: `pytest`, `pytest-qt`, `pyinstaller`

## Configuration

Settings stored in `app/settings.json` (gitignored). Source of truth: `app/core/constants.py`
(`DEFAULT_SETTINGS` + `SETTINGS_SCHEMA`). Notable keys: `api_key`, `activation_mode`
(`push_to_talk`/`toggle`/`wake_word`), `hotkey`, `engine` (`cloud`/`local`), `cloud_stt_model`,
`text_model`, `output_mode` (`technical`/`natural`/`verbatim`), `expand_spoken_symbols`,
`vocabulary`, `insertion_method` (`paste`/`type`), `translate_to`, `language_hint`,
`vad_enabled`, `show_hud`.

## File Structure

```
app/
├── __main__.py        # entry point: python -m app (PySide6 app wired in Phase 4)
├── core/              # platform-agnostic logic
│   ├── constants.py   # VERSION, LANGUAGES, HOTKEYS, DEFAULT_SETTINGS, SCHEMA
│   ├── config.py      # Settings load/save/validate/migrate
│   ├── audio.py / devices.py   # sounddevice capture + device enumeration
│   ├── hotkeys.py     # pynput HotkeyManager (added Phase 1)
│   ├── permissions.py # macOS TCC detection (added Phase 1)
│   ├── typer.py       # clipboard-paste / pynput insertion
│   ├── notifications.py # desktop-notifier wrapper (added Phase 1)
│   ├── engines/       # TranscriptionEngine: cloud + local (added Phase 2)
│   ├── formatting.py / vocabulary.py  # no-slop subsystem (added Phase 3)
│   ├── api.py / transcriber.py / vad.py / sounds.py / history.py / logger.py
│   └── (legacy: yapper_tray.py, yapper.py, settings_ui.py — retired in Phase 4)
├── ui/                # PySide6 app, wizard, settings, hud, history (added Phase 4)
pyproject.toml         # uv-managed deps + [local]/[macos]/dev extras
setup / setup.bat      # uv sync bootstrap
run.sh/.command/.bat   # thin launchers -> uv run python -m app
tests/                 # pytest suite (conftest + smoke; grows per phase)
```

## Platform Notes

- **Cross-platform** (macOS Apple Silicon + Windows; Linux best-effort).
- **macOS** needs Microphone, Accessibility (paste/type), and Input Monitoring (hotkey capture)
  permissions. macOS re-reads these only at process start — **quit & relaunch after granting**.
  `pynput` injection **fails silently** without Accessibility; `permissions.py` detects this and the
  wizard guides the user.
- **Windows** needs no special grants (global hotkeys may need an elevated terminal in some configs).
- Distribution is **clone-first** (`uv`); unsigned `.app`/`.dmg` + `.zip` are attached to Releases
  (macOS first launch: `xattr -dr com.apple.quarantine /Applications/Yapper.app`).
