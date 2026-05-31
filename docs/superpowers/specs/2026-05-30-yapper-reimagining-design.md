# Yapper — Cross‑Platform Reimagining (Design Spec)

**Date:** 2026‑05‑30
**Status:** Approved for planning
**Author:** brainstorming session
**Topic:** Port Yapper to macOS Apple Silicon + full UI/UX reimagining, open‑sourced clone‑first.

---

## 1. Goal & context

Yapper is a speech‑to‑text utility that records the user's voice, transcribes it, optionally translates / cleans it, and types the result at the cursor. Today it is **Windows‑only** (ships an embedded Windows Python runtime, uses the Windows‑only `keyboard` library, a PowerShell notification, and a `customtkinter` settings window).

This project does two things at once:

1. **Make it run first‑class on macOS Apple Silicon (M3/M4/M5)** while keeping Windows first‑class — one cross‑platform codebase.
2. **Reimagine the UI/UX** to 2026 standards (guided onboarding, a floating recording HUD, push‑to‑talk, modern settings, native notifications) **and** add the features that make it genuinely useful to software engineers.

It will be **open‑sourced on GitHub, clone‑first**: the primary install path is `git clone` + a one‑command setup; prebuilt **unsigned** `.app`/`.dmg` (macOS) and `.zip` (Windows) are attached to Releases as a convenience.

### Non‑negotiable product requirements (from the user)

- **No "AI slop."** Output must faithfully preserve technical terms, code identifiers, CLI flags, file paths, and product/library names — the kind of text an engineer dictates when prompting an AI agent or writing docs. The cleanup step must **never paraphrase** technical phrasing.
- **No personal information** in code, comments, or README. (Scan confirmed: the only identifier present is the brand `Cloudelipute`, which **stays** — normalized to `© 2026 Cloudelipute`. No real name/email exists in tracked files.)
- **`.claude/` must not ship** — already untracked and in `.gitignore` (verified).
- **Upgraded README** with diagrams.
- **QA finale:** after the build, fan out parallel review agents (quality + missing logic + cross‑platform correctness), auto‑fix everything that surfaces, then re‑verify.

---

## 2. Locked decisions

| Area | Decision | Rationale (May 2026 research) |
|---|---|---|
| Scope | Full reimagining | User choice. |
| Platforms | Windows + macOS (Apple Silicon) first‑class; Linux best‑effort | Single cross‑platform codebase. |
| **STT engine** | **Both**, user‑switchable, default **cloud** | Cloud = `gpt-4o-mini-transcribe`; on‑device = `mlx-whisper`/`whisper.cpp` (mac), `faster-whisper` (win). |
| Cloud STT model | `gpt-4o-mini-transcribe` (default), `whisper-1` selectable | ~50% cheaper (~$0.003/min), more accurate, same SDK call; whisper‑1 kept for long‑tail langs / timestamps. |
| **Text model** | **`gpt-5-nano`** (default), `gpt-5.4-nano` optional, `reasoning_effort='minimal'` | **`gpt-4.1-nano` is deprecated, shuts down 2026‑10‑23.** Must migrate. |
| OpenAI SDK | Upgrade to `openai` 2.x (≥2.38) | Needed for new model names + reasoning params. |
| **Activation** | **Push‑to‑talk default**, toggle selectable, wake‑word optional | Modern default; PTT via `pynput` `on_press`/`on_release`. |
| **Hotkeys + typing** | **`pynput` ≥1.8.2** | One lib does capture **and** injection on Win+Mac+Linux; replaces Windows‑only `keyboard`. |
| Text insertion | **clipboard‑paste (⌘/Ctrl+V) primary**, `pynput.type()` fallback | Unicode/emoji/CJK‑safe; fixes racy clipboard restore. |
| **Audio** | **`sounddevice`** (replaces PyAudio) | PyAudio has no macOS wheel; sounddevice bundles portaudio in its wheels (kills #1 packaging risk). |
| **UI toolkit** | **PySide6 / Qt** | Settings + wizard + HUD + tray (`QSystemTrayIcon`) in one event loop; near‑native on macOS; dodges pystray/rumps main‑thread contention. |
| Notifications | **`desktop-notifier`** + the HUD | Cross‑platform; HUD is primary feedback so unsigned‑app notification limits don't bite. |
| Distribution | clone‑first via **`uv`** + unsigned `.app`/`.dmg`/`.zip` on Releases | No Apple fee. Document Gatekeeper `xattr` workaround (Sequoia/Tahoe removed right‑click‑Open). |
| Packaging tool | `PyInstaller` (cross‑platform) primary; `py2app` acceptable for mac | Both build arm64 `.app`; PyInstaller reuses one pipeline for Win+Mac. |
| Attribution | `© 2026 Cloudelipute` | User choice (keep brand, add ©). |

---

## 3. Target architecture

Layered, cross‑platform, single codebase. Platform differences are isolated behind thin abstractions; the UI and core logic are platform‑agnostic.

```
                         ┌─────────────────────────────────────────┐
                         │  UI layer (PySide6 / Qt — one event loop)│
                         │  app · tray · wizard · settings · HUD ·  │
                         │  history · notifications                 │
                         └───────────────▲─────────────────────────┘
                                         │ Qt signals/slots
        ┌────────────────────────────────┼────────────────────────────────┐
        │                         Controller (app orchestrator)            │
        │   wires hotkeys → record → engine → formatting → insert → HUD    │
        └───▲──────────▲───────────▲───────────▲───────────▲───────────▲───┘
            │          │           │           │           │           │
     ┌──────┴───┐ ┌────┴────┐ ┌────┴─────┐ ┌───┴─────┐ ┌───┴────┐ ┌────┴────┐
     │ hotkeys  │ │ audio   │ │ engines  │ │formatting│ │ typer  │ │ history │
     │ (pynput) │ │(sounddev│ │ (STT)    │ │ no-slop  │ │(pynput/│ │         │
     │ PTT/togg │ │ +vad)   │ │cloud/loc │ │vocab/mode│ │clip)   │ │         │
     └────┬─────┘ └─────────┘ └────┬─────┘ └──────────┘ └────────┘ └─────────┘
          │                        │
   ┌──────┴───────┐         ┌──────┴───────────────┐
   │ permissions  │         │ api (OpenAI 2.x) /   │
   │ (mac TCC)    │         │ local model runtimes │
   └──────────────┘         └──────────────────────┘
            platform.py  ·  config.py  ·  constants.py  ·  logger.py
```

### Module map (evolution of `app/core/` + new packages)

**Existing → changed**
- `core/audio.py` — `AudioRecorder` reimplemented on **`sounddevice`** (same public API: `start()`/`stop()/frames/duration`). 16 kHz mono int16.
- `core/devices.py` — `list_input_devices()` via `sounddevice.query_devices()`.
- `core/typer.py` — `TextTyper` reworked: **clipboard‑paste primary** (save → set → ⌘/Ctrl+V → restore after ~1.5 s on a background thread), `pynput.keyboard.Controller().type()` fallback; remove the `text.isascii()` branch; macOS Accessibility check before injecting.
- `core/transcriber.py` — becomes a thin orchestrator over the new **engine** abstraction + **formatting** subsystem (keeps wake‑word cleaning).
- `core/api.py` — `openai` 2.x; default transcription `gpt-4o-mini-transcribe`; chat/post‑processing on `gpt-5-nano` with `reasoning_effort='minimal'`; pass Whisper `prompt` bias from vocabulary.
- `core/constants.py` — new settings keys + schema (see §6); Mac‑appropriate default hotkey; activation‑mode enum; engine/model/formatting/vocabulary keys; bump `VERSION` → `4.0.0`.
- `core/config.py` — extended schema; migration of old settings files.
- `core/sounds.py`, `core/history.py`, `core/vad.py`, `core/logger.py` — largely unchanged (history gets a UI; sounds reused by HUD).

**New modules**
- `core/hotkeys.py` — `HotkeyManager` (pynput `Listener`): push‑to‑talk (`on_press`/`on_release`, guard key auto‑repeat with an `is_active` flag), toggle, and optional wake‑word bridge. Emits `start`/`stop` callbacks. Avoids ⌃/⌥ **combos** on macOS (pynput issue #297); defaults to a single F‑key or ⌘/⇧ combo.
- `core/permissions.py` — macOS TCC: `accessibility_trusted()` via `AXIsProcessTrusted()` (pyobjc/HIServices), `input_monitoring_ok()` via pynput `Listener.IS_TRUSTED`, mic via a probe. No‑ops to `True` on Windows/Linux. Returns a structured status the wizard/HUD use to guide the user (and the "must relaunch after granting" message).
- `core/engines/` — `TranscriptionEngine` ABC (`transcribe(wav_path, language, prompt) -> str`), `CloudEngine` (OpenAI), `LocalEngine` (lazy‑imports `mlx_whisper`/`whisper.cpp` on mac, `faster_whisper` on win). Selected by settings; default cloud. Optional install extra `[local]`.
- `core/formatting.py` — **the "no‑slop" subsystem** (see §5): output modes, no‑paraphrase cleanup prompts, spoken‑symbol expansion, post‑pass canonical correction.
- `core/vocabulary.py` — vocabulary store (terms + optional replacements), CSV/textarea import, builds the Whisper prompt bias and the correction map.
- `core/notifications.py` — `Notifier` over `desktop-notifier`; degrades to HUD‑only when notifications are unavailable (e.g. unsigned mac build).
- `core/platform.py` — small helpers (`IS_MAC`/`IS_WIN`, open‑settings deep links, open‑folder, default hotkey per OS).

**New UI package (`app/ui/`, PySide6)**
- `ui/app.py` — `QApplication`, the tray (`QSystemTrayIcon` with state‑colored icon + menu), owns the event loop; bridges `HotkeyManager` (runs its pynput listener thread) into Qt via signals.
- `ui/wizard.py` — first‑run **sidebar wizard** (Direction A): Welcome → Engine → Connect (API key *or* model download) → Permissions (mac) → Hotkey & Voice (PTT/toggle + key capture + live mic test) → All set. Permissions step auto‑skips on Windows.
- `ui/settings_window.py` — sidebar nav: General · Engine & Models · Vocabulary · Formatting · Hotkeys · Audio · History · About.
- `ui/hud.py` — frameless, translucent, always‑on‑top **recording HUD** pill with live waveform and an idle→listening→transcribing→done state machine. macOS: `Qt.WindowTransparentForInput` for click‑through + `NSWindow` collection‑behavior flags (CanJoinAllSpaces | FullScreenAuxiliary | Stationary) via a small pyobjc shim so it floats over full‑screen Spaces. Respects Reduce Motion.
- `ui/history_window.py` — searchable list over `TranscriptionHistory`: copy, re‑insert, reprocess‑with‑different‑settings, clear/export.
- `ui/theme.py` — dark theme + `© Cloudelipute` accent (pink `#ec2a8e`), shared QSS.

The old `app/yapper_tray.py`, `app/yapper.py`, `app/settings_ui.py`, `app/settings_console.py` are replaced by the Qt app (`python -m app` / `app/ui/app.py`). Console mode is retired in favor of the unified tray app (a `--once` CLI flag can cover scripted single‑shot use).

---

## 4. Dictation lifecycle (data flow)

```
   ┌ Push‑to‑talk: key down ──────────────┐         ┌ key up ┐
   │  (or toggle / wake word)             ▼         ▼        │
 idle ──► HUD: listening + waveform ──► record (sounddevice, 16k mono)
                                            │
                                            ▼  on stop
                                   VAD check (skip if silent)
                                            │ speech
                                            ▼
                          vocabulary → Whisper prompt bias
                                            │
                                            ▼
                       Engine.transcribe()  (cloud gpt‑4o‑mini‑transcribe
                                             │  or local mlx/faster‑whisper)
                                            ▼  raw text
                          HUD: transcribing  │
                                            ▼
                       Formatting subsystem (§5):
                         clean wake words → spoken‑symbol expand →
                         canonical vocab correction → mode cleanup
                         (Technical = no paraphrase / Natural / Verbatim) →
                         optional translate (gpt‑5‑nano)
                                            │ final text
                                            ▼
                       Typer: clipboard‑paste at cursor (⌘/Ctrl+V)
                                            │
                                            ▼
                    HUD: done ✓ · sound cue · history.add() · notify
```

Latency is masked by an instant clipboard paste of the whole result and a visible "transcribing" HUD state. A future **live mode** (P2) can stream partials from `gpt-realtime-whisper` into the HUD.

---

## 5. The "no AI slop" subsystem (`core/formatting.py` + `core/vocabulary.py`)

This is the product differentiator and a P0. Pipeline, in order, after raw transcription:

1. **Wake‑word stripping** (existing) — only when wake‑word activation is used.
2. **Spoken‑symbol expansion** (toggle, default on in Technical mode): `"dash dash help"` → `--help`, `"dot py"` → `.py`, `"backtick"` → `` ` ``, `"open paren"` → `(`, `"new line"` → `\n`, etc. Implemented as ordered regex rules; conservative (only fire on clear cues) to avoid corrupting prose.
3. **Canonical vocabulary correction** — fuzzy‑match mis‑hears to user terms: `"cube cuttle"`→`kubectl`, `"next J S"`→`Next.js`, `"post gres"`→`PostgreSQL`. Built from `core/vocabulary.py` (user terms + a small built‑in dev dictionary). Uses word/phrase‑level fuzzy replacement (rapidfuzz) with a high threshold.
4. **Mode cleanup** (LLM, `gpt-5-nano`, `reasoning_effort='minimal'`):
   - **Technical** (default): system prompt explicitly instructs *"fix only capitalization/obvious punctuation; **preserve all identifiers, camelCase/snake_case, CLI flags, file paths, code, and technical phrasing verbatim; never paraphrase, never 'improve' wording, never translate code tokens.'"* Vocabulary terms passed in the prompt as protected tokens.
   - **Natural**: grammar‑polished prose, remove fillers, fix punctuation (the old grammar‑fix behavior).
   - **Verbatim**: no LLM step at all (steps 2–3 optional).
5. **Translation** (optional, replaces mode cleanup when a target language is set) — `gpt-5-nano`, instructed to leave code/identifiers untranslated.

**Whisper biasing (before transcription):** the vocabulary builds the `prompt=` argument passed to `client.audio.transcriptions.create(...)` so the model is primed for the user's terms — counters Whisper's known weakness on proper nouns.

**Vocabulary UX:** Settings → Vocabulary: add/remove terms, optional `said → typed` replacements/snippets, CSV import, a starter dev pack (kubectl, Next.js, PostgreSQL, nginx, OAuth, JWT, pnpm, async/await, …). (Self‑learning auto‑add is a P2 nicety.)

---

## 6. Settings schema additions (`constants.py`)

New keys (with defaults), validated in `SETTINGS_SCHEMA`:

| Key | Default | Notes |
|---|---|---|
| `activation_mode` | `"push_to_talk"` | `push_to_talk` \| `toggle` \| `wake_word` |
| `engine` | `"cloud"` | `cloud` \| `local` |
| `cloud_stt_model` | `"gpt-4o-mini-transcribe"` | or `whisper-1` |
| `local_stt_model` | `"base"` | mlx/whisper.cpp/faster‑whisper size |
| `text_model` | `"gpt-5-nano"` | post‑processing/translation |
| `output_mode` | `"technical"` | `technical` \| `natural` \| `verbatim` |
| `expand_spoken_symbols` | `true` | |
| `vocabulary` | `[]` | list of terms / `{said,typed}` |
| `insertion_method` | `"paste"` | `paste` \| `type` |
| `hotkey` | OS‑specific | mac default a single F‑key or ⌘/⇧ combo; win keeps F‑keys |
| `show_hud` | `true` | |
| `reduce_motion` | `false` | also auto‑detected |

Old keys preserved; `config.py` migrates legacy files (e.g. drops `always_listening` into `activation_mode`). The `_comment`/`_available_*` self‑documentation in saved JSON stays.

---

## 7. Cross‑platform & packaging

### Permissions (macOS)
- **Microphone** — declared via `NSMicrophoneUsageDescription`; OS prompts on first capture.
- **Accessibility** (inject keys/paste) and **Input Monitoring** (capture hotkeys) — *cannot* be declared; detect at startup (`AXIsProcessTrusted`, `Listener.IS_TRUSTED`), and if missing show the wizard's Permissions panel with deep links to System Settings and a clear **"quit & relaunch after granting"** notice (macOS only re‑reads TCC at process start). `pynput` injection **fails silently** without Accessibility — never rely on exceptions.
- Permissions attach to the **app's identity**, so the prebuilt `.app` is what users grant (not Terminal/python).

### Packaging
- **Clone‑first (primary):** `pyproject.toml` + `uv`. `./setup` → `uv sync` (creates `.venv`, installs locked deps). Optional extras: `uv sync --extra local` for on‑device models. Thin `run.sh`/`run.bat`/`run.command` launchers. Drop the committed `python/` embedded runtime entirely.
- **Prebuilt releases (secondary, unsigned):** `PyInstaller` builds an arm64 `.app` (Info.plist: `NSMicrophoneUsageDescription`, `LSUIElement=true`) → `.dmg` (macOS) and a `.zip` (Windows). Document the first‑launch Gatekeeper workaround (`xattr -dr com.apple.quarantine /Applications/Yapper.app` or System Settings → Open Anyway). Notifications may be unavailable on the unsigned mac build → HUD covers feedback.
- `sounddevice` ships portaudio in its wheels, so no native portaudio bundling step is needed.

### Repo hygiene (Phase 0)
- Remove `python/`, `*.pyd`, old `BUILD_PORTABLE.bat`/`build_portable.py`/`installer/` (Windows‑embedded‑specific).
- Normalize all copyright → `© 2026 Cloudelipute` (33 spots) and the `COPYRIGHT` constant.
- Confirm `.claude/` stays gitignored (it is).
- New **README.md** with: banner, feature grid, **Mermaid** diagrams (architecture from §3, dictation lifecycle from §4, onboarding flow), clone‑first install for macOS/Windows/Linux, permissions guide, model/cost notes, BYOK + privacy statement, screenshots/mockups.

---

## 8. UI/UX design summary

- **First‑run wizard** (sidebar / Direction A): Welcome → Engine → Connect → Permissions (mac) → Hotkey & Voice (PTT/toggle, key capture, live mic‑level test, a "say this sentence" success moment) → All set. Replaces the hand‑edit `settings.json` / console first‑run.
- **Settings** (same sidebar): General · Engine & Models · Vocabulary · Formatting · Hotkeys · Audio · History · About.
- **Recording HUD**: frameless always‑on‑top pill, live waveform, state machine, sound cues, Reduce‑Motion aware. The single biggest UX gap vs 2026 leaders.
- **Notifications**: `desktop-notifier` for done/error toasts; never block on them.
- **Tray**: `QSystemTrayIcon` with state‑colored icon, quick toggles (engine, output mode, language), open settings/history, quit.

---

## 9. Phased implementation plan

Each phase is independently testable. Phases 0–4 = **P0** (a fully reimagined, cross‑platform, slop‑free app). Phase 5 = fast‑follow. Phase 6 = the QA finale.

- **Phase 0 — OSS hygiene & repo prep:** remove embedded Python/installers; `pyproject.toml`+`uv`; launchers; normalize `©`; new README w/ Mermaid diagrams. *(small)*
- **Phase 1 — Cross‑platform core:** `hotkeys.py` (pynput PTT+toggle), `typer.py` (clipboard‑paste), `audio.py`/`devices.py` (sounddevice), `permissions.py`, `notifications.py`. Headless‑testable. *(foundation — everything depends on it)*
- **Phase 2 — Engine abstraction & model updates:** `engines/` (cloud+local), `api.py` to `openai` 2.x with `gpt-4o-mini-transcribe` + `gpt-5-nano`. Retire `gpt-4.1-nano`/`whisper-1` default.
- **Phase 3 — No‑slop subsystem:** `formatting.py` + `vocabulary.py` (modes, spoken symbols, correction map, Whisper bias).
- **Phase 4 — UI overhaul (PySide6):** `ui/app.py` (tray+loop), `wizard.py`, `settings_window.py`, `hud.py`, `history_window.py`, theme. Retire `customtkinter`/`pystray`/console.
- **Phase 5 — Power features:** searchable history actions, AI edit/command mode (transform selection), app‑specific Modes/Power Mode, live streaming mode (`gpt-realtime-whisper`), clipboard‑vs‑type mode.
- **Phase 6 — QA & hardening:** parallel review agents (correctness/bugs · missing‑or‑incomplete logic · cross‑platform/macOS correctness · security/secrets) → adversarially verify findings → auto‑fix (small & large) → second verification pass. Manual smoke test on macOS (M‑series) + Windows.

---

## 10. Dependencies (target)

Runtime: `pynput>=1.8.2`, `sounddevice`, `pyperclip`, `openai>=2.38`, `PySide6`, `desktop-notifier`, `rapidfuzz`, `Pillow` (icon).
macOS extra (pulled by pynput): `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices` (for `AXIsProcessTrusted`).
Optional `[local]` extra: `mlx-whisper` (mac) / `faster-whisper` (win), `whisper.cpp` binding.
Dev/build: `uv`, `pyinstaller` (and/or `py2app` on mac), `pytest`.
**Removed:** embedded `python/` runtime, `keyboard`, `pyaudio`, `customtkinter`, `pystray`, `pyautogui`.

---

## 11. Risks & open decisions

- **macOS permission UX** is the top risk — `pynput` silent‑fail without Accessibility, TCC re‑read only at launch. Mitigated by `permissions.py` + the wizard's relaunch guidance. **Must be tested on real M‑series hardware.**
- **Qt main‑thread / pynput listener thread bridging** — listener runs on its own thread, must marshal into Qt via signals. Decided early: Qt owns the loop.
- **Unsigned mac build** — first‑launch friction + possibly no Notification Center; HUD is the safety net. Acceptable for a clone‑first dev audience; signing remains an upgrade path.
- **On‑device engine size/perf** — keep behind an optional extra; default cloud so the base install stays light.
- **Bundle size** (PySide6 ~100–150 MB) — fine for clone‑first; note in README.
- **Linux** — best‑effort (pynput needs X/uinput; tray varies). Not a release target; don't block on it.

---

## 12. Testing & verification

- **Unit/headless:** formatting pipeline (golden no‑slop cases like the kubectl example), vocabulary correction, spoken‑symbol expansion, settings migration, engine selection (mock OpenAI), hotkey state machine (mock pynput), clipboard typer (mock).
- **Integration:** record→transcribe→format→insert with a stub engine.
- **Manual:** macOS M‑series + Windows — permissions flow, PTT/toggle, HUD states, paste into real apps (editor, browser, terminal, Slack), Unicode/emoji.
- **Phase 6 multi‑agent review** as above.

---

## 13. Out of scope (now)

- Code signing / notarization / App Store (upgrade path documented).
- Mobile / web.
- Self‑learning auto‑vocabulary (P2 idea, not committed).
- Multi‑speaker diarization (`gpt-4o-transcribe-diarize` exists; not needed for dictation).

---

## Appendix A — Verified facts driving the design (May 2026)

- `pynput` 1.8.2 (2026‑05‑12) — single cross‑platform lib for capture + injection; ⌃/⌥ **combos** broken on macOS (issue #297, open); `IS_TRUSTED` on Listener; injection needs Accessibility (silent‑fail otherwise).
- `gpt-4.1-nano` **deprecated, shutdown 2026‑10‑23** → `gpt-5-nano` ($0.05/$0.40 per 1M) / `gpt-5.4-nano`; reasoning models → `reasoning_effort='minimal'`.
- `gpt-4o-mini-transcribe` ~$0.003/min (≈50% < whisper‑1), more accurate; `whisper-1` not deprecated, kept for long‑tail langs/timestamps.
- PyAudio has **no macOS wheel** → `sounddevice` (bundles portaudio).
- `customtkinter` maintenance‑stalled (5.2.2, Jan 2024) → **PySide6/Qt**.
- `desktop-notifier` 6.1.1 cross‑platform notifications; `pystray` macOS gaps (main‑thread, no default item) → `QSystemTrayIcon`.
- Sequoia/Tahoe removed right‑click‑Open → unsigned apps need `xattr -dr com.apple.quarantine` / Open Anyway.
- Info.plist: `NSMicrophoneUsageDescription` + `LSUIElement=true`.
