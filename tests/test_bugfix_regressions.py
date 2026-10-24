"""Regression tests for the 26-bug fix batch.

Each test corresponds to one or more confirmed bugs and asserts the new
correct behavior.  GUI-thread–only behaviors (HUD timer cancellation, tray
sync, wizard queued signal) are exercised at the unit/logic level where
possible; the manual-only parts are documented inline.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Bug #1 — set_mode / set_hotkey fire on_stop when _active is True
# ---------------------------------------------------------------------------
from core.hotkeys import HotkeyManager


class _FakeKey:
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return isinstance(other, _FakeKey) and other.name == self.name
    def __hash__(self):
        return hash(self.name)


def _make_mgr(mode="push_to_talk", hotkey="f8"):
    on_start = MagicMock()
    on_stop = MagicMock()
    mgr = HotkeyManager(mode=mode, hotkey=hotkey,
                        on_start=on_start, on_stop=on_stop)
    mgr._target_key = _FakeKey("f8")
    return mgr, on_start, on_stop


def test_set_mode_fires_on_stop_when_active():
    """set_mode() while PTT key is held must deliver on_stop so the controller
    exits LISTENING (bug #1 — previously cleared _active silently)."""
    mgr, on_start, on_stop = _make_mgr("push_to_talk")
    mgr._on_press(_FakeKey("f8"))   # _active = True, on_start fired
    on_start.assert_called_once()
    on_stop.assert_not_called()

    mgr.set_mode("toggle")          # <- bug was: on_stop never fired
    on_stop.assert_called_once()    # must deliver the stop edge
    assert mgr._active is False


def test_set_hotkey_fires_on_stop_when_active():
    """set_hotkey() while recording fires on_stop once (bug #1)."""
    mgr, on_start, on_stop = _make_mgr("push_to_talk")
    mgr._on_press(_FakeKey("f8"))
    on_start.assert_called_once()

    mgr.set_hotkey("f9")            # <- bug was: on_stop never fired
    on_stop.assert_called_once()
    assert mgr._active is False


def test_set_mode_then_set_hotkey_no_double_stop():
    """_on_settings_saved calls set_mode then set_hotkey back-to-back; only
    one on_stop should be delivered (bug #1 guard against double-stop)."""
    mgr, on_start, on_stop = _make_mgr("push_to_talk")
    mgr._on_press(_FakeKey("f8"))   # _active = True

    mgr.set_mode("toggle")          # fires on_stop, clears _active
    mgr.set_hotkey("f9")            # _active already False; must NOT fire again

    on_stop.assert_called_once()    # exactly one stop


def test_set_mode_when_not_active_does_not_fire_on_stop():
    """When not recording, set_mode/set_hotkey must not fire on_stop."""
    mgr, on_start, on_stop = _make_mgr("push_to_talk")
    mgr.set_mode("toggle")
    mgr.set_hotkey("f9")
    on_stop.assert_not_called()


# ---------------------------------------------------------------------------
# Bug #2 — input_monitoring_ok uses AXIsProcessTrusted (not class attribute)
# ---------------------------------------------------------------------------
from core.permissions import input_monitoring_ok


def test_input_monitoring_uses_ax_is_process_trusted():
    """input_monitoring_ok() must use AXIsProcessTrusted, not the stale
    class-level IS_TRUSTED attribute (bug #2)."""
    fake_hi = MagicMock()
    fake_hi.AXIsProcessTrusted.return_value = True
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert input_monitoring_ok() is True

    fake_hi.AXIsProcessTrusted.return_value = False
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._load_hiservices", return_value=fake_hi):
        assert input_monitoring_ok() is False


# ---------------------------------------------------------------------------
# Bug #4 — microphone_ok uses AVFoundation / stream probe, not format check
# ---------------------------------------------------------------------------
from core.permissions import microphone_ok


def test_microphone_ok_avfoundation_authorized():
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 3
    with patch("core.permissions.IS_MAC", True), \
         patch.dict("sys.modules", {"AVFoundation": fake_av}):
        assert microphone_ok() is True


def test_microphone_ok_avfoundation_denied():
    fake_av = MagicMock()
    fake_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 2
    with patch("core.permissions.IS_MAC", True), \
         patch.dict("sys.modules", {"AVFoundation": fake_av}):
        assert microphone_ok() is False


def test_microphone_ok_falls_back_to_stream_probe():
    """When AVFoundation is absent, _probe_input_stream() is used (bug #4)."""
    with patch("core.permissions.IS_MAC", True), \
         patch("core.permissions._probe_input_stream", return_value=False) as probe, \
         patch.dict("sys.modules", {"AVFoundation": None}):
        result = microphone_ok()
    probe.assert_called_once()
    assert result is False


# ---------------------------------------------------------------------------
# Bug #5 — chat() None content guard
# ---------------------------------------------------------------------------
from core.api import APIClient


def test_chat_none_content_returns_empty_string():
    """When the model returns message.content=None, chat() must return ''
    (not raise AttributeError, bug #5)."""
    fake_choice = MagicMock()
    fake_choice.message.content = None
    fake_choice.finish_reason = "length"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    client = APIClient(api_key="sk_test")
    fake_backend = MagicMock()
    fake_backend.chat.completions.create.return_value = fake_response
    client._client = fake_backend

    result = client.chat([{"role": "user", "content": "hi"}])
    assert result == ""


def test_chat_empty_string_content_returns_empty_string():
    """chat() with content="" also returns '' without raising (bug #5)."""
    fake_choice = MagicMock()
    fake_choice.message.content = ""
    fake_choice.finish_reason = "stop"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    client = APIClient(api_key="sk-test")
    client._client = MagicMock()
    client._client.chat.completions.create.return_value = fake_response

    result = client.chat([{"role": "user", "content": "hi"}])
    assert result == ""


# ---------------------------------------------------------------------------
# Bug #6/#22/#23 — formatting false positives (paren, double-dash, backtick)
# ---------------------------------------------------------------------------
from core.formatting import expand_spoken_symbols


def test_paren_requires_matched_pair():
    """Standalone 'open paren' or 'close paren' in prose must not convert
    (bug #6 — was firing on each cue independently)."""
    assert expand_spoken_symbols("please close paren the deal") == "please close paren the deal"
    assert expand_spoken_symbols("the open paren house") == "the open paren house"
    assert expand_spoken_symbols("he said close paren was wrong") == "he said close paren was wrong"


def test_paren_paired_cue_converts():
    """A matched pair 'open paren X close paren' -> '(X)' must still work."""
    result = expand_spoken_symbols("open paren hello close paren")
    assert result == "(hello)"


def test_backtick_lone_in_prose_unchanged():
    """Lone 'backtick' in prose must NOT be converted (bug #23)."""
    assert expand_spoken_symbols("the backtick of doom") == "the backtick of doom"
    assert expand_spoken_symbols("what is a backtick?") == "what is a backtick?"


def test_backtick_paired_still_converts():
    """Paired 'backtick X backtick' must still produce `X` (bug #23)."""
    assert expand_spoken_symbols("wrap backtick code backtick here") == "wrap `code` here"


def test_double_dash_prose_preceder_suppressed():
    """'dash dash' after a clearly-prose word must NOT convert to '--'
    (bug #22 — narrow prose blacklist; convert-by-default otherwise)."""
    assert expand_spoken_symbols("the score was dash dash even") == "the score was dash dash even"
    assert expand_spoken_symbols("a long dash dash mark") == "a long dash dash mark"
    assert expand_spoken_symbols("plan dash dash backup") == "plan dash dash backup"


def test_double_dash_cli_context_still_converts():
    """Real CLI long-flags must convert, including when a CLI subcommand or
    argument noun precedes 'dash dash' (bug #22 re-verification regression).

    'dash dash' is a near-unambiguous cue so we convert by default and only
    suppress a narrow prose blacklist — NOT a CLI-verb whitelist — so that
    'npm set --global' / 'git config --global' / 'kubectl get pods --all'
    keep working."""
    assert expand_spoken_symbols("dash dash help") == "--help"
    assert expand_spoken_symbols("git commit dash dash amend") == "git commit --amend"
    # The regression case: a subcommand word ("set") precedes "dash dash".
    assert expand_spoken_symbols("npm set dash dash global") == "npm set --global"
    assert expand_spoken_symbols("git config dash dash global") == "git config --global"
    assert expand_spoken_symbols("npm install dash dash save dev") == "npm install --save dev"
    # Argument noun ("pods") precedes "dash dash".
    assert expand_spoken_symbols("kubectl get pods dash dash all") == "kubectl get pods --all"


# ---------------------------------------------------------------------------
# Bug #7 — single-dash rule restricted to CLI context
# ---------------------------------------------------------------------------
def test_single_dash_non_cli_preceder_unchanged():
    """'she dash B', 'plan dash B', 'vitamin dash C' must NOT convert (bug #7)."""
    assert expand_spoken_symbols("she dash B list celeb") == "she dash B list celeb"
    assert expand_spoken_symbols("we need plan dash B") == "we need plan dash B"
    assert expand_spoken_symbols("I got a grade dash B") == "I got a grade dash B"
    assert expand_spoken_symbols("choose option dash C") == "choose option dash C"
    assert expand_spoken_symbols("rated dash R") == "rated dash R"
    assert expand_spoken_symbols("vitamin dash C") == "vitamin dash C"


def test_single_dash_cli_preceder_still_converts():
    """'apply dash f', 'git dash x' must still convert (bug #7 guard)."""
    result = expand_spoken_symbols("kubectl apply dash f deployment dot yaml")
    assert "-f" in result
    assert result == "kubectl apply -f deployment.yaml"


# ---------------------------------------------------------------------------
# Bug #21 — "press enter" prose guard
# ---------------------------------------------------------------------------
def test_press_enter_prose_follower_unchanged():
    """'press enter to continue', 'I press enter the room' must not inject
    a newline when followed by a prose word (bug #21)."""
    assert expand_spoken_symbols("press enter to continue") == "press enter to continue"
    assert expand_spoken_symbols("I press enter the room") == "I press enter the room"
    assert expand_spoken_symbols("press enter the button") == "press enter the button"


def test_press_enter_inline_command_still_converts():
    """'first line press enter second line' -> newline (intended inline command,
    test_explicit_newline_triggers must keep passing, bug #21)."""
    result = expand_spoken_symbols("first line press enter second line")
    assert "\n" in result
    assert "first line" in result
    assert "second line" in result


# ---------------------------------------------------------------------------
# Bug #8 — Vocabulary.add() skips non-string 'typed'
# ---------------------------------------------------------------------------
from core.vocabulary import Vocabulary


def test_vocabulary_add_skips_non_string_typed():
    """Non-string 'typed' values must be skipped with a warning (bug #8)."""
    v = Vocabulary(load_starter=False)
    v.add(123)          # int — should be skipped, not crash
    v.add(True)         # bool — should be skipped
    v.add(3.14)         # float — should be skipped
    v.add(["a", "b"])   # list — should be skipped
    assert len(v.terms) == 0


def test_vocabulary_from_list_non_string_typed_skipped():
    """from_list with non-string 'typed' in a dict must not crash (bug #8)."""
    v = Vocabulary(load_starter=False)
    v.from_list([{"typed": 123}, {"typed": "kubectl"}])
    assert len(v.terms) == 1
    assert v.terms[0]["typed"] == "kubectl"


# ---------------------------------------------------------------------------
# Bug #9 — import_csv header skip uses AND, not OR
# ---------------------------------------------------------------------------
def test_import_csv_keeps_said_as_term(tmp_path):
    """A single-column CSV containing the word 'said' must NOT be dropped
    (bug #9 — was using OR which dropped legitimate terms)."""
    csv_file = tmp_path / "vocab.csv"
    csv_file.write_text("hello\nsaid\nworld\n")
    v = Vocabulary(load_starter=False)
    v.import_csv(str(csv_file))
    typed_vals = [t["typed"] for t in v.terms]
    assert "said" in typed_vals
    assert "hello" in typed_vals
    assert "world" in typed_vals


def test_import_csv_keeps_typed_as_typed_cell(tmp_path):
    """A two-column row whose second cell is the word 'typed' must NOT be
    dropped (bug #9 — was using 'or' which dropped it as a false header match).
    Column order: first col = said (alias), second col = typed (canonical)."""
    csv_file = tmp_path / "vocab.csv"
    # Header skipped because BOTH cells match (alias != 'said' so this is a
    # non-standard header that should NOT be skipped by our AND guard).
    # Row "foo,typed" -> said='foo', typed='typed' (the word "typed" is valid).
    # Row "bar,baz" -> said='bar', typed='baz'.
    csv_file.write_text("foo,typed\nbar,baz\n")
    v = Vocabulary(load_starter=False)
    v.import_csv(str(csv_file))
    typed_vals = [t["typed"] for t in v.terms]
    # The data row foo,typed must be kept (typed='typed' is the canonical form).
    assert "typed" in typed_vals
    assert "baz" in typed_vals


def test_import_csv_real_header_still_skipped(tmp_path):
    """A real 'said,typed' header row is still skipped (both cells match).
    Column order is: first col = 'said' (alias), second col = 'typed' (canonical).
    So 'cube cuttle,kubectl' -> said='cube cuttle', typed='kubectl'."""
    csv_file = tmp_path / "vocab.csv"
    # First row: header (said,typed). Data row: alias=cube cuttle, typed=kubectl.
    csv_file.write_text("said,typed\ncube cuttle,kubectl\n")
    v = Vocabulary(load_starter=False)
    v.import_csv(str(csv_file))
    typed_vals = [t["typed"] for t in v.terms]
    # Header must be skipped; data row must be imported.
    assert "typed" not in typed_vals
    assert "kubectl" in typed_vals


# ---------------------------------------------------------------------------
# Bug #16 — TranscriptionHistory has a lock
# ---------------------------------------------------------------------------
from core.history import TranscriptionHistory, TranscriptionRecord


def test_transcription_history_has_lock():
    """TranscriptionHistory must have a _lock attribute (bug #16)."""
    h = TranscriptionHistory(history_dir=None, enabled=True)
    assert hasattr(h, "_lock")
    import threading as _threading
    assert isinstance(h._lock, type(_threading.RLock()))


def test_transcription_history_concurrent_add_clear(tmp_path):
    """Concurrent add() and clear() must not raise or corrupt the list."""
    h = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    errors = []

    def _add():
        for _ in range(20):
            try:
                h.add(TranscriptionRecord.create("hi", 1.0))
            except Exception as exc:
                errors.append(exc)

    def _clear():
        for _ in range(10):
            try:
                h.clear()
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=_add) for _ in range(3)]
    threads += [threading.Thread(target=_clear) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [], f"Concurrent history errors: {errors}"


# ---------------------------------------------------------------------------
# Bug #17 — bool settings coerce strings correctly
# ---------------------------------------------------------------------------
from core.config import Settings


def test_bool_setting_string_false_parsed_as_false(tmp_path):
    """settings.json with "audio_feedback": "false" must load as False
    (bug #17 — was coercing via bool() which makes "false" truthy)."""
    import json
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"audio_feedback": "false", "save_history": "no",
                              "show_hud": "0", "fix_grammar": "False"}))
    s = Settings(settings_path=p)
    s.load()
    assert s.get("audio_feedback") is False
    assert s.get("save_history") is False
    assert s.get("show_hud") is False
    assert s.get("fix_grammar") is False


def test_bool_setting_string_true_parsed_as_true(tmp_path):
    """Truthy string forms also parse correctly (bug #17)."""
    import json
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"audio_feedback": "true", "save_history": "yes",
                              "show_hud": "1", "fix_grammar": "on"}))
    s = Settings(settings_path=p)
    s.load()
    assert s.get("audio_feedback") is True
    assert s.get("save_history") is True
    assert s.get("show_hud") is True
    assert s.get("fix_grammar") is True


def test_bool_setting_unrecognized_string_uses_default(tmp_path):
    """An unrecognized string like 'maybe' should fall back to the default."""
    import json
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"audio_feedback": "maybe"}))
    s = Settings(settings_path=p)
    s.load()
    # Default is True; the bad value should be rejected.
    from core.constants import DEFAULT_SETTINGS
    assert s.get("audio_feedback") == DEFAULT_SETTINGS["audio_feedback"]


# ---------------------------------------------------------------------------
# Bug #26 — get_recent(0) returns []
# ---------------------------------------------------------------------------
def test_get_recent_zero_returns_empty(tmp_path):
    """get_recent(0) must return [] not all records (bug #26)."""
    h = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    h.add(TranscriptionRecord.create("hello", 1.0))
    h.add(TranscriptionRecord.create("world", 1.0))
    assert h.get_recent(0) == []


def test_get_recent_negative_returns_empty(tmp_path):
    """Negative counts also return [] (bug #26 guard)."""
    h = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    h.add(TranscriptionRecord.create("hello", 1.0))
    assert h.get_recent(-5) == []


def test_get_recent_positive_works_normally(tmp_path):
    """get_recent with positive count still works after the fix."""
    h = TranscriptionHistory(history_dir=tmp_path, enabled=True)
    for i in range(5):
        h.add(TranscriptionRecord.create(f"item{i}", 1.0))
    assert len(h.get_recent(3)) == 3
    assert len(h.get_recent(10)) == 5  # fewer records than requested


# ---------------------------------------------------------------------------
# Bug #15 — Controller dry_run flag skips typing
# ---------------------------------------------------------------------------
def test_controller_dry_run_does_not_call_type_text(tmp_path):
    """When dry_run=True the Controller must NOT call TextTyper.type_text
    (bug #15 — wizard mic test was typing into the user's focused window)."""
    from core import Settings
    from ui.controller import Controller, ControllerState

    s = Settings(settings_path=tmp_path / "s.json")
    s.load()
    s.set("api_key", "sk-fake")
    s.set("output_mode", "verbatim")
    s.set("expand_spoken_symbols", False)
    s.set("vad_enabled", False)

    results = []
    controller = Controller(
        s,
        on_result=lambda t: results.append(t),
        dry_run=True,
    )

    # Override internals to avoid real I/O.
    typed_calls = []

    class _FakeEngine:
        def transcribe(self, *a, **kw):
            return "hello world"

    class _FakeFormatter:
        def format(self, text, **kw):
            return text

    class _FakeTyper:
        def type_text(self, text, **kw):
            typed_calls.append(text)
            return True

    controller._engine_factory = lambda: _FakeEngine()
    controller._formatter_factory = lambda: _FakeFormatter()
    controller._typer_factory = lambda: _FakeTyper()

    import tempfile, wave, os
    tmp_wav = tempfile.mktemp(suffix=".wav")
    with wave.open(tmp_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 3200)

    controller._process(tmp_wav, 0.1)
    try:
        os.unlink(tmp_wav)
    except OSError:
        pass

    # Result delivered via on_result callback.
    assert results == ["hello world"]
    # TextTyper.type_text must NOT have been called.
    assert typed_calls == []


# ---------------------------------------------------------------------------
# No-mangling contract additions (bugs #6, #7, #21, #22, #23)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("s", [
    "she dash B list celeb",
    "we need plan dash B",
    "I got a grade dash B",
    "choose option dash C",
    "the score was dash dash even",
    "a long dash dash mark",
    "plan dash dash backup",
    "the backtick of doom",
    "what is a backtick?",
    "please close paren the deal",
    "the open paren house",
    "press enter to continue",
    "I press enter the room",
])
def test_new_no_mangling_cases(s):
    """Regression: these strings were mangled before the bug fixes."""
    assert expand_spoken_symbols(s) == s


# ---------------------------------------------------------------------------
# Technical golden cases still work after formatting changes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("dash dash help", "--help"),
    ("git commit dash dash amend", "git commit --amend"),
    ("npm set dash dash global", "npm set --global"),
    ("git config dash dash global", "git config --global"),
    ("npm install dash dash save dev", "npm install --save dev"),
    ("kubectl get pods dash dash all", "kubectl get pods --all"),
    ("kubectl apply dash f deployment dot yaml", "kubectl apply -f deployment.yaml"),
    ("open paren hello close paren", "(hello)"),
    ("wrap backtick code backtick here", "wrap `code` here"),
    ("first line press enter second line", "first line\nsecond line"),
])
def test_technical_golden_cases_still_convert(raw, expected):
    """These technical conversions must keep working after the bug fixes."""
    assert expand_spoken_symbols(raw) == expected
