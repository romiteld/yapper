# [Phase 3: No-Slop Formatting Subsystem] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the "no AI slop" formatting subsystem — `core/vocabulary.py` (fuzzy term correction + Whisper prompt bias) and `core/formatting.py` (spoken-symbol expansion + technical/natural/verbatim mode cleanup) — and wire it into `transcriber.py` so dictated technical text (CLI flags, file paths, code identifiers) is preserved verbatim and never paraphrased.

**Architecture:** Pure deterministic transforms (spoken-symbol regex, rapidfuzz vocabulary correction) run first and are fully unit-testable with golden cases; the only non-deterministic step is a single LLM cleanup call (`gpt-5-nano`, `reasoning_effort='minimal'`) wrapped behind `Formatter.format()` and mocked in tests. `Vocabulary` produces both the pre-transcription Whisper `prompt` bias and the post-transcription correction map, and `Transcriber` becomes a thin orchestrator that calls `Vocabulary` → `Formatter` in order.

**Tech Stack:** Python 3.11, `rapidfuzz` (fuzzy phrase matching), `re` (ordered regex rules), `openai>=2.38` (via the Phase 2 `APIClient.chat`), `pytest` + `unittest.mock`.

---

## File Structure

**Create**
- `app/core/vocabulary.py` — `Vocabulary` class: term store, `whisper_prompt()` bias string, `correct(text)` rapidfuzz phrase replacement, `add`/`remove`/`import_csv`/`to_list`/`from_list`, built-in dev starter pack.
- `app/core/formatting.py` — `expand_spoken_symbols(text)` ordered regex rules + `Formatter` class with `format(...)` modes (technical/natural/verbatim) and LLM system prompts.
- `tests/__init__.py` — empty package marker for the tests package.
- `tests/test_vocabulary.py` — unit tests for `Vocabulary`.
- `tests/test_formatting.py` — unit tests for `expand_spoken_symbols` + `Formatter` (LLM mocked).
- `tests/test_transcriber_formatting.py` — integration test wiring `Vocabulary`+`Formatter` into `Transcriber` (API mocked).
- `tests/fixtures/vocab_import.csv` — fixture CSV for `import_csv` test.

**Modify**
- `app/core/constants.py` — add `output_mode`, `expand_spoken_symbols`, `vocabulary` keys to `DEFAULT_SETTINGS` and `SETTINGS_SCHEMA`; add `OUTPUT_MODES` list.
- `app/core/transcriber.py` — replace the Phase 2 passthrough/grammar path with `Vocabulary` + `Formatter`; accept new constructor args; build Whisper prompt bias before transcription.
- `app/core/__init__.py` — export `Vocabulary`, `Formatter`, `expand_spoken_symbols`.

---

## Tasks

### Task 1: Add formatting settings keys to constants

**Files:**
- Modify: `app/core/constants.py`
- Test: `tests/__init__.py` (Create), `tests/test_constants_formatting.py` (Create)

- [ ] **Step 1.1** — Create the tests package marker. Create `tests/__init__.py` with exactly:
  ```python
  # Yapper test package
  ```

- [ ] **Step 1.2** — Write failing test. Create `tests/test_constants_formatting.py`:
  ```python
  """Tests for Phase 3 formatting settings keys in constants."""
  from app.core import constants


  def test_output_modes_list_present():
      assert constants.OUTPUT_MODES == ["technical", "natural", "verbatim"]


  def test_default_settings_has_formatting_keys():
      d = constants.DEFAULT_SETTINGS
      assert d["output_mode"] == "technical"
      assert d["expand_spoken_symbols"] is True
      assert d["vocabulary"] == []


  def test_schema_validates_output_mode():
      _type, validator, _desc = constants.SETTINGS_SCHEMA["output_mode"]
      assert _type is str
      assert validator("technical") is True
      assert validator("natural") is True
      assert validator("verbatim") is True
      assert validator("slop") is False


  def test_schema_validates_expand_spoken_symbols_and_vocabulary():
      assert constants.SETTINGS_SCHEMA["expand_spoken_symbols"][0] is bool
      vtype, vvalidator, _ = constants.SETTINGS_SCHEMA["vocabulary"]
      assert vtype is list
      assert vvalidator([]) is True
      assert vvalidator([{"said": None, "typed": "kubectl"}]) is True
      assert vvalidator("not-a-list") is False
  ```

- [ ] **Step 1.3** — Run the test, expect FAIL (KeyError / AttributeError):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_constants_formatting.py -q
  ```
  Expected: failures referencing missing `OUTPUT_MODES` / `output_mode` keys.

- [ ] **Step 1.4** — Add `OUTPUT_MODES` to `app/core/constants.py`. Insert immediately after the `HOTKEYS` list block (after line 87, before the `# DEFAULT SETTINGS` banner):
  ```python
  # =============================================================================
  # OUTPUT MODES (no-slop formatting)
  # =============================================================================

  # Output formatting modes for the no-slop subsystem.
  # technical = fix only caps/punctuation, never paraphrase code/identifiers
  # natural   = grammar-polished prose (filler removal, punctuation)
  # verbatim  = no LLM cleanup at all
  OUTPUT_MODES: List[str] = ["technical", "natural", "verbatim"]
  ```

- [ ] **Step 1.5** — Add the three keys to `DEFAULT_SETTINGS` in `app/core/constants.py`. Insert inside the `DEFAULT_SETTINGS` dict, immediately after the `"fix_grammar": True,` line (line 105):
  ```python
      # No-slop formatting (Phase 3)
      "output_mode": "technical",       # technical | natural | verbatim
      "expand_spoken_symbols": True,    # expand "dash dash help" -> "--help"
      "vocabulary": [],                 # list of {said, typed} term dicts
  ```

- [ ] **Step 1.6** — Add the three schema entries to `SETTINGS_SCHEMA` in `app/core/constants.py`. Insert immediately after the `"fix_grammar": (bool, None, "Auto-correct grammar"),` line (line 133):
  ```python
      "output_mode": (str, lambda x: x in OUTPUT_MODES, "Output formatting mode"),
      "expand_spoken_symbols": (bool, None, "Expand spoken symbols to characters"),
      "vocabulary": (
          list,
          lambda x: isinstance(x, list)
          and all(isinstance(t, dict) and "typed" in t for t in x),
          "Custom vocabulary terms",
      ),
  ```

- [ ] **Step 1.7** — Run the test, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_constants_formatting.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 1.8** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/constants.py tests/__init__.py tests/test_constants_formatting.py && git commit -m "feat(constants): add output_mode, expand_spoken_symbols, vocabulary settings keys"
  ```

---

### Task 2: Spoken-symbol expansion (`expand_spoken_symbols`)

Ordered, conservative regex rules. Multi-word/structural cues first, then single tokens, then path/extension joins, so longer patterns win.

**Files:**
- Create: `app/core/formatting.py`
- Test: `tests/test_formatting.py` (Create — symbol section only)

- [ ] **Step 2.1** — Write failing test. Create `tests/test_formatting.py`:
  ```python
  """Tests for the no-slop formatting subsystem."""
  from app.core.formatting import expand_spoken_symbols


  def test_dash_dash_flag():
      assert expand_spoken_symbols("run dash dash help now") == "run --help now"


  def test_single_dash_flag():
      assert expand_spoken_symbols("apply dash f file") == "apply -f file"


  def test_dot_extension_py():
      assert expand_spoken_symbols("open deployment dot yaml") == "open deployment.yaml"
      assert expand_spoken_symbols("edit main dot py") == "edit main.py"


  def test_backtick_word():
      assert expand_spoken_symbols("wrap backtick code backtick here") == "wrap `code` here"


  def test_open_close_paren():
      assert expand_spoken_symbols("call open paren x close paren") == "call (x)"


  def test_new_line():
      assert expand_spoken_symbols("line one new line line two") == "line one\nline two"


  def test_does_not_corrupt_prose():
      # 'dash' as a normal word without a following token stays untouched
      text = "I went for a quick dash to the store"
      assert expand_spoken_symbols(text) == text


  def test_idempotent_on_plain_prose():
      text = "the quick brown fox jumps over the lazy dog"
      assert expand_spoken_symbols(text) == text
  ```

- [ ] **Step 2.2** — Run, expect FAIL (ModuleNotFoundError: `app.core.formatting`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -q
  ```

- [ ] **Step 2.3** — Create `app/core/formatting.py` with the expansion function only:
  ```python
  """
  Yapper No-Slop Formatting Subsystem
  ===================================
  Spoken-symbol expansion and output-mode cleanup that preserves technical
  text verbatim (CLI flags, file paths, code identifiers) and never paraphrases.

  Copyright (c) 2026 Cloudelipute
  """

  import re
  from typing import List, Optional, Tuple

  from .logger import get_logger

  logger = get_logger("formatting")


  # Ordered, conservative spoken-symbol rules: (compiled_pattern, replacement).
  # Order matters — longer/structural cues are matched before single tokens so
  # that e.g. "dash dash help" beats "dash". Each rule only fires on a clear cue
  # to avoid corrupting ordinary prose.
  _SYMBOL_RULES: List[Tuple[re.Pattern, str]] = [
      # Long flags: "dash dash help" -> "--help"
      (re.compile(r"\bdash dash (\w+)\b", re.IGNORECASE), r"--\1"),
      # Short flags: "dash f" -> "-f" (single letter only, to avoid prose)
      (re.compile(r"\bdash ([a-zA-Z])\b", re.IGNORECASE), r"-\1"),
      # File extensions: "deployment dot yaml" -> "deployment.yaml"
      (
          re.compile(
              r"\b(\w+) dot (py|yaml|yml|json|js|ts|tsx|jsx|md|txt|sh|toml|cfg|ini|env|go|rs|rb|java|c|cpp|h)\b",
              re.IGNORECASE,
          ),
          r"\1.\2",
      ),
      # Backtick: "backtick code backtick" -> "`code`"
      (re.compile(r"\bbacktick\b", re.IGNORECASE), "`"),
      # Parentheses
      (re.compile(r"\bopen paren\b", re.IGNORECASE), "("),
      (re.compile(r"\bclose paren\b", re.IGNORECASE), ")"),
      # New line
      (re.compile(r"\bnew line\b", re.IGNORECASE), "\n"),
  ]


  def expand_spoken_symbols(text: str) -> str:
      """
      Expand spoken-symbol cues to their characters.

      Conservative: only fires on clear cues (e.g. "dash dash <word>",
      "<name> dot py", "backtick", "open/close paren", "new line"). Ordinary
      prose is left untouched.

      Args:
          text: Raw transcription text.

      Returns:
          Text with spoken symbols expanded.
      """
      result = text
      for pattern, replacement in _SYMBOL_RULES:
          result = pattern.sub(replacement, result)

      # Backtick / paren replacements can leave doubled spaces around the
      # inserted character; collapse spaces immediately inside backticks/parens.
      result = re.sub(r"`\s+", "`", result)
      result = re.sub(r"\s+`", "`", result)
      result = re.sub(r"\(\s+", "(", result)
      result = re.sub(r"\s+\)", ")", result)
      return result
  ```

- [ ] **Step 2.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -q
  ```
  Expected: `8 passed`.

- [ ] **Step 2.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/formatting.py tests/test_formatting.py && git commit -m "feat(formatting): add conservative spoken-symbol expansion"
  ```

---

### Task 3: Vocabulary store — `add`/`remove`/`to_list`/`from_list` + dev starter pack

**Files:**
- Create: `app/core/vocabulary.py`
- Test: `tests/test_vocabulary.py` (Create — store section)

- [ ] **Step 3.1** — Write failing test. Create `tests/test_vocabulary.py`:
  ```python
  """Tests for the Vocabulary store and fuzzy correction."""
  from app.core.vocabulary import Vocabulary, DEV_STARTER_PACK


  def test_starter_pack_loaded_by_default():
      v = Vocabulary()
      typed = {t["typed"] for t in v.terms}
      assert "kubectl" in typed
      assert "Next.js" in typed
      assert "PostgreSQL" in typed


  def test_empty_constructor_with_no_starter():
      v = Vocabulary(load_starter=False)
      assert v.terms == []


  def test_add_term_typed_only():
      v = Vocabulary(load_starter=False)
      v.add("FastAPI")
      assert {"said": None, "typed": "FastAPI"} in v.terms


  def test_add_term_with_said():
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      assert {"said": "cube cuttle", "typed": "kubectl"} in v.terms


  def test_add_is_idempotent_on_typed():
      v = Vocabulary(load_starter=False)
      v.add("nginx")
      v.add("nginx", said="engine x")
      typed_count = sum(1 for t in v.terms if t["typed"] == "nginx")
      assert typed_count == 1
      # later add updates the 'said' alias
      assert any(t["typed"] == "nginx" and t["said"] == "engine x" for t in v.terms)


  def test_remove_term():
      v = Vocabulary(load_starter=False)
      v.add("redis")
      v.remove("redis")
      assert all(t["typed"] != "redis" for t in v.terms)


  def test_to_list_and_from_list_roundtrip():
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      v.add("OAuth")
      data = v.to_list()
      assert data == [
          {"said": "cube cuttle", "typed": "kubectl"},
          {"said": None, "typed": "OAuth"},
      ]
      v2 = Vocabulary(load_starter=False)
      v2.from_list(data)
      assert v2.terms == v.terms


  def test_from_list_normalizes_bare_strings():
      v = Vocabulary(load_starter=False)
      v.from_list(["kubectl", {"typed": "nginx"}])
      assert {"said": None, "typed": "kubectl"} in v.terms
      assert {"said": None, "typed": "nginx"} in v.terms
  ```

- [ ] **Step 3.2** — Run, expect FAIL (ModuleNotFoundError: `app.core.vocabulary`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -q
  ```

- [ ] **Step 3.3** — Create `app/core/vocabulary.py` with the store (no `correct`/`whisper_prompt`/`import_csv` yet):
  ```python
  """
  Yapper Vocabulary
  =================
  User term store that (a) builds the Whisper prompt bias before transcription
  and (b) fuzzy-corrects mis-heard technical terms after transcription.

  Each term is a dict: {"said": str | None, "typed": str}.
    - "typed": the canonical output spelling (e.g. "kubectl").
    - "said":  an optional phonetic alias the model tends to mis-hear
               (e.g. "cube cuttle"). None means correct toward "typed" only.

  Copyright (c) 2026 Cloudelipute
  """

  from typing import Dict, List, Optional

  from .logger import get_logger

  logger = get_logger("vocabulary")


  # Small built-in developer starter pack. Aliases are common Whisper mis-hears.
  DEV_STARTER_PACK: List[Dict[str, Optional[str]]] = [
      {"said": "cube cuttle", "typed": "kubectl"},
      {"said": "next J S", "typed": "Next.js"},
      {"said": "post gres", "typed": "PostgreSQL"},
      {"said": "engine x", "typed": "nginx"},
      {"said": None, "typed": "OAuth"},
      {"said": None, "typed": "JWT"},
      {"said": "p npm", "typed": "pnpm"},
      {"said": None, "typed": "async/await"},
      {"said": None, "typed": "TypeScript"},
      {"said": None, "typed": "GraphQL"},
      {"said": None, "typed": "Redis"},
      {"said": None, "typed": "Docker"},
  ]


  class Vocabulary:
      """User vocabulary store + Whisper bias + fuzzy correction."""

      def __init__(self, load_starter: bool = True):
          """
          Args:
              load_starter: Seed with the built-in dev starter pack.
          """
          self.terms: List[Dict[str, Optional[str]]] = []
          if load_starter:
              self.from_list([dict(t) for t in DEV_STARTER_PACK])

      def add(self, typed: str, said: Optional[str] = None) -> None:
          """Add or update a term keyed by ``typed`` (idempotent)."""
          typed = typed.strip()
          if not typed:
              return
          for term in self.terms:
              if term["typed"] == typed:
                  if said is not None:
                      term["said"] = said.strip()
                  return
          self.terms.append({"said": said.strip() if said else None, "typed": typed})

      def remove(self, typed: str) -> None:
          """Remove all terms whose ``typed`` equals ``typed``."""
          self.terms = [t for t in self.terms if t["typed"] != typed]

      def to_list(self) -> List[Dict[str, Optional[str]]]:
          """Serialize to a JSON-friendly list (for settings)."""
          return [dict(t) for t in self.terms]

      def from_list(self, data: List) -> None:
          """
          Load terms from a list. Accepts bare strings (treated as ``typed``)
          or dicts with at least a ``typed`` key.
          """
          self.terms = []
          for entry in data or []:
              if isinstance(entry, str):
                  self.add(entry)
              elif isinstance(entry, dict) and entry.get("typed"):
                  self.add(entry["typed"], said=entry.get("said"))
              else:
                  logger.warning(f"Skipping malformed vocabulary entry: {entry!r}")
  ```

- [ ] **Step 3.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -q
  ```
  Expected: `9 passed`.

- [ ] **Step 3.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/vocabulary.py tests/test_vocabulary.py && git commit -m "feat(vocabulary): add term store with dev starter pack and list serialization"
  ```

---

### Task 4: Vocabulary Whisper prompt bias (`whisper_prompt`)

**Files:**
- Modify: `app/core/vocabulary.py`
- Test: `tests/test_vocabulary.py` (extend)

- [ ] **Step 4.1** — Append failing tests to `tests/test_vocabulary.py`:
  ```python
  def test_whisper_prompt_lists_typed_terms():
      v = Vocabulary(load_starter=False)
      v.add("kubectl")
      v.add("Next.js")
      prompt = v.whisper_prompt()
      assert "kubectl" in prompt
      assert "Next.js" in prompt


  def test_whisper_prompt_empty_when_no_terms():
      v = Vocabulary(load_starter=False)
      assert v.whisper_prompt() == ""


  def test_whisper_prompt_is_bounded():
      v = Vocabulary(load_starter=False)
      for i in range(500):
          v.add(f"Term{i}")
      # Whisper prompt is capped (~224 tokens); keep it well under that.
      assert len(v.whisper_prompt()) <= 900
  ```

- [ ] **Step 4.2** — Run, expect FAIL (AttributeError: no `whisper_prompt`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -k whisper_prompt -q
  ```

- [ ] **Step 4.3** — Add `whisper_prompt` to `Vocabulary` in `app/core/vocabulary.py`, immediately after the `from_list` method:
  ```python
      def whisper_prompt(self, max_chars: int = 800) -> str:
          """
          Build a Whisper ``prompt=`` bias string from the canonical ``typed``
          spellings. Priming Whisper with these counters its weakness on proper
          nouns. Bounded to ``max_chars`` (Whisper caps the prompt at ~224
          tokens).
          """
          typed_terms = [t["typed"] for t in self.terms if t["typed"]]
          if not typed_terms:
              return ""
          prompt = ""
          for term in typed_terms:
              candidate = f"{prompt}{term}, "
              if len(candidate.rstrip(", ")) > max_chars:
                  break
              prompt = candidate
          return prompt.rstrip(", ")
  ```

- [ ] **Step 4.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -q
  ```
  Expected: all vocabulary tests pass (`12 passed`).

- [ ] **Step 4.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/vocabulary.py tests/test_vocabulary.py && git commit -m "feat(vocabulary): build bounded Whisper prompt bias from typed terms"
  ```

---

### Task 5: Vocabulary fuzzy correction (`correct`) with rapidfuzz

Phrase-level fuzzy replacement: match each `said` alias (or `typed` spelling) against sliding word windows of the transcription; replace the best window above a high threshold with the canonical `typed`. Aliases are checked first (they have known mis-hears), longest aliases first so multi-word phrases win.

**Files:**
- Modify: `app/core/vocabulary.py`
- Test: `tests/test_vocabulary.py` (extend)

- [ ] **Step 5.1** — Append failing tests to `tests/test_vocabulary.py`:
  ```python
  def test_correct_two_word_alias():
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      assert v.correct("then cube cuttle apply") == "then kubectl apply"


  def test_correct_postgres_alias():
      v = Vocabulary(load_starter=False)
      v.add("PostgreSQL", said="post gres")
      assert v.correct("connect to post gres now") == "connect to PostgreSQL now"


  def test_correct_preserves_case_of_surrounding_text():
      v = Vocabulary(load_starter=False)
      v.add("Next.js", said="next J S")
      out = v.correct("I love Next J S a lot")
      assert "Next.js" in out
      assert out.startswith("I love")


  def test_correct_does_not_overcorrect_unrelated_words():
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      # 'the cube of seven' must NOT become kubectl
      assert v.correct("the cube of seven is large") == "the cube of seven is large"


  def test_correct_noop_with_empty_vocabulary():
      v = Vocabulary(load_starter=False)
      assert v.correct("nothing to do here") == "nothing to do here"


  def test_correct_golden_kubectl_phrase():
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      raw = "cube cuttle apply deployment"
      assert v.correct(raw) == "kubectl apply deployment"
  ```

- [ ] **Step 5.2** — Run, expect FAIL (AttributeError: no `correct`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -k correct -q
  ```

- [ ] **Step 5.3** — Add the import and `correct` method to `app/core/vocabulary.py`. First add to the top imports (replace the existing `from typing import ...` line with):
  ```python
  import re
  from typing import Dict, List, Optional, Tuple

  from rapidfuzz import fuzz
  ```
  Then add this method to `Vocabulary`, immediately after `whisper_prompt`:
  ```python
      # Minimum fuzzy similarity (0-100) for a window to be replaced. High on
      # purpose: we only want confident mis-hear corrections, never paraphrase.
      CORRECT_THRESHOLD: float = 85.0

      def _correction_targets(self) -> List[Tuple[str, str]]:
          """
          Yield (phrase_to_match, canonical_typed) pairs, longest phrase first
          so multi-word aliases are matched before single words.
          """
          targets: List[Tuple[str, str]] = []
          for term in self.terms:
              typed = term["typed"]
              if term["said"]:
                  targets.append((term["said"], typed))
              # Also match the canonical spelling itself (catches near-misses).
              targets.append((typed, typed))
          # Longest phrase (by word count, then chars) first.
          targets.sort(key=lambda p: (len(p[0].split()), len(p[0])), reverse=True)
          return targets

      def correct(self, text: str) -> str:
          """
          Fuzzy-replace mis-heard windows with canonical ``typed`` spellings.

          For each target phrase, slide a same-word-length window across the
          text and replace the best-matching window whose similarity exceeds
          ``CORRECT_THRESHOLD``. Single-word targets that already equal the
          canonical spelling are skipped (nothing to fix).
          """
          if not self.terms or not text.strip():
              return text

          words = text.split()
          for phrase, typed in self._correction_targets():
              phrase_words = phrase.split()
              n = len(phrase_words)
              if n == 0 or n > len(words):
                  continue
              i = 0
              while i + n <= len(words):
                  window = " ".join(words[i : i + n])
                  if window == typed:
                      i += 1
                      continue
                  score = fuzz.ratio(window.lower(), phrase.lower())
                  if score >= self.CORRECT_THRESHOLD:
                      words[i : i + n] = [typed]
                      logger.debug(
                          f"Vocab correct: '{window}' -> '{typed}' (score={score:.0f})"
                      )
                      # restart scan; lengths changed
                      i = 0
                      continue
                  i += 1
          return " ".join(words)
  ```
  > // verify against docs: `rapidfuzz.fuzz.ratio` returns a 0-100 float in rapidfuzz 3.x.

- [ ] **Step 5.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -q
  ```
  Expected: all vocabulary tests pass (`18 passed`). If `test_correct_does_not_overcorrect_unrelated_words` fails, the threshold is too low — confirm `fuzz.ratio("the cube", "cube cuttle")` < 85; do **not** lower `CORRECT_THRESHOLD`.

- [ ] **Step 5.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/vocabulary.py tests/test_vocabulary.py && git commit -m "feat(vocabulary): add high-threshold rapidfuzz phrase correction"
  ```

---

### Task 6: Vocabulary CSV import (`import_csv`)

**Files:**
- Modify: `app/core/vocabulary.py`
- Test: `tests/test_vocabulary.py` (extend), `tests/fixtures/vocab_import.csv` (Create)

- [ ] **Step 6.1** — Create the fixture `tests/fixtures/vocab_import.csv` with exactly:
  ```csv
  said,typed
  cube cuttle,kubectl
  ,FastAPI
  engine x,nginx
  ```

- [ ] **Step 6.2** — Append failing test to `tests/test_vocabulary.py`:
  ```python
  import os


  def test_import_csv_with_header(tmp_path=None):
      v = Vocabulary(load_starter=False)
      fixture = os.path.join(
          os.path.dirname(__file__), "fixtures", "vocab_import.csv"
      )
      v.import_csv(fixture)
      assert {"said": "cube cuttle", "typed": "kubectl"} in v.terms
      assert {"said": None, "typed": "FastAPI"} in v.terms
      assert {"said": "engine x", "typed": "nginx"} in v.terms


  def test_import_csv_single_column(tmp_path):
      p = tmp_path / "single.csv"
      p.write_text("kubectl\nnginx\n", encoding="utf-8")
      v = Vocabulary(load_starter=False)
      v.import_csv(str(p))
      typed = {t["typed"] for t in v.terms}
      assert "kubectl" in typed
      assert "nginx" in typed
  ```

- [ ] **Step 6.3** — Run, expect FAIL (AttributeError: no `import_csv`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -k import_csv -q
  ```

- [ ] **Step 6.4** — Add the `csv` import to the top of `app/core/vocabulary.py` (after `import re`):
  ```python
  import csv
  ```
  Then add `import_csv` to `Vocabulary`, immediately after the `from_list` method:
  ```python
      def import_csv(self, path: str) -> None:
          """
          Import terms from a CSV file. Supports either:
            - two columns ``said,typed`` (optional header row), or
            - a single column treated as ``typed``.
          Empty ``said`` cells become None.
          """
          try:
              with open(path, "r", encoding="utf-8", newline="") as f:
                  reader = csv.reader(f)
                  for row in reader:
                      if not row:
                          continue
                      cells = [c.strip() for c in row]
                      # Skip a header row.
                      if cells[0].lower() == "said" or (
                          len(cells) > 1 and cells[1].lower() == "typed"
                      ):
                          continue
                      if len(cells) == 1:
                          if cells[0]:
                              self.add(cells[0])
                      else:
                          said, typed = cells[0], cells[1]
                          if typed:
                              self.add(typed, said=said or None)
          except OSError as e:
              logger.error(f"Could not import vocabulary CSV '{path}': {e}")
  ```

- [ ] **Step 6.5** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_vocabulary.py -q
  ```
  Expected: all vocabulary tests pass (`20 passed`).

- [ ] **Step 6.6** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/vocabulary.py tests/test_vocabulary.py tests/fixtures/vocab_import.csv && git commit -m "feat(vocabulary): add CSV import (said,typed or single column)"
  ```

---

### Task 7: `Formatter` — verbatim mode (no LLM)

`Formatter.__init__(self, api_client, vocabulary)`. `format(...)` runs deterministic steps (expand symbols → vocab correct) then, for `verbatim`, returns without any LLM call.

**Files:**
- Modify: `app/core/formatting.py`
- Test: `tests/test_formatting.py` (extend)

- [ ] **Step 7.1** — Append failing tests to `tests/test_formatting.py`:
  ```python
  from unittest.mock import MagicMock

  from app.core.formatting import Formatter
  from app.core.vocabulary import Vocabulary


  def _vocab():
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      return v


  def test_verbatim_runs_no_llm():
      api = MagicMock()
      fmt = Formatter(api, _vocab())
      out = fmt.format(
          "cube cuttle apply dash f deploy",
          mode="verbatim",
          expand_symbols=True,
          translate_to=None,
      )
      assert out == "kubectl apply -f deploy"
      api.chat.assert_not_called()


  def test_verbatim_can_skip_symbol_expansion():
      api = MagicMock()
      fmt = Formatter(api, Vocabulary(load_starter=False))
      out = fmt.format(
          "run dash dash help",
          mode="verbatim",
          expand_symbols=False,
          translate_to=None,
      )
      assert out == "run dash dash help"
      api.chat.assert_not_called()
  ```

- [ ] **Step 7.2** — Run, expect FAIL (ImportError: `Formatter`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -k verbatim -q
  ```

- [ ] **Step 7.3** — Append the `Formatter` class skeleton (with verbatim path) to `app/core/formatting.py`:
  ```python
  class Formatter:
      """
      Output formatter for the no-slop pipeline.

      Pipeline order (after raw transcription, wake-word stripping happens
      upstream):
        1. spoken-symbol expansion (optional)
        2. canonical vocabulary correction
        3. mode cleanup (LLM) — technical | natural ; verbatim skips the LLM
        4. translation (replaces mode cleanup when a target language is set)
      """

      def __init__(self, api_client, vocabulary: "Vocabulary"):
          """
          Args:
              api_client: APIClient with a ``chat(messages, ...)`` method.
              vocabulary: Vocabulary used for correction and protected tokens.
          """
          self._api = api_client
          self._vocab = vocabulary

      def format(
          self,
          raw_text: str,
          *,
          mode: str,
          expand_symbols: bool,
          translate_to: Optional[str],
      ) -> str:
          """
          Run the no-slop pipeline.

          Args:
              raw_text: Raw transcription text.
              mode: 'technical' | 'natural' | 'verbatim'.
              expand_symbols: Whether to run spoken-symbol expansion.
              translate_to: Target language code, or None/"" for no translation.

          Returns:
              Final formatted text.
          """
          text = raw_text.strip()
          if not text:
              return text

          # 1. Spoken-symbol expansion (deterministic).
          if expand_symbols:
              text = expand_spoken_symbols(text)

          # 2. Canonical vocabulary correction (deterministic).
          text = self._vocab.correct(text)

          # Verbatim: no LLM step at all.
          if mode == "verbatim" and not translate_to:
              return text

          return text
  ```

- [ ] **Step 7.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -q
  ```
  Expected: all formatting tests pass so far.

- [ ] **Step 7.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/formatting.py tests/test_formatting.py && git commit -m "feat(formatting): add Formatter with deterministic steps and verbatim mode"
  ```

---

### Task 8: `Formatter` — technical & natural mode LLM cleanup (mocked)

Adds the LLM call via `api_client.chat(messages, model='gpt-5-nano', reasoning_effort='minimal')`. Technical prompt forbids paraphrase/translation of code and passes vocabulary terms as protected tokens. On LLM failure (`chat` returns None) it falls back to the deterministic text.

> // verify against docs: Phase 2's `APIClient.chat` is expected to accept `reasoning_effort='minimal'` and forward it to `client.chat.completions.create`. If Phase 2's signature differs, pass `reasoning_effort` through whatever kwarg `chat` exposes; the messages contract below is stable.

**Files:**
- Modify: `app/core/formatting.py`
- Test: `tests/test_formatting.py` (extend)

- [ ] **Step 8.1** — Append failing tests to `tests/test_formatting.py`:
  ```python
  def test_technical_mode_calls_llm_with_protected_tokens():
      api = MagicMock()
      api.chat.return_value = "kubectl apply -f deployment.yaml then check the pod logs"
      fmt = Formatter(api, _vocab())
      out = fmt.format(
          "cube cuttle apply dash f deployment dot yaml then check the pod logs",
          mode="technical",
          expand_symbols=True,
          translate_to=None,
      )
      assert out == "kubectl apply -f deployment.yaml then check the pod logs"
      # LLM was called once.
      api.chat.assert_called_once()
      messages = api.chat.call_args.kwargs.get("messages") or api.chat.call_args.args[0]
      system = messages[0]["content"]
      user = messages[1]["content"]
      # System prompt must forbid paraphrasing and list protected tokens.
      assert "never paraphrase" in system.lower()
      assert "kubectl" in system  # protected token from vocabulary
      # The deterministic text (already corrected/expanded) is what we send.
      assert "kubectl apply -f deployment.yaml" in user
      # gpt-5-nano with minimal reasoning effort.
      assert api.chat.call_args.kwargs.get("model") == "gpt-5-nano"
      assert api.chat.call_args.kwargs.get("reasoning_effort") == "minimal"


  def test_natural_mode_uses_grammar_prompt():
      api = MagicMock()
      api.chat.return_value = "I think we should deploy now."
      fmt = Formatter(api, Vocabulary(load_starter=False))
      out = fmt.format(
          "um i think we should like deploy now",
          mode="natural",
          expand_symbols=False,
          translate_to=None,
      )
      assert out == "I think we should deploy now."
      system = api.chat.call_args.kwargs.get("messages")[0]["content"]
      assert "grammar" in system.lower()


  def test_llm_failure_falls_back_to_deterministic_text():
      api = MagicMock()
      api.chat.return_value = None  # simulate API failure
      fmt = Formatter(api, _vocab())
      out = fmt.format(
          "cube cuttle apply",
          mode="technical",
          expand_symbols=True,
          translate_to=None,
      )
      assert out == "kubectl apply"  # deterministic result, no crash
  ```

- [ ] **Step 8.2** — Run, expect FAIL (LLM not wired; technical path still returns deterministic text and never calls `chat`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -k "technical or natural or llm_failure" -q
  ```

- [ ] **Step 8.3** — Add module-level constants and the LLM methods. In `app/core/formatting.py`, add the model constant just below the `logger = get_logger("formatting")` line:
  ```python
  TEXT_MODEL = "gpt-5-nano"
  ```
  Then replace the `verbatim` early-return block at the end of `Formatter.format` (the lines `# Verbatim: no LLM step at all.` through `return text`) with:
  ```python
          # Verbatim: no LLM step at all.
          if mode == "verbatim" and not translate_to:
              return text

          # 4. Translation replaces mode cleanup when a target language is set.
          if translate_to:
              return self._translate(text, translate_to)

          # 3. Mode cleanup (LLM).
          if mode == "natural":
              return self._natural_cleanup(text)
          # default / technical
          return self._technical_cleanup(text)
  ```
  Then add these three methods to `Formatter` (after `format`):
  ```python
      def _protected_tokens(self) -> str:
          tokens = [t["typed"] for t in self._vocab.terms if t["typed"]]
          return ", ".join(tokens)

      def _technical_cleanup(self, text: str) -> str:
          system = (
              "You clean up dictated technical text for a software engineer. "
              "Fix ONLY capitalization and obvious punctuation. "
              "Preserve all identifiers, camelCase/snake_case, CLI flags, file "
              "paths, URLs, and code verbatim. Never paraphrase, never 'improve' "
              "wording, never translate or alter code tokens, never add or remove "
              "words. Output ONLY the cleaned text, nothing else."
          )
          protected = self._protected_tokens()
          if protected:
              system += f"\nProtected tokens (keep exactly as written): {protected}."
          result = self._api.chat(
              messages=[
                  {"role": "system", "content": system},
                  {"role": "user", "content": text},
              ],
              model=TEXT_MODEL,
              reasoning_effort="minimal",
          )
          return result.strip() if result else text

      def _natural_cleanup(self, text: str) -> str:
          system = (
              "You polish dictated prose. Fix grammar and punctuation, remove "
              "filler words (um, uh, like, you know), and produce clean, natural "
              "sentences while preserving the original meaning and tone. "
              "Output ONLY the cleaned text, nothing else."
          )
          result = self._api.chat(
              messages=[
                  {"role": "system", "content": system},
                  {"role": "user", "content": text},
              ],
              model=TEXT_MODEL,
              reasoning_effort="minimal",
          )
          return result.strip() if result else text
  ```

- [ ] **Step 8.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -q
  ```
  Expected: all formatting tests pass.

- [ ] **Step 8.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/formatting.py tests/test_formatting.py && git commit -m "feat(formatting): add technical/natural LLM cleanup with no-paraphrase prompt"
  ```

---

### Task 9: `Formatter` — translation step (mocked)

Translation replaces mode cleanup when `translate_to` is set; instructs the model to leave code/identifiers untranslated.

**Files:**
- Modify: `app/core/formatting.py`
- Test: `tests/test_formatting.py` (extend)

- [ ] **Step 9.1** — Append failing tests to `tests/test_formatting.py`:
  ```python
  def test_translation_replaces_cleanup_and_keeps_code():
      api = MagicMock()
      api.chat.return_value = "ejecuta kubectl apply -f deployment.yaml"
      fmt = Formatter(api, _vocab())
      out = fmt.format(
          "cube cuttle apply dash f deployment dot yaml",
          mode="technical",
          expand_symbols=True,
          translate_to="es",
      )
      assert out == "ejecuta kubectl apply -f deployment.yaml"
      system = api.chat.call_args.kwargs.get("messages")[0]["content"]
      assert "Spanish" in system  # resolved from language code
      assert "untranslated" in system.lower() or "do not translate" in system.lower()


  def test_translation_failure_falls_back_to_deterministic_text():
      api = MagicMock()
      api.chat.return_value = None
      fmt = Formatter(api, _vocab())
      out = fmt.format(
          "cube cuttle apply",
          mode="technical",
          expand_symbols=True,
          translate_to="es",
      )
      assert out == "kubectl apply"
  ```

- [ ] **Step 9.2** — Run, expect FAIL (AttributeError: `Formatter._translate`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -k translation -q
  ```

- [ ] **Step 9.3** — Add the `_translate` method to `Formatter` in `app/core/formatting.py` (after `_natural_cleanup`):
  ```python
      def _translate(self, text: str, translate_to: str) -> str:
          from .constants import LANGUAGE_CODES

          lang_name = LANGUAGE_CODES.get(translate_to, translate_to)
          system = (
              f"You are a translator. Translate the user's text to {lang_name}. "
              "Leave code, identifiers, CLI flags, file paths, and URLs "
              "untranslated and verbatim. Do not translate technical tokens. "
              "Output ONLY the translation, nothing else."
          )
          protected = self._protected_tokens()
          if protected:
              system += f"\nKeep these tokens exactly as written: {protected}."
          result = self._api.chat(
              messages=[
                  {"role": "system", "content": system},
                  {"role": "user", "content": text},
              ],
              model=TEXT_MODEL,
              reasoning_effort="minimal",
          )
          return result.strip() if result else text
  ```

- [ ] **Step 9.4** — Run, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting.py -q
  ```
  Expected: all formatting tests pass.

- [ ] **Step 9.5** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/formatting.py tests/test_formatting.py && git commit -m "feat(formatting): add translation step preserving code tokens"
  ```

---

### Task 10: Golden end-to-end formatting cases (deterministic + mocked LLM passthrough)

A focused golden-case file proving the full pipeline on the spec's flagship example. The LLM is mocked to act as an identity (technical mode must already be near-correct from deterministic steps).

**Files:**
- Test: `tests/test_formatting_golden.py` (Create)

- [ ] **Step 10.1** — Create `tests/test_formatting_golden.py`:
  ```python
  """Golden no-slop cases for the full formatting pipeline (LLM mocked identity)."""
  from unittest.mock import MagicMock

  import pytest

  from app.core.formatting import Formatter
  from app.core.vocabulary import Vocabulary


  def _identity_api():
      api = MagicMock()
      # Technical-mode LLM only fixes caps/punctuation; here the deterministic
      # output is already clean, so the LLM echoes it back unchanged.
      api.chat.side_effect = lambda messages, **kw: messages[1]["content"]
      return api


  @pytest.mark.parametrize(
      "raw,expected",
      [
          (
              "cube cuttle apply dash f deployment dot yaml then check the pod logs",
              "kubectl apply -f deployment.yaml then check the pod logs",
          ),
          (
              "run cube cuttle get pods dash dash all dash namespaces",
              "run kubectl get pods --all -namespaces",
          ),
          (
              "open main dot py and import FastAPI",
              "open main.py and import FastAPI",
          ),
      ],
  )
  def test_golden_technical_pipeline(raw, expected):
      v = Vocabulary(load_starter=False)
      v.add("kubectl", said="cube cuttle")
      fmt = Formatter(_identity_api(), v)
      out = fmt.format(
          raw, mode="technical", expand_symbols=True, translate_to=None
      )
      assert out == expected
  ```
  > Note: the second case's `--all -namespaces` reflects the conservative single-letter/long-flag rules as implemented; if a future rule handles `dash namespaces`, update this golden value deliberately.

- [ ] **Step 10.2** — Run, expect PASS (if a golden value mismatches, fix the *expected* value to the real deterministic output, or refine a `_SYMBOL_RULES` rule and re-run Task 2 tests — never weaken the no-paraphrase prompt):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_formatting_golden.py -q
  ```
  Expected: `3 passed`.

- [ ] **Step 10.3** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/test_formatting_golden.py && git commit -m "test(formatting): add golden no-slop pipeline cases"
  ```

---

### Task 11: Wire `Vocabulary` + `Formatter` into `Transcriber`

Replace the Phase 2 passthrough (`fix_grammar`/`translate` branches) with the no-slop pipeline. `Transcriber` builds the Whisper `prompt` bias from `Vocabulary` before transcription and runs `Formatter.format(...)` after. Keep wake-word stripping and the public `transcribe()` / `transcribe_for_wake_word()` signatures.

**Files:**
- Modify: `app/core/transcriber.py`
- Test: `tests/test_transcriber_formatting.py` (Create)

- [ ] **Step 11.1** — Write failing test. Create `tests/test_transcriber_formatting.py`:
  ```python
  """Integration: Transcriber wires Vocabulary + Formatter (API mocked)."""
  from unittest.mock import MagicMock, patch

  from app.core.transcriber import Transcriber
  from app.core.vocabulary import Vocabulary


  def _make_transcriber(raw_transcription):
      with patch("app.core.transcriber.APIClient") as MockAPI:
          api = MockAPI.return_value
          api.transcribe.return_value = raw_transcription
          # Technical-mode LLM echoes the already-clean deterministic text.
          api.chat.side_effect = lambda messages, **kw: messages[1]["content"]
          vocab = Vocabulary(load_starter=False)
          vocab.add("kubectl", said="cube cuttle")
          t = Transcriber(
              api_key="sk-test",
              vocabulary=vocab,
              output_mode="technical",
              expand_spoken_symbols=True,
          )
          return t, api


  def test_transcribe_runs_noslop_pipeline(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      t, api = _make_transcriber(
          "cube cuttle apply dash f deployment dot yaml"
      )
      out = t.transcribe(str(wav), delete_audio=False)
      assert out == "kubectl apply -f deployment.yaml"


  def test_transcribe_passes_vocab_prompt_bias_to_whisper(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      t, api = _make_transcriber("cube cuttle apply")
      t.transcribe(str(wav), delete_audio=False)
      # Whisper prompt bias built from vocabulary 'typed' terms.
      prompt_arg = api.transcribe.call_args.kwargs.get("prompt")
      assert prompt_arg is not None and "kubectl" in prompt_arg


  def test_verbatim_mode_skips_llm(tmp_path):
      wav = tmp_path / "a.wav"
      wav.write_bytes(b"RIFFfake")
      with patch("app.core.transcriber.APIClient") as MockAPI:
          api = MockAPI.return_value
          api.transcribe.return_value = "cube cuttle apply"
          vocab = Vocabulary(load_starter=False)
          vocab.add("kubectl", said="cube cuttle")
          t = Transcriber(
              api_key="sk-test",
              vocabulary=vocab,
              output_mode="verbatim",
              expand_spoken_symbols=True,
          )
          out = t.transcribe(str(wav), delete_audio=False)
          assert out == "kubectl apply"
          api.chat.assert_not_called()
  ```

- [ ] **Step 11.2** — Run, expect FAIL (`Transcriber.__init__` rejects `vocabulary`/`output_mode`/`expand_spoken_symbols`; `api.transcribe` not called with `prompt`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_transcriber_formatting.py -q
  ```

- [ ] **Step 11.3** — Rewrite `app/core/transcriber.py`. Replace the imports block (lines 9-16) with:
  ```python
  import os
  import re
  from typing import Optional

  from .api import APIClient
  from .formatting import Formatter
  from .logger import get_logger
  from .vocabulary import Vocabulary

  logger = get_logger("transcriber")
  ```

- [ ] **Step 11.4** — Replace the `__init__` method (lines 38-60) of `Transcriber` with:
  ```python
      def __init__(
          self,
          api_key: str,
          language_hint: str = "",
          translate_to: str = "",
          clean_wake_words: bool = True,
          vocabulary: Optional[Vocabulary] = None,
          output_mode: str = "technical",
          expand_spoken_symbols: bool = True,
      ):
          """
          Initialize the transcriber.

          Args:
              api_key: OpenAI API key.
              language_hint: Optional language hint for Whisper (ISO code).
              translate_to: Target language for translation (empty = none).
              clean_wake_words: Remove wake word phrases from transcription.
              vocabulary: Vocabulary for Whisper bias + correction.
              output_mode: 'technical' | 'natural' | 'verbatim'.
              expand_spoken_symbols: Expand spoken symbols (dash dash -> --).
          """
          self._api_client = APIClient(api_key=api_key)
          self.language_hint = language_hint
          self.translate_to = translate_to
          self.clean_wake_words = clean_wake_words
          self.output_mode = output_mode
          self.expand_spoken_symbols = expand_spoken_symbols
          self._vocabulary = vocabulary or Vocabulary()
          self._formatter = Formatter(self._api_client, self._vocabulary)
  ```

- [ ] **Step 11.5** — Replace the `transcribe` method body (the `# Step 1` through `return text` block, lines 77-109) with a version that passes the prompt bias and runs the Formatter. Replace lines 77-109 with:
  ```python
          logger.info(f"Transcribing: {audio_path}")

          # Step 1: Build Whisper prompt bias from vocabulary.
          prompt_bias = self._vocabulary.whisper_prompt() or None

          # Step 2: Transcribe audio.
          text = self._api_client.transcribe(
              audio_path=audio_path,
              language=self.language_hint if self.language_hint else None,
              prompt=prompt_bias,
          )

          # Clean up audio file.
          if delete_audio:
              self._delete_audio_file(audio_path)

          if not text:
              logger.warning("Transcription returned empty result")
              return None

          logger.debug(f"Raw transcription: {text[:100]}...")

          # Step 3: Clean wake words if enabled.
          if self.clean_wake_words:
              text = self._clean_wake_words(text)
              if not text:
                  logger.warning("Text empty after removing wake words")
                  return None

          # Step 4: No-slop formatting pipeline.
          text = self._formatter.format(
              text,
              mode=self.output_mode,
              expand_symbols=self.expand_spoken_symbols,
              translate_to=self.translate_to or None,
          )

          logger.info(f"Final text ({len(text)} chars): {text[:50]}...")
          return text
  ```

- [ ] **Step 11.6** — Remove the now-dead `_translate` and `_fix_grammar` methods (the methods that call `self._api_client.translate` / `self._api_client.fix_grammar`, original lines 148-160) from `app/core/transcriber.py`. Delete them entirely; keep `_clean_wake_words` and `_delete_audio_file`.

- [ ] **Step 11.7** — Run the integration test, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_transcriber_formatting.py -q
  ```
  Expected: `3 passed`.
  > // verify against docs: this assumes Phase 2's `APIClient.transcribe` accepts a `prompt=` kwarg (per the shared contract). If the kwarg name differs, align this call to Phase 2's actual signature.

- [ ] **Step 11.8** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/transcriber.py tests/test_transcriber_formatting.py && git commit -m "feat(transcriber): wire Vocabulary bias and Formatter no-slop pipeline"
  ```

---

### Task 12: Export new symbols and run the full Phase 3 suite

**Files:**
- Modify: `app/core/__init__.py`
- Test: `tests/test_exports.py` (Create)

- [ ] **Step 12.1** — Write failing test. Create `tests/test_exports.py`:
  ```python
  """Phase 3 public exports."""
  import app.core as core


  def test_vocabulary_exported():
      from app.core import Vocabulary
      assert Vocabulary is core.Vocabulary


  def test_formatter_and_expand_exported():
      from app.core import Formatter, expand_spoken_symbols
      assert callable(expand_spoken_symbols)
      assert Formatter is core.Formatter
  ```

- [ ] **Step 12.2** — Run, expect FAIL (ImportError):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_exports.py -q
  ```

- [ ] **Step 12.3** — Add exports to `app/core/__init__.py`. Insert after the `from .transcriber import Transcriber` line (line 46):
  ```python

  # No-slop formatting subsystem
  from .vocabulary import Vocabulary
  from .formatting import Formatter, expand_spoken_symbols
  ```
  Then add to the `__all__` list, immediately after the `"Transcriber",` entry:
  ```python
      # No-slop formatting
      "Vocabulary",
      "Formatter",
      "expand_spoken_symbols",
  ```

- [ ] **Step 12.4** — Run the exports test, expect PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_exports.py -q
  ```
  Expected: `2 passed`.

- [ ] **Step 12.5** — Run the **entire Phase 3 suite**, expect all PASS:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python -m pytest tests/test_constants_formatting.py tests/test_formatting.py tests/test_formatting_golden.py tests/test_vocabulary.py tests/test_transcriber_formatting.py tests/test_exports.py -q
  ```
  Expected: all green (no failures, no errors).

- [ ] **Step 12.6** — Commit:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/__init__.py tests/test_exports.py && git commit -m "feat(core): export Vocabulary, Formatter, expand_spoken_symbols"
  ```

---

## Phase 3 Done Criteria

- `core/vocabulary.py` exists with `Vocabulary` (`terms`, `whisper_prompt`, `correct`, `add`, `remove`, `import_csv`, `to_list`, `from_list`) and a built-in dev starter pack; rapidfuzz correction uses a high threshold (`CORRECT_THRESHOLD=85`) that does not over-correct unrelated prose.
- `core/formatting.py` exists with `expand_spoken_symbols` (ordered conservative regex rules) and `Formatter.format(..., mode, expand_symbols, translate_to)` covering technical (no-paraphrase LLM prompt + protected vocabulary tokens), natural (grammar polish), verbatim (no LLM), and translation (code preserved).
- `constants.py` has `output_mode`, `expand_spoken_symbols`, `vocabulary` in `DEFAULT_SETTINGS` and `SETTINGS_SCHEMA`, plus `OUTPUT_MODES`.
- `transcriber.py` builds the Whisper `prompt` bias and runs the `Formatter` pipeline, replacing the Phase 2 passthrough; public method signatures preserved.
- The golden case `"cube cuttle apply dash f deployment dot yaml then check the pod logs"` → `"kubectl apply -f deployment.yaml then check the pod logs"` passes.
- `python -m pytest tests/ -q` is green; LLM calls are always mocked in tests.
