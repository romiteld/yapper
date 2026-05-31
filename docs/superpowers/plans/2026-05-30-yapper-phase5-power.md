# Phase 5: Power Features Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add the "power" tier on top of the reimagined cross-platform app — fully-wired History actions (search/copy/re-insert/reprocess/export), an AI Edit/Command mode that transforms the current selection, app-specific auto-applied Modes (Email/Chat/Code/Notes via foreground-app detection), and an opt-in live-streaming transcription engine.

**Architecture:** Pure logic (command-prompt building, mode matching, history filtering/reprocessing) is isolated into testable functions/classes in `app/core/` and TDD'd with `unittest.mock`; OS-specific surfaces (foreground-app detection, WebSocket streaming, clipboard read of a live selection) are thin shims behind injectable seams and covered by integration/manual checks. The existing Phase 4 `Controller`/`HotkeyManager`/`RecordingHUD`/`Notifier`/`TextTyper`/`Formatter`/`Vocabulary`/engine layer are reused — Phase 5 adds new modules and wires them into the already-built UI.

**Tech Stack:** Python 3.11, pytest + pytest-qt + unittest.mock, openai 2.x (`gpt-5-nano`, `reasoning_effort='minimal'`), `pyperclip`, `pynput`, PySide6/Qt6, `rapidfuzz`, `websockets` (optional `[realtime]` extra), `pyobjc`/`pywin32` (OS foreground-app, optional/guarded).

---

## File Structure

**Create**
- `app/core/commands.py` — `CommandMode`: read selection (clipboard copy) → build instruction prompt → `gpt-5-nano` transform → replace selection. Pure `build_command_messages()` helper.
- `app/core/modes.py` — `ModeManager` + `Mode` dataclass: map foreground app → profile (output_mode/translate/vocabulary/hotkey); presets Email/Chat/Code/Notes; pure `match_profile()`.
- `app/core/foreground.py` — `get_foreground_app() -> str | None`: Win (`GetForegroundWindow`+process name), mac (`NSWorkspace.frontmostApplication`), `None` elsewhere. Thin, OS-guarded, mockable.
- `app/core/engines/realtime.py` — `RealtimeEngine(TranscriptionEngine)`: opt-in `gpt-realtime` WebSocket streaming; `transcribe()` blocking-compat wrapper + `stream()` generator. Pure `build_session_config()` / `parse_event()`.
- `app/ui/command_window.py` — `CommandPalette(QWidget)`: small frameless input for typed/spoken instruction; thin controller `CommandController`.
- `tests/test_commands.py`, `tests/test_modes.py`, `tests/test_foreground.py`, `tests/test_history_actions.py`, `tests/test_realtime.py`, `tests/test_command_window.py` — unit/headless tests.

**Modify**
- `app/core/constants.py` — add Phase-5 settings keys + schema entries (`command_hotkey`, `command_mode_enabled`, `app_modes_enabled`, `app_mode_profiles`, `realtime_enabled`, `realtime_model`).
- `app/core/config.py` — migrate legacy files to include the new keys (defaults merge).
- `app/core/history.py` — add `search()`, `export_text()`, `export_csv()`, `delete()`, and extend `TranscriptionRecord` with `id` + `output_mode` (back-compat defaults).
- `app/ui/history_window.py` — wire search box, Copy, Re-insert, Reprocess (with settings override), Export, Delete to real `TranscriptionHistory` data via a non-Qt `HistoryController`.
- `app/core/engines/__init__.py` — `get_engine()` returns `RealtimeEngine` when `realtime_enabled` and `engine=='cloud'`.
- `app/ui/app.py` — register `command_hotkey`, instantiate `ModeManager`/`CommandMode`, apply active profile before each dictation, route command-hotkey into Qt via the existing `_Bridge`.

---

## Tasks

### Task 1: History data-layer — record `id` + `output_mode`, back-compatible

**Files:**
- Modify: `app/core/history.py`
- Test: `tests/test_history_actions.py`

- [ ] Write failing test for new record fields with defaults. Append to `tests/test_history_actions.py`:
```python
# tests/test_history_actions.py
from pathlib import Path
from app.core.history import TranscriptionRecord, TranscriptionHistory


def test_record_has_id_and_output_mode_defaults():
    rec = TranscriptionRecord.create("hello", 1.0)
    assert isinstance(rec.id, str) and len(rec.id) >= 8
    assert rec.output_mode == ""  # unknown/legacy -> empty


def test_legacy_record_without_new_fields_loads(tmp_path: Path):
    import json
    hist_dir = tmp_path / "logs"
    hist_dir.mkdir()
    legacy = [{
        "timestamp": "2026-05-30T10:00:00", "duration_seconds": 1.0,
        "text": "legacy", "was_translated": False, "target_language": "",
        "was_grammar_fixed": False, "source_language": "", "character_count": 6,
    }]
    (hist_dir / TranscriptionHistory.HISTORY_FILENAME).write_text(json.dumps(legacy))
    h = TranscriptionHistory(history_dir=hist_dir)
    recs = h.get_all()
    assert len(recs) == 1
    assert recs[0].id  # backfilled, non-empty
    assert recs[0].output_mode == ""
```
- [ ] Run it (expect FAIL — `id`/`output_mode` don't exist, legacy load raises `TypeError`):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -q
```
- [ ] Add fields to `TranscriptionRecord`. In `app/core/history.py`, add imports near the top (`import uuid`) and add two fields with defaults plus update `create()`:
```python
# in dataclass TranscriptionRecord, after character_count: int
    id: str = ""                # stable record id (uuid4 hex, 12 chars)
    output_mode: str = ""       # technical|natural|verbatim ("" = legacy/unknown)
```
Update `TranscriptionRecord.create` signature and body:
```python
    @classmethod
    def create(
        cls,
        text: str,
        duration: float,
        translated: bool = False,
        target_lang: str = "",
        grammar_fixed: bool = False,
        source_lang: str = "",
        output_mode: str = "",
    ) -> "TranscriptionRecord":
        return cls(
            timestamp=datetime.now().isoformat(),
            duration_seconds=round(duration, 2),
            text=text,
            was_translated=translated,
            target_language=target_lang,
            was_grammar_fixed=grammar_fixed,
            source_language=source_lang,
            character_count=len(text),
            id=uuid.uuid4().hex[:12],
            output_mode=output_mode,
        )
```
- [ ] Backfill `id` on legacy load. In `TranscriptionHistory._ensure_loaded`, replace the record-construction block so unknown keys are tolerated and `id` is backfilled:
```python
            if isinstance(data, list):
                for item in data:
                    try:
                        known = {
                            k: v for k, v in item.items()
                            if k in TranscriptionRecord.__dataclass_fields__
                        }
                        record = TranscriptionRecord(**known)
                        if not record.id:
                            record.id = uuid.uuid4().hex[:12]
                        self._records.append(record)
                    except (TypeError, KeyError) as e:
                        logger.warning(f"Skipping invalid record: {e}")
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/history.py tests/test_history_actions.py && git commit -m "feat(history): add stable record id and output_mode with legacy backfill"
```

### Task 2: History data-layer — `search`, `delete`, `export_text`, `export_csv`

**Files:**
- Modify: `app/core/history.py`
- Test: `tests/test_history_actions.py`

- [ ] Write failing tests. Append to `tests/test_history_actions.py`:
```python
def _seed(tmp_path):
    h = TranscriptionHistory(history_dir=tmp_path / "logs")
    h.add(TranscriptionRecord.create("run kubectl get pods", 1.0, output_mode="technical"))
    h.add(TranscriptionRecord.create("Dear team, hello", 2.0, output_mode="natural"))
    h.add(TranscriptionRecord.create("nginx restart now", 1.5, output_mode="technical"))
    return h


def test_search_case_insensitive_substring(tmp_path):
    h = _seed(tmp_path)
    hits = h.search("KUBECTL")
    assert len(hits) == 1 and hits[0].text == "run kubectl get pods"


def test_search_empty_returns_all_newest_first(tmp_path):
    h = _seed(tmp_path)
    hits = h.search("")
    assert [r.text for r in hits] == ["nginx restart now", "Dear team, hello", "run kubectl get pods"]


def test_delete_by_id(tmp_path):
    h = _seed(tmp_path)
    target = h.search("nginx")[0]
    assert h.delete(target.id) is True
    assert h.search("nginx") == []
    assert h.delete("does-not-exist") is False


def test_export_text_and_csv(tmp_path):
    h = _seed(tmp_path)
    txt = h.export_text(tmp_path / "out.txt")
    assert txt.exists() and "kubectl" in txt.read_text(encoding="utf-8")
    csv_path = h.export_csv(tmp_path / "out.csv")
    body = csv_path.read_text(encoding="utf-8")
    assert "timestamp" in body and "kubectl" in body and "output_mode" in body
```
- [ ] Run it (expect FAIL — methods don't exist):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -q
```
- [ ] Implement the methods. In `app/core/history.py` add `import csv` at the top, and add these methods to `TranscriptionHistory` (after `get_by_date`):
```python
    def search(self, query: str) -> List[TranscriptionRecord]:
        """Case-insensitive substring search over text; newest first. Empty query = all."""
        self._ensure_loaded()
        ordered = list(reversed(self._records))
        if not query.strip():
            return ordered
        q = query.lower()
        return [r for r in ordered if q in r.text.lower()]

    def delete(self, record_id: str) -> bool:
        """Delete a record by id. Returns True if a record was removed."""
        self._ensure_loaded()
        before = len(self._records)
        self._records = [r for r in self._records if r.id != record_id]
        if len(self._records) == before:
            return False
        return self._save()

    def export_text(self, path: Path) -> Path:
        """Export all transcript texts (oldest first) to a UTF-8 .txt file."""
        self._ensure_loaded()
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            for r in self._records:
                f.write(f"[{r.timestamp}] {r.text}\n")
        return path

    def export_csv(self, path: Path) -> Path:
        """Export all records to a CSV with a header row."""
        self._ensure_loaded()
        path = Path(path)
        fields = list(TranscriptionRecord.__dataclass_fields__.keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in self._records:
                writer.writerow(asdict(r))
        return path
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/history.py tests/test_history_actions.py && git commit -m "feat(history): add search, delete-by-id, and text/csv export"
```

### Task 3: New Phase-5 settings keys + schema + migration

**Files:**
- Modify: `app/core/constants.py`, `app/core/config.py`
- Test: `tests/test_history_actions.py` (reuse file for a config migration test) → actually create `tests/test_phase5_settings.py`

- [ ] Write failing test. Create `tests/test_phase5_settings.py`:
```python
# tests/test_phase5_settings.py
import json
from app.core.config import Settings
from app.core import constants


def test_new_defaults_present():
    for key, expected in [
        ("command_hotkey", "f7"),
        ("command_mode_enabled", True),
        ("app_modes_enabled", False),
        ("realtime_enabled", False),
        ("realtime_model", "gpt-realtime"),
    ]:
        assert constants.DEFAULT_SETTINGS[key] == expected
    assert constants.DEFAULT_SETTINGS["app_mode_profiles"] == []


def test_schema_validates_new_keys():
    for key in ("command_hotkey", "command_mode_enabled", "app_modes_enabled",
                "app_mode_profiles", "realtime_enabled", "realtime_model"):
        assert key in constants.SETTINGS_SCHEMA


def test_legacy_settings_file_gets_new_keys(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"api_key": "sk-x", "hotkey": "f8"}))
    s = Settings(settings_path=p).load()
    assert s.get("command_mode_enabled") is True
    assert s.get("realtime_enabled") is False
    assert s.get("app_mode_profiles") == []
```
- [ ] Run it (expect FAIL — keys missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_phase5_settings.py -q
```
- [ ] Add defaults to `app/core/constants.py`. Insert into `DEFAULT_SETTINGS` (after `"reduce_motion": False,` added in Phase 4; if that line is absent, add before the closing brace):
```python
    # Power features (Phase 5)
    "command_hotkey": "f7",            # AI Edit/Command mode hotkey
    "command_mode_enabled": True,      # enable selection-transform command mode
    "app_modes_enabled": False,        # auto-apply app-specific profiles
    "app_mode_profiles": [],           # list of profile dicts (see core/modes.py)
    "realtime_enabled": False,         # opt-in live streaming transcription
    "realtime_model": "gpt-realtime",  # realtime STT model
```
- [ ] Add the command hotkey to selectable `HOTKEYS` so schema validation passes. In `app/core/constants.py`, change the `HOTKEYS` list to include `"f7"` (insert before `"f8"`):
```python
HOTKEYS: List[str] = [
    "f7",
    "f8",
```
- [ ] Add schema entries to `app/core/constants.py` `SETTINGS_SCHEMA`:
```python
    "command_hotkey": (str, lambda x: x in HOTKEYS, "AI command-mode hotkey"),
    "command_mode_enabled": (bool, None, "Enable selection-transform command mode"),
    "app_modes_enabled": (bool, None, "Auto-apply app-specific profiles"),
    "app_mode_profiles": (list, None, "App-mode profile definitions"),
    "realtime_enabled": (bool, None, "Enable live streaming transcription"),
    "realtime_model": (str, lambda x: x in {"gpt-realtime", "gpt-4o-realtime-preview"}, "Realtime STT model"),
```
- [ ] Confirm migration works automatically. `Settings._data` is seeded from `DEFAULT_SETTINGS.copy()` in `__init__`, so loading a legacy file leaves new keys at defaults — no code change needed in `config.py`. (// verify: `Settings.__init__` already does `self._data = DEFAULT_SETTINGS.copy()`.)
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_phase5_settings.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/constants.py app/core/config.py tests/test_phase5_settings.py && git commit -m "feat(settings): add command-mode, app-modes, and realtime keys + schema"
```

### Task 4: `core/commands.py` — pure prompt builder for AI Edit/Command mode

**Files:**
- Create: `app/core/commands.py`
- Test: `tests/test_commands.py`

- [ ] Write failing test for the pure message builder. Create `tests/test_commands.py`:
```python
# tests/test_commands.py
from app.core.commands import build_command_messages


def test_build_messages_includes_instruction_and_selection():
    msgs = build_command_messages("make this formal", "hey whats up", protected_terms=[])
    assert msgs[0]["role"] == "system"
    assert "only the transformed text" in msgs[0]["content"].lower()
    assert msgs[1]["role"] == "user"
    assert "make this formal" in msgs[1]["content"]
    assert "hey whats up" in msgs[1]["content"]


def test_build_messages_lists_protected_terms():
    msgs = build_command_messages("translate to Spanish", "run kubectl now",
                                  protected_terms=["kubectl", "Next.js"])
    sys = msgs[0]["content"]
    assert "kubectl" in sys and "Next.js" in sys
    assert "do not translate" in sys.lower() or "preserve" in sys.lower()


def test_build_messages_empty_protected_terms_no_crash():
    msgs = build_command_messages("bullets", "a b c", protected_terms=None)
    assert len(msgs) == 2
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_commands.py -q
```
- [ ] Implement the pure builder. Create `app/core/commands.py`:
```python
"""
Yapper AI Edit / Command Mode
=============================
Transform the user's current selection per a spoken/typed instruction.

© 2026 Cloudelipute
"""

import time
from typing import Callable, List, Optional

from .logger import get_logger

logger = get_logger("commands")


def build_command_messages(
    instruction: str,
    selection: str,
    protected_terms: Optional[List[str]] = None,
) -> List[dict]:
    """
    Build chat messages for transforming `selection` according to `instruction`.

    Returns a 2-message list (system, user) suitable for APIClient.chat().
    """
    terms = [t for t in (protected_terms or []) if t]
    protected_block = ""
    if terms:
        protected_block = (
            "\nProtected technical terms — preserve EXACTLY, do not translate or "
            "rephrase them: " + ", ".join(terms) + "."
        )
    system = (
        "You edit a snippet of text the user has selected. Apply the user's "
        "instruction to the selected text and return ONLY the transformed text "
        "with no quotes, preamble, or explanation. Preserve code identifiers, "
        "CLI flags, file paths, and technical phrasing verbatim; never paraphrase "
        "technical wording." + protected_block
    )
    user = f"Instruction: {instruction}\n\nSelected text:\n{selection}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_commands.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/commands.py tests/test_commands.py && git commit -m "feat(commands): add pure prompt builder for AI command mode"
```

### Task 5: `core/commands.py` — `CommandMode.run()` with injected seams (clipboard read → LLM → replace)

**Files:**
- Modify: `app/core/commands.py`
- Test: `tests/test_commands.py`

- [ ] Write failing test using fakes for clipboard read, LLM, and typer. Append to `tests/test_commands.py`:
```python
from unittest.mock import MagicMock
from app.core.commands import CommandMode


class FakeVocab:
    def __init__(self, terms): self._terms = terms
    def protected_terms(self): return self._terms


def _make_cmd(selection_text, llm_reply, *, terms=("kubectl",)):
    api = MagicMock()
    api.chat.return_value = llm_reply
    typer = MagicMock()
    typer.type_text.return_value = True
    copied = {"text": selection_text}
    cmd = CommandMode(
        api_client=api,
        vocabulary=FakeVocab(list(terms)),
        typer=typer,
        copy_selection=lambda: copied["text"],     # injected: simulate Ctrl/Cmd+C
        settings_get=lambda k, d=None: {"text_model": "gpt-5-nano"}.get(k, d),
    )
    return cmd, api, typer


def test_run_transforms_and_replaces_selection():
    cmd, api, typer = _make_cmd("hey whats up", "Hello, how are you?")
    ok = cmd.run("make this formal")
    assert ok is True
    api.chat.assert_called_once()
    kwargs = api.chat.call_args.kwargs
    assert kwargs["model"] == "gpt-5-nano"
    typer.type_text.assert_called_once_with("Hello, how are you?", method="paste")


def test_run_aborts_on_empty_selection():
    cmd, api, typer = _make_cmd("", "unused")
    assert cmd.run("make formal") is False
    api.chat.assert_not_called()
    typer.type_text.assert_not_called()


def test_run_aborts_on_empty_instruction():
    cmd, api, typer = _make_cmd("some text", "unused")
    assert cmd.run("   ") is False
    api.chat.assert_not_called()


def test_run_returns_false_when_llm_fails():
    cmd, api, typer = _make_cmd("text", None)
    assert cmd.run("make formal") is False
    typer.type_text.assert_not_called()
```
- [ ] Run it (expect FAIL — `CommandMode` not defined):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_commands.py -q
```
- [ ] Implement `CommandMode`. Append to `app/core/commands.py`:
```python
class CommandMode:
    """
    AI Edit/Command mode: read the current selection (via an injected copy
    function), transform it with an instruction using gpt-5-nano, and paste the
    result back over the selection.

    The `copy_selection` callable performs the OS copy + clipboard read and
    returns the selected text (the UI layer wires this to a Ctrl/Cmd+C press
    followed by clipboard read). It is injected so the core stays headless-testable.
    """

    def __init__(
        self,
        api_client,
        vocabulary,
        typer,
        copy_selection: Callable[[], Optional[str]],
        settings_get: Callable[[str, object], object],
    ):
        self._api = api_client
        self._vocab = vocabulary
        self._typer = typer
        self._copy_selection = copy_selection
        self._get = settings_get

    def run(self, instruction: str) -> bool:
        """Transform the current selection per `instruction`. Returns success."""
        if not instruction or not instruction.strip():
            logger.warning("Command mode: empty instruction, aborting")
            return False

        try:
            selection = self._copy_selection()
        except Exception as e:  # noqa: BLE001 - copy can fail on locked clipboards
            logger.error(f"Command mode: failed to read selection: {e}")
            return False

        if not selection or not selection.strip():
            logger.warning("Command mode: no selection found, aborting")
            return False

        protected = []
        try:
            protected = list(self._vocab.protected_terms())
        except Exception:  # noqa: BLE001
            protected = []

        messages = build_command_messages(instruction, selection, protected)
        model = self._get("text_model", "gpt-5-nano")
        result = self._api.chat(messages, model=model, reasoning_effort="minimal")

        if not result or not result.strip():
            logger.error("Command mode: LLM returned no text")
            return False

        return self._typer.type_text(result.strip(), method="paste")
```
- [ ] Add `Vocabulary.protected_terms()` (the contract gives `terms`, `to_list()`, etc., but `CommandMode`/`ModeManager` need a flat list of typed terms). Append the method to `app/core/vocabulary.py` `Vocabulary` class (created in Phase 3):
```python
    def protected_terms(self) -> list[str]:
        """Flat list of the 'typed' forms — used to protect terms during edits/translation."""
        return [t["typed"] for t in self.terms if t.get("typed")]
```
  (// verify against the Phase 3 `Vocabulary` implementation: `terms` is a `list[dict]` of `{'said','typed'}`.)
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_commands.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/commands.py app/core/vocabulary.py tests/test_commands.py && git commit -m "feat(commands): add CommandMode.run with injected clipboard/LLM/typer seams"
```

### Task 6: `core/foreground.py` — foreground-app detection (OS-guarded, mockable)

**Files:**
- Create: `app/core/foreground.py`
- Test: `tests/test_foreground.py`

- [ ] Write a test that verifies the non-mac/non-win fallback and that the function never raises. Create `tests/test_foreground.py`:
```python
# tests/test_foreground.py
import app.core.foreground as fg


def test_returns_none_or_str_never_raises(monkeypatch):
    # Force the "unsupported platform" branch.
    monkeypatch.setattr(fg, "_PLATFORM", "Linux", raising=False)
    assert fg.get_foreground_app() is None


def test_windows_branch_uses_injected_impl(monkeypatch):
    monkeypatch.setattr(fg, "_PLATFORM", "Windows", raising=False)
    monkeypatch.setattr(fg, "_foreground_windows", lambda: "Code.exe", raising=False)
    assert fg.get_foreground_app() == "Code.exe"


def test_mac_branch_uses_injected_impl(monkeypatch):
    monkeypatch.setattr(fg, "_PLATFORM", "Darwin", raising=False)
    monkeypatch.setattr(fg, "_foreground_macos", lambda: "com.apple.Mail", raising=False)
    assert fg.get_foreground_app() == "com.apple.Mail"


def test_swallows_impl_exceptions(monkeypatch):
    monkeypatch.setattr(fg, "_PLATFORM", "Windows", raising=False)
    def boom(): raise RuntimeError("no win32")
    monkeypatch.setattr(fg, "_foreground_windows", boom, raising=False)
    assert fg.get_foreground_app() is None
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_foreground.py -q
```
- [ ] Implement `app/core/foreground.py`:
```python
"""
Yapper Foreground App Detection
==============================
Best-effort current-foreground-app identifier for app-specific Modes.
Returns a process name (Windows, e.g. "Code.exe") or bundle id (macOS, e.g.
"com.microsoft.VSCode"); None on unsupported platforms or any failure.

© 2026 Cloudelipute
"""

import platform

from .logger import get_logger

logger = get_logger("foreground")

_PLATFORM = platform.system()  # "Windows" | "Darwin" | "Linux"


def _foreground_windows() -> "str | None":
    """Foreground window's owning process name (e.g. 'Code.exe')."""
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wt.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
        return None
    finally:
        kernel32.CloseHandle(h)


def _foreground_macos() -> "str | None":
    """Frontmost application's bundle identifier (e.g. 'com.apple.mail')."""
    from AppKit import NSWorkspace  # pyobjc

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return None
    return app.bundleIdentifier() or app.localizedName()


def get_foreground_app() -> "str | None":
    """Return the foreground app id, or None on any platform/error."""
    try:
        if _PLATFORM == "Windows":
            return _foreground_windows()
        if _PLATFORM == "Darwin":
            return _foreground_macos()
        return None
    except Exception as e:  # noqa: BLE001 - never let detection crash a dictation
        logger.debug(f"Foreground app detection failed: {e}")
        return None
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_foreground.py -q
```
- [ ] Manual integration check (run on a real OS desktop, not CI):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -c "from app.core.foreground import get_foreground_app; print(repr(get_foreground_app()))"
```
  Expected: a non-empty string like `'Code.exe'` (Win) or `'com.microsoft.VSCode'` (mac); `None` is acceptable on Linux/headless.
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/foreground.py tests/test_foreground.py && git commit -m "feat(foreground): add OS-guarded foreground-app detection"
```

### Task 7: `core/modes.py` — `Mode` dataclass, presets, and pure `match_profile`

**Files:**
- Create: `app/core/modes.py`
- Test: `tests/test_modes.py`

- [ ] Write failing tests for matching logic and presets. Create `tests/test_modes.py`:
```python
# tests/test_modes.py
from app.core.modes import Mode, match_profile, PRESET_PROFILES


def test_presets_cover_email_chat_code_notes():
    names = {p["name"] for p in PRESET_PROFILES}
    assert {"Email", "Chat", "Code", "Notes"} <= names


def test_match_profile_substring_case_insensitive():
    profiles = [
        {"name": "Code", "match": ["code", "pycharm"], "output_mode": "technical"},
        {"name": "Email", "match": ["mail", "outlook"], "output_mode": "natural"},
    ]
    p = match_profile("com.microsoft.VSCode", profiles)
    assert p["name"] == "Code"
    p2 = match_profile("Microsoft Outlook.exe", profiles)
    assert p2["name"] == "Email"


def test_match_profile_no_match_returns_none():
    profiles = [{"name": "Code", "match": ["code"], "output_mode": "technical"}]
    assert match_profile("Terminal", profiles) is None
    assert match_profile(None, profiles) is None


def test_mode_dataclass_to_dict_roundtrip():
    m = Mode(name="Code", match=["code"], output_mode="technical",
             translate_to="", vocabulary=["kubectl"], hotkey="f8")
    d = m.to_dict()
    assert d["name"] == "Code" and d["vocabulary"] == ["kubectl"]
    assert Mode.from_dict(d) == m
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_modes.py -q
```
- [ ] Implement `app/core/modes.py` (dataclass + presets + pure matcher; manager added next task):
```python
"""
Yapper App-Specific Modes (Power Mode)
=====================================
Map the foreground app to a profile that bundles output_mode + translate +
vocabulary + hotkey, applied automatically while that app is in front.

© 2026 Cloudelipute
"""

from dataclasses import dataclass, asdict, field
from typing import List, Optional

from .logger import get_logger

logger = get_logger("modes")


@dataclass
class Mode:
    """An app-specific profile."""
    name: str
    match: List[str] = field(default_factory=list)   # substrings matched vs foreground app id
    output_mode: str = "technical"                    # technical|natural|verbatim
    translate_to: str = ""                            # "" = no translation
    vocabulary: List[str] = field(default_factory=list)  # extra protected terms
    hotkey: str = ""                                  # "" = use global hotkey

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Mode":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


# Built-in starter profiles. `match` entries are lowercased substrings tested
# against the foreground app id (process name or bundle id).
PRESET_PROFILES: List[dict] = [
    {"name": "Email", "match": ["mail", "outlook", "thunderbird", "spark"],
     "output_mode": "natural", "translate_to": "", "vocabulary": [], "hotkey": ""},
    {"name": "Chat", "match": ["slack", "discord", "teams", "telegram", "whatsapp"],
     "output_mode": "natural", "translate_to": "", "vocabulary": [], "hotkey": ""},
    {"name": "Code", "match": ["code", "vscode", "pycharm", "intellij", "terminal",
                               "iterm", "windowsterminal", "sublime", "zed", "cursor"],
     "output_mode": "technical", "translate_to": "", "vocabulary": [], "hotkey": ""},
    {"name": "Notes", "match": ["notion", "obsidian", "notes", "bear", "onenote"],
     "output_mode": "natural", "translate_to": "", "vocabulary": [], "hotkey": ""},
]


def match_profile(app_id: Optional[str], profiles: List[dict]) -> Optional[dict]:
    """Return the first profile whose `match` substring appears in `app_id`."""
    if not app_id:
        return None
    haystack = app_id.lower()
    for profile in profiles:
        for needle in profile.get("match", []):
            if needle and needle.lower() in haystack:
                return profile
    return None
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_modes.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/modes.py tests/test_modes.py && git commit -m "feat(modes): add Mode dataclass, preset profiles, and pure matcher"
```

### Task 8: `core/modes.py` — `ModeManager.active_profile()` with injected detector

**Files:**
- Modify: `app/core/modes.py`
- Test: `tests/test_modes.py`

- [ ] Write failing tests. Append to `tests/test_modes.py`:
```python
from app.core.modes import ModeManager


def _settings(enabled, profiles):
    store = {"app_modes_enabled": enabled, "app_mode_profiles": profiles}
    class S:
        def get(self, k, d=None): return store.get(k, d)
    return S()


def test_active_profile_disabled_returns_none():
    mgr = ModeManager(_settings(False, [{"name": "Code", "match": ["code"]}]),
                      detector=lambda: "VSCode")
    assert mgr.active_profile() is None


def test_active_profile_uses_user_profiles_then_presets():
    user = [{"name": "MyCode", "match": ["code"], "output_mode": "technical"}]
    mgr = ModeManager(_settings(True, user), detector=lambda: "com.microsoft.VSCode")
    assert mgr.active_profile()["name"] == "MyCode"


def test_active_profile_falls_back_to_presets_when_no_user_profiles():
    mgr = ModeManager(_settings(True, []), detector=lambda: "Slack.exe")
    assert mgr.active_profile()["name"] == "Chat"


def test_active_profile_none_when_no_match():
    mgr = ModeManager(_settings(True, []), detector=lambda: "SomeRandomApp")
    assert mgr.active_profile() is None
```
- [ ] Run it (expect FAIL — `ModeManager` not defined):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_modes.py -q
```
- [ ] Implement `ModeManager`. Append to `app/core/modes.py`:
```python
class ModeManager:
    """
    Resolves the active app-specific profile by detecting the foreground app and
    matching it against user-defined profiles (preferred) then built-in presets.

    `detector` is injected (defaults to core.foreground.get_foreground_app) so the
    manager stays headless-testable.
    """

    def __init__(self, settings, detector=None):
        self._settings = settings
        if detector is None:
            from .foreground import get_foreground_app
            detector = get_foreground_app
        self._detector = detector

    def active_profile(self) -> Optional[dict]:
        """Return the profile for the current foreground app, or None."""
        if not self._settings.get("app_modes_enabled", False):
            return None
        app_id = self._detector()
        if not app_id:
            return None
        user_profiles = self._settings.get("app_mode_profiles", []) or []
        profile = match_profile(app_id, user_profiles)
        if profile is None:
            profile = match_profile(app_id, PRESET_PROFILES)
        if profile is not None:
            logger.debug(f"Active app-mode profile '{profile.get('name')}' for {app_id}")
        return profile
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_modes.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/modes.py tests/test_modes.py && git commit -m "feat(modes): add ModeManager.active_profile with injected detector"
```

### Task 9: `core/engines/realtime.py` — pure session/event helpers

**Files:**
- Create: `app/core/engines/realtime.py`
- Test: `tests/test_realtime.py`

- [ ] Write failing tests for the pure helpers (no network). Create `tests/test_realtime.py`:
```python
# tests/test_realtime.py
import json
from app.core.engines.realtime import build_session_config, parse_event


def test_session_config_sets_model_and_pcm16():
    cfg = build_session_config(model="gpt-realtime", language="en", prompt="kubectl")
    assert cfg["type"] == "transcription_session.update"
    audio = cfg["session"]["input_audio_format"]
    assert audio == "pcm16"
    tr = cfg["session"]["input_audio_transcription"]
    assert tr["model"] == "gpt-realtime"
    assert tr["language"] == "en"
    assert tr["prompt"] == "kubectl"


def test_session_config_omits_empty_language_and_prompt():
    cfg = build_session_config(model="gpt-realtime", language=None, prompt=None)
    tr = cfg["session"]["input_audio_transcription"]
    assert "language" not in tr and "prompt" not in tr


def test_parse_event_partial_delta():
    ev = json.dumps({"type": "conversation.item.input_audio_transcription.delta",
                     "delta": "hel"})
    kind, text = parse_event(ev)
    assert kind == "partial" and text == "hel"


def test_parse_event_completed():
    ev = json.dumps({"type": "conversation.item.input_audio_transcription.completed",
                     "transcript": "hello world"})
    kind, text = parse_event(ev)
    assert kind == "final" and text == "hello world"


def test_parse_event_other_is_ignored():
    kind, text = parse_event(json.dumps({"type": "session.updated"}))
    assert kind == "other" and text == ""


def test_parse_event_bad_json_is_other():
    kind, text = parse_event("not json")
    assert kind == "other"
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_realtime.py -q
```
- [ ] Implement `app/core/engines/realtime.py` (pure helpers + a `transcribe()` that lazy-imports `websockets`):
```python
"""
Yapper Realtime (live streaming) Engine — OPT-IN
================================================
Streams audio to OpenAI's realtime transcription endpoint over a WebSocket and
emits partial + final transcripts. Opt-in only (settings.realtime_enabled).

Requires the optional [realtime] extra: `websockets`.

© 2026 Cloudelipute
"""

import json
import wave
from typing import Callable, Optional, Tuple

from .base import TranscriptionEngine
from ..logger import get_logger

logger = get_logger("realtime")

REALTIME_URL = "wss://api.openai.com/v1/realtime?intent=transcription"


def build_session_config(model: str, language: Optional[str], prompt: Optional[str]) -> dict:
    """Build the transcription_session.update payload for the realtime socket."""
    transcription: dict = {"model": model}
    if language:
        transcription["language"] = language
    if prompt:
        transcription["prompt"] = prompt
    return {
        "type": "transcription_session.update",
        "session": {
            "input_audio_format": "pcm16",
            "input_audio_transcription": transcription,
            "turn_detection": {"type": "server_vad"},
        },
    }


def parse_event(raw: str) -> Tuple[str, str]:
    """
    Parse a server event JSON string.

    Returns (kind, text): kind in {'partial','final','other'}.
    """
    try:
        ev = json.loads(raw)
    except (ValueError, TypeError):
        return ("other", "")
    etype = ev.get("type", "")
    if etype.endswith("input_audio_transcription.delta"):
        return ("partial", ev.get("delta", ""))
    if etype.endswith("input_audio_transcription.completed"):
        return ("final", ev.get("transcript", ""))
    return ("other", "")


class RealtimeEngine(TranscriptionEngine):
    """
    Opt-in streaming engine. `transcribe()` provides the blocking,
    TranscriptionEngine-compatible path (used when streaming UI isn't active):
    it opens the socket, streams the WAV, and returns the final transcript.

    `on_partial` (optional) is called with partial text so the HUD can show
    live words; the UI sets it before invoking.
    """

    def __init__(self, api_key: str, model: str = "gpt-realtime"):
        self._api_key = api_key
        self._model = model
        self.on_partial: Optional[Callable[[str], None]] = None

    def transcribe(self, wav_path: str, language: Optional[str] = None,
                   prompt: Optional[str] = None) -> Optional[str]:
        try:
            import asyncio
            return asyncio.run(self._run(wav_path, language, prompt))
        except Exception as e:  # noqa: BLE001
            logger.error(f"Realtime transcription failed: {e}")
            return None

    async def _run(self, wav_path: str, language: Optional[str],
                   prompt: Optional[str]) -> Optional[str]:
        try:
            import websockets  # optional [realtime] extra
        except ImportError:
            logger.error("websockets not installed; run: uv sync --extra realtime")
            return None

        headers = {"Authorization": f"Bearer {self._api_key}",
                   "OpenAI-Beta": "realtime=v1"}
        final_parts: list[str] = []
        # `additional_headers` is the websockets>=14 kwarg.  // verify against docs
        async with websockets.connect(REALTIME_URL, additional_headers=headers) as ws:
            await ws.send(json.dumps(build_session_config(self._model, language, prompt)))
            with wave.open(wav_path, "rb") as wf:
                import base64
                frame = wf.readframes(3200)  # ~100ms @16k mono int16
                while frame:
                    await ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(frame).decode("ascii"),
                    }))
                    frame = wf.readframes(3200)
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            async for raw in ws:
                kind, text = parse_event(raw)
                if kind == "partial" and self.on_partial:
                    self.on_partial(text)
                elif kind == "final":
                    final_parts.append(text)
                    break
        return " ".join(p for p in final_parts if p).strip() or None
```
- [ ] Run it (expect PASS — only the pure helpers are exercised; `_run` is never called):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_realtime.py -q
```
- [ ] Add the optional extra to `pyproject.toml`. Under `[project.optional-dependencies]` add:
```toml
realtime = ["websockets>=14.0"]
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/engines/realtime.py tests/test_realtime.py pyproject.toml && git commit -m "feat(engines): add opt-in RealtimeEngine with pure session/event helpers"
```

### Task 10: Wire `get_engine()` to return `RealtimeEngine` when opted in

**Files:**
- Modify: `app/core/engines/__init__.py`
- Test: `tests/test_realtime.py`

- [ ] Write failing test. Append to `tests/test_realtime.py`:
```python
from app.core.engines import get_engine
from app.core.engines.realtime import RealtimeEngine


class _S:
    def __init__(self, d): self._d = d
    def get(self, k, default=None): return self._d.get(k, default)


def test_get_engine_returns_realtime_when_enabled():
    s = _S({"engine": "cloud", "realtime_enabled": True,
            "api_key": "sk-x", "realtime_model": "gpt-realtime"})
    eng = get_engine(s)
    assert isinstance(eng, RealtimeEngine)


def test_get_engine_skips_realtime_for_local_engine():
    s = _S({"engine": "local", "realtime_enabled": True, "api_key": "sk-x"})
    eng = get_engine(s)
    assert not isinstance(eng, RealtimeEngine)
```
- [ ] Run it (expect FAIL — current `get_engine` ignores realtime):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_realtime.py -k get_engine -q
```
- [ ] Modify `get_engine` in `app/core/engines/__init__.py`. Add a realtime short-circuit at the top of the function body (before the existing cloud/local branch from Phase 2):
```python
def get_engine(settings):
    """Return the configured TranscriptionEngine."""
    engine = settings.get("engine", "cloud")
    if engine == "cloud" and settings.get("realtime_enabled", False):
        from .realtime import RealtimeEngine
        return RealtimeEngine(
            api_key=settings.get("api_key", ""),
            model=settings.get("realtime_model", "gpt-realtime"),
        )
    # ... existing cloud / local selection from Phase 2 follows unchanged ...
```
  (// verify: keep the Phase 2 `CloudEngine`/`LocalEngine` branch below this guard intact.)
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_realtime.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/engines/__init__.py tests/test_realtime.py && git commit -m "feat(engines): route get_engine to RealtimeEngine when opted in"
```

### Task 11: `HistoryController` — non-Qt logic for the History window actions

**Files:**
- Modify: `app/ui/history_window.py` (add `HistoryController`)
- Test: `tests/test_history_actions.py`

- [ ] Write failing tests for the controller (no Qt). Append to `tests/test_history_actions.py`:
```python
from unittest.mock import MagicMock
from app.ui.history_window import HistoryController


def _ctrl(tmp_path):
    hist = TranscriptionHistory(history_dir=tmp_path / "logs")
    hist.add(TranscriptionRecord.create("run kubectl get pods", 1.0, output_mode="technical"))
    hist.add(TranscriptionRecord.create("dear team hello", 2.0, output_mode="natural"))
    typer = MagicMock(); typer.type_text.return_value = True
    formatter = MagicMock(); formatter.format.return_value = "REPROCESSED"
    ctrl = HistoryController(history=hist, typer=typer, formatter=formatter)
    return ctrl, hist, typer, formatter


def test_controller_search(tmp_path):
    ctrl, *_ = _ctrl(tmp_path)
    rows = ctrl.search("kubectl")
    assert len(rows) == 1 and rows[0].text == "run kubectl get pods"


def test_controller_reinsert_pastes(tmp_path):
    ctrl, hist, typer, _ = _ctrl(tmp_path)
    rec = ctrl.search("kubectl")[0]
    assert ctrl.reinsert(rec.id) is True
    typer.type_text.assert_called_once_with("run kubectl get pods", method="paste")


def test_controller_reprocess_uses_formatter_and_pastes(tmp_path):
    ctrl, hist, typer, formatter = _ctrl(tmp_path)
    rec = ctrl.search("kubectl")[0]
    out = ctrl.reprocess(rec.id, mode="natural", expand_symbols=False, translate_to="es")
    assert out == "REPROCESSED"
    formatter.format.assert_called_once()
    kwargs = formatter.format.call_args.kwargs
    assert kwargs["mode"] == "natural" and kwargs["translate_to"] == "es"
    typer.type_text.assert_called_once_with("REPROCESSED", method="paste")


def test_controller_delete(tmp_path):
    ctrl, hist, *_ = _ctrl(tmp_path)
    rec = ctrl.search("kubectl")[0]
    assert ctrl.delete(rec.id) is True
    assert ctrl.search("kubectl") == []


def test_controller_export(tmp_path):
    ctrl, *_ = _ctrl(tmp_path)
    p = ctrl.export(tmp_path / "h.csv", fmt="csv")
    assert p.exists() and "kubectl" in p.read_text(encoding="utf-8")
```
- [ ] Run it (expect FAIL — `HistoryController` missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -k controller -q
```
- [ ] Add `HistoryController` to `app/ui/history_window.py` (above the `HistoryWindow` Qt class so it can be imported without a `QApplication`):
```python
class HistoryController:
    """
    Non-Qt logic backing the History window. Holds the TranscriptionHistory plus
    the shared TextTyper and Formatter, so the Qt widget is a thin view.
    """

    def __init__(self, history, typer, formatter):
        self._history = history
        self._typer = typer
        self._formatter = formatter

    def search(self, query: str):
        return self._history.search(query)

    def _find(self, record_id: str):
        for r in self._history.get_all():
            if r.id == record_id:
                return r
        return None

    def reinsert(self, record_id: str) -> bool:
        rec = self._find(record_id)
        if rec is None:
            return False
        return self._typer.type_text(rec.text, method="paste")

    def reprocess(self, record_id: str, *, mode: str, expand_symbols: bool,
                  translate_to):
        rec = self._find(record_id)
        if rec is None:
            return None
        result = self._formatter.format(
            rec.text, mode=mode, expand_symbols=expand_symbols,
            translate_to=translate_to,
        )
        if result:
            self._typer.type_text(result, method="paste")
        return result

    def delete(self, record_id: str) -> bool:
        return self._history.delete(record_id)

    def export(self, path, fmt: str = "txt"):
        if fmt == "csv":
            return self._history.export_csv(path)
        return self._history.export_text(path)
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -k controller -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/history_window.py tests/test_history_actions.py && git commit -m "feat(history-ui): add non-Qt HistoryController for search/reinsert/reprocess/export/delete"
```

### Task 12: Wire History window widgets to `HistoryController` (pytest-qt)

**Files:**
- Modify: `app/ui/history_window.py`
- Test: `tests/test_history_actions.py`

- [ ] Write a pytest-qt smoke test that drives the real widget. Append to `tests/test_history_actions.py`:
```python
import pytest

pytestmark_qt = pytest.importorskip("pytestqt")  # skip if pytest-qt unavailable


def test_history_window_search_filters_list(qtbot, tmp_path):
    from app.ui.history_window import HistoryWindow
    ctrl, *_ = _ctrl(tmp_path)
    win = HistoryWindow(controller=ctrl)
    qtbot.addWidget(win)
    win.refresh()
    assert win.list_widget.count() == 2
    win.search_box.setText("kubectl")
    win.on_search_changed("kubectl")
    assert win.list_widget.count() == 1
```
- [ ] Run it (expect FAIL — `HistoryWindow` does not yet accept a `controller` / lacks `search_box`/`list_widget`/`on_search_changed`/`refresh`):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -k window -q
```
- [ ] Update `HistoryWindow.__init__` in `app/ui/history_window.py` to accept the controller and expose the widgets the test asserts. Add/adjust the constructor and a `refresh`/`on_search_changed`:
```python
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Yapper — History")
        from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLineEdit,
                                       QListWidget, QPushButton)
        layout = QVBoxLayout(self)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search transcripts…")
        self.search_box.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_box)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        actions = QHBoxLayout()
        self.copy_btn = QPushButton("Copy")
        self.reinsert_btn = QPushButton("Re-insert")
        self.reprocess_btn = QPushButton("Reprocess…")
        self.delete_btn = QPushButton("Delete")
        self.export_btn = QPushButton("Export…")
        for b in (self.copy_btn, self.reinsert_btn, self.reprocess_btn,
                  self.delete_btn, self.export_btn):
            actions.addWidget(b)
        layout.addLayout(actions)
        self.copy_btn.clicked.connect(self._on_copy)
        self.reinsert_btn.clicked.connect(self._on_reinsert)
        self.reprocess_btn.clicked.connect(self._on_reprocess)
        self.delete_btn.clicked.connect(self._on_delete)
        self.export_btn.clicked.connect(self._on_export)
        self.refresh()

    def refresh(self):
        self.on_search_changed(self.search_box.text())

    def on_search_changed(self, query: str):
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        self.list_widget.clear()
        for rec in self._controller.search(query):
            item = QListWidgetItem(f"{rec.timestamp[:19]}  {rec.text}")
            item.setData(Qt.UserRole, rec.id)
            self.list_widget.addItem(item)

    def _selected_id(self):
        from PySide6.QtCore import Qt
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_copy(self):
        rid = self._selected_id()
        if not rid:
            return
        import pyperclip
        for rec in self._controller.search(""):
            if rec.id == rid:
                pyperclip.copy(rec.text)
                return

    def _on_reinsert(self):
        rid = self._selected_id()
        if rid:
            self._controller.reinsert(rid)

    def _on_reprocess(self):
        rid = self._selected_id()
        if not rid:
            return
        from PySide6.QtWidgets import QInputDialog
        mode, ok = QInputDialog.getItem(
            self, "Reprocess", "Output mode:",
            ["technical", "natural", "verbatim"], 0, False)
        if ok:
            self._controller.reprocess(rid, mode=mode, expand_symbols=True,
                                       translate_to=None)
            self.refresh()

    def _on_delete(self):
        rid = self._selected_id()
        if rid and self._controller.delete(rid):
            self.refresh()

    def _on_export(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export history", "yapper_history.csv",
            "CSV (*.csv);;Text (*.txt)")
        if path:
            self._controller.export(path, fmt="csv" if path.endswith(".csv") else "txt")
```
  (// verify: if Phase 4 already laid out `HistoryWindow`, fold these widgets/methods into the existing class instead of duplicating the layout; the test only requires `controller`, `search_box`, `list_widget`, `refresh`, `on_search_changed`.)
- [ ] Run it (expect PASS, or SKIP if pytest-qt/PySide6 absent in this env):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_history_actions.py -k window -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/history_window.py tests/test_history_actions.py && git commit -m "feat(history-ui): wire search/copy/reinsert/reprocess/export/delete buttons to controller"
```

### Task 13: `CommandController` + `CommandPalette` — typed-instruction palette (pytest-qt)

**Files:**
- Create: `app/ui/command_window.py`
- Test: `tests/test_command_window.py`

- [ ] Write a failing non-Qt controller test plus a Qt smoke test. Create `tests/test_command_window.py`:
```python
# tests/test_command_window.py
import pytest
from unittest.mock import MagicMock
from app.ui.command_window import CommandController


def test_controller_submit_runs_command_mode():
    cmd = MagicMock(); cmd.run.return_value = True
    ctrl = CommandController(command_mode=cmd)
    assert ctrl.submit("make this formal") is True
    cmd.run.assert_called_once_with("make this formal")


def test_controller_ignores_blank():
    cmd = MagicMock()
    ctrl = CommandController(command_mode=cmd)
    assert ctrl.submit("   ") is False
    cmd.run.assert_not_called()


def test_palette_emits_submit(qtbot):
    pytest.importorskip("PySide6")
    from app.ui.command_window import CommandPalette
    cmd = MagicMock(); cmd.run.return_value = True
    pal = CommandPalette(CommandController(command_mode=cmd))
    qtbot.addWidget(pal)
    pal.input.setText("translate to Spanish")
    pal._submit()
    cmd.run.assert_called_once_with("translate to Spanish")
```
- [ ] Run it (expect FAIL — module missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_command_window.py -q
```
- [ ] Implement `app/ui/command_window.py`:
```python
"""
Yapper Command Palette
=====================
A small frameless input that captures a typed (or dictated) edit instruction and
runs it through CommandMode against the user's current selection.

© 2026 Cloudelipute
"""

from ..core.logger import get_logger

logger = get_logger("command_window")


class CommandController:
    """Non-Qt logic: validate the instruction and dispatch to CommandMode."""

    def __init__(self, command_mode):
        self._command_mode = command_mode

    def submit(self, instruction: str) -> bool:
        if not instruction or not instruction.strip():
            return False
        return bool(self._command_mode.run(instruction.strip()))


try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit
    from PySide6.QtCore import Qt

    class CommandPalette(QWidget):
        """Frameless always-on-top single-line instruction box."""

        def __init__(self, controller: CommandController, parent=None):
            super().__init__(parent)
            self._controller = controller
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            layout = QVBoxLayout(self)
            self.input = QLineEdit()
            self.input.setPlaceholderText(
                "Edit selection: 'make formal', 'translate to Spanish', 'bullets'…")
            self.input.returnPressed.connect(self._submit)
            layout.addWidget(self.input)

        def _submit(self):
            ok = self._controller.submit(self.input.text())
            if ok:
                self.input.clear()
                self.hide()

        def open_palette(self):
            self.input.clear()
            self.show()
            self.input.setFocus()
except ImportError:  # PySide6 not installed (headless CI)
    CommandPalette = None  # type: ignore
```
- [ ] Run it (expect PASS; Qt test SKIPs if PySide6 absent):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_command_window.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/command_window.py tests/test_command_window.py && git commit -m "feat(command-ui): add CommandController and CommandPalette for AI edit mode"
```

### Task 14: Selection-copy helper for the UI (Ctrl/Cmd+C → clipboard read)

**Files:**
- Modify: `app/ui/app.py` (add a module-level `copy_current_selection`)
- Test: `tests/test_command_window.py`

- [ ] Write a failing test that mocks pynput + pyperclip. Append to `tests/test_command_window.py`:
```python
def test_copy_current_selection_presses_modifier_and_reads_clipboard(monkeypatch):
    import app.ui.app as appmod

    presses = []

    class FakeController:
        def __init__(self): pass
        def press(self, k): presses.append(("press", k))
        def release(self, k): presses.append(("release", k))

    fake_pynput = MagicMock()
    fake_pynput.keyboard.Controller = FakeController
    fake_pynput.keyboard.Key = MagicMock()
    monkeypatch.setattr(appmod, "_pynput_keyboard", fake_pynput.keyboard, raising=False)
    monkeypatch.setattr(appmod, "pyperclip", MagicMock(paste=lambda: "SELECTED"), raising=False)

    text = appmod.copy_current_selection(settle=0.0)
    assert text == "SELECTED"
    assert any(a == "press" for a, _ in presses)
```
- [ ] Run it (expect FAIL — `copy_current_selection` not defined):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_command_window.py -k copy_current_selection -q
```
- [ ] Add the helper to `app/ui/app.py`. Near the top-level imports add module aliases (so tests can monkeypatch them), then the function:
```python
import platform as _platform
import time as _time

import pyperclip  # noqa: F401  (module-level so tests can monkeypatch)
from pynput import keyboard as _pynput_keyboard  # noqa: F401


def copy_current_selection(settle: float = 0.12):
    """
    Copy the user's current selection by synthesizing Cmd/Ctrl+C, then read the
    clipboard. Returns the selected text (may be empty). Used by AI command mode.
    """
    ctrl = _pynput_keyboard.Controller()
    Key = _pynput_keyboard.Key
    mod = Key.cmd if _platform.system() == "Darwin" else Key.ctrl
    ctrl.press(mod)
    ctrl.press("c")
    ctrl.release("c")
    ctrl.release(mod)
    if settle:
        _time.sleep(settle)  # let the foreground app populate the clipboard
    try:
        return pyperclip.paste()
    except Exception:  # noqa: BLE001
        return ""
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_command_window.py -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/app.py tests/test_command_window.py && git commit -m "feat(command-ui): add copy_current_selection helper (Ctrl/Cmd+C then clipboard read)"
```

### Task 15: App-mode profile application — pure `apply_profile_to_settings`

**Files:**
- Modify: `app/core/modes.py`
- Test: `tests/test_modes.py`

- [ ] Write failing test for a pure overlay function that produces a per-dictation override dict (without mutating saved settings). Append to `tests/test_modes.py`:
```python
from app.core.modes import apply_profile_to_settings


def test_apply_profile_overrides_mode_and_translate_and_vocab():
    base = {"output_mode": "verbatim", "translate_to": "", "vocabulary": ["base"]}
    profile = {"name": "Code", "output_mode": "technical", "translate_to": "fr",
               "vocabulary": ["kubectl"]}
    out = apply_profile_to_settings(base, profile)
    assert out["output_mode"] == "technical"
    assert out["translate_to"] == "fr"
    assert "kubectl" in out["vocabulary"] and "base" in out["vocabulary"]
    # base must be untouched
    assert base["output_mode"] == "verbatim"


def test_apply_profile_none_returns_base_copy():
    base = {"output_mode": "natural", "translate_to": "", "vocabulary": []}
    out = apply_profile_to_settings(base, None)
    assert out == base and out is not base


def test_apply_profile_blank_fields_do_not_override():
    base = {"output_mode": "natural", "translate_to": "es", "vocabulary": []}
    profile = {"name": "X", "output_mode": "", "translate_to": "", "vocabulary": []}
    out = apply_profile_to_settings(base, profile)
    assert out["output_mode"] == "natural"  # blank profile field ignored
    assert out["translate_to"] == "es"
```
- [ ] Run it (expect FAIL — function missing):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_modes.py -k apply_profile -q
```
- [ ] Implement `apply_profile_to_settings` in `app/core/modes.py`:
```python
def apply_profile_to_settings(base: dict, profile: Optional[dict]) -> dict:
    """
    Return a copy of `base` with the profile's non-blank fields overlaid.
    Vocabulary is merged (base + profile, de-duplicated, order-preserving).
    Never mutates `base`.
    """
    result = dict(base)
    result["vocabulary"] = list(base.get("vocabulary", []) or [])
    if not profile:
        return result
    if profile.get("output_mode"):
        result["output_mode"] = profile["output_mode"]
    if profile.get("translate_to"):
        result["translate_to"] = profile["translate_to"]
    for term in profile.get("vocabulary", []) or []:
        if term not in result["vocabulary"]:
            result["vocabulary"].append(term)
    return result
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_modes.py -k apply_profile -q
```
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/modes.py tests/test_modes.py && git commit -m "feat(modes): add pure apply_profile_to_settings overlay"
```

### Task 16: Integrate command-mode, app-modes, and realtime HUD into `ui/app.py` (wiring + smoke)

**Files:**
- Modify: `app/ui/app.py`
- Test: `tests/test_app_wiring.py`

- [ ] Write a failing wiring test that checks the bridge signal and resolver methods exist and the command hotkey is registered, without spinning a real `QApplication` (use a fake/headless path). Create `tests/test_app_wiring.py`:
```python
# tests/test_app_wiring.py
import pytest
from unittest.mock import MagicMock


def test_resolve_dictation_settings_applies_active_profile(monkeypatch):
    import app.ui.app as appmod
    # Build a YapperApp instance without constructing Qt: call the pure resolver
    # via a lightweight object exposing the same method.
    base = {"output_mode": "verbatim", "translate_to": "", "vocabulary": []}

    class S:
        def get(self, k, d=None): return base.get(k, d)

    mode_mgr = MagicMock()
    mode_mgr.active_profile.return_value = {
        "name": "Code", "output_mode": "technical", "translate_to": "", "vocabulary": []}
    resolved = appmod.resolve_dictation_settings(S(), mode_mgr)
    assert resolved["output_mode"] == "technical"


def test_resolve_dictation_settings_no_profile(monkeypatch):
    import app.ui.app as appmod
    base = {"output_mode": "natural", "translate_to": "", "vocabulary": []}

    class S:
        def get(self, k, d=None): return base.get(k, d)

    mode_mgr = MagicMock()
    mode_mgr.active_profile.return_value = None
    resolved = appmod.resolve_dictation_settings(S(), mode_mgr)
    assert resolved["output_mode"] == "natural"
```
- [ ] Run it (expect FAIL — `resolve_dictation_settings` not defined):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_app_wiring.py -q
```
- [ ] Add the pure resolver to `app/ui/app.py` (module-level, so it's testable without Qt):
```python
def resolve_dictation_settings(settings, mode_manager):
    """
    Compute the effective per-dictation settings: read the user's base
    output_mode/translate_to/vocabulary, then overlay the active app-mode
    profile (if any). Pure; called right before each transcription.
    """
    from ..core.modes import apply_profile_to_settings
    base = {
        "output_mode": settings.get("output_mode", "technical"),
        "translate_to": settings.get("translate_to", ""),
        "vocabulary": settings.get("vocabulary", []),
    }
    profile = mode_manager.active_profile() if mode_manager else None
    return apply_profile_to_settings(base, profile)
```
- [ ] Run it (expect PASS):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_app_wiring.py -q
```
- [ ] Wire the runtime pieces into `YapperApp.__init__` (no test asserts these directly; verified by the smoke step below). Inside `YapperApp.__init__`, after the existing controller/hotkey setup from Phase 4, add:
```python
        # --- Phase 5: power features ---
        from ..core.modes import ModeManager
        from ..core.commands import CommandMode
        from ..core.foreground import get_foreground_app
        from .command_window import CommandController, CommandPalette

        self.mode_manager = ModeManager(self.settings, detector=get_foreground_app)
        self.command_mode = CommandMode(
            api_client=self.api_client,
            vocabulary=self.vocabulary,
            typer=self.typer,
            copy_selection=lambda: copy_current_selection(),
            settings_get=self.settings.get,
        )
        self._command_palette = CommandPalette(CommandController(self.command_mode))

        if self.settings.get("command_mode_enabled", True):
            self._command_hotkey = HotkeyManager(
                mode="toggle",
                hotkey=self.settings.get("command_hotkey", "f7"),
                on_start=lambda: self._bridge.command_requested.emit(),
                on_stop=lambda: None,
            )
            self._command_hotkey.start()
```
  Add a signal to the `_Bridge` class in `app/ui/app.py`:
```python
        command_requested = Signal()
```
  Connect it in `YapperApp.__init__` after the bridge exists:
```python
        self._bridge.command_requested.connect(self._command_palette.open_palette)
```
  And make the dictation entrypoint (the slot that runs after recording stops — Phase 4's `_on_recording_finished`/equivalent) call `resolve_dictation_settings(self.settings, self.mode_manager)` to get `output_mode`/`translate_to`/`vocabulary` for that turn, passing them into `Formatter.format(...)`. (// verify: locate the Phase 4 method that calls `self.formatter.format(...)` and replace its hard-coded `mode=`/`translate_to=` args with values from the resolved dict.)
- [ ] Hook realtime partials into the HUD when opted in. Where the engine is obtained (`get_engine(self.settings)`), add:
```python
        from ..core.engines.realtime import RealtimeEngine
        if isinstance(self.engine, RealtimeEngine) and self.settings.get("show_hud", True):
            self.engine.on_partial = lambda text: self._bridge.partial_text.emit(text)
```
  Add `partial_text = Signal(str)` to `_Bridge` and connect it to the HUD:
```python
        self._bridge.partial_text.connect(
            lambda t: self.hud.set_state("transcribing"))
```
  (The HUD's live-text display is a Phase 4 concern; here we at least drive the `transcribing` state from partials. // verify HUD has `set_state`.)
- [ ] Smoke-check the module imports cleanly (catches signal/typo wiring errors without a display server):
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && QT_QPA_PLATFORM=offscreen python -c "import app.ui.app as a; print('app import OK', hasattr(a, 'resolve_dictation_settings'), hasattr(a, 'copy_current_selection'))"
```
  Expected: `app import OK True True` (or a clean `ModuleNotFoundError: PySide6` if Qt isn't installed in this env — acceptable; the pure tests above still pass).
- [ ] Run the full Phase 5 suite:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_app_wiring.py tests/test_commands.py tests/test_modes.py tests/test_foreground.py tests/test_history_actions.py tests/test_realtime.py tests/test_command_window.py tests/test_phase5_settings.py -q
```
  Expected: all pass (Qt-only tests SKIP if PySide6/pytest-qt are absent).
- [ ] Commit:
```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/ui/app.py tests/test_app_wiring.py && git commit -m "feat(app): wire command mode, app-modes, and realtime HUD partials into the Qt app"
```

### Task 17: Manual integration checklist (real desktop, not CI)

**Files:**
- Test: manual (document results in the PR description; no code)

- [ ] Run the app on a real macOS Apple Silicon machine and a real Windows machine: `./run.command` (mac) / `run.bat` (win).
- [ ] **History actions:** open History; type a query → list filters live; select a row → Copy puts text on clipboard; Re-insert pastes into a focused editor; Reprocess… pick "natural" → transformed text pastes; Export… → produced `.csv` opens with all columns; Delete removes the row and persists after relaunch.
- [ ] **AI Command mode:** select text in an editor, press the command hotkey (`f7`), type "make this formal", press Enter → selection is replaced by the formal version; verify code identifiers in the selection are preserved verbatim; test "translate to Spanish" and "bullets".
- [ ] **App-specific Modes:** enable `app_modes_enabled`; focus VS Code → dictate, confirm Technical mode (identifiers preserved); focus Mail/Outlook → dictate, confirm Natural prose; focus Slack → Natural. Confirm `core.foreground.get_foreground_app()` returns a sane id on both OSes.
- [ ] **Live streaming (opt-in):** enable `realtime_enabled`; dictate a long sentence → HUD shows `transcribing` and the final text pastes; disable it → falls back to the standard cloud engine.
- [ ] **macOS permissions:** confirm command mode's synthesized Cmd+C and the paste both require Accessibility (Phase 1 guidance) — if not granted, command mode degrades gracefully (no crash, empty selection → no-op).
- [ ] Record pass/fail for each in the PR; file follow-ups for any failures (do not silently fix during the manual pass).
