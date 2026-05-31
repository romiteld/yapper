# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Yapper is a cross-platform push-to-talk speech-to-text application for engineers. It uses OpenAI's Whisper API for transcription and GPT-4.1-nano for translation/grammar correction. Clone-first, uv-managed — Python runtime is managed automatically by uv.

**Two modes:**
- **System Tray mode** (`yapper_tray.py` v3.0.0) - Default. Background app with wake word detection ("Yapper start/stop")
- **Console mode** (`yapper.py` v2.0.0) - Single-shot hotkey-based recording

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

## Architecture

```
[Hotkey/Wake Word] → [AudioRecorder] → [Whisper API] → [GPT Translation/Grammar] → [TextTyper]
                          ↓
                    PyAudio 16kHz mono
```

**Key classes:**
- `AudioRecorder` - PyAudio capture at 16kHz mono
- `WakeWordListener` - Continuous 3-second clip monitoring with fuzzy matching (Levenshtein > 0.75)
- `Transcriber` - Whisper API + optional GPT-4.1-nano post-processing
- `TextTyper` - Uses `keyboard` library to type at cursor position

## Dependencies

Managed via `uv` / `pyproject.toml`:
- `openai` - API client
- `keyboard` - Global hotkey capture (Windows-specific)
- `pyaudio` - Audio recording
- `pystray` - System tray
- `Pillow` - Tray icon
- `customtkinter` - GUI settings (auto-installed on first use)

## Configuration

Settings stored in `app/settings.json`:
- `api_key` - OpenAI API key
- `hotkey` - f8, f9, f10, f12, pause, scroll lock
- `translate_to` - Target language code (empty = same language)
- `language_hint` - Input language hint for Whisper
- `fix_grammar` - Auto-correct when not translating
- `wake_word_fuzzy` - Fuzzy matching for wake words

## File Structure

```
app/
├── yapper.py          # Console mode main app
├── yapper_tray.py     # Tray mode main app (default)
├── settings_ui.py     # customtkinter GUI settings
├── settings_console.py # CLI settings fallback
└── settings.json      # Configuration
pyproject.toml         # uv-managed deps + dev/[local] extras
setup / setup.bat      # uv sync bootstrap
run.sh/.command/.bat   # thin launchers -> uv run python -m app
tests/                 # pytest suite (conftest + smoke)
```

## Platform Notes

- **Windows-only** - Uses batch files and Windows-specific keyboard library
- `keyboard` library may require admin privileges on some Windows versions
- PyAudio can fail to auto-install; manual wheel installation documented in README.md
