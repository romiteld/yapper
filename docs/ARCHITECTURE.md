<div align="center">

# Yapper — Architecture

Cross‑platform push‑to‑talk dictation. One codebase runs on macOS (Apple Silicon) and Windows.
PySide6/Qt owns a single event loop; platform differences are isolated behind thin abstractions.

</div>

---

## 1. System overview

Layered: a Qt **UI layer** talks to a headless **Controller**, which orchestrates the **core** modules. The core is platform‑agnostic; only `hotkeys`, `permissions`, `typer`, `notifications`, and `platform` touch OS‑specific APIs, and each degrades gracefully off its native platform.

```mermaid
flowchart TB
    subgraph UI["UI layer · PySide6 / Qt (single event loop)"]
        direction LR
        tray["Tray<br/>QSystemTrayIcon"]
        wizard["Setup Wizard"]
        settings["Settings"]
        hud["Recording HUD"]
        history_ui["History"]
    end

    subgraph CTRL["Controller · app/ui/controller.py"]
        ctl["state machine + pipeline<br/>idle → listening → transcribing → done"]
        bridge["_Bridge(QObject)<br/>cross-thread Qt signals"]
    end

    subgraph CORE["Core · app/core (platform-agnostic)"]
        direction LR
        hotkeys["hotkeys<br/>pynput PTT/toggle"]
        audio["audio + vad<br/>sounddevice"]
        engines["engines<br/>cloud / local STT"]
        fmt["formatting + vocabulary<br/>faithful 'no-slop'"]
        typer["typer<br/>clipboard-paste"]
        hist["history"]
        notif["notifications"]
    end

    subgraph PLAT["Platform + external"]
        direction LR
        perms["permissions<br/>macOS TCC"]
        api["api · OpenAI 2.x"]
        local["local Whisper<br/>mlx / faster-whisper"]
        os["OS: mic · clipboard · keys · tray"]
    end

    UI <-->|Qt signals/slots| CTRL
    CTRL --> hotkeys & audio & engines & fmt & typer & hist & notif
    hotkeys --> perms
    typer --> perms
    engines --> api
    engines --> local
    audio --> os
    typer --> os
    hotkeys --> os

    classDef ext fill:#1b1b22,stroke:#ec2a8e,color:#fff;
    class perms,api,local,os ext;
```

---

## 2. Threading model

The single most important design constraint. Three threads cooperate; **all** cross‑thread communication goes through `_Bridge` Qt signals (queued), so no widget is ever touched off the GUI thread, and the blocking transcription/API call never freezes the UI.

```mermaid
flowchart LR
    subgraph T1["pynput listener thread"]
        hk["HotkeyManager<br/>on_press / on_release"]
    end
    subgraph T2["Qt GUI / main thread"]
        bridgeq["_Bridge signals (queued)"]
        controller["Controller"]
        widgets["Tray · HUD · windows"]
    end
    subgraph T3["worker thread (per dictation)"]
        pipe["record.stop → VAD →<br/>engine.transcribe →<br/>Formatter → TextTyper.paste"]
    end

    hk -->|"emit hotkey_start / hotkey_stop"| bridgeq
    bridgeq --> controller
    controller -->|"spawn"| pipe
    pipe -->|"emit state_changed / level / result / error"| bridgeq
    bridgeq --> widgets
```

**Rules enforced in code**
- Hotkey callbacks (background thread) only `emit()` signals — never call Controller/Qt directly.
- Recording + the network/transcription call run on a worker thread, so the GUI never blocks.
- Widget mutation happens only on the GUI thread, driven by queued signals.

---

## 3. Dictation lifecycle

Push‑to‑talk: hold the key, speak, release. The result is pasted at the cursor.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant HK as HotkeyManager<br/>(listener thread)
    participant C as Controller<br/>(GUI thread)
    participant HUD
    participant W as Worker thread
    participant Eng as Engine (cloud/local)
    participant F as Formatter
    participant Typer

    User->>HK: hold hotkey
    HK-->>C: hotkey_start (signal)
    C->>HUD: state = listening (waveform)
    C->>W: start AudioRecorder (sounddevice)
    User->>HK: release hotkey
    HK-->>C: hotkey_stop (signal)
    C->>W: stop recording
    W->>W: VAD — speech present?
    alt silence
        W-->>HUD: state = idle
    else speech
        C->>HUD: state = transcribing
        W->>Eng: transcribe(wav, prompt = vocabulary bias)
        Eng-->>W: raw text
        W->>F: format(text, mode=clean, …)
        Note over F: spoken-symbols → vocab correct →<br/>LLM clean (no paraphrase) → optional translate
        F-->>W: faithful text
        W->>Typer: paste at cursor (Cmd/Ctrl+V)
        W-->>HUD: state = done ✓
        W-->>C: result → history.add() + notify
    end
    HUD-->>HUD: back to idle
```

---

## 4. Transcription engine abstraction

Cloud and on‑device engines share one interface, selected at runtime from settings. Default is cloud; on‑device is an optional install (`uv sync --extra local`).

```mermaid
classDiagram
    class TranscriptionEngine {
        <<abstract>>
        +transcribe(wav_path, language, prompt) str
    }
    class CloudEngine {
        APIClient client
        +transcribe() str
    }
    class LocalEngine {
        lazy backend
        +transcribe() str
    }
    class APIClient {
        +transcribe(model=gpt-4o-mini-transcribe, prompt=)
        +chat(model=gpt-5-nano, reasoning_effort=minimal)
    }
    TranscriptionEngine <|-- CloudEngine
    TranscriptionEngine <|-- LocalEngine
    CloudEngine --> APIClient
    LocalEngine --> mlx_whisper
    LocalEngine --> faster_whisper
```

`get_engine(settings)` returns the configured engine (raises on unknown names). The vocabulary's `whisper_prompt()` is passed as the transcription `prompt=` bias to improve accuracy on names/terms.

---

## 5. The faithful formatting pipeline ("no slop")

The product promise: type what you actually said — your wording, voice, and slang **and** any jargon/code — and never reword it. Cleanup fixes only mechanics.

```mermaid
flowchart LR
    raw["raw transcript"] --> sym{"expand spoken<br/>symbols?"}
    sym -->|on| s["conservative symbol rules<br/>'dash dash help' → --help<br/>(guarded against prose)"]
    sym -->|off| v
    s --> v["vocabulary.correct()<br/>explicit mis-hear map only<br/>'cube cuttle' → kubectl"]
    v --> mode{"output mode"}
    mode -->|verbatim| out["paste"]
    mode -->|clean default| clean["LLM: fix caps/punct + fillers,<br/>NEVER paraphrase, preserve<br/>voice + jargon/code"]
    mode -->|polished| pol["LLM: tidy-prose rewrite<br/>(still preserves code)"]
    clean --> tr
    pol --> tr
    tr{"translate?"} -->|yes| t["translate, leave code intact"]
    tr -->|no| out
    t --> out
```

Deterministic stages (symbols, vocabulary) are tuned so casual speech passes through **unchanged** — e.g. "i use pnpm instead of npm" and "the dot product" are never rewritten — while CLI/code dictation still converts.

---

## 6. UI surfaces & actions

What the user actually sees and clicks. The menu‑bar/tray is the always‑present control; the wizard runs once; settings/history open on demand; the HUD appears only during dictation.

```mermaid
flowchart TB
    subgraph Tray["Menu-bar / tray · QSystemTrayIcon (always present)"]
        t_eng["Engine: Cloud / Local"]
        t_mode["Mode: Clean / Polished / Verbatim"]
        t_lang["Language: off / 40+"]
        t_set["Settings…"]
        t_hist["History…"]
        t_quit["Quit"]
    end
    subgraph HUD["Recording HUD (during dictation)"]
        h["idle to listening (live level ring) to transcribing to done"]
    end
    subgraph Wizard["First-run wizard (once)"]
        w["Welcome to Engine to Connect to Permissions (mac) to Hotkey and Voice to Done"]
    end
    subgraph Settings["Settings sidebar (applied on Save)"]
        s["General / Engine and Models / Vocabulary / Formatting / Hotkeys / Audio / History / About"]
    end
    subgraph Hist["History window"]
        hi["search / copy / re-insert / reprocess / clear / export"]
    end
    t_set --> Settings
    t_hist --> Hist
```

- **Tray quick toggles** flip engine / output mode / language inline and persist immediately; everything else lives in **Settings**, where edits are buffered and applied only on **Save** (close‑without‑save discards).
- **No GUI required:** `python -m app` runs the tray app; `python -m app --once [--seconds N]` does a single scripted record→type with no tray/HUD.

---

## 7. Package layout

```
app/
├── __main__.py            # python -m app → cli → ui.app.main()  (--once for scripted single-shot)
├── cli.py
├── core/                  # platform-agnostic logic (heavily unit-tested)
│   ├── hotkeys.py         # pynput PTT / toggle / wake-word + auto-repeat guard
│   ├── permissions.py     # macOS TCC detection (no-op True off-mac)
│   ├── typer.py           # clipboard-paste primary, pynput type fallback
│   ├── audio.py/devices.py# sounddevice capture + device enumeration
│   ├── vad.py             # voice-activity detection
│   ├── notifications.py   # desktop-notifier wrapper
│   ├── platform.py        # IS_MAC/IS_WIN, default hotkey, settings deep-links
│   ├── engines/           # base · cloud · local · get_engine()
│   ├── formatting.py      # Clean/Polished/Verbatim + spoken symbols
│   ├── vocabulary.py      # Whisper bias + fuzzy mis-hear correction
│   ├── transcriber.py     # orchestrates engine + formatter
│   ├── api.py             # OpenAI 2.x client (retry)
│   ├── config.py/constants.py
│   └── sounds.py · history.py · logger.py
└── ui/                    # PySide6
    ├── app.py             # YapperApp · QSystemTrayIcon · _Bridge · main()
    ├── controller.py      # headless state machine + pipeline
    ├── hud.py             # frameless always-on-top recording pill
    ├── wizard.py          # first-run setup (Permissions step macOS-only)
    ├── settings_window.py # sidebar settings
    ├── history_window.py  # searchable history
    └── theme.py           # dark QSS, accent #ec2a8e
```

---

## 8. Key design decisions

- **One Qt event loop** (PySide6) for tray + HUD + wizard + settings, avoiding the macOS main‑thread contention that a separate tray library would create.
- **`pynput`** for both global hotkey capture **and** keystroke/paste injection, cross‑platform (replaced the Windows‑only `keyboard`).
- **Clipboard‑paste insertion** (⌘/Ctrl+V) as the primary path — Unicode/emoji/CJK‑safe — with `pynput` typing as a fallback.
- **`sounddevice`** for audio (bundles PortAudio in its wheels, removing the macOS PyAudio build problem).
- **Engine interface** so cloud and on‑device transcription are interchangeable; cloud default keeps the base install light.
- **Faithful formatting** with deterministic, conservative text transforms plus a strict no‑paraphrase LLM prompt.
- **Clone‑first** distribution via `uv`; unsigned `.app`/`.dmg`/`.zip` attached to Releases as a convenience.

## 9. Cross-platform notes

| Concern | macOS | Windows |
|---|---|---|
| Hotkeys / typing | needs Accessibility + Input Monitoring (detected, guided; fails silently otherwise) | works without special grants |
| Microphone | `NSMicrophoneUsageDescription` prompt | OS prompt |
| Notifications | Notification Center (signed builds) — HUD is the always‑on fallback | WinRT toasts |
| Tray | `QSystemTrayIcon` | `QSystemTrayIcon` |
| First launch (unsigned) | `xattr -dr com.apple.quarantine` or Open Anyway | run normally |
