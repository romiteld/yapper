"""Phase 4 Task 9: SettingsWindow tests."""
import pytest

from core import LANGUAGES, Settings
from ui.settings_window import (
    SettingsWindow,
    SettingsBinder,
    vocabulary_to_text,
    text_to_vocabulary,
)


@pytest.fixture
def settings(tmp_path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.load()
    return s


def test_binder_reads_default(settings):
    b = SettingsBinder(settings)
    # default output_mode is "clean" (general-purpose framing)
    assert b.read("output_mode") == "clean"


def test_binder_writes_and_saves(settings):
    b = SettingsBinder(settings)
    b.write("output_mode", "polished")
    b.commit()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("output_mode") == "polished"


def test_binder_rejects_unknown_value_silently(settings):
    b = SettingsBinder(settings)
    prior = settings.get("hotkey")
    # invalid hotkey not in HOTKEYS must not crash; on commit it is rejected by
    # Settings validation and the live Settings value is left unchanged.
    b.write("hotkey", "not-a-key")
    b.commit()
    assert settings.get("hotkey") == prior


# ---- HIGH-3: binder buffers edits, commits only on Save --------------------

def test_binder_write_does_not_mutate_settings_until_commit(settings):
    settings.set("output_mode", "clean")
    b = SettingsBinder(settings)
    b.write("output_mode", "verbatim")
    # Buffered: live Settings still holds the old value.
    assert settings.get("output_mode") == "clean"
    # But read reflects the staged edit.
    assert b.read("output_mode") == "verbatim"
    assert b.dirty is True


def test_binder_commit_applies_pending(settings):
    settings.set("output_mode", "clean")
    b = SettingsBinder(settings)
    b.write("output_mode", "verbatim")
    b.commit()
    assert settings.get("output_mode") == "verbatim"
    assert b.dirty is False


def test_binder_discard_drops_pending(settings):
    settings.set("output_mode", "clean")
    b = SettingsBinder(settings)
    b.write("output_mode", "verbatim")
    b.discard()
    assert b.read("output_mode") == "clean"
    assert settings.get("output_mode") == "clean"


def test_settings_window_close_without_save_does_not_mutate(qtbot, settings):
    settings.set("expand_spoken_symbols", True)
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win.binder.write("expand_spoken_symbols", False)
    # Simulate closing without Save.
    win.close()
    assert settings.get("expand_spoken_symbols") is True


# ---- HIGH-5: Vocabulary + History sections ---------------------------------

def test_vocabulary_text_roundtrip():
    vocab = [
        {"typed": "kubectl", "said": None},
        {"typed": "Next.js", "said": "next js, nextjs"},
    ]
    text = vocabulary_to_text(vocab)
    assert "kubectl" in text
    assert "Next.js = next js, nextjs" in text
    back = text_to_vocabulary(text)
    assert {"typed": "kubectl", "said": None} in back
    assert {"typed": "Next.js", "said": "next js, nextjs"} in back


def test_vocabulary_text_ignores_blank_lines():
    assert text_to_vocabulary("\n\n  \n") == []
    assert text_to_vocabulary("alpha\n\nbeta") == [
        {"typed": "alpha", "said": None}, {"typed": "beta", "said": None}]


def test_settings_window_vocabulary_edit_persists(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win._nav.setCurrentRow(win.SECTIONS.index("Vocabulary"))
    win._vocab_edit.setPlainText("kubectl\nNext.js = next js")
    win._on_save()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    vocab = reloaded.get("vocabulary")
    typed = {t["typed"] for t in vocab}
    assert "kubectl" in typed and "Next.js" in typed


def test_settings_window_history_section_has_open_button(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win._nav.setCurrentRow(win.SECTIONS.index("History"))
    from PySide6.QtWidgets import QPushButton
    labels = {b.text() for b in win.findChildren(QPushButton)}
    assert "Open history…" in labels


def test_settings_window_history_open_emits_signal(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    received = []
    win.open_history_requested.connect(lambda: received.append(True))
    win._nav.setCurrentRow(win.SECTIONS.index("History"))
    from PySide6.QtWidgets import QPushButton
    btn = next(b for b in win.findChildren(QPushButton) if b.text() == "Open history…")
    btn.click()
    assert received == [True]


# ---- MINOR-11: translate combo shows display names, stores codes -----------

def test_translate_combo_shows_display_names_stores_code(qtbot, settings):
    settings.set("translate_to", "")  # No Translation
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win._nav.setCurrentRow(win.SECTIONS.index("Formatting"))
    combo = win._translate
    # Display text is a human-readable name, not a raw code.
    assert combo.currentText() in LANGUAGES.values()
    # Select Spanish by display name; binder must stage the code "es".
    es_index = list(LANGUAGES.keys()).index("es")
    combo.setCurrentIndex(es_index)
    assert win.binder.read("translate_to") == "es"
    win._on_save()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("translate_to") == "es"


def test_settings_window_constructs_with_nav_sections(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    assert win.SECTIONS == [
        "General", "Engine & Models", "Vocabulary", "Formatting",
        "Hotkeys", "Audio", "History", "About",
    ]
    assert win._nav.count() == len(win.SECTIONS)


def test_settings_window_save_persists(qtbot, settings):
    win = SettingsWindow(settings)
    qtbot.addWidget(win)
    win.binder.write("expand_spoken_symbols", False)
    win._on_save()
    reloaded = Settings(settings_path=settings.path)
    reloaded.load()
    assert reloaded.get("expand_spoken_symbols") is False
