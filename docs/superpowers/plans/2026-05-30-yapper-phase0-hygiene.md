# Phase 0: OSS Hygiene & Repo Prep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Strip the repo of the Windows-embedded Python runtime and embedded-only build artifacts, stand up a clone-first `uv`/`pyproject.toml` + cross-platform launchers, normalize copyright to `© 2026 Cloudelipute`, bump the version to `4.0.0`, ship an upgraded README with Mermaid diagrams, and add the first `pytest` smoke harness.

**Architecture:** This phase touches no runtime logic — it is repository hygiene plus a test harness. The deliverables are: a `pyproject.toml` declaring the v4 dependency set (spec §10) with `[local]` and `dev` extras configured for `uv`; thin `run.sh`/`run.command`/`run.bat` launchers that call `uv run python -m app`; a `setup` script that runs `uv sync`; a `tests/` package with `conftest.py` and a TDD-driven smoke test; and source-wide copyright/version normalization.

**Tech Stack:** `uv` (package/venv manager), `pyproject.toml` (PEP 621 metadata), `pytest` + `pytest-qt` + `pyinstaller` (dev/build deps, declared not yet used), GitHub-flavored Markdown + Mermaid (README diagrams).

---

## File Structure

**Delete (remove from working tree + `git rm`):**
- `python/` — committed Windows embedded Python 3.11 runtime (already gitignored & untracked; delete from disk only).
- `build_portable.py` — embedded-runtime portable builder.
- `BUILD_PORTABLE.bat` — embedded-runtime build launcher.
- `INSTALL.bat` — installs pip packages into embedded `python/`.
- `Install Yapper.bat` — embedded-install wrapper.
- `Setup.bat` — embedded setup wrapper.
- `Settings.bat` — launches `python\python.exe app\settings_ui.py` (embedded path).
- `Yapper.bat` — old embedded launcher (replaced by new `run.bat`).
- `Create Desktop Shortcuts.bat` — Windows embedded shortcut maker.
- `installer/` (`installer.py`, `setup.ps1`, `settings_gui.ps1`) — Windows embedded installer.
- `install.sh` — old non-uv installer (replaced by `setup`).
- `requirements.txt` — superseded by `pyproject.toml`.
- `dist/` — empty build output dir (untrack/remove if tracked).

**Create:**
- `pyproject.toml` — PEP 621 project metadata + deps + `[local]`/`dev` extras + `[tool.pytest.ini_options]`.
- `setup` — POSIX `uv sync` bootstrap script (chmod +x).
- `setup.bat` — Windows `uv sync` bootstrap script.
- `run.command` — macOS double-click launcher (`uv run python -m app`).
- `run.bat` — Windows launcher (`uv run python -m app`).
- `app/__init__.py` — makes `app` a real package so `python -m app` resolves.
- `app/__main__.py` — temporary v4 entry point (prints version/banner until Phase 4 wires `ui.app.main`).
- `tests/__init__.py` — marks `tests` as a package.
- `tests/conftest.py` — pytest fixtures: put repo root + `app` on `sys.path`, temp settings path.
- `tests/test_smoke.py` — first TDD smoke test (import core, load settings, assert version).
- `README.md` — full rewrite (banner, feature grid, 3 Mermaid diagrams, clone-first install, permissions, model/cost, BYOK/privacy). *(replaces existing)*

**Modify:**
- `run.sh` — rewrite as thin `uv run python -m app` launcher (keep file, replace body).
- `app/core/constants.py` — `VERSION = "4.0.0"`, `COPYRIGHT = "© 2026 Cloudelipute"`, header copyright line.
- `VERSION` — `4.0.0`.
- `.gitignore` — confirm `.claude/` and `python/` stay ignored; ensure `.venv/` ignored (it is); no functional change expected but verified.
- All tracked source files containing the literal `© 2026 Cloudelipute` header/notice (see Task 5 list) → `© 2026 Cloudelipute`.
- `LICENSE` — **left intact** (the formal MIT `© 2026 Cloudelipute` line is legally conventional; do NOT change). Called out explicitly in Task 5 so it is not "missed."
- `CLAUDE.md` — update version refs / removed-file references so docs stay truthful.

---

## Tasks

### Task 1: Remove embedded Python runtime & embedded-only build artifacts

**Files:**
- Delete: `python/` (disk only — untracked), `build_portable.py`, `BUILD_PORTABLE.bat`, `INSTALL.bat`, `Install Yapper.bat`, `Setup.bat`, `Settings.bat`, `Yapper.bat`, `Create Desktop Shortcuts.bat`, `installer/installer.py`, `installer/setup.ps1`, `installer/settings_gui.ps1`, `install.sh`, `requirements.txt`, `dist/`.

**Steps:**

- [ ] **Verify what is tracked before deleting.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git ls-files | grep -iE 'build_portable|BUILD_PORTABLE|INSTALL.bat|Install Yapper|Setup.bat|Settings.bat|Yapper.bat|Create Desktop|installer/|install.sh|requirements.txt'
  ```
  Expected output (tracked files to `git rm`):
  ```
  BUILD_PORTABLE.bat
  Create Desktop Shortcuts.bat
  INSTALL.bat
  Install Yapper.bat
  Settings.bat
  Setup.bat
  Yapper.bat
  build_portable.py
  install.sh
  installer/installer.py
  installer/settings_gui.ps1
  installer/setup.ps1
  requirements.txt
  ```

- [ ] **Confirm `python/` is untracked (delete from disk only, do NOT `git rm`).** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git ls-files python/ | wc -l
  ```
  Expected output: `0` (it is gitignored; safe to `rm -rf`).

- [ ] **Delete the untracked embedded runtime from disk.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && rm -rf python/ dist/ && ls python dist 2>&1
  ```
  Expected output: `ls: cannot access 'python': No such file or directory` (and same for `dist`).

- [ ] **`git rm` the tracked embedded-only artifacts.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git rm -f \
    BUILD_PORTABLE.bat "Create Desktop Shortcuts.bat" INSTALL.bat "Install Yapper.bat" \
    Settings.bat Setup.bat Yapper.bat build_portable.py install.sh requirements.txt \
    installer/installer.py installer/setup.ps1 installer/settings_gui.ps1
  ```
  Expected: `rm '...'` lines for each, no errors. The now-empty `installer/` directory is removed automatically by git.

- [ ] **Verify removal complete.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git status --short && echo "---REMAINING BAT---" && git ls-files '*.bat'
  ```
  Expected: deletions staged (`D` lines); `git ls-files '*.bat'` prints nothing (no `.bat` remain tracked — new launchers are added in Task 3).

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add -A && git commit -m "chore: remove Windows embedded Python runtime and embedded-only build artifacts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 2: Create `pyproject.toml` with v4 dependencies, extras, and pytest config

**Files:**
- Create: `pyproject.toml`

**Steps:**

- [ ] **Confirm `uv` is available.** Run:
  ```bash
  uv --version
  ```
  Expected: a version line like `uv 0.x.x`. (If absent, install per https://docs.astral.sh/uv/ — but it is already on PATH at `/home/romiteld/.local/bin/uv`.)

- [ ] **Create `pyproject.toml`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/pyproject.toml` with exactly:
  ```toml
  [project]
  name = "yapper"
  version = "4.0.0"
  description = "Cross-platform push-to-talk speech-to-text for engineers — clone-first, BYOK."
  readme = "README.md"
  license = { text = "MIT" }
  requires-python = ">=3.10"
  authors = [{ name = "Cloudelipute" }]
  keywords = ["speech-to-text", "dictation", "whisper", "macos", "windows", "push-to-talk"]
  classifiers = [
      "Development Status :: 4 - Beta",
      "Environment :: MacOS X",
      "Environment :: Win32 (MS Windows)",
      "Intended Audience :: Developers",
      "License :: OSI Approved :: MIT License",
      "Operating System :: MacOS",
      "Operating System :: Microsoft :: Windows",
      "Programming Language :: Python :: 3.10",
      "Topic :: Multimedia :: Sound/Audio :: Speech",
  ]
  dependencies = [
      "pynput>=1.8.2",
      "sounddevice>=0.5.1",
      "pyperclip>=1.9.0",
      "openai>=2.38",
      "PySide6>=6.8",
      "desktop-notifier>=6.1.1",
      "rapidfuzz>=3.10",
      "Pillow>=11.0",
  ]

  [project.optional-dependencies]
  # On-device transcription engines. Platform-conditional via environment markers.
  # mlx-whisper is Apple-Silicon-only; faster-whisper covers Windows/Linux.
  local = [
      "mlx-whisper>=0.4.2; sys_platform == 'darwin' and platform_machine == 'arm64'",
      "faster-whisper>=1.1.0; sys_platform != 'darwin'",
  ]
  # macOS TCC permission checks (AXIsProcessTrusted). pynput already pulls Quartz;
  # ApplicationServices is declared explicitly for permissions.py.
  macos = [
      "pyobjc-framework-Quartz>=10.3; sys_platform == 'darwin'",
      "pyobjc-framework-ApplicationServices>=10.3; sys_platform == 'darwin'",
  ]
  dev = [
      "pytest>=8.3",
      "pytest-qt>=4.4",
      "pyinstaller>=6.11",
  ]

  [project.urls]
  Homepage = "https://github.com/Cloudelipute/yapper"
  Repository = "https://github.com/Cloudelipute/yapper"
  Issues = "https://github.com/Cloudelipute/yapper/issues"

  [project.scripts]
  yapper = "app.__main__:main"

  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["app"]

  [tool.uv]
  # Auto-install the macOS pyobjc extra only on macOS so Win/Linux clones stay lean.
  default-groups = []

  [tool.pytest.ini_options]
  minversion = "8.0"
  testpaths = ["tests"]
  addopts = "-ra -q"
  # Qt UI tests are offscreen-safe in CI; set per-run with QT_QPA_PLATFORM=offscreen.
  ```
  *// verify against docs: `mlx-whisper`/`faster-whisper`/`pyobjc` exact minimum versions and `[tool.uv]` keys against the installed uv version.*

- [ ] **Verify the file parses as valid TOML and `uv` reads it.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python3 -c "import tomllib,sys; d=tomllib.load(open('pyproject.toml','rb')); print(d['project']['name'], d['project']['version'])"
  ```
  Expected output: `yapper 4.0.0`

- [ ] **Verify `uv` resolves the manifest (lock-only, no install, offline-safe dry parse).** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv lock --dry-run 2>&1 | tail -5 || echo "lock dry-run attempted"
  ```
  Expected: uv parses the manifest without a TOML/schema error (network resolution may print progress; a TOML *parse* error is the only failure that blocks this step). *// verify against docs: `uv lock --dry-run` flag name for the installed uv version; fall back to `uv tree --offline` if unavailable.*

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add pyproject.toml && git commit -m "build: add pyproject.toml with uv deps, [local]/[macos]/dev extras, pytest config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 3: Create `setup` bootstrap + thin cross-platform launchers

**Files:**
- Create: `setup` (POSIX), `setup.bat` (Windows), `run.command` (macOS), `run.bat` (Windows)
- Modify: `run.sh` (rewrite body)
- Create: `app/__init__.py`, `app/__main__.py`

**Steps:**

- [ ] **Create `app/__init__.py`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/app/__init__.py` with exactly:
  ```python
  """Yapper application package.

  © 2026 Cloudelipute
  """

  from app.core.constants import VERSION

  __version__ = VERSION
  ```

- [ ] **Create `app/__main__.py`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/app/__main__.py` with exactly (this is a temporary entry point; Phase 4 replaces the body with `from app.ui.app import main`):
  ```python
  """Yapper entry point — ``python -m app``.

  © 2026 Cloudelipute

  Phase 0 placeholder: prints version/banner. The PySide6 tray app
  (``app.ui.app.main``) replaces this body in Phase 4.
  """

  import sys

  from app.core.constants import COPYRIGHT, VERSION


  def main() -> int:
      """Run Yapper. Returns a process exit code."""
      print(f"Yapper {VERSION}")
      print(COPYRIGHT)
      print("The PySide6 app is wired up in Phase 4. Run the tests with: uv run pytest")
      return 0


  if __name__ == "__main__":
      sys.exit(main())
  ```

- [ ] **Verify the entry point runs with the system interpreter** (no uv/venv needed since it only imports stdlib + `app.core.constants`). Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && PYTHONPATH=. python3 -m app
  ```
  Expected output (the version line still reads 3.3.1 until Task 4 bumps it):
  ```
  Yapper 3.3.1
  © 2026 Cloudelipute
  The PySide6 app is wired up in Phase 4. Run the tests with: uv run pytest
  ```

- [ ] **Create `setup`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/setup` with exactly:
  ```bash
  #!/usr/bin/env bash
  # Yapper clone-first setup — creates .venv and installs locked deps via uv.
  # © 2026 Cloudelipute
  set -euo pipefail

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$SCRIPT_DIR"

  if ! command -v uv >/dev/null 2>&1; then
    echo "Error: 'uv' is not installed."
    echo "Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Docs: https://docs.astral.sh/uv/"
    exit 1
  fi

  echo "Syncing dependencies with uv..."
  # Base sync. On macOS also pull the pyobjc permission helpers.
  if [ "$(uname -s)" = "Darwin" ]; then
    uv sync --extra macos
  else
    uv sync
  fi

  echo
  echo "Done. Start Yapper with:  ./run.sh   (or ./run.command on macOS)"
  echo "For on-device models:     uv sync --extra local"
  ```

- [ ] **Create `setup.bat`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/setup.bat` with exactly:
  ```bat
  @echo off
  REM Yapper clone-first setup (Windows) - creates .venv and installs deps via uv.
  REM (c) 2026 Cloudelipute
  setlocal
  cd /d "%~dp0"

  where uv >nul 2>nul
  if errorlevel 1 (
    echo Error: 'uv' is not installed.
    echo Install it: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    echo Docs: https://docs.astral.sh/uv/
    exit /b 1
  )

  echo Syncing dependencies with uv...
  uv sync
  if errorlevel 1 exit /b 1

  echo.
  echo Done. Start Yapper with:  run.bat
  echo For on-device models:     uv sync --extra local
  ```

- [ ] **Rewrite `run.sh`** — replace the entire file at `/home/romiteld/Development/Desktop_Apps/yapper-portable/run.sh` with exactly:
  ```bash
  #!/usr/bin/env bash
  # Yapper launcher (macOS / Linux). Runs the app inside the uv-managed venv.
  # © 2026 Cloudelipute
  set -euo pipefail

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$SCRIPT_DIR"

  if ! command -v uv >/dev/null 2>&1; then
    echo "Error: 'uv' not found. Run ./setup first (see README)."
    exit 1
  fi

  exec uv run python -m app "$@"
  ```

- [ ] **Create `run.command`** (macOS double-click launcher) at `/home/romiteld/Development/Desktop_Apps/yapper-portable/run.command` with exactly:
  ```bash
  #!/usr/bin/env bash
  # Yapper launcher for macOS (double-clickable in Finder).
  # © 2026 Cloudelipute
  set -euo pipefail

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$SCRIPT_DIR"

  if ! command -v uv >/dev/null 2>&1; then
    echo "Error: 'uv' not found. Run ./setup first (see README)."
    read -r -p "Press Return to close..."
    exit 1
  fi

  exec uv run python -m app "$@"
  ```

- [ ] **Create `run.bat`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/run.bat` with exactly:
  ```bat
  @echo off
  REM Yapper launcher (Windows). Runs the app inside the uv-managed venv.
  REM (c) 2026 Cloudelipute
  setlocal
  cd /d "%~dp0"

  where uv >nul 2>nul
  if errorlevel 1 (
    echo Error: 'uv' not found. Run setup.bat first ^(see README^).
    exit /b 1
  )

  uv run python -m app %*
  ```

- [ ] **Make the POSIX scripts executable.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && chmod +x setup run.sh run.command && ls -l setup run.sh run.command | awk '{print $1, $NF}'
  ```
  Expected output (executable bits set):
  ```
  -rwxr-xr-x run.command
  -rwxr-xr-x run.sh
  -rwxr-xr-x setup
  ```

- [ ] **Verify the launchers correctly delegate to `uv run python -m app`** (confirm wiring without a network sync by checking the literal command). Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -h "uv run python -m app" run.sh run.command run.bat
  ```
  Expected output: three lines, each containing `uv run python -m app`.

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/__init__.py app/__main__.py setup setup.bat run.sh run.command run.bat && git commit -m "feat: add uv setup script and cross-platform launchers (run.sh/.command/.bat)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 4: Bump version to 4.0.0 (TDD — version is asserted by the smoke test)

This task is TDD: the failing test lives in `tests/test_smoke.py` and is authored in Task 6. Here we do the minimal version bump that Task 6's `test_version_is_4` will assert against. To keep TDD ordering honest, **author the version assertion test first** (it will also be the seed of Task 6's full smoke file), watch it fail, then make it pass.

**Files:**
- Modify: `app/core/constants.py`, `VERSION`
- Create (seed): `tests/__init__.py`, `tests/test_smoke.py` (version assertion only; expanded in Task 6)

**Steps:**

- [ ] **Create `tests/__init__.py`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/tests/__init__.py` with exactly:
  ```python
  """Yapper test suite."""
  ```

- [ ] **Write the failing version test.** Create `/home/romiteld/Development/Desktop_Apps/yapper-portable/tests/test_smoke.py` with exactly:
  ```python
  """Smoke tests: the package imports and reports the v4 version.

  © 2026 Cloudelipute
  """

  import sys
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parent.parent
  if str(REPO_ROOT) not in sys.path:
      sys.path.insert(0, str(REPO_ROOT))


  def test_version_is_4():
      from app.core.constants import VERSION

      assert VERSION == "4.0.0"
  ```

- [ ] **Run the test and watch it FAIL.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python3 -m pytest tests/test_smoke.py -q
  ```
  Expected: **FAIL** —
  ```
  AssertionError: assert '3.3.1' == '4.0.0'
  ```
  (If `pytest` is not importable with the system Python, install it for this step only: `python3 -m pip install --user pytest` — the project's pinned dev `pytest` is installed via `uv sync --extra dev` in Task 6's verification.)

- [ ] **Bump `VERSION` in `constants.py`.** Edit `app/core/constants.py` line 15: change `VERSION = "3.3.1"` to `VERSION = "4.0.0"`.

- [ ] **Bump the `VERSION` file.** Replace the contents of `/home/romiteld/Development/Desktop_Apps/yapper-portable/VERSION` with exactly:
  ```
  4.0.0
  ```

- [ ] **Run the test and watch it PASS.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python3 -m pytest tests/test_smoke.py -q
  ```
  Expected: **PASS** — `1 passed`.

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add app/core/constants.py VERSION tests/__init__.py tests/test_smoke.py && git commit -m "chore: bump version to 4.0.0 with seed smoke test

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 5: Normalize copyright to `© 2026 Cloudelipute`

Normalize the `COPYRIGHT` constant and every source-header / brand-notice occurrence of the literal `© 2026 Cloudelipute` to `© 2026 Cloudelipute`. **The `LICENSE` file is the single intentional exception** — the formal MIT `© 2026 Cloudelipute` line is legally conventional and stays exactly as-is.

**Files (tracked, contain the literal — confirmed by grep):**
- Modify: `app/core/constants.py` (the `COPYRIGHT = ...` constant + its header line — 2 occurrences), `app/core/__init__.py`, `app/core/api.py`, `app/core/audio.py`, `app/core/config.py`, `app/core/devices.py`, `app/core/history.py`, `app/core/logger.py`, `app/core/sounds.py`, `app/core/transcriber.py`, `app/core/typer.py`, `app/core/vad.py`, `app/yapper.py`, `app/yapper_tray.py`, `app/settings_ui.py`, `app/settings_console.py`, `README.md`.
- **Leave unchanged:** `LICENSE`.

> Note: the spec cites "33 occurrences"; the actual tracked count of the literal string is **29** across these files (embedded-runtime files removed in Task 1 accounted for the difference). `README.md` is fully rewritten in Task 7, so its occurrence is handled there — but normalizing it here first keeps the repo consistent at every commit.

**Steps:**

- [ ] **Snapshot the current occurrence count (excluding LICENSE).** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -rl "© 2026 Cloudelipute" . 2>/dev/null | grep -v '/python/' | grep -v '.venv/' | grep -v '^./LICENSE$'
  ```
  Expected: the file list above (17 files, all `.py` + `README.md`, NOT `LICENSE`).

- [ ] **Change the `COPYRIGHT` constant** in `app/core/constants.py` line 16 from:
  ```python
  COPYRIGHT = "© 2026 Cloudelipute"
  ```
  to:
  ```python
  COPYRIGHT = "© 2026 Cloudelipute"
  ```

- [ ] **Bulk-normalize every remaining source-header occurrence except LICENSE.** Run (uses `find` + `sed -i`; explicitly excludes `LICENSE`, `python/`, `.venv/`, `.git/`):
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
  grep -rl "© 2026 Cloudelipute" . 2>/dev/null \
    | grep -v '/python/' | grep -v './.venv/' | grep -v './.git/' \
    | grep -v '^./LICENSE$' \
    | while IFS= read -r f; do
        sed -i 's/© 2026 Cloudelipute/© 2026 Cloudelipute/g' "$f"
      done
  ```

- [ ] **Verify: zero remaining literals outside LICENSE.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -rn "© 2026 Cloudelipute" . 2>/dev/null | grep -v '/python/' | grep -v './.venv/'
  ```
  Expected output: exactly one line —
  ```
  ./LICENSE:3:© 2026 Cloudelipute
  ```

- [ ] **Verify: the new `©` form is present and the constant is correct.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -rc "© 2026 Cloudelipute" app/core/constants.py && grep "COPYRIGHT = " app/core/constants.py
  ```
  Expected:
  ```
  2
  COPYRIGHT = "© 2026 Cloudelipute"
  ```
  (constants.py has 2: the header comment line + the constant value.)

- [ ] **Verify nothing import-breaks** (the `©` char is inside string/comment contexts only — confirm the module still compiles). Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && PYTHONPATH=. python3 -c "from app.core.constants import COPYRIGHT, VERSION; print(VERSION, COPYRIGHT)"
  ```
  Expected output: `4.0.0 © 2026 Cloudelipute`

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add -A && git commit -m "chore: normalize copyright to '© 2026 Cloudelipute' (LICENSE MIT line unchanged)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 6: Build the pytest harness — `conftest.py` + full smoke test (TDD)

Expand the seed test from Task 4 into the full smoke suite and add `conftest.py` so `tests/` runs under the project's pinned dev `pytest` via `uv`.

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_smoke.py` (add core-import + settings-load tests)

**Steps:**

- [ ] **Create `tests/conftest.py`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/tests/conftest.py` with exactly:
  ```python
  """Shared pytest fixtures for the Yapper suite.

  Puts the repo root on ``sys.path`` so ``import app...`` works under any runner,
  and provides an isolated temp settings path so tests never touch the real
  ``app/settings.json``.

  © 2026 Cloudelipute
  """

  import sys
  from pathlib import Path

  import pytest

  REPO_ROOT = Path(__file__).resolve().parent.parent
  if str(REPO_ROOT) not in sys.path:
      sys.path.insert(0, str(REPO_ROOT))


  @pytest.fixture
  def temp_settings_path(tmp_path, monkeypatch):
      """Point Settings at an isolated temp file for the duration of a test."""
      from app.core import config

      path = tmp_path / "settings.json"
      monkeypatch.setattr(config, "_SETTINGS_FILE", path, raising=False)
      return path
  ```

- [ ] **Write the failing expanded smoke test.** Replace `/home/romiteld/Development/Desktop_Apps/yapper-portable/tests/test_smoke.py` with exactly:
  ```python
  """Smoke tests: the package imports, reports the v4 version, and Settings load.

  © 2026 Cloudelipute
  """


  def test_version_is_4():
      from app.core.constants import VERSION

      assert VERSION == "4.0.0"


  def test_core_package_imports():
      import app.core as core

      assert core.__version__ == "4.0.0"
      assert core.COPYRIGHT == "© 2026 Cloudelipute"
      # Public surface that later phases extend must already be importable.
      assert hasattr(core, "Settings")
      assert hasattr(core, "DEFAULT_SETTINGS")
      assert hasattr(core, "get_logger")


  def test_settings_load_creates_defaults(temp_settings_path):
      from app.core.config import Settings

      settings = Settings(settings_path=temp_settings_path).load()

      # Defaults present and the file was materialized.
      assert temp_settings_path.exists()
      assert settings.get("audio_feedback") is True
      assert settings.get("api_key") == ""


  def test_entrypoint_main_returns_zero(capsys):
      from app.__main__ import main

      rc = main()
      out = capsys.readouterr().out

      assert rc == 0
      assert "Yapper 4.0.0" in out
      assert "© 2026 Cloudelipute" in out
  ```

- [ ] **Run with the system pytest and watch it PASS** (these assertions all hold after Tasks 3–5; this confirms the harness wiring before introducing `uv`). Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python3 -m pytest -q
  ```
  Expected: **PASS** — `4 passed`.
  (If you want to first observe a FAIL for the new `test_core_package_imports`/`test_entrypoint_main_returns_zero` cases, temporarily run them against a stash before Task 5 — but since Task 5 is already committed, they pass now; this is honest because the production code they assert is already in place.)

- [ ] **Sync dev deps and run under `uv` (the canonical project runner).** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv sync --extra dev && uv run pytest -q
  ```
  Expected: `uv` creates `.venv/`, installs the pinned `pytest`, and prints `4 passed`. *// verify against docs: if the platform lacks a PySide6 wheel during `uv sync --extra dev`, the dev extra still resolves because PySide6 is a base dep with broad wheel coverage on Win/macOS-arm64/manylinux; on an unsupported arch, fall back to `uv sync --extra dev --no-build-isolation` or skip the `uv` step and rely on the system-`pytest` PASS above.*

- [ ] **Confirm `.venv/` is gitignored (not staged).** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git status --short | grep -E '\.venv|uv.lock' || echo "venv ignored; uv.lock is the only new tracked artifact (intentional)"
  ```
  Expected: `.venv/` does NOT appear (it is covered by `.venv/` in `.gitignore`); `uv.lock` MAY appear as a new untracked file — it should be committed for reproducible clone-first installs.

- [ ] **Commit the harness and lockfile.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/conftest.py tests/test_smoke.py uv.lock && git commit -m "test: add pytest harness with conftest fixtures and smoke suite

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 7: Write the upgraded README with Mermaid diagrams

Full rewrite of `README.md`: banner, feature grid, three GitHub-native Mermaid diagrams (architecture from spec §3, dictation lifecycle from §4, onboarding flow from §8), clone-first install for macOS/Windows/Linux, permissions guide, model/cost notes, BYOK + privacy statement.

**Files:**
- Modify (replace): `README.md`

**Steps:**

- [ ] **Replace `README.md`** at `/home/romiteld/Development/Desktop_Apps/yapper-portable/README.md` with exactly:
  ```markdown
  <div align="center">

  # 🎙️ Yapper

  **Push-to-talk speech-to-text for engineers — clone-first, bring-your-own-key.**

  Record your voice, transcribe it, clean it up *without AI slop*, and paste it at your cursor.
  Cross-platform: **macOS (Apple Silicon)** and **Windows**, one codebase.

  `© 2026 Cloudelipute` · MIT License · v4.0.0

  </div>

  ---

  ## ✨ Features

  | | |
  |---|---|
  | 🎯 **Push-to-talk** | Hold a key to dictate. Toggle and wake-word modes too. |
  | 🧠 **No "AI slop"** | Technical mode preserves identifiers, CLI flags, file paths & code **verbatim** — never paraphrased. |
  | 🔤 **Spoken symbols** | "dash dash help" → `--help`, "dot py" → `.py`, "open paren" → `(`. |
  | 📚 **Vocabulary** | Teach it your terms: "cube cuttle" → `kubectl`, "next J S" → `Next.js`. CSV import. |
  | ☁️ **Cloud or 🖥️ on-device** | Default cloud `gpt-4o-mini-transcribe`; optional local `mlx-whisper`/`faster-whisper`. |
  | 🪟 **Recording HUD** | Frameless always-on-top pill with live waveform and idle→listening→transcribing→done states. |
  | ⌨️ **Unicode-safe paste** | Clipboard-paste primary (⌘/Ctrl+V), `pynput` type fallback — emoji & CJK safe. |
  | 🔔 **Native notifications** | Cross-platform toasts; HUD is the always-on fallback. |
  | 🔑 **BYOK** | Your OpenAI key, your machine. No telemetry, no middleman. |

  ---

  ## 🏗️ Architecture

  ```mermaid
  flowchart TB
      subgraph UI["UI layer — PySide6 / Qt (one event loop)"]
          tray["Tray"] --- wizard["Wizard"] --- settings["Settings"]
          settings --- hud["HUD"] --- history["History"] --- notif["Notifications"]
      end
      UI -- "Qt signals/slots" --> CTRL
      subgraph CTRL["Controller (app orchestrator)"]
          direction LR
          c["wires: hotkeys → record → engine → formatting → insert → HUD"]
      end
      CTRL --> hotkeys["hotkeys<br/>(pynput) PTT/toggle"]
      CTRL --> audio["audio<br/>(sounddevice + vad)"]
      CTRL --> engines["engines (STT)<br/>cloud / local"]
      CTRL --> formatting["formatting<br/>no-slop / vocab / mode"]
      CTRL --> typer["typer<br/>(pynput / clipboard)"]
      CTRL --> hist["history"]
      hotkeys --> perms["permissions<br/>(mac TCC)"]
      engines --> api["api (OpenAI 2.x) /<br/>local model runtimes"]
      classDef plat fill:#1b1b22,stroke:#ec2a8e,color:#fff;
      class perms,api plat;
  ```

  ## 🔄 Dictation lifecycle

  ```mermaid
  flowchart TD
      idle(["idle"]) -->|"PTT key down / toggle / wake word"| listen["HUD: listening + waveform"]
      listen --> record["record (sounddevice, 16 kHz mono)"]
      record -->|"key up / stop"| vad{"VAD: speech?"}
      vad -->|"silent"| idle
      vad -->|"speech"| bias["vocabulary → Whisper prompt bias"]
      bias --> stt["Engine.transcribe()<br/>cloud gpt-4o-mini-transcribe<br/>or local mlx / faster-whisper"]
      stt --> fmt["Formatting:<br/>strip wake words → expand spoken symbols →<br/>canonical vocab correction → mode cleanup<br/>(technical / natural / verbatim) →<br/>optional translate (gpt-5-nano)"]
      fmt --> paste["Typer: clipboard-paste at cursor (⌘/Ctrl+V)"]
      paste --> done["HUD: done ✓ · sound cue · history.add() · notify"]
      done --> idle
  ```

  ## 🚀 Onboarding flow

  ```mermaid
  flowchart LR
      welcome["Welcome"] --> engine["Engine<br/>cloud / local"]
      engine --> connect["Connect<br/>API key or model download"]
      connect --> perms["Permissions<br/>(macOS only)"]
      perms --> voice["Hotkey & Voice<br/>PTT/toggle · key capture · mic test"]
      voice --> done["All set ✓"]
      connect -. "Windows skips Permissions" .-> voice
  ```

  ---

  ## 📦 Install (clone-first)

  Yapper installs from source with [**uv**](https://docs.astral.sh/uv/). No Python install dance, no embedded runtime.

  **Prerequisite:** install `uv` once —

  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  ```powershell
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

  ### macOS (Apple Silicon)
  ```bash
  git clone https://github.com/Cloudelipute/yapper.git
  cd yapper
  ./setup          # uv sync — creates .venv, installs deps (+ macOS pyobjc helpers)
  ./run.command    # or ./run.sh
  ```

  ### Windows
  ```bat
  git clone https://github.com/Cloudelipute/yapper.git
  cd yapper
  setup.bat
  run.bat
  ```

  ### Linux (best-effort)
  ```bash
  git clone https://github.com/Cloudelipute/yapper.git
  cd yapper
  ./setup
  ./run.sh
  ```
  > Linux is best-effort: global hotkeys need X/uinput and tray support varies by desktop. Not a release target.

  ### On-device transcription (optional)
  ```bash
  uv sync --extra local   # mlx-whisper on macOS arm64, faster-whisper on Windows/Linux
  ```

  ### Prebuilt releases (unsigned)
  Unsigned `.app`/`.dmg` (macOS) and `.zip` (Windows) are attached to GitHub Releases as a convenience.
  On macOS Sequoia/Tahoe, clear the quarantine flag on first launch:
  ```bash
  xattr -dr com.apple.quarantine /Applications/Yapper.app
  ```
  (or System Settings → Privacy & Security → **Open Anyway**). Notifications may be unavailable on the unsigned build — the HUD covers all feedback.

  ---

  ## 🔐 Permissions (macOS)

  macOS only re-reads permissions **at process start** — after granting anything, **quit & relaunch Yapper**.

  | Permission | Why | How |
  |---|---|---|
  | 🎤 **Microphone** | Record your voice | OS prompts on first capture |
  | ♿ **Accessibility** | Paste / type at the cursor | System Settings → Privacy & Security → Accessibility → enable Yapper |
  | ⌨️ **Input Monitoring** | Capture the push-to-talk hotkey | System Settings → Privacy & Security → Input Monitoring → enable Yapper |

  Grant these to the **Yapper app's identity** (the `.app`, or your terminal/Python when running from source). Without Accessibility, key injection **fails silently** — the first-run wizard detects and guides you through it.

  Windows and Linux require no special TCC grants (Windows hotkeys may need an elevated terminal in some configurations).

  ---

  ## 🤖 Models & cost

  | Role | Default | Alternative | Notes |
  |---|---|---|---|
  | Cloud STT | `gpt-4o-mini-transcribe` (~$0.003/min) | `whisper-1` | mini is ~50% cheaper & more accurate; whisper-1 kept for long-tail langs / timestamps |
  | On-device STT | `mlx-whisper` (mac) / `faster-whisper` (win) | size selectable (`base`…) | runs offline; install via `--extra local` |
  | Text cleanup / translate | `gpt-5-nano` (`reasoning_effort='minimal'`) | `gpt-5.4-nano` | `gpt-4.1-nano` is **deprecated** (shuts down 2026-10-23) |

  A few minutes of dictation per day on the cloud default costs cents. On-device is free after download.

  ---

  ## 🔑 BYOK & privacy

  Yapper is **bring-your-own-key**. You paste your own OpenAI API key during onboarding; it is stored locally in `app/settings.json` (gitignored) and used only to call OpenAI directly from your machine.

  - **No telemetry.** Yapper phones home to nothing.
  - **No middleman.** Audio and text go straight from your machine to the API you chose.
  - **Local-only option.** With `--extra local`, transcription never leaves your device.
  - **Your key, gitignored.** `app/settings.json` is never committed.

  ---

  ## 🛠️ Development

  ```bash
  uv sync --extra dev     # pytest, pytest-qt, pyinstaller
  uv run pytest           # run the test suite
  uv run python -m app    # run from source
  ```

  ---

  <div align="center">

  `© 2026 Cloudelipute` · Released under the [MIT License](LICENSE).

  </div>
  ```

- [ ] **Verify the README has exactly three Mermaid blocks and no stray old copyright literal.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && echo "mermaid blocks:" && grep -c '```mermaid' README.md && echo "old literal (expect 0):" && grep -c "© 2026 Cloudelipute" README.md && echo "new form present:" && grep -c "© 2026 Cloudelipute" README.md
  ```
  Expected:
  ```
  mermaid blocks:
  3
  old literal (expect 0):
  0
  new form present:
  3
  ```

- [ ] **Verify each Mermaid block is balanced (opened and closed).** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && python3 -c "t=open('README.md').read(); o=t.count('\`\`\`mermaid'); c=t.count('\`\`\`'); print('mermaid opens:',o,'total fences:',c,'-> balanced' if c % 2 == 0 else '-> UNBALANCED')"
  ```
  Expected: `balanced` (total backtick-fence count is even). *// verify visually: open the README on the GitHub PR to confirm all three Mermaid diagrams render.*

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add README.md && git commit -m "docs: rewrite README with banner, feature grid, Mermaid diagrams, clone-first install

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 8: Verify hygiene invariants & update CLAUDE.md to match the new repo

Confirm `.claude/` stays gitignored, the embedded runtime/installers are fully gone, and the project docs no longer reference deleted files.

**Files:**
- Modify: `CLAUDE.md`
- Verify: `.gitignore`

**Steps:**

- [ ] **Verify `.claude/` is ignored and untracked.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && echo "tracked .claude files:" && git ls-files .claude/ | wc -l && echo "git check-ignore:" && git check-ignore .claude/ && echo ".gitignore has .claude/:" && grep -c '^\.claude/$' .gitignore
  ```
  Expected:
  ```
  tracked .claude files:
  0
  git check-ignore:
  .claude/
  .gitignore has .claude/:
  1
  ```

- [ ] **Verify `python/` and `.venv/` stay ignored.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git check-ignore python/ .venv/ && echo "OK both ignored"
  ```
  Expected:
  ```
  python/
  .venv/
  OK both ignored
  ```

- [ ] **Verify no embedded-runtime/installer artifacts remain tracked.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git ls-files | grep -iE 'build_portable|installer/|INSTALL.bat|Install Yapper|^python/|requirements.txt' || echo "CLEAN: no embedded artifacts tracked"
  ```
  Expected: `CLEAN: no embedded artifacts tracked`

- [ ] **Update `CLAUDE.md`** — the current file describes the embedded-Python/`.bat` workflow that no longer exists. Replace the "## Running the Application" code block (the one with `INSTALL.bat` / `Yapper.bat` / `python\python.exe app\yapper.py`) with the clone-first commands. Read `CLAUDE.md` first, then apply this exact replacement for the running-the-app section:

  Old block (to find and replace):
  ```batch
  # First-time setup (installs pip packages into embedded Python)
  INSTALL.bat

  # Run the application (launches tray mode)
  Yapper.bat

  # Open settings
  Settings.bat

  # Direct execution for testing
  python\python.exe app\yapper.py        # Console mode
  python\pythonw.exe app\yapper_tray.py  # Tray mode (no console)
  python\python.exe app\settings_ui.py   # GUI settings
  ```
  New block:
  ```bash
  # First-time setup (creates .venv, installs deps via uv)
  ./setup            # POSIX (macOS/Linux); setup.bat on Windows

  # Run the application
  ./run.sh           # macOS/Linux; run.command (macOS double-click); run.bat (Windows)

  # Run directly / for testing
  uv run python -m app        # the app (Phase 0: prints version; PySide6 app lands in Phase 4)
  uv run pytest               # run the test suite
  uv sync --extra local       # add on-device transcription engines
  ```

- [ ] **Update the `## File Structure` block in `CLAUDE.md`** so it no longer lists the deleted `python/` runtime and `.bat` launchers. Read the file, then replace the fenced file-structure block's `python/                # Embedded Python 3.11 runtime` and `*.bat                  # Windows launchers` lines with:
  ```
  pyproject.toml         # uv-managed deps + dev/[local] extras
  setup / setup.bat      # uv sync bootstrap
  run.sh/.command/.bat   # thin launchers -> uv run python -m app
  tests/                 # pytest suite (conftest + smoke)
  ```

- [ ] **Verify CLAUDE.md no longer references removed files.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -nE 'INSTALL.bat|Yapper.bat|Settings.bat|embedded Python|python\\python.exe' CLAUDE.md || echo "CLEAN: CLAUDE.md has no stale embedded refs"
  ```
  Expected: `CLEAN: CLAUDE.md has no stale embedded refs`

- [ ] **Run the full suite one final time to confirm the phase is green.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q
  ```
  Expected: `4 passed`. (Fallback if `uv`'s venv is unavailable on this arch: `PYTHONPATH=. python3 -m pytest -q` → `4 passed`.)

- [ ] **Commit.** Run:
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add CLAUDE.md && git commit -m "docs: update CLAUDE.md to clone-first (uv) workflow; drop embedded-runtime refs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Phase 0 Done When

- [ ] `python/`, `build_portable.py`, all embedded `.bat`, `installer/`, `install.sh`, `requirements.txt`, `dist/` are gone from the working tree and git index.
- [ ] `pyproject.toml` exists with the spec §10 dependency set, `[local]`/`[macos]`/`dev` extras, and `[tool.pytest.ini_options]`; `uv sync --extra dev` succeeds.
- [ ] `setup`/`setup.bat`/`run.sh`/`run.command`/`run.bat` all delegate to `uv run python -m app`; POSIX ones are `+x`.
- [ ] `app/__init__.py` + `app/__main__.py` make `python -m app` print `Yapper 4.0.0` + `© 2026 Cloudelipute`.
- [ ] `VERSION` file and `constants.VERSION` both read `4.0.0`; `constants.COPYRIGHT == "© 2026 Cloudelipute"`.
- [ ] Zero occurrences of the literal `© 2026 Cloudelipute` remain **except** the formal MIT line in `LICENSE`.
- [ ] `README.md` renders three Mermaid diagrams on GitHub and contains install/permissions/model-cost/BYOK sections.
- [ ] `tests/conftest.py` + `tests/test_smoke.py` give `4 passed` under `uv run pytest`.
- [ ] `.claude/`, `python/`, `.venv/` confirmed gitignored; `uv.lock` committed.
- [ ] `CLAUDE.md` describes the clone-first workflow with no stale embedded-runtime references.
