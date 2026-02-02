# Yapper - Portable Edition

```
╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐
╚╦╝├─┤├─┘├─┘├┤ ├┬┘
 ╩ ┴ ┴┴  ┴  └─┘┴└─
```

**Speech-to-Text Tool** — Speak and type anywhere with a single hotkey.

This is the **Portable Edition** - no Python installation required! Just unzip and run.

## Quick Start (3 Steps)

### Step 1: First-Time Setup
1. **Unzip** this folder anywhere you like
2. **Double-click `INSTALL.bat`**
3. Wait for dependencies to install (2-3 minutes)

### Step 2: Get Your API Key
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)

### Step 3: Configure & Run
1. The Settings window opens automatically after install
2. Paste your API key
3. Click "Save & Launch Yapper"
4. **Done!** Press F8 to start/stop recording

## Files

| File | What it does |
|------|--------------|
| `INSTALL.bat` | First-time setup (run once) |
| `Yapper.bat` | Main application |
| `Settings.bat` | Change settings anytime |
| `Create Desktop Shortcuts.bat` | Add shortcuts to your desktop |

## How to Use

1. Click where you want to type (email, document, browser, etc.)
2. Press **F8** to start recording
3. Speak clearly into your microphone
4. Press **F8** again to stop
5. Your words appear at the cursor!

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F8** | Start/Stop recording |
| **S** | Open Settings |
| **ESC** | Exit Yapper |

## Features

- **No Installation Required** - Portable Python included
- **Universal Typing** - Works in any application
- **Excellent Accuracy** - OpenAI Whisper model
- **Translation** - Speak English, output in 28+ languages
- **Modern Settings UI** - Easy configuration

## Troubleshooting

### "First-time setup required"
Run `INSTALL.bat` first. This only needs to be done once.

### PyAudio installation fails
Audio recording requires PyAudio. If it fails to install automatically:
1. Download the wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
2. Choose `PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl`
3. Copy it to the `python` folder
4. Run: `python\python.exe -m pip install PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl`

### No audio recorded
- Check your microphone is connected
- Make sure it's set as default in Windows Sound settings

### API key error
- Verify your key in Settings
- Check you have credits at platform.openai.com

## Cost

- **Transcription**: ~$0.006 per minute
- **Translation**: ~$0.001 per request

A typical 30-second recording costs less than a penny.

---

**Copyright © 2026 Cloudelipute. All rights reserved.**
