# Phase 4 Manual Smoke Checklist (mac + Windows)

GUI automation covers construction and signal wiring only. The items below
require a human on real hardware. Run `python -m app`.

## Both platforms
- [ ] First launch with no API key shows the SetupWizard at the Welcome step.
- [ ] Wizard: Engine -> Connect (paste key) -> Hotkey & Voice -> "Test microphone"
      records ~2s and shows "Heard: …". Finish closes the wizard.
- [ ] Tray icon appears; right-click shows Settings…, History…, Quit Yapper.
- [ ] Push-to-talk: hold the hotkey -> HUD shows "Listening…" with a moving ring;
      release -> "Transcribing…" -> text pastes at the cursor -> HUD "Done" fades.
- [ ] Tray icon dot color changes idle(grey) -> listening(pink) -> transcribing(amber) -> done(green).
- [ ] Toggle mode (Settings -> Hotkeys -> Activation=toggle): one press starts, next stops.
- [ ] Settings -> Formatting -> output_mode=verbatim: no LLM cleanup; clean: mechanics only.
- [ ] History window: search filters rows; Copy, Re-insert, Export, Clear all work.
- [ ] Reduce motion ON: HUD ring stays flat (no level animation).
- [ ] Paste into: code editor, browser address bar, terminal, Slack — Unicode/emoji intact.

## macOS only
- [ ] Without Accessibility granted, paste fails silently; wizard Permissions step
      flags accessibility=False and tells user to quit & relaunch after granting.
- [ ] After granting Accessibility + Input Monitoring and relaunching, PTT + paste work.
- [ ] HUD floats over a full-screen Space and is click-through (clicks pass to app beneath).

## Windows only
- [ ] Wizard skips the Permissions step entirely.
- [ ] F-key hotkeys (f8–f12) capture and inject without admin elevation where possible.
