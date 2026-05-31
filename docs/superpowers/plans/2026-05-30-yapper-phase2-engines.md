# Phase 2: Engine Abstraction & Model Updates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Introduce a pluggable transcription-engine abstraction (cloud + local), upgrade `core/api.py` to OpenAI 2.x with current model names (`gpt-4o-mini-transcribe` for STT, `gpt-5-nano` for text), and refactor `core/transcriber.py` to orchestrate over the selected engine while preserving wake-word cleaning and retry logic.

**Architecture:** A new `core/engines/` package defines `TranscriptionEngine` (ABC), `CloudEngine` (wraps the upgraded `APIClient`), and `LocalEngine` (lazy-imports `mlx_whisper`/`faster_whisper`), selected by `get_engine(settings)`. `APIClient` gains a `prompt=` bias on transcription and routes chat/post-processing through `gpt-5-nano` with `reasoning_effort='minimal'`. `Transcriber` is refactored to call the chosen engine plus a passthrough formatting hook (the real Formatter arrives in Phase 3).

**Tech Stack:** Python 3.11, `openai>=2.38`, `pytest`, `unittest.mock`, optional `[local]` extra (`mlx-whisper` on mac / `faster-whisper` on win).

---

## File Structure

**Create**
- `app/core/engines/__init__.py` — exports `TranscriptionEngine`, `CloudEngine`, `LocalEngine`, `get_engine`.
- `app/core/engines/base.py` — `TranscriptionEngine(ABC)` with the single `transcribe(...)` contract.
- `app/core/engines/cloud.py` — `CloudEngine`: wraps `APIClient`, default model `gpt-4o-mini-transcribe`.
- `app/core/engines/local.py` — `LocalEngine`: lazy local backend (mlx/faster-whisper), optional `[local]` extra.
- `tests/__init__.py` — empty package marker for the test suite.
- `tests/conftest.py` — shared fixtures (`mock_openai`, `fake_local_backend`, `settings_factory`).
- `tests/test_api_models.py` — asserts correct model names/params passed to the mocked OpenAI client + retry preserved.
- `tests/test_engines.py` — engine ABC contract, `CloudEngine`, `LocalEngine`, `get_engine` selection.
- `tests/test_transcriber_orchestration.py` — `Transcriber` orchestrates over an engine + passthrough formatting.
- `tests/test_config_migration_phase2.py` — new settings keys default + legacy migration.

**Modify**
- `app/core/api.py` — OpenAI 2.x; `transcribe(prompt=)`; `chat`/`translate`/`fix_grammar` on `gpt-5-nano` w/ `reasoning_effort='minimal'`; drop deprecated `gpt-4.1-nano`/`whisper-1` default.
- `app/core/constants.py` — add `engine`, `cloud_stt_model`, `local_stt_model`, `text_model` to `DEFAULT_SETTINGS` + `SETTINGS_SCHEMA`; add enum/option lists.
- `app/core/config.py` — `migrate()` step for legacy settings files (keep old keys).
- `app/core/transcriber.py` — accept `Settings`/engine; orchestrate engine + passthrough formatter; keep wake-word cleaning.
- `app/core/__init__.py` — export the new engine symbols.

---

## Tasks

### Task 1: Test scaffolding (conftest + fixtures)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

> Note: Phase 0 adds `pytest` to `pyproject.toml` and creates `tests/`. If the directory does not yet exist, these steps create it. `conftest.py` makes `app/` importable so `from core...` works without installing.

- [ ] **Step 1.1** — Create the test package marker.

  Create `tests/__init__.py` (empty file, single newline).

- [ ] **Step 1.2** — Write `tests/conftest.py` with shared fixtures.

  Create `tests/conftest.py`:

  ```python
  """Shared pytest fixtures for Yapper tests."""
  import sys
  from pathlib import Path
  from unittest.mock import MagicMock

  import pytest

  # Make `app/` importable so `import core...` resolves.
  APP_DIR = Path(__file__).resolve().parent.parent / "app"
  if str(APP_DIR) not in sys.path:
      sys.path.insert(0, str(APP_DIR))


  @pytest.fixture
  def mock_openai(monkeypatch):
      """Patch `openai.OpenAI` so no network call happens.

      Returns the mock *client instance* (openai.OpenAI(...) return value).
      Configure: mock_openai.audio.transcriptions.create.return_value = "..."
                 mock_openai.chat.completions.create.return_value = <obj>
      """
      client = MagicMock(name="OpenAIClient")
      # Default transcription returns a plain string (response_format='text').
      client.audio.transcriptions.create.return_value = "hello world"

      # Default chat returns an object shaped like the SDK response.
      chat_resp = MagicMock()
      chat_resp.choices = [MagicMock()]
      chat_resp.choices[0].message.content = "cleaned text"
      client.chat.completions.create.return_value = chat_resp

      factory = MagicMock(name="OpenAIFactory", return_value=client)
      # `core.api` does `from openai import OpenAI` inside _get_client.
      import openai
      monkeypatch.setattr(openai, "OpenAI", factory)
      client._factory = factory  # expose for assertions on constructor args
      return client


  @pytest.fixture
  def fake_local_backend():
      """A stand-in local whisper backend exposing a `transcribe(...)` callable."""
      backend = MagicMock(name="LocalBackend")
      backend.transcribe.return_value = {"text": " local transcript "}
      return backend


  @pytest.fixture
  def settings_factory():
      """Build a core.config.Settings with overrides, no file I/O."""
      from core.config import Settings

      def _make(**overrides):
          s = Settings.__new__(Settings)
          from core.constants import DEFAULT_SETTINGS
          s._path = Path("/tmp/yapper-test-settings.json")
          s._data = {**DEFAULT_SETTINGS, **overrides}
          s._extra_data = {}
          return s

      return _make
  ```

- [ ] **Step 1.3** — Verify the scaffolding imports and `openai` is installed.

  Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -c "import openai; print(openai.__version__)" && python -m pytest tests/conftest.py -q
  ```
  Expected: prints an `openai` version `>= 2.38`, and pytest reports `no tests ran` (collecting `conftest.py` defines fixtures, runs zero tests — exit code 5 is acceptable here). If `openai` import fails, install Phase 0 deps first: `uv sync` (or `pip install 'openai>=2.38'`). // verify against docs

- [ ] **Step 1.4** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/__init__.py tests/conftest.py && git commit -m "test: add pytest scaffolding and shared fixtures for phase 2"
  ```

---

### Task 2: New settings keys (constants)

**Files:**
- Modify: `app/core/constants.py`
- Test: `tests/test_config_migration_phase2.py`

- [ ] **Step 2.1** — Write the failing test for new defaults + schema.

  Create `tests/test_config_migration_phase2.py`:
  ```python
  """Phase 2: new engine/model settings keys + legacy migration."""
  import json

  from core.constants import (
      DEFAULT_SETTINGS,
      SETTINGS_SCHEMA,
      ENGINES,
      CLOUD_STT_MODELS,
      TEXT_MODELS,
  )


  def test_new_keys_have_defaults():
      assert DEFAULT_SETTINGS["engine"] == "cloud"
      assert DEFAULT_SETTINGS["cloud_stt_model"] == "gpt-4o-mini-transcribe"
      assert DEFAULT_SETTINGS["local_stt_model"] == "base"
      assert DEFAULT_SETTINGS["text_model"] == "gpt-5-nano"


  def test_new_keys_in_schema():
      for key in ("engine", "cloud_stt_model", "local_stt_model", "text_model"):
          assert key in SETTINGS_SCHEMA


  def test_option_lists_present():
      assert "cloud" in ENGINES and "local" in ENGINES
      assert "gpt-4o-mini-transcribe" in CLOUD_STT_MODELS
      assert "whisper-1" in CLOUD_STT_MODELS
      assert "gpt-5-nano" in TEXT_MODELS
      assert "gpt-4.1-nano" not in TEXT_MODELS  # deprecated, must be gone


  def test_engine_schema_rejects_bad_value():
      typ, validator, _ = SETTINGS_SCHEMA["engine"]
      assert typ is str
      assert validator("cloud") is True
      assert validator("bogus") is False
  ```

- [ ] **Step 2.2** — Run it (expect FAIL: `ImportError` on `ENGINES`).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_config_migration_phase2.py -q
  ```
  Expected: collection/import error — `cannot import name 'ENGINES' from 'core.constants'`.

- [ ] **Step 2.3** — Add option lists to `app/core/constants.py`.

  Insert after the `HOTKEYS` list block (after line 87, before the `DEFAULT SETTINGS` header):
  ```python
  # =============================================================================
  # ENGINES & MODELS
  # =============================================================================

  # Transcription engine backends
  ENGINES: List[str] = ["cloud", "local"]

  # Activation modes (consumed by hotkeys.py in Phase 1)
  ACTIVATION_MODES: List[str] = ["push_to_talk", "toggle", "wake_word"]

  # Cloud speech-to-text models (gpt-4o-mini-transcribe default; whisper-1 kept
  # for long-tail languages / timestamps).
  CLOUD_STT_MODELS: List[str] = ["gpt-4o-mini-transcribe", "whisper-1"]

  # Local on-device model sizes (mlx-whisper / faster-whisper).
  LOCAL_STT_MODELS: List[str] = ["tiny", "base", "small", "medium", "large-v3"]

  # Text post-processing / translation models.
  # gpt-4.1-nano is DEPRECATED (shutdown 2026-10-23) and intentionally excluded.
  TEXT_MODELS: List[str] = ["gpt-5-nano", "gpt-5.4-nano"]
  ```

- [ ] **Step 2.4** — Add new defaults to `DEFAULT_SETTINGS` in `app/core/constants.py`.

  Edit the `DEFAULT_SETTINGS` dict — insert these keys right after the `"api_key": "",` line:
  ```python
      # Engine & models (Phase 2)
      "engine": "cloud",                            # cloud | local
      "cloud_stt_model": "gpt-4o-mini-transcribe",  # or whisper-1
      "local_stt_model": "base",                    # mlx/faster-whisper size
      "text_model": "gpt-5-nano",                   # post-processing/translation
  ```

- [ ] **Step 2.5** — Add schema entries to `SETTINGS_SCHEMA` in `app/core/constants.py`.

  Insert after the `"api_key": (...)` line inside `SETTINGS_SCHEMA`:
  ```python
      "engine": (str, lambda x: x in ENGINES, "Transcription engine"),
      "cloud_stt_model": (str, lambda x: x in CLOUD_STT_MODELS, "Cloud STT model"),
      "local_stt_model": (str, lambda x: x in LOCAL_STT_MODELS, "Local STT model"),
      "text_model": (str, lambda x: x in TEXT_MODELS, "Text post-processing model"),
  ```

- [ ] **Step 2.6** — Run the test (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_config_migration_phase2.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 2.7** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/constants.py tests/test_config_migration_phase2.py && git commit -m "feat(config): add engine/model settings keys and option lists"
  ```

---

### Task 3: Legacy settings migration

**Files:**
- Modify: `app/core/config.py`
- Test: `tests/test_config_migration_phase2.py` (extend)

> Legacy `settings.json` files predate the engine keys. Loading must fill in defaults for the new keys without losing existing values, and the `engine` key must default to `cloud` for any file that lacks it. This is additive — old keys are preserved by the existing `_extra_data`/`_data` logic, but the new keys need explicit backfill so callers always read a value.

- [ ] **Step 3.1** — Add failing migration tests to `tests/test_config_migration_phase2.py`.

  Append:
  ```python
  def test_legacy_file_backfills_new_keys(tmp_path):
      from core.config import Settings, set_settings_path
      legacy = {
          "api_key": "sk-legacy",
          "hotkey": "f8",
          "translate_to": "",
          "fix_grammar": True,
          "always_listening": True,  # legacy key, must be preserved
      }
      p = tmp_path / "settings.json"
      p.write_text(json.dumps(legacy), encoding="utf-8")

      set_settings_path(p)
      s = Settings(p).load()

      # New keys present with sane defaults.
      assert s.get("engine") == "cloud"
      assert s.get("cloud_stt_model") == "gpt-4o-mini-transcribe"
      assert s.get("text_model") == "gpt-5-nano"
      # Legacy values preserved.
      assert s.get("api_key") == "sk-legacy"
      assert s.get("always_listening") is True


  def test_migrate_is_idempotent(tmp_path):
      from core.config import Settings
      p = tmp_path / "settings.json"
      p.write_text(json.dumps({"api_key": "sk-x"}), encoding="utf-8")
      s = Settings(p).load()
      first = s.get("text_model")
      s.save()
      s2 = Settings(p).load()
      assert s2.get("text_model") == first == "gpt-5-nano"
  ```

- [ ] **Step 3.2** — Run (expect FAIL: `engine` resolves to `None` because legacy file + `get` default chain returns `DEFAULT_SETTINGS.get("engine")` which now exists — so this may actually pass for `get`; the failing assertion is the idempotency `save()`/reload round-trip if migration is absent). Confirm actual behavior:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_config_migration_phase2.py -q -k "legacy or idempotent"
  ```
  Expected: at least one FAIL. (If both pass because `get()` already falls back to `DEFAULT_SETTINGS`, still add the explicit migration below so saved files are self-documenting and future-proof; the migration test for `_migrated` below will then be the failing one.)

- [ ] **Step 3.3** — Add an explicit `migrate()` method and call it from `load()` in `app/core/config.py`.

  In `Settings.load()`, replace the final `return self` with a migrate call. Change:
  ```python
            logger.debug(f"Loaded settings from {self._path}")

        except json.JSONDecodeError as e:
  ```
  to:
  ```python
            logger.debug(f"Loaded settings from {self._path}")
            self.migrate()

        except json.JSONDecodeError as e:
  ```

  Add this method to the `Settings` class (after `_create_default_file`):
  ```python
    def migrate(self) -> bool:
        """Backfill new keys onto legacy settings files.

        Returns True if any value was changed (caller may choose to save).
        Idempotent: running twice changes nothing.
        """
        changed = False

        # Backfill any DEFAULT_SETTINGS key missing from the loaded data.
        for key, default in DEFAULT_SETTINGS.items():
            if key not in self._data:
                self._data[key] = default
                changed = True

        # Legacy: `always_listening` was the wake-word toggle. Mirror it onto
        # the new activation_mode if that key is owned elsewhere (Phase 1).
        # We only set it when activation_mode is unknown to avoid clobbering.
        if "activation_mode" not in DEFAULT_SETTINGS:
            # activation_mode is owned by Phase 1; nothing to migrate here yet.
            pass

        if changed:
            logger.info("Migrated legacy settings: backfilled new keys")
        return changed
  ```

  > Note: `activation_mode` is added by Phase 1's constants change. This `migrate()` is intentionally engine/model-only here; the activation-mode mapping belongs to Phase 1 and is left as a no-op guard so the two migrations compose without conflict. // verify against Phase 1 plan

- [ ] **Step 3.4** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_config_migration_phase2.py -q
  ```
  Expected: `6 passed`.

- [ ] **Step 3.5** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/config.py tests/test_config_migration_phase2.py && git commit -m "feat(config): backfill new engine/model keys via Settings.migrate()"
  ```

---

### Task 4: Upgrade `core/api.py` — transcription model + prompt bias

**Files:**
- Modify: `app/core/api.py`
- Test: `tests/test_api_models.py`

- [ ] **Step 4.1** — Write the failing transcription test.

  Create `tests/test_api_models.py`:
  ```python
  """Phase 2: APIClient passes correct OpenAI 2.x models/params; retry preserved."""
  from unittest.mock import mock_open, patch

  import pytest

  from core.api import APIClient


  def _make_client():
      return APIClient(api_key="sk-test")


  def test_transcribe_default_model_and_params(mock_openai, tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      client = _make_client()

      out = client.transcribe(str(wav), language="en", prompt="kubectl Next.js")

      assert out == "hello world"
      call = mock_openai.audio.transcriptions.create.call_args
      assert call.kwargs["model"] == "gpt-4o-mini-transcribe"
      assert call.kwargs["response_format"] == "text"
      assert call.kwargs["language"] == "en"
      assert call.kwargs["prompt"] == "kubectl Next.js"


  def test_transcribe_honors_explicit_model(mock_openai, tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      client = _make_client()

      client.transcribe(str(wav), model="whisper-1")
      call = mock_openai.audio.transcriptions.create.call_args
      assert call.kwargs["model"] == "whisper-1"


  def test_transcribe_omits_empty_prompt_and_language(mock_openai, tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      client = _make_client()

      client.transcribe(str(wav))
      kwargs = mock_openai.audio.transcriptions.create.call_args.kwargs
      assert "language" not in kwargs
      assert "prompt" not in kwargs
  ```

- [ ] **Step 4.2** — Run (expect FAIL: default model is `whisper-1`, no `prompt` kwarg).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_api_models.py -q -k transcribe
  ```
  Expected: FAIL on `model == "gpt-4o-mini-transcribe"` and on `prompt` (TypeError: unexpected keyword argument `prompt`).

- [ ] **Step 4.3** — Update `APIClient.transcribe` in `app/core/api.py`.

  Replace the entire `transcribe` method (lines 148–190) with:
  ```python
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        model: str = "gpt-4o-mini-transcribe",
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file.
            language: Optional language hint (ISO code).
            model: STT model (default gpt-4o-mini-transcribe; whisper-1 selectable).
            prompt: Optional vocabulary bias passed to the model.

        Returns:
            Transcribed text or None on failure.
        """
        def _do_transcribe() -> str:
            client = self._get_client()

            with open(audio_path, "rb") as audio_file:
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "file": audio_file,
                    "response_format": "text",
                }
                if language:
                    kwargs["language"] = language
                if prompt:
                    kwargs["prompt"] = prompt

                result = client.audio.transcriptions.create(**kwargs)

                # response_format='text' returns a plain str; guard for objects.
                if isinstance(result, str):
                    return result.strip()
                return result.text.strip()

        logger.debug(f"Transcribing: {audio_path} (model={model})")
        text = self._with_retry(_do_transcribe, "Transcription")

        if text:
            logger.debug(f"Transcribed {len(text)} characters")

        return text
  ```

- [ ] **Step 4.4** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_api_models.py -q -k transcribe
  ```
  Expected: `3 passed`.

- [ ] **Step 4.5** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/api.py tests/test_api_models.py && git commit -m "feat(api): default transcription to gpt-4o-mini-transcribe with prompt bias"
  ```

---

### Task 5: Upgrade `core/api.py` — chat/text model (`gpt-5-nano`, reasoning_effort)

**Files:**
- Modify: `app/core/api.py`
- Test: `tests/test_api_models.py` (extend)

> OpenAI 2.x reasoning models (gpt-5-nano) use `reasoning_effort` and do **not** accept the legacy `temperature`/`max_tokens` the same way. Per the shared contract: `client.chat.completions.create(model='gpt-5-nano', messages=..., reasoning_effort='minimal')`. We drop `temperature`/`max_tokens` from the call for reasoning models and replace the `gpt-4.1-nano` defaults everywhere.

- [ ] **Step 5.1** — Add failing chat/translate/fix_grammar tests.

  Append to `tests/test_api_models.py`:
  ```python
  def test_chat_uses_gpt5nano_and_reasoning_effort(mock_openai):
      client = _make_client()
      out = client.chat([{"role": "user", "content": "hi"}])
      assert out == "cleaned text"
      kwargs = mock_openai.chat.completions.create.call_args.kwargs
      assert kwargs["model"] == "gpt-5-nano"
      assert kwargs["reasoning_effort"] == "minimal"
      # Reasoning models: legacy sampling args must NOT be sent.
      assert "temperature" not in kwargs
      assert "max_tokens" not in kwargs


  def test_fix_grammar_default_model(mock_openai):
      client = _make_client()
      client.fix_grammar("teh cat")
      assert mock_openai.chat.completions.create.call_args.kwargs["model"] == "gpt-5-nano"


  def test_translate_default_model(mock_openai):
      client = _make_client()
      client.translate("hello", target_language="es")
      assert mock_openai.chat.completions.create.call_args.kwargs["model"] == "gpt-5-nano"


  def test_no_deprecated_model_referenced():
      import inspect
      import core.api as api_mod
      src = inspect.getsource(api_mod)
      assert "gpt-4.1-nano" not in src
  ```

- [ ] **Step 5.2** — Run (expect FAIL: model still `gpt-4.1-nano`, `reasoning_effort` absent, `temperature` present).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_api_models.py -q -k "chat or grammar or translate or deprecated"
  ```
  Expected: 4 FAIL.

- [ ] **Step 5.3** — Rewrite `chat` in `app/core/api.py`.

  Replace the entire `chat` method (lines 192–224) with:
  ```python
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-nano",
        reasoning_effort: str = "minimal",
    ) -> Optional[str]:
        """
        Send a chat completion request to a reasoning model.

        Args:
            messages: List of message dicts.
            model: Text model (default gpt-5-nano).
            reasoning_effort: 'minimal' for fast, low-latency post-processing.

        Returns:
            Response text or None on failure.
        """
        def _do_chat() -> str:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                reasoning_effort=reasoning_effort,
            )
            return response.choices[0].message.content.strip()

        logger.debug(f"Chat request ({model}) with {len(messages)} messages")
        return self._with_retry(_do_chat, "Chat")
  ```

- [ ] **Step 5.4** — Update `translate` defaults in `app/core/api.py`.

  Change the signature line:
  ```python
        model: str = "gpt-4.1-nano"
  ```
  inside `translate` (line 229) to:
  ```python
        model: str = "gpt-5-nano",
  ```
  And change its `self.chat(...)` call (line 258) from:
  ```python
        result = self.chat(messages, model=model, temperature=0.3)
  ```
  to:
  ```python
        result = self.chat(messages, model=model)
  ```

- [ ] **Step 5.5** — Update `fix_grammar` defaults in `app/core/api.py`.

  Change its signature line (line 269):
  ```python
        model: str = "gpt-4.1-nano"
  ```
  to:
  ```python
        model: str = "gpt-5-nano",
  ```
  And change its `self.chat(...)` call (line 294) from:
  ```python
        result = self.chat(messages, model=model, temperature=0.2)
  ```
  to:
  ```python
        result = self.chat(messages, model=model)
  ```

- [ ] **Step 5.6** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_api_models.py -q
  ```
  Expected: `7 passed`.

- [ ] **Step 5.7** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/api.py tests/test_api_models.py && git commit -m "feat(api): route chat/translate/grammar to gpt-5-nano with reasoning_effort=minimal"
  ```

---

### Task 6: Verify retry logic is preserved after the API rewrite

**Files:**
- Test: `tests/test_api_models.py` (extend)

> The rewrite must not break `_with_retry` / `_is_retryable_error`. Add explicit regression tests rather than assuming.

- [ ] **Step 6.1** — Add failing-then-passing retry tests.

  Append to `tests/test_api_models.py`:
  ```python
  class _RateLimitError(Exception):
      """Stand-in named to match _is_retryable_error allow-list."""
      def __init__(self):
          super().__init__("rate limited")
  _RateLimitError.__name__ = "RateLimitError"


  def test_transcribe_retries_then_succeeds(mock_openai, tmp_path, monkeypatch):
      monkeypatch.setattr("core.api.time.sleep", lambda *_: None)  # no real waiting
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      mock_openai.audio.transcriptions.create.side_effect = [
          _RateLimitError(),
          "second try",
      ]
      client = APIClient(api_key="sk-test")
      out = client.transcribe(str(wav))
      assert out == "second try"
      assert mock_openai.audio.transcriptions.create.call_count == 2


  def test_chat_gives_up_after_max_retries(mock_openai, monkeypatch):
      monkeypatch.setattr("core.api.time.sleep", lambda *_: None)
      mock_openai.chat.completions.create.side_effect = _RateLimitError()
      client = APIClient(api_key="sk-test")
      out = client.chat([{"role": "user", "content": "x"}])
      assert out is None
      assert mock_openai.chat.completions.create.call_count == 3  # MAX_RETRIES
  ```

- [ ] **Step 6.2** — Run (expect PASS — retry code was untouched; this is a regression guard).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_api_models.py -q -k retry
  ```
  Expected: `2 passed`. If FAIL, the rewrite regressed retry — fix `transcribe`/`chat` to keep calling `self._with_retry`.

- [ ] **Step 6.3** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/test_api_models.py && git commit -m "test(api): regression-guard retry logic after model upgrade"
  ```

---

### Task 7: Engine ABC (`engines/base.py`)

**Files:**
- Create: `app/core/engines/__init__.py` (temporary minimal export; finalized in Task 10)
- Create: `app/core/engines/base.py`
- Test: `tests/test_engines.py`

- [ ] **Step 7.1** — Write the failing ABC contract test.

  Create `tests/test_engines.py`:
  ```python
  """Phase 2: engine abstraction (ABC, cloud, local, selection)."""
  import inspect
  from abc import ABC

  import pytest

  from core.engines.base import TranscriptionEngine


  def test_base_is_abstract():
      assert issubclass(TranscriptionEngine, ABC)
      with pytest.raises(TypeError):
          TranscriptionEngine()  # cannot instantiate abstract class


  def test_transcribe_signature():
      sig = inspect.signature(TranscriptionEngine.transcribe)
      params = list(sig.parameters)
      assert params == ["self", "wav_path", "language", "prompt"]
      assert sig.parameters["language"].default is None
      assert sig.parameters["prompt"].default is None
  ```

- [ ] **Step 7.2** — Run (expect FAIL: module does not exist).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k "base or signature"
  ```
  Expected: collection error — `No module named 'core.engines'`.

- [ ] **Step 7.3** — Create the package and ABC.

  Create `app/core/engines/__init__.py`:
  ```python
  """Yapper transcription engines.

  © 2026 Cloudelipute
  """

  from .base import TranscriptionEngine

  __all__ = ["TranscriptionEngine"]
  ```

  Create `app/core/engines/base.py`:
  ```python
  """
  Transcription engine abstraction.
  ===============================
  Defines the contract every STT backend (cloud, local) must satisfy.

  © 2026 Cloudelipute
  """

  from abc import ABC, abstractmethod
  from typing import Optional


  class TranscriptionEngine(ABC):
      """Abstract base for speech-to-text engines."""

      @abstractmethod
      def transcribe(
          self,
          wav_path: str,
          language: Optional[str] = None,
          prompt: Optional[str] = None,
      ) -> Optional[str]:
          """Transcribe a 16 kHz mono WAV file to text.

          Args:
              wav_path: Path to the WAV file.
              language: Optional ISO language hint.
              prompt: Optional vocabulary bias.

          Returns:
              Transcribed text, or None on failure / empty audio.
          """
          raise NotImplementedError
  ```

- [ ] **Step 7.4** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k "base or signature"
  ```
  Expected: `2 passed`.

- [ ] **Step 7.5** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/engines/ tests/test_engines.py && git commit -m "feat(engines): add TranscriptionEngine ABC"
  ```

---

### Task 8: `CloudEngine` (`engines/cloud.py`)

**Files:**
- Create: `app/core/engines/cloud.py`
- Test: `tests/test_engines.py` (extend)

- [ ] **Step 8.1** — Write the failing `CloudEngine` test.

  Append to `tests/test_engines.py`:
  ```python
  from unittest.mock import MagicMock

  from core.engines.cloud import CloudEngine
  from core.engines.base import TranscriptionEngine


  def test_cloud_engine_is_engine():
      assert issubclass(CloudEngine, TranscriptionEngine)


  def test_cloud_engine_delegates_to_api_client():
      api = MagicMock()
      api.transcribe.return_value = "hi there"
      eng = CloudEngine(api_client=api, model="gpt-4o-mini-transcribe")

      out = eng.transcribe("/tmp/x.wav", language="en", prompt="kubectl")

      assert out == "hi there"
      api.transcribe.assert_called_once_with(
          "/tmp/x.wav",
          language="en",
          model="gpt-4o-mini-transcribe",
          prompt="kubectl",
      )


  def test_cloud_engine_default_model():
      api = MagicMock()
      api.transcribe.return_value = "ok"
      eng = CloudEngine(api_client=api)
      eng.transcribe("/tmp/x.wav")
      assert api.transcribe.call_args.kwargs["model"] == "gpt-4o-mini-transcribe"
  ```

- [ ] **Step 8.2** — Run (expect FAIL: module missing).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k cloud
  ```
  Expected: import error — `No module named 'core.engines.cloud'`.

- [ ] **Step 8.3** — Create `app/core/engines/cloud.py`.
  ```python
  """
  Cloud transcription engine (OpenAI).
  ====================================
  Wraps APIClient; default model gpt-4o-mini-transcribe.

  © 2026 Cloudelipute
  """

  from typing import Optional

  from ..api import APIClient
  from ..logger import get_logger
  from .base import TranscriptionEngine

  logger = get_logger("engines.cloud")


  class CloudEngine(TranscriptionEngine):
      """OpenAI-backed speech-to-text engine."""

      def __init__(
          self,
          api_client: APIClient,
          model: str = "gpt-4o-mini-transcribe",
      ):
          self._api = api_client
          self._model = model

      def transcribe(
          self,
          wav_path: str,
          language: Optional[str] = None,
          prompt: Optional[str] = None,
      ) -> Optional[str]:
          logger.debug(f"CloudEngine.transcribe model={self._model}")
          return self._api.transcribe(
              wav_path,
              language=language,
              model=self._model,
              prompt=prompt,
          )
  ```

- [ ] **Step 8.4** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k cloud
  ```
  Expected: `3 passed`.

- [ ] **Step 8.5** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/engines/cloud.py tests/test_engines.py && git commit -m "feat(engines): add CloudEngine wrapping APIClient"
  ```

---

### Task 9: `LocalEngine` (`engines/local.py`)

**Files:**
- Create: `app/core/engines/local.py`
- Test: `tests/test_engines.py` (extend)

> `LocalEngine` must **not** import `mlx_whisper`/`faster_whisper` at module load (they live behind the optional `[local]` extra). It lazy-loads the right backend per OS on first `transcribe`, raises a clear error if the extra is missing, and exposes a `_load_backend` seam tests can patch.

- [ ] **Step 9.1** — Write failing `LocalEngine` tests (lazy import via injected backend).

  Append to `tests/test_engines.py`:
  ```python
  from core.engines.local import LocalEngine, LocalEngineUnavailable


  def test_local_engine_is_engine():
      assert issubclass(LocalEngine, TranscriptionEngine)


  def test_local_engine_uses_injected_backend(fake_local_backend):
      eng = LocalEngine(model="base")
      eng._backend = fake_local_backend  # bypass lazy load
      out = eng.transcribe("/tmp/x.wav", language="en", prompt="ignored")
      assert out == "local transcript"  # stripped from fixture's " local transcript "
      fake_local_backend.transcribe.assert_called_once()


  def test_local_engine_lazy_loads_once(monkeypatch, fake_local_backend):
      eng = LocalEngine(model="base")
      calls = {"n": 0}

      def _fake_load():
          calls["n"] += 1
          return fake_local_backend

      monkeypatch.setattr(eng, "_load_backend", _fake_load)
      eng.transcribe("/tmp/x.wav")
      eng.transcribe("/tmp/y.wav")
      assert calls["n"] == 1  # backend cached after first call


  def test_local_engine_missing_extra_raises(monkeypatch):
      eng = LocalEngine(model="base")

      def _boom():
          raise LocalEngineUnavailable("install the [local] extra")

      monkeypatch.setattr(eng, "_load_backend", _boom)
      with pytest.raises(LocalEngineUnavailable):
          eng.transcribe("/tmp/x.wav")
  ```

- [ ] **Step 9.2** — Run (expect FAIL: module missing).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k local
  ```
  Expected: import error — `No module named 'core.engines.local'`.

- [ ] **Step 9.3** — Create `app/core/engines/local.py`.
  ```python
  """
  Local on-device transcription engine.
  =====================================
  Lazy-imports mlx_whisper (macOS Apple Silicon) or faster_whisper (Windows).
  Requires the optional install extra:  uv sync --extra local

  © 2026 Cloudelipute
  """

  import sys
  from typing import Any, Optional

  from ..logger import get_logger
  from .base import TranscriptionEngine

  logger = get_logger("engines.local")

  IS_MAC = sys.platform == "darwin"


  class LocalEngineUnavailable(RuntimeError):
      """Raised when the [local] extra (mlx/faster-whisper) is not installed."""


  class LocalEngine(TranscriptionEngine):
      """On-device speech-to-text via mlx-whisper (mac) / faster-whisper (win)."""

      def __init__(self, model: str = "base"):
          self._model = model
          self._backend: Optional[Any] = None

      def _load_backend(self) -> Any:
          """Lazily import and build the platform backend.

          Returns an object exposing `.transcribe(wav_path, language=...) -> dict`
          with a 'text' key. Raises LocalEngineUnavailable if the extra is absent.
          """
          if IS_MAC:
              try:
                  import mlx_whisper  # noqa: F401  # verify against docs
              except ImportError as e:
                  raise LocalEngineUnavailable(
                      "mlx-whisper not installed. Run: uv sync --extra local"
                  ) from e
              return _MlxBackend(self._model)

          try:
              from faster_whisper import WhisperModel  # verify against docs
          except ImportError as e:
              raise LocalEngineUnavailable(
                  "faster-whisper not installed. Run: uv sync --extra local"
              ) from e
          return _FasterWhisperBackend(WhisperModel(self._model))

      def transcribe(
          self,
          wav_path: str,
          language: Optional[str] = None,
          prompt: Optional[str] = None,
      ) -> Optional[str]:
          if self._backend is None:
              self._backend = self._load_backend()
          result = self._backend.transcribe(wav_path, language=language)
          text = result.get("text") if isinstance(result, dict) else result
          return text.strip() if text else None


  class _MlxBackend:
      """Thin adapter so mlx_whisper matches the dict-returning contract."""

      def __init__(self, model: str):
          self._model = model

      def transcribe(self, wav_path: str, language: Optional[str] = None) -> dict:
          import mlx_whisper  # verify against docs
          repo = f"mlx-community/whisper-{self._model}"
          return mlx_whisper.transcribe(
              wav_path, path_or_hf_repo=repo, language=language
          )


  class _FasterWhisperBackend:
      """Adapter joining faster-whisper's segment generator into a dict."""

      def __init__(self, model: Any):
          self._model = model

      def transcribe(self, wav_path: str, language: Optional[str] = None) -> dict:
          segments, _info = self._model.transcribe(wav_path, language=language)
          text = "".join(seg.text for seg in segments)
          return {"text": text}
  ```

- [ ] **Step 9.4** — Run (expect PASS — tests inject/patch the backend, so neither real lib is imported).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k local
  ```
  Expected: `4 passed`.

- [ ] **Step 9.5** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/engines/local.py tests/test_engines.py && git commit -m "feat(engines): add LocalEngine with lazy mlx/faster-whisper backend"
  ```

---

### Task 10: `get_engine(settings)` factory + package exports

**Files:**
- Modify: `app/core/engines/__init__.py`
- Modify: `app/core/__init__.py`
- Test: `tests/test_engines.py` (extend)

- [ ] **Step 10.1** — Write the failing factory test.

  Append to `tests/test_engines.py`:
  ```python
  from core.engines import get_engine


  def test_get_engine_cloud_default(settings_factory):
      s = settings_factory(api_key="sk-x", engine="cloud")
      eng = get_engine(s)
      assert isinstance(eng, CloudEngine)
      assert eng._model == "gpt-4o-mini-transcribe"


  def test_get_engine_cloud_honors_model(settings_factory):
      s = settings_factory(api_key="sk-x", engine="cloud", cloud_stt_model="whisper-1")
      eng = get_engine(s)
      assert isinstance(eng, CloudEngine)
      assert eng._model == "whisper-1"


  def test_get_engine_local(settings_factory):
      s = settings_factory(engine="local", local_stt_model="small")
      eng = get_engine(s)
      assert isinstance(eng, LocalEngine)
      assert eng._model == "small"


  def test_get_engine_exported_from_core():
      import core
      assert hasattr(core, "get_engine")
      assert hasattr(core, "TranscriptionEngine")
  ```

- [ ] **Step 10.2** — Run (expect FAIL: `get_engine` not exported).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q -k get_engine
  ```
  Expected: ImportError — `cannot import name 'get_engine' from 'core.engines'`.

- [ ] **Step 10.3** — Implement `get_engine` and finalize `app/core/engines/__init__.py`.

  Replace the entire contents of `app/core/engines/__init__.py` with:
  ```python
  """Yapper transcription engines.

  © 2026 Cloudelipute
  """

  from ..logger import get_logger
  from .base import TranscriptionEngine
  from .cloud import CloudEngine
  from .local import LocalEngine, LocalEngineUnavailable

  logger = get_logger("engines")

  __all__ = [
      "TranscriptionEngine",
      "CloudEngine",
      "LocalEngine",
      "LocalEngineUnavailable",
      "get_engine",
  ]


  def get_engine(settings) -> TranscriptionEngine:
      """Build the engine selected by settings.

      Args:
          settings: a core.config.Settings instance.

      Returns:
          A configured TranscriptionEngine (CloudEngine or LocalEngine).
      """
      engine = settings.get("engine")
      if engine == "local":
          model = settings.get("local_stt_model")
          logger.info(f"Using LocalEngine (model={model})")
          return LocalEngine(model=model)

      # Default: cloud.
      from ..api import APIClient
      api = APIClient(api_key=settings.get("api_key"))
      model = settings.get("cloud_stt_model")
      logger.info(f"Using CloudEngine (model={model})")
      return CloudEngine(api_client=api, model=model)
  ```

- [ ] **Step 10.4** — Export engine symbols from `app/core/__init__.py`.

  After the `# Transcription` import block (after line 46, `from .transcriber import Transcriber`), add:
  ```python

  # Engines
  from .engines import (
      TranscriptionEngine,
      CloudEngine,
      LocalEngine,
      LocalEngineUnavailable,
      get_engine,
  )
  ```

  And in the `__all__` list, after the `"Transcriber",` line, add:
  ```python
      # Engines
      "TranscriptionEngine",
      "CloudEngine",
      "LocalEngine",
      "LocalEngineUnavailable",
      "get_engine",
  ```

- [ ] **Step 10.5** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_engines.py -q
  ```
  Expected: all engine tests pass (`13 passed`).

- [ ] **Step 10.6** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/engines/__init__.py app/core/__init__.py tests/test_engines.py && git commit -m "feat(engines): add get_engine factory and core exports"
  ```

---

### Task 11: Refactor `Transcriber` to orchestrate over an engine + passthrough formatter

**Files:**
- Modify: `app/core/transcriber.py`
- Test: `tests/test_transcriber_orchestration.py`

> The real `Formatter` arrives in Phase 3. For this phase, `Transcriber` accepts an optional `formatter` with a `format(raw_text, *, mode, expand_symbols, translate_to) -> str` method (the Phase 3 contract). When none is supplied, it uses an internal passthrough that returns the text unchanged. The engine is injected (so it's swappable/testable); wake-word cleaning is preserved. Backward-compat: the old `api_key=`/`translate_to=`/`fix_grammar=` constructor still works by building a `CloudEngine` internally.

- [ ] **Step 11.1** — Write the failing orchestration tests.

  Create `tests/test_transcriber_orchestration.py`:
  ```python
  """Phase 2: Transcriber orchestrates engine + passthrough formatting."""
  from unittest.mock import MagicMock

  from core.transcriber import Transcriber, _PassthroughFormatter


  def _engine_returning(text):
      eng = MagicMock()
      eng.transcribe.return_value = text
      return eng


  def test_transcriber_calls_injected_engine(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"x")
      eng = _engine_returning("hello world")
      t = Transcriber(engine=eng, language_hint="en", clean_wake_words=False)

      out = t.transcribe(str(wav), delete_audio=False)

      assert out == "hello world"
      eng.transcribe.assert_called_once()
      assert eng.transcribe.call_args.kwargs["language"] == "en"


  def test_transcriber_passes_prompt_bias(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"x")
      eng = _engine_returning("ok")
      t = Transcriber(engine=eng, clean_wake_words=False)
      t.transcribe(str(wav), delete_audio=False, prompt="kubectl Next.js")
      assert eng.transcribe.call_args.kwargs["prompt"] == "kubectl Next.js"


  def test_transcriber_cleans_wake_words(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"x")
      eng = _engine_returning("yapper start deploy the app")
      t = Transcriber(engine=eng, clean_wake_words=True)
      out = t.transcribe(str(wav), delete_audio=False)
      assert "yapper" not in out.lower()
      assert "deploy the app" in out


  def test_transcriber_uses_formatter(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"x")
      eng = _engine_returning("raw text")
      fmt = MagicMock()
      fmt.format.return_value = "FORMATTED"
      t = Transcriber(engine=eng, formatter=fmt, clean_wake_words=False)
      out = t.transcribe(str(wav), delete_audio=False)
      assert out == "FORMATTED"
      assert fmt.format.call_args.kwargs["mode"] == "technical"


  def test_passthrough_formatter_returns_input():
      f = _PassthroughFormatter()
      assert f.format("xyz", mode="technical", expand_symbols=True,
                      translate_to=None) == "xyz"


  def test_transcriber_empty_engine_result_returns_none(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"x")
      eng = _engine_returning(None)
      t = Transcriber(engine=eng)
      assert t.transcribe(str(wav), delete_audio=False) is None
  ```

- [ ] **Step 11.2** — Run (expect FAIL: `_PassthroughFormatter` missing, `Transcriber(engine=...)` unsupported).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_transcriber_orchestration.py -q
  ```
  Expected: ImportError on `_PassthroughFormatter`, plus TypeErrors on the `engine=` kwarg.

- [ ] **Step 11.3** — Rewrite `app/core/transcriber.py`.

  Replace the entire file with:
  ```python
  """
  Yapper Transcriber
  ==================
  Thin orchestrator: engine.transcribe() -> wake-word clean -> formatting.

  The real formatting subsystem lands in Phase 3 (core/formatting.Formatter).
  Until then, a passthrough formatter is used by default.

  © 2026 Cloudelipute
  """

  import os
  import re
  from typing import Optional

  from .engines.base import TranscriptionEngine
  from .logger import get_logger

  logger = get_logger("transcriber")


  class _PassthroughFormatter:
      """No-op stand-in for the Phase 3 Formatter; returns text unchanged."""

      def format(
          self,
          raw_text: str,
          *,
          mode: str,
          expand_symbols: bool,
          translate_to: Optional[str],
      ) -> str:
          return raw_text


  class Transcriber:
      """Orchestrates transcription over a TranscriptionEngine + a Formatter.

      Example:
          eng = get_engine(settings)
          t = Transcriber(engine=eng, output_mode="technical")
          text = t.transcribe("audio.wav")
      """

      WAKE_WORD_PATTERNS = [
          r"\byapper[\s,]*start\b",
          r"\byapper[\s,]*stop\b",
          r"\byap\s*or\s*start\b",
          r"\byap\s*or\s*stop\b",
          r"\byap\s*er\s*start\b",
          r"\byap\s*er\s*stop\b",
      ]

      def __init__(
          self,
          engine: Optional[TranscriptionEngine] = None,
          *,
          api_key: str = "",
          language_hint: str = "",
          translate_to: str = "",
          output_mode: str = "technical",
          expand_spoken_symbols: bool = True,
          formatter: Optional[object] = None,
          clean_wake_words: bool = True,
          # Legacy compat (Phase 1/old callers); folded into output_mode.
          fix_grammar: bool = True,
      ):
          if engine is None:
              # Backward-compat: build a CloudEngine from an api_key.
              from .api import APIClient
              from .engines.cloud import CloudEngine
              engine = CloudEngine(api_client=APIClient(api_key=api_key))
          self._engine = engine
          self.language_hint = language_hint
          self.translate_to = translate_to
          self.output_mode = output_mode
          self.expand_spoken_symbols = expand_spoken_symbols
          self.clean_wake_words = clean_wake_words
          self._formatter = formatter or _PassthroughFormatter()

      def transcribe(
          self,
          audio_path: str,
          delete_audio: bool = True,
          prompt: Optional[str] = None,
      ) -> Optional[str]:
          """Transcribe + clean + format an audio file."""
          logger.info(f"Transcribing: {audio_path}")

          text = self._engine.transcribe(
              audio_path,
              language=self.language_hint or None,
              prompt=prompt,
          )

          if delete_audio:
              self._delete_audio_file(audio_path)

          if not text:
              logger.warning("Transcription returned empty result")
              return None

          logger.debug(f"Raw transcription: {text[:100]}...")

          if self.clean_wake_words:
              text = self._clean_wake_words(text)
              if not text:
                  logger.warning("Text empty after removing wake words")
                  return None

          text = self._formatter.format(
              text,
              mode=self.output_mode,
              expand_symbols=self.expand_spoken_symbols,
              translate_to=self.translate_to or None,
          )

          logger.info(f"Final text ({len(text)} chars): {text[:50]}...")
          return text

      def transcribe_for_wake_word(self, audio_path: str) -> Optional[str]:
          """Raw transcription for wake-word detection (no formatting)."""
          text = self._engine.transcribe(
              audio_path, language=self.language_hint or None
          )
          self._delete_audio_file(audio_path)
          if text:
              return text.lower().strip()
          return None

      def _clean_wake_words(self, text: str) -> str:
          cleaned = text
          for pattern in self.WAKE_WORD_PATTERNS:
              cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
          cleaned = re.sub(r"\s+", " ", cleaned).strip()
          if cleaned != text:
              logger.debug(f"Cleaned wake words: '{text}' -> '{cleaned}'")
          return cleaned

      def _delete_audio_file(self, audio_path: str) -> None:
          try:
              os.unlink(audio_path)
              logger.debug(f"Deleted audio file: {audio_path}")
          except OSError as e:
              logger.warning(f"Could not delete audio file: {e}")
  ```

- [ ] **Step 11.4** — Run (expect PASS).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_transcriber_orchestration.py -q
  ```
  Expected: `6 passed`.

- [ ] **Step 11.5** — Commit.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/transcriber.py tests/test_transcriber_orchestration.py && git commit -m "refactor(transcriber): orchestrate over engine + passthrough formatter"
  ```

---

### Task 12: Full-suite green + core import smoke

**Files:**
- (verification only)

- [ ] **Step 12.1** — Run the whole Phase 2 test set.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_api_models.py tests/test_engines.py tests/test_transcriber_orchestration.py tests/test_config_migration_phase2.py -q
  ```
  Expected: all pass (roughly `7 + 13 + 6 + 6 = 32 passed`), zero failures.

- [ ] **Step 12.2** — Smoke-import the whole `core` package (catches export typos and circular imports introduced by `engines/`).
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && PYTHONPATH=app python -c "import core; print(core.get_engine, core.CloudEngine, core.LocalEngine, core.TranscriptionEngine)"
  ```
  Expected: prints four class/function reprs, no traceback.

- [ ] **Step 12.3** — Confirm no deprecated model string remains anywhere in `core`.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && ! grep -rn "gpt-4.1-nano" app/core/ ; echo "exit=$?"
  ```
  Expected: `exit=0` (grep found nothing, so the negated command succeeds). If any match prints, replace it with `gpt-5-nano`.

- [ ] **Step 12.4** — Final commit (no-op if clean; records the verification milestone via an empty-allowed amend or a marker). If steps above produced edits, commit them.
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add -A && git diff --cached --quiet || git commit -m "chore(engines): finalize phase 2 engine abstraction and model upgrade"
  ```

---

## Done criteria (Phase 2)

- `core/engines/` exists with `TranscriptionEngine` ABC, `CloudEngine`, `LocalEngine`, and `get_engine(settings)`; all exported from `core`.
- `core/api.py` runs on OpenAI 2.x: transcription defaults to `gpt-4o-mini-transcribe` (with `whisper-1` selectable and a `prompt=` bias), chat/translate/grammar default to `gpt-5-nano` with `reasoning_effort='minimal'`; no `gpt-4.1-nano` references remain.
- `core/transcriber.py` orchestrates over an injected engine plus a `format(...)` hook (passthrough now; Phase 3 supplies the real `Formatter`), preserving wake-word cleaning and the legacy `api_key=` constructor path.
- New settings keys (`engine`, `cloud_stt_model`, `local_stt_model`, `text_model`) are in `constants.DEFAULT_SETTINGS` + `SETTINGS_SCHEMA`, with `Settings.migrate()` backfilling legacy files.
- All Phase 2 tests pass against a mocked `openai.OpenAI` and a fake local backend; retry logic is regression-guarded.
