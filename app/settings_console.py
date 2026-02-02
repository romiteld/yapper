"""
Yapper Settings (Console Version)
=================================
Simple console-based settings configuration.
Cross-platform: Windows, macOS, Linux

Copyright (c) 2026 Cloudelipute
"""

import os
import sys
from pathlib import Path

# Add app directory to path for imports
APP_DIR = Path(__file__).parent.resolve()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Import core components
from core import (
    VERSION,
    COPYRIGHT,
    LANGUAGES,
    HOTKEYS,
    Settings,
    list_input_devices,
)

# Build console-friendly options
HOTKEY_OPTIONS = {str(i + 1): key for i, key in enumerate(HOTKEYS[:5])}

# Build language options for console (subset of most common)
_COMMON_LANGS = ["", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ru", "ar", "nl"]
LANGUAGE_OPTIONS = {
    str(i + 1): (code, LANGUAGES.get(code, code))
    for i, code in enumerate(_COMMON_LANGS)
}


# =============================================================================
# CONSOLE UI
# =============================================================================

def clear_screen():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print the header."""
    print()
    print("  ╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐")
    print("  ╚╦╝├─┤├─┘├─┘├┤ ├┬┘")
    print("   ╩ ┴ ┴┴  ┴  └─┘┴└─")
    print()
    print(f"  ════════════════════════════════════")
    print(f"        S E T T I N G S  v{VERSION}")
    print(f"  ════════════════════════════════════")
    print(f"  {COPYRIGHT}")
    print()


def mask_api_key(key: str) -> str:
    """Mask API key for display."""
    if not key:
        return "(not set)"
    if len(key) < 10:
        return "****"
    return key[:7] + "..." + key[-4:]


def main():
    """Main settings interface."""
    clear_screen()
    print_header()

    # Load settings
    settings = Settings()
    settings.load()
    data = settings.as_dict()

    # Check if this is first-time setup
    first_time = not data.get('api_key', '').strip()

    if not first_time:
        # Show current settings
        print("  Current Settings:")
        print("  ─────────────────────────────────────")
        print(f"  API Key:     {mask_api_key(data.get('api_key', ''))}")
        print(f"  Hotkey:      {data.get('hotkey', 'f8').upper()}")

        translate = data.get('translate_to', '')
        if translate:
            lang_name = LANGUAGES.get(translate, translate)
            print(f"  Translate:   {lang_name}")
        else:
            print(f"  Translate:   Off (same language)")

        print(f"  Grammar:     {'On' if data.get('fix_grammar', True) else 'Off'}")
        print(f"  VAD:         {'On' if data.get('vad_enabled', True) else 'Off'}")
        print()

    # ===== STEP 1: API KEY =====
    print("  ─────────────────────────────────────")
    print("  STEP 1: OpenAI API Key")
    print("  ─────────────────────────────────────")
    print()
    print("  Get your API key at:")
    print("  https://platform.openai.com/api-keys")
    print()

    current_key = data.get('api_key', '')
    if current_key:
        print(f"  Current: {mask_api_key(current_key)}")
        new_key = input("  Enter new API key (or press Enter to keep): ").strip()
        if new_key:
            settings.set('api_key', new_key)
            print("  API key updated!")
    else:
        while True:
            new_key = input("  Enter your API key: ").strip()
            if new_key:
                settings.set('api_key', new_key)
                print("  API key saved!")
                break
            else:
                print("  API key is required. Please enter it.")

    print()

    # ===== STEP 2: HOTKEY =====
    print("  ─────────────────────────────────────")
    print("  STEP 2: Hotkey (press to record)")
    print("  ─────────────────────────────────────")
    print()
    print("  Options:")
    for num, key in HOTKEY_OPTIONS.items():
        current = " (current)" if key == data.get('hotkey', 'f8') else ""
        print(f"    {num}. {key.upper()}{current}")
    print()

    choice = input(f"  Choose 1-{len(HOTKEY_OPTIONS)} (or press Enter to keep current): ").strip()
    if choice in HOTKEY_OPTIONS:
        settings.set('hotkey', HOTKEY_OPTIONS[choice])
        print(f"  Hotkey set to {HOTKEY_OPTIONS[choice].upper()}")

    print()

    # ===== STEP 3: AUDIO DEVICE =====
    print("  ─────────────────────────────────────")
    print("  STEP 3: Microphone (optional)")
    print("  ─────────────────────────────────────")
    print()

    devices = list_input_devices()
    if devices:
        print("  Available devices:")
        print("    0. System Default (current)" if data.get('audio_device_index') is None else "    0. System Default")
        for i, device in enumerate(devices, 1):
            current = " (current)" if device.index == data.get('audio_device_index') else ""
            print(f"    {i}. {device.name}{current}")
        print()

        choice = input(f"  Choose 0-{len(devices)} (or press Enter to keep current): ").strip()
        if choice == "0":
            settings.set('audio_device_index', None)
            print("  Using system default microphone")
        elif choice.isdigit() and 1 <= int(choice) <= len(devices):
            device = devices[int(choice) - 1]
            settings.set('audio_device_index', device.index)
            print(f"  Using: {device.name}")
    else:
        print("  No microphones detected. Using system default.")

    print()

    # ===== STEP 4: TRANSLATION =====
    print("  ─────────────────────────────────────")
    print("  STEP 4: Translation (optional)")
    print("  ─────────────────────────────────────")
    print()
    print("  Speak in any language, output in another:")
    print()
    for num, (code, name) in LANGUAGE_OPTIONS.items():
        current = " (current)" if code == data.get('translate_to', '') else ""
        display = name if name else "No translation (same language)"
        print(f"    {num}. {display}{current}")
    print()

    choice = input(f"  Choose 1-{len(LANGUAGE_OPTIONS)} (or press Enter to keep current): ").strip()
    if choice in LANGUAGE_OPTIONS:
        code, name = LANGUAGE_OPTIONS[choice]
        settings.set('translate_to', code)
        if code:
            print(f"  Will translate to {name}")
        else:
            print("  Translation disabled")

    print()

    # ===== STEP 5: GRAMMAR =====
    print("  ─────────────────────────────────────")
    print("  STEP 5: Grammar Correction (optional)")
    print("  ─────────────────────────────────────")
    print()
    print("  Automatically fix grammar and punctuation when not translating.")
    print(f"  Current: {'On' if data.get('fix_grammar', True) else 'Off'}")
    choice = input("  Enable grammar correction? (y/n, Enter to keep): ").strip().lower()
    if choice == 'y':
        settings.set('fix_grammar', True)
        print("  Grammar correction enabled")
    elif choice == 'n':
        settings.set('fix_grammar', False)
        print("  Grammar correction disabled")

    print()

    # ===== STEP 6: VAD =====
    print("  ─────────────────────────────────────")
    print("  STEP 6: Voice Activity Detection (optional)")
    print("  ─────────────────────────────────────")
    print()
    print("  Skip API calls when no speech is detected (reduces costs).")
    print(f"  Current: {'On' if data.get('vad_enabled', True) else 'Off'}")
    choice = input("  Enable VAD? (y/n, Enter to keep): ").strip().lower()
    if choice == 'y':
        settings.set('vad_enabled', True)
        print("  VAD enabled")
    elif choice == 'n':
        settings.set('vad_enabled', False)
        print("  VAD disabled")

    print()

    # ===== STEP 7: FUZZY WAKE WORD =====
    print("  ─────────────────────────────────────")
    print("  STEP 7: Wake Word Flexibility (optional)")
    print("  ─────────────────────────────────────")
    print()
    print("  Allow mispronunciations of 'yapper start' and 'yapper stop'.")
    print(f"  Current: {'On' if data.get('wake_word_fuzzy', True) else 'Off'}")
    choice = input("  Enable fuzzy wake word? (y/n, Enter to keep): ").strip().lower()
    if choice == 'y':
        settings.set('wake_word_fuzzy', True)
        print("  Fuzzy wake word enabled")
    elif choice == 'n':
        settings.set('wake_word_fuzzy', False)
        print("  Fuzzy wake word disabled")

    print()

    # ===== SAVE =====
    settings.save()
    data = settings.as_dict()

    print("  ═════════════════════════════════════")
    print("  SETTINGS SAVED!")
    print("  ═════════════════════════════════════")
    print()
    print(f"  API Key:    {mask_api_key(data.get('api_key', ''))}")
    print(f"  Hotkey:     {data.get('hotkey', 'f8').upper()}")

    translate = data.get('translate_to', '')
    if translate:
        lang_name = LANGUAGES.get(translate, translate)
        print(f"  Translate:  {lang_name}")
    else:
        print(f"  Translate:  Off")

    print(f"  Grammar:    {'On' if data.get('fix_grammar', True) else 'Off'}")
    print(f"  VAD:        {'On' if data.get('vad_enabled', True) else 'Off'}")
    print(f"  Fuzzy Wake: {'On' if data.get('wake_word_fuzzy', True) else 'Off'}")
    print()
    print("  You can now run Yapper!")
    print()

    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()
