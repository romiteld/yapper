# Yapper v4 — Implementation Plan (Index)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port Yapper to macOS Apple Silicon while keeping Windows first-class, reimagine the UI/UX (guided onboarding, push-to-talk, recording HUD, modern settings), add an engineer-grade "no AI slop" transcription pipeline, and open-source it clone-first.

**Architecture:** Single cross-platform Python codebase. Platform differences isolated behind thin abstractions (`hotkeys`, `permissions`, `typer`, `notifications`). PySide6/Qt owns one event loop for settings + wizard + recording HUD + tray. Cloud (`gpt-4o-mini-transcribe`) and on-device (mlx/faster-whisper) transcription behind a `TranscriptionEngine` interface. A vocabulary-biased, mode-aware formatting subsystem guarantees technical terms survive verbatim.

**Tech Stack:** `pynput`, `sounddevice`, `openai` 2.x (`gpt-4o-mini-transcribe` + `gpt-5-nano`), `PySide6`, `desktop-notifier`, `rapidfuzz`, `uv`, `PyInstaller`.

**Design spec:** [`docs/superpowers/specs/2026-05-30-yapper-reimagining-design.md`](../specs/2026-05-30-yapper-reimagining-design.md)

---

## How to use this index

Implement the phases **in order** — each depends on the ones before it. Each phase plan is self-contained, TDD-driven, and ends with working, committed, testable software. Total: **86 tasks / ~571 bite-sized steps** across 7 plans.

| # | Phase plan | Goal | Tasks | Depends on |
|---|---|---|---|---|
| 0 | [Phase 0 · OSS Hygiene & Repo Prep](2026-05-30-yapper-phase0-hygiene.md) | Drop embedded Python; `uv`/`pyproject`; launchers; normalize `© Cloudelipute`; README w/ Mermaid; pytest harness; v4.0.0 | 8 | — |
| 1 | [Phase 1 · Cross-Platform Core](2026-05-30-yapper-phase1-core.md) | `hotkeys` (pynput PTT/toggle), `typer` (clipboard-paste), `audio`/`devices` (sounddevice), `permissions` (mac TCC), `notifications` (desktop-notifier) | 11 | 0 |
| 2 | [Phase 2 · Engine Abstraction & Model Updates](2026-05-30-yapper-phase2-engines.md) | `engines/` (cloud+local), `api.py` → openai 2.x, `gpt-4o-mini-transcribe` + `gpt-5-nano`, prompt bias | 12 | 0,1 |
| 3 | [Phase 3 · No-Slop Formatting Subsystem](2026-05-30-yapper-phase3-formatting.md) | `vocabulary` + `formatting` (Technical/Natural/Verbatim, spoken symbols, fuzzy correction, Whisper bias) | 12 | 0,2 |
| 4 | [Phase 4 · UI Overhaul (PySide6)](2026-05-30-yapper-phase4-ui.md) | Tray app, sidebar wizard, settings, recording HUD, history window; retire customtkinter/pystray/console | 15 | 0–3 |
| 5 | [Phase 5 · Power Features](2026-05-30-yapper-phase5-power.md) | History actions, AI edit/command mode, app-specific Modes, opt-in live streaming, clipboard/type mode | 17 | 0–4 |
| 6 | [Phase 6 · QA & Hardening (finale)](2026-05-30-yapper-phase6-qa.md) | Parallel multi-agent review → auto-fix → re-verify; full test gate; mac+win smoke checklist; unsigned release | 11 | 0–5 |

**P0 = Phases 0–4** (a fully reimagined, cross-platform, slop-free app). **Phase 5** = fast-follow. **Phase 6** = the QA finale (the user's explicit closing directive).

## Self-review summary (writing-plans checklist)

- **Spec coverage:** every spec §9 phase and the cross-cutting requirements (no-slop §5, permissions/packaging §7, UI §8, settings schema §6) map to tasks. ✅
- **Placeholder scan:** no `TBD`/`implement later`/`similar to Task N`/`add error handling`-style placeholders across all 7 plans. ✅
- **Cross-phase consistency:** load-bearing interfaces verified identical across phases — `TranscriptionEngine.transcribe(wav_path, language, prompt)`, `Formatter.format(raw_text, *, mode, expand_symbols, translate_to)`, `HotkeyManager(mode, hotkey, on_start, on_stop)`, `get_engine(settings)`, `RecordingHUD.set_state(...)`, settings keys, `gpt-4o-mini-transcribe`/`gpt-5-nano` + `reasoning_effort='minimal'`. ✅ (The two `dict`-returning `transcribe()` defs in Phase 2 are intentional `_MlxBackend`/`_FasterWhisperBackend` adapters, not the engine interface.)

## Verify-before-implementing notes

The authoring agents honestly flagged a few library specifics with `# verify against docs` — confirm against current docs when you reach them:
- **Phase 5 realtime model name:** plan uses `gpt-realtime`; the spec/research names the purpose-built streaming STT model `gpt-realtime-whisper`. Confirm the correct current model id before implementing the opt-in live mode (P2 — non-blocking).
- `mlx_whisper.transcribe(...)` repo/arg names (Phase 2 local backend).
- macOS `NSWindow` collection-behavior flags + `Qt.WindowTransparentForInput` click-through (Phase 4 HUD).
- `desktop-notifier` send API shape (Phase 1).
- `pyobjc` `AXIsProcessTrusted` import path (Phase 1 permissions).

These are intentionally explicit so the implementer checks the live API rather than trusting an invented signature.
