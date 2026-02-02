# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Yapper is a portable Windows desktop application for speech-to-text transcription. It uses OpenAI's Whisper API for transcription and GPT-4.1-nano for translation/grammar correction. The application includes an embedded Python 3.11 runtime—no Python installation required.

**Two modes:**
- **System Tray mode** (`yapper_tray.py` v3.0.0) - Default. Background app with wake word detection ("Yapper start/stop")
- **Console mode** (`yapper.py` v2.0.0) - Single-shot hotkey-based recording

## Running the Application

```batch
# First-time setup (installs pip packages into embedded Python)
INSTALL.bat

# Run the application (launches tray mode)
Yapper.bat

# Open settings
Settings.bat

# Direct execution for testing
python\python.exe app\yapper.py        # Console mode
python\pythonw.exe app\yapper_tray.py  # Tray mode (no console)
python\python.exe app\settings_ui.py   # GUI settings
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

Installed via INSTALL.bat into `python/`:
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
python/                # Embedded Python 3.11 runtime
*.bat                  # Windows launchers
```

## Platform Notes

- **Windows-only** - Uses batch files and Windows-specific keyboard library
- `keyboard` library may require admin privileges on some Windows versions
- PyAudio can fail to auto-install; manual wheel installation documented in README.md
