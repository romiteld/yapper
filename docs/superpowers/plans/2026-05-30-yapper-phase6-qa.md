# Phase 6: QA & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Run the closing QA pass that adversarially reviews the whole Yapper v4 codebase across four parallel dimensions, auto-fixes every confirmed finding, re-verifies, gates on an all-green automated test run, completes manual smoke tests on macOS (M-series) and Windows, ships unsigned release artifacts, and scrubs the tree of personal info and `.claude/`.

**Architecture:** This phase is an orchestration + manual-verification plan, not new feature code — it adds CI/QA tooling (a coverage gate, a secret-scan test, a release script) and drives a multi-agent review→refute→fix→re-review loop, plus documented manual smoke and release checklists. It consumes the artifacts produced by Phases 0–5 (`app/core/`, `app/ui/`, `tests/`, `pyproject.toml`).

**Tech Stack:** `pytest` + `pytest-cov` + `unittest.mock` + `pytest-qt`, `uv`, `ruff` (lint gate), `pyinstaller`, `gh` CLI, `git`, the superpowers `dispatching-parallel-agents` sub-skill for the review fan-out.

---

## File Structure

**Create**
- `tests/qa/__init__.py` — empty package marker so `tests/qa/` is importable.
- `tests/qa/test_no_secrets.py` — fails if any API key / secret literal or `.env` is tracked.
- `tests/qa/test_no_personal_info.py` — fails if personal info beyond `© 2026 Cloudelipute` appears in tracked files, or if `.claude/` is tracked.
- `tests/qa/test_release_metadata.py` — asserts `VERSION == "4.0.0"`, `COPYRIGHT == "© 2026 Cloudelipute"`, and `pyproject` version match.
- `scripts/qa_review.md` — the multi-agent review workflow runbook (dimensions, refute approach, fix→re-review loop).
- `scripts/smoke_macos.md` — macOS M-series manual smoke checklist.
- `scripts/smoke_windows.md` — Windows manual smoke checklist.
- `scripts/release.md` — release runbook (build unsigned `.app`/`.dmg`/`.zip`, Gatekeeper workaround, tag, draft notes).
- `scripts/build_release.sh` — PyInstaller build driver for macOS (`.app` → `.dmg`) and the Windows-zip step it documents.
- `Yapper.spec` — PyInstaller spec (Info.plist with `NSMicrophoneUsageDescription` + `LSUIElement`, icon, hidden imports).
- `docs/RELEASE_NOTES_v4.0.0.md` — drafted GitHub release notes for the tag.

**Modify**
- `pyproject.toml` — add `[tool.pytest.ini_options]` coverage flags, `[tool.coverage.*]`, dev deps (`pytest-cov`, `ruff`, `pyinstaller`), and `qa` / `release` extras.
- `app/core/constants.py` — bump `VERSION = "4.0.0"` and normalize `COPYRIGHT = "© 2026 Cloudelipute"` (if Phase 0 left it at the old C-string form).
- `VERSION` (repo-root file) — set to `4.0.0`.
- `README.md` — replace the `romiteld` GitHub handle URLs with the org-neutral `cloudelipute` placeholder and add the Gatekeeper / unsigned-build section if Phase 0 did not.

---

## Tasks

### Task 1: Secret-scan gate (TDD)

Prevent any API key, token, or `.env` from being tracked. This is the first automated security gate.

**Files:**
- Create: `tests/qa/__init__.py`
- Create (Test): `tests/qa/test_no_secrets.py`

- [ ] Create the package marker.

```bash
mkdir -p /home/romiteld/Development/Desktop_Apps/yapper-portable/tests/qa
printf '' > /home/romiteld/Development/Desktop_Apps/yapper-portable/tests/qa/__init__.py
```

- [ ] Write the failing test. File: `tests/qa/test_no_secrets.py`

```python
"""QA gate: no secrets or API keys may be committed.

© 2026 Cloudelipute
"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# OpenAI keys: sk-... (legacy) and sk-proj-... (project). Match a realistic length.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),        # OpenAI secret/legacy keys
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),  # OpenAI project keys
    re.compile(r"AKIA[0-9A-Z]{16}"),            # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{36}"),         # GitHub personal token
]

# Self-reference: this test file legitimately contains the regex source strings.
_ALLOWLIST = {"tests/qa/test_no_secrets.py"}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [p for p in out.stdout.splitlines() if p]


def test_no_env_files_tracked():
    tracked = _tracked_files()
    bad = [p for p in tracked if Path(p).name == ".env" or p.endswith(".env")]
    assert not bad, f"Tracked .env files must not be committed: {bad}"


def test_no_secret_literals_in_tracked_text():
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel in _ALLOWLIST:
            continue
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for pat in _SECRET_PATTERNS:
            if pat.search(text):
                offenders.append(f"{rel}: matched {pat.pattern}")
    assert not offenders, "Secret-like literals found:\n" + "\n".join(offenders)
```

- [ ] Run the test, expect it to PASS if the tree is clean (this gate is "green when safe"). If it FAILS, that is a real finding to fix before continuing.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q tests/qa/test_no_secrets.py
# Expected: 2 passed.  If FAIL: a secret/.env is tracked -> remove it (git rm --cached) before proceeding.
```

- [ ] Sanity-check the detector actually catches a planted secret (temporary, never committed).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
printf 'token = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890"\n' > /tmp/leak.py && \
git -C /home/romiteld/Development/Desktop_Apps/yapper-portable add -N /tmp/leak.py 2>/dev/null; \
cp /tmp/leak.py /home/romiteld/Development/Desktop_Apps/yapper-portable/app/core/_leak_probe.py && \
git -C /home/romiteld/Development/Desktop_Apps/yapper-portable add app/core/_leak_probe.py && \
uv run pytest -q tests/qa/test_no_secrets.py; echo "exit=$?"; \
git -C /home/romiteld/Development/Desktop_Apps/yapper-portable rm -f --quiet app/core/_leak_probe.py && rm -f /tmp/leak.py
# Expected: pytest FAILS (exit=1) while the probe is present, proving the detector works. Probe is removed afterward.
```

- [ ] Commit.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/qa/__init__.py tests/qa/test_no_secrets.py && \
git commit -m "test(qa): add committed-secret scan gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Personal-info & `.claude/` scrub gate (TDD)

Enforce spec §1: the only identifier allowed is the brand `Cloudelipute` (normalized `© 2026 Cloudelipute`); no real name/email; `.claude/` must not be tracked.

**Files:**
- Create (Test): `tests/qa/test_no_personal_info.py`

- [ ] Write the failing test. File: `tests/qa/test_no_personal_info.py`

```python
"""QA gate: no personal info beyond the Cloudelipute brand; .claude/ not tracked.

© 2026 Cloudelipute
"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Personal identifiers that must NOT appear in tracked files.
# 'romiteld' is the maintainer's GitHub handle and leaks identity; replace with
# the org-neutral 'cloudelipute' in repo URLs.
_FORBIDDEN = [
    re.compile(r"romitelli", re.IGNORECASE),
    re.compile(r"\bromiteld\b", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+\-]+@(?:gmail|outlook|yahoo|hotmail|icloud)\.com", re.IGNORECASE),
    re.compile(r"\bdaniel(?:\.romitelli)?\b", re.IGNORECASE),
    re.compile(r"cloudelipute\.solutions", re.IGNORECASE),
]

# This test file contains the forbidden patterns as regex source -> allowlist it.
_ALLOWLIST = {"tests/qa/test_no_personal_info.py"}

# Brand string that is explicitly allowed to remain.
_ALLOWED_BRAND = "© 2026 Cloudelipute"


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [p for p in out.stdout.splitlines() if p]


def test_claude_dir_not_tracked():
    tracked = _tracked_files()
    bad = [p for p in tracked if p == ".claude" or p.startswith(".claude/")]
    assert not bad, f".claude/ must not be tracked: {bad}"


def test_no_personal_identifiers():
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel in _ALLOWLIST:
            continue
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for pat in _FORBIDDEN:
            if pat.search(text):
                offenders.append(f"{rel}: matched /{pat.pattern}/")
    assert not offenders, (
        "Personal info found (only the brand is allowed):\n" + "\n".join(offenders)
    )


def test_brand_is_present_somewhere():
    # The allowed brand should exist in LICENSE so attribution is intact.
    license_text = (REPO / "LICENSE").read_text(encoding="utf-8")
    assert "Cloudelipute" in license_text
```

- [ ] Run the test. It will FAIL because `README.md` contains `romiteld` GitHub URLs (confirmed present).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q tests/qa/test_no_personal_info.py
# Expected: test_no_personal_identifiers FAILS, listing README.md: matched /\bromiteld\b/.
```

- [ ] Fix the finding: replace the `romiteld` GitHub handle in `README.md` with `cloudelipute`. Run this replacement and verify the exact lines changed.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
python3 - <<'PY'
from pathlib import Path
p = Path("README.md")
t = p.read_text(encoding="utf-8")
t = t.replace("github.com/romiteld/yapper", "github.com/cloudelipute/yapper")
p.write_text(t, encoding="utf-8")
print("rewritten README.md")
PY
grep -n "github.com" README.md
# Expected: every GitHub URL now reads github.com/cloudelipute/yapper ; no 'romiteld' remains.
```

- [ ] Re-run the test, expect PASS.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q tests/qa/test_no_personal_info.py
# Expected: 3 passed.
```

- [ ] Commit.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/qa/test_no_personal_info.py README.md && \
git commit -m "test(qa): scrub personal info; replace maintainer handle in README

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Release-metadata gate (TDD)

Lock the version/copyright so the release artifacts and the in-app About screen agree. Spec §2 mandates `VERSION → 4.0.0` and `© 2026 Cloudelipute`.

**Files:**
- Create (Test): `tests/qa/test_release_metadata.py`
- Modify: `app/core/constants.py`, `VERSION` (repo root)

- [ ] Write the failing test. File: `tests/qa/test_release_metadata.py`

```python
"""QA gate: version and copyright metadata are consistent for release.

© 2026 Cloudelipute
"""
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "app"))

from core import constants  # noqa: E402

EXPECTED_VERSION = "4.0.0"
EXPECTED_COPYRIGHT = "© 2026 Cloudelipute"


def test_constants_version():
    assert constants.VERSION == EXPECTED_VERSION


def test_constants_copyright_normalized():
    assert constants.COPYRIGHT == EXPECTED_COPYRIGHT


def test_root_version_file():
    text = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert text == EXPECTED_VERSION


def test_pyproject_version_matches():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = data["project"]["version"]
    assert project_version == EXPECTED_VERSION
```

- [ ] Run the test, expect FAILs (constants is `3.3.1` / old copyright string; root `VERSION` may differ; pyproject may differ).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q tests/qa/test_release_metadata.py
# Expected: failures on version/copyright mismatch.
```

- [ ] Fix `app/core/constants.py`. Apply both edits.

  Edit `VERSION = "3.3.1"` → `VERSION = "4.0.0"`.

  Edit `COPYRIGHT = "© 2026 Cloudelipute"` → `COPYRIGHT = "© 2026 Cloudelipute"`.

- [ ] Fix the root `VERSION` file.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && printf '4.0.0' > VERSION
```

- [ ] Ensure `pyproject.toml` declares `version = "4.0.0"` under `[project]`. If Phase 0 set a different value, edit it to `4.0.0`. Verify.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && grep -nE '^version *= *"' pyproject.toml
# Expected: version = "4.0.0"
```

- [ ] Re-run the test, expect PASS.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q tests/qa/test_release_metadata.py
# Expected: 4 passed.
```

- [ ] Commit.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add tests/qa/test_release_metadata.py app/core/constants.py VERSION pyproject.toml && \
git commit -m "chore(release): pin v4.0.0 metadata and copyright; add gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Coverage gate + lint wiring in pyproject (verification, not unit-tested)

Wire the full-suite gate so `uv run pytest -q` runs everything with coverage, and add `ruff` as a static gate. TDD is impractical for build config; use explicit command verification.

**Files:**
- Modify: `pyproject.toml`

- [ ] Read the current `pyproject.toml` to confirm Phase 0's structure before editing.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && cat pyproject.toml
```

- [ ] Add the dev dependency group (PEP 735) and tool config. Insert/merge these blocks (do not duplicate keys Phase 0 already wrote; merge into existing tables).

```toml
[dependency-groups]
dev = [
    "pytest>=8.2",
    "pytest-cov>=5.0",
    "pytest-qt>=4.4",
    "ruff>=0.6",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --cov=app/core --cov-report=term-missing --cov-fail-under=70"
qt_api = "pyside6"

[tool.coverage.run]
source = ["app/core"]
omit = ["app/core/engines/local.py"]  # optional [local] extra not installed in base CI

[tool.coverage.report]
show_missing = true
skip_empty = true

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B"]
ignore = ["E501"]  # line length handled by formatter; long QSS/prompt strings allowed
```

- [ ] Sync the dev group.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv sync --group dev
# Expected: pytest-cov, pytest-qt, ruff resolved and installed into .venv.
```

- [ ] Run the lint gate and fix any errors it reports (ruff auto-fixable issues via `--fix`).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run ruff check app tests --fix && uv run ruff check app tests
# Expected (second command): "All checks passed!"  Fix any remaining B/F errors by hand before continuing.
```

- [ ] Run the full suite with the coverage gate.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q
# Expected: all tests pass; coverage table prints; "Required test coverage of 70% reached" (no --cov-fail-under failure).
# If coverage < 70%: that is a real gap in Phases 1-5 tests -> file it as a Task 5 finding, do not lower the threshold.
```

- [ ] Commit.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add pyproject.toml uv.lock && \
git commit -m "chore(qa): add coverage gate (70%), ruff lint, pytest-qt config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Multi-agent adversarial review → refute → fix → re-review

This is the heart of Phase 6. Use the superpowers `dispatching-parallel-agents` sub-skill to fan out four independent review agents over the Phase 0–5 code, then adversarially verify (refute) each finding, fix confirmed ones, and run a SECOND review pass. This task produces a runbook AND executes it.

**Files:**
- Create: `scripts/qa_review.md`

- [ ] Write the runbook. File: `scripts/qa_review.md`

````markdown
# Yapper v4 — Multi-Agent QA Review Runbook

© 2026 Cloudelipute

## Goal
Adversarially find every real defect across four dimensions, refute false
positives, auto-fix confirmed findings (small and large), then re-review.

## Preconditions
- Working tree clean: `git status --porcelain` is empty.
- Baseline green: `uv run pytest -q` passes; `uv run ruff check app tests` passes.
- Capture the review scope (the diff against the last shipped tag):
  `git diff v3.3.2 --stat`  (everything since the v3 line is in scope).

## Pass 1 — Parallel review (dispatch 4 subagents, one per dimension)
Dispatch all four IN PARALLEL (single message, four Task calls) using the
`superpowers:dispatching-parallel-agents` sub-skill. Each agent is read-only and
returns a numbered findings list; each finding MUST cite file:line and a concrete
repro or argument. No agent edits code in Pass 1.

### Dimension A — Correctness / bugs
Scope: `app/core/audio.py`, `hotkeys.py`, `typer.py`, `transcriber.py`,
`engines/*.py`, `formatting.py`, `vocabulary.py`, `vad.py`, `ui/app.py`,
`ui/hud.py`.
Hunt for: PTT auto-repeat double-trigger (the `_active` guard in HotkeyManager),
race in clipboard restore daemon thread (the ~1.5s timer), wrong sample
width/rate in sounddevice path, off-by-one in VAD frame slicing, signal/slot
threading (pynput listener thread mutating Qt widgets directly), unhandled None
from `Engine.transcribe`, exceptions swallowed silently.

### Dimension B — Missing / incomplete logic
Scope: every module touched in Phases 1-5 + `constants.DEFAULT_SETTINGS`/
`SETTINGS_SCHEMA`.
Hunt for: settings keys present in DEFAULT_SETTINGS but absent from
SETTINGS_SCHEMA (or vice versa), migration that drops `always_listening` into
`activation_mode` not actually wired, engine `get_engine()` branches with no
fallback, formatting modes ('technical'/'natural'/'verbatim') where one path is
a stub, vocabulary `import_csv` not validating columns, `Notifier` no-op path
never reached, wizard Permissions step not skipped on Windows.

### Dimension C — Cross-platform / macOS correctness
Scope: `permissions.py`, `typer.py`, `hotkeys.py`, `notifications.py`,
`platform.py`, `ui/hud.py`, `Yapper.spec`.
Hunt for: code that assumes Windows paths/keys, `permission_status()` not
returning True on non-mac, pynput ⌃/⌥ combo defaults on macOS (issue #297),
HUD missing `Qt.WindowTransparentForInput` / NSWindow collection-behavior shim,
Info.plist missing `NSMicrophoneUsageDescription`/`LSUIElement`, accessibility
silent-fail not detected before inject, hardcoded `/Applications` assumptions.

### Dimension D — Security / secrets / API-key handling
Scope: `api.py`, `config.py`, `settings.json` handling, logging calls, `ui/*`.
Hunt for: API key written to logs (grep for `logger.*api_key`), key echoed in
exceptions, settings.json saved world-readable, key in tracebacks/notifications,
`prompt`/transcript text logged at INFO (privacy), missing redaction in the
About/diagnostics screen, key passed in URL/query.

## Pass 1.5 — Adversarial refutation (refute every finding)
For EACH finding from Pass 1, dispatch a refutation step (can be one
consolidating agent): try to PROVE THE FINDING WRONG. Acceptable refutations:
- Write a focused failing test that would catch the bug. If you cannot make it
  fail, the finding is likely a false positive — mark REFUTED with the test.
- Show the guarding code path the reviewer missed (cite file:line).
Classify each finding: CONFIRMED (repro/failing test exists) | REFUTED (proof) |
UNCERTAIN (needs maintainer). Only CONFIRMED findings get fixed.

## Fix loop — small & large
- SMALL fix (≤ ~20 lines, local): apply directly, add/keep the failing test from
  refutation, make it pass, `uv run pytest -q`, commit one fix per commit:
  `git commit -m "fix(<area>): <finding> (QA pass 1)"`.
- LARGE fix (cross-module / behavioral): write the failing test first (TDD),
  implement, run full suite, commit. If a fix risks regressions, run the
  smoke checklist section relevant to it.
- After each fix: re-run `uv run pytest -q` and `uv run ruff check app tests`.

## Pass 2 — Second verification review
After ALL confirmed findings are fixed and the suite is green, re-dispatch the
same four dimensions (parallel) over the NEW diff. Goal: confirm fixes did not
introduce regressions and no new defects surfaced. Any new CONFIRMED finding
re-enters the fix loop. Phase 6 review is DONE when Pass 2 returns zero
CONFIRMED findings across all four dimensions and the suite + lint are green.

## Exit artifact
Record in the PR description: counts per dimension (found / confirmed / refuted /
fixed) for Pass 1 and Pass 2, and the final `uv run pytest -q` summary line.
````

- [ ] Verify the working tree is clean and the baseline is green before dispatching.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git status --porcelain; uv run pytest -q && uv run ruff check app tests
# Expected: porcelain empty; tests pass; ruff "All checks passed!". Do NOT dispatch reviewers on a dirty/red tree.
```

- [ ] Execute Pass 1: invoke the `superpowers:dispatching-parallel-agents` sub-skill to dispatch four read-only review subagents (Dimensions A–D above), in parallel, each returning a numbered findings list with file:line citations. Collect all four lists.

- [ ] Execute Pass 1.5: for each finding, run the refutation step (write a focused failing test under `tests/qa/` or `tests/`, or cite the guarding code). Label each CONFIRMED / REFUTED / UNCERTAIN. Keep the failing tests for CONFIRMED findings.

- [ ] Execute the fix loop: fix every CONFIRMED finding (small inline, large TDD), one fix per commit, re-running `uv run pytest -q` and `uv run ruff check app tests` after each. Use this commit format.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q && uv run ruff check app tests && \
git add -A && git commit -m "fix(<area>): <one-line finding summary> (QA pass 1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] Execute Pass 2: re-dispatch the four dimensions over the post-fix diff. Loop any new CONFIRMED findings back through the fix loop until Pass 2 returns zero CONFIRMED findings.

- [ ] Final green confirmation for the review gate.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q && uv run ruff check app tests
# Expected: all tests pass, coverage >= 70%, ruff clean. Record the pytest summary line for the PR.
```

- [ ] Commit the runbook (if not already committed alongside fixes).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add scripts/qa_review.md && \
git commit -m "docs(qa): add multi-agent review runbook (4 dimensions, refute+re-review)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Automated-test run gate (full green, documented)

Make the all-green gate explicit and repeatable, including the `[local]` extra path and a coverage report artifact.

**Files:**
- Modify: `scripts/qa_review.md` (append a "CI gate" section) — or document inline; no new test code.

- [ ] Run the base gate and capture the exit code.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q; echo "base_exit=$?"
# Expected: base_exit=0, all green, coverage >= 70%.
```

- [ ] Run the suite with the optional `[local]` engine extra installed, to exercise `engines/local.py` import paths that base CI omits. (This requires the host to support the extra; on Windows that is `faster-whisper`, on mac `mlx-whisper`.)

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv sync --extra local --group dev && \
uv run pytest -q tests/ -k "engine or local"; echo "local_exit=$?"
# Expected: local_exit=0. If the extra cannot install on this host, note it and rely on Task 5 Dimension C mac/win smoke instead.
```

- [ ] Generate an HTML coverage report for the release record (not committed; attach to PR if useful).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q --cov=app/core --cov-report=html && \
ls htmlcov/index.html
# Expected: htmlcov/index.html exists. htmlcov/ is gitignored via the build/ and *.egg-info patterns? Confirm next step.
```

- [ ] Ensure `htmlcov/` and `.coverage` are gitignored so coverage artifacts never get tracked. Add the lines if missing, then verify the scan gate still passes.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
grep -qxF 'htmlcov/' .gitignore || printf 'htmlcov/\n.coverage\n' >> .gitignore; \
uv run pytest -q tests/qa/test_no_secrets.py tests/qa/test_no_personal_info.py
# Expected: gitignore contains htmlcov/ and .coverage; QA scan gates pass.
```

- [ ] Commit the gitignore update.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add .gitignore && \
git commit -m "chore(qa): gitignore coverage artifacts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Manual smoke checklist — macOS (M-series)

Real-hardware verification per spec §11 (macOS permission UX is the top risk). This is a manual checklist run on an M3/M4/M5 Mac; there is no honest unit test for TCC/HUD/paste-into-real-apps.

**Files:**
- Create: `scripts/smoke_macos.md`

- [ ] Write the checklist. File: `scripts/smoke_macos.md`

````markdown
# Yapper v4 — macOS (Apple Silicon) Manual Smoke Checklist

© 2026 Cloudelipute

Run on a clean M-series Mac (Sequoia/Tahoe). Tick each box; record OS version,
chip, and Yapper build (clone vs `.app`).

## Setup
- [ ] `git clone` + `./setup` (`uv sync`) succeeds; `./run.command` launches.
- [ ] App appears as menu-bar item only (LSUIElement); no Dock icon.

## Permissions flow (the top risk)
- [ ] First mic capture triggers the macOS Microphone prompt; granting works.
- [ ] Wizard Permissions step shows Accessibility = NOT trusted before granting
      (`AXIsProcessTrusted()` via permissions.py).
- [ ] Wizard Permissions step shows Input Monitoring status correctly.
- [ ] "Open System Settings" deep links open the correct panes.
- [ ] After granting Accessibility + Input Monitoring, the wizard shows the
      "quit & relaunch after granting" notice.
- [ ] RELAUNCH: after restart, `permission_status()` reports all three True;
      hotkey capture and paste now work (TCC re-read only at process start).

## Activation modes
- [ ] Push-to-talk: hold the configured key → HUD = listening; release → stop.
      Hold for 5s and confirm NO double-trigger (the `_active` guard).
- [ ] Toggle: press once → listening; press again → stop+transcribe.
- [ ] (If enabled) Wake word: "Yapper start"/"Yapper stop" bridges correctly.

## HUD states
- [ ] idle → listening (waveform animates with `update_level`) → transcribing
      → done ✓, then auto-hides.
- [ ] HUD floats over a full-screen Space (collection-behavior shim) and is
      click-through (`Qt.WindowTransparentForInput`).
- [ ] Reduce Motion on: HUD does not animate the waveform.

## Paste into real apps (Unicode-safe paste primary)
- [ ] Paste into a code editor (VS Code): identifiers/flags preserved.
- [ ] Paste into a browser text field.
- [ ] Paste into Terminal/iTerm.
- [ ] Paste into Slack.
- [ ] Dictate emoji + CJK ("café ☕ 日本語 🚀"): inserted intact (no isascii loss).
- [ ] Clipboard is restored to its prior contents ~1.5s after paste.

## No-slop golden example (end-to-end)
- [ ] Dictate: "run cube cuttle get pods dash n kube system then cat config dot
      yaml". Technical mode output is exactly:
      `kubectl get pods -n kube-system then cat config.yaml`
      (vocabulary correction + spoken-symbol expansion; NO paraphrase).

## Engine switch
- [ ] Tray/Settings switch cloud → local (with `[local]` extra): mlx-whisper
      transcribes offline; switch back to cloud works.

## Vocabulary correction
- [ ] Add term "Next.js" (said "next J S"); dictation produces `Next.js`.
- [ ] CSV import of a 3-row vocab file loads without error.
````

- [ ] Run the checklist on real hardware and record results. (Manual; no command output to assert — capture pass/fail per box in the PR.)

- [ ] Commit.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add scripts/smoke_macos.md && \
git commit -m "docs(qa): add macOS M-series manual smoke checklist

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Manual smoke checklist — Windows

Windows is first-class; verify the no-permission-prompt path and the same end-to-end flows.

**Files:**
- Create: `scripts/smoke_windows.md`

- [ ] Write the checklist. File: `scripts/smoke_windows.md`

````markdown
# Yapper v4 — Windows Manual Smoke Checklist

© 2026 Cloudelipute

Run on Windows 10/11. Record OS build and Yapper build (clone vs `.zip`).

## Setup
- [ ] `git clone` + `setup.bat`/`run.bat` (`uv sync`) launches the tray app.
- [ ] `permission_status()` returns all True (permissions are no-ops on Windows).
- [ ] Wizard auto-SKIPS the Permissions step on Windows.

## Activation modes
- [ ] Push-to-talk: hold key → listening; release → transcribe. Hold 5s → NO
      double-trigger.
- [ ] Toggle: press/press works.

## HUD states
- [ ] idle → listening (waveform) → transcribing → done ✓ → auto-hide.
- [ ] Tray icon changes color per state; right-click menu opens settings/history.

## Paste into real apps
- [ ] VS Code / Notepad / browser / Windows Terminal / Slack: paste intact.
- [ ] Emoji + CJK preserved; clipboard restored ~1.5s after paste.

## No-slop golden example
- [ ] Same kubectl example as macOS → exact `kubectl get pods -n kube-system
      then cat config.yaml`.

## Engine switch
- [ ] cloud → local (`[local]` extra = faster-whisper) transcribes offline;
      back to cloud works.

## Vocabulary correction
- [ ] "next J S" → `Next.js`; CSV import loads.
````

- [ ] Run on a Windows machine and record results (manual).

- [ ] Commit.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add scripts/smoke_windows.md && \
git commit -m "docs(qa): add Windows manual smoke checklist

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: PyInstaller spec + build driver (verification)

Produce the unsigned artifacts. Spec §7: arm64 `.app` (Info.plist with `NSMicrophoneUsageDescription`, `LSUIElement=true`) → `.dmg` (mac); `.zip` (Windows). No TDD for packaging; verify the build produces the artifact and the plist keys are present.

**Files:**
- Create: `Yapper.spec`
- Create: `scripts/build_release.sh`

- [ ] Write the PyInstaller spec. File: `Yapper.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
# Yapper v4 unsigned-bundle PyInstaller spec.
# © 2026 Cloudelipute
# Build (mac):  uv run pyinstaller Yapper.spec --noconfirm
# Build (win):  uv run pyinstaller Yapper.spec --noconfirm

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    ["app/__main__.py"],  # Phase 4 entry: `python -m app` -> ui.app.main()
    pathex=[str(ROOT), str(ROOT / "app")],
    binaries=[],
    datas=[
        ("sounds", "sounds"),
        ("yapper_icon_pink.png", "."),
    ],
    hiddenimports=[
        "sounddevice",
        "pynput.keyboard._darwin" if sys.platform == "darwin" else "pynput.keyboard._win32",
        "pynput.mouse._darwin" if sys.platform == "darwin" else "pynput.mouse._win32",
        "desktop_notifier",
        "rapidfuzz",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "customtkinter", "pystray", "pyaudio"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="Yapper", debug=False, strip=False, upx=False, console=False,
    icon=str(ROOT / "yapper.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, name="Yapper",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Yapper.app",
        icon=None,  # supply yapper.icns if available; .png fallback bundled in datas
        bundle_identifier="solutions.cloudelipute.yapper",
        info_plist={
            "LSUIElement": True,  # menu-bar/agent app, no Dock icon
            "NSMicrophoneUsageDescription":
                "Yapper records your microphone to transcribe speech to text.",
            "CFBundleShortVersionString": "4.0.0",
            "CFBundleVersion": "4.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "13.0",
        },
    )
```

- [ ] Write the build driver. File: `scripts/build_release.sh`

```bash
#!/usr/bin/env bash
# Yapper v4 unsigned release builder.
# © 2026 Cloudelipute
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(cat VERSION)"

echo "==> Building Yapper v${VERSION} (unsigned)"
uv sync --extra release
rm -rf build dist

uv run pyinstaller Yapper.spec --noconfirm

case "$(uname -s)" in
  Darwin)
    echo "==> Verifying Info.plist keys"
    /usr/libexec/PlistBuddy -c 'Print :NSMicrophoneUsageDescription' \
      "dist/Yapper.app/Contents/Info.plist"
    /usr/libexec/PlistBuddy -c 'Print :LSUIElement' \
      "dist/Yapper.app/Contents/Info.plist"
    echo "==> Creating .dmg"
    hdiutil create -volname "Yapper" -srcfolder "dist/Yapper.app" \
      -ov -format UDZO "dist/Yapper-${VERSION}-arm64.dmg"
    echo "==> .dmg ready: dist/Yapper-${VERSION}-arm64.dmg"
    echo "    First-launch (unsigned): xattr -dr com.apple.quarantine /Applications/Yapper.app"
    ;;
  *)  # Windows (Git Bash / MSYS) or Linux
    echo "==> Zipping Windows bundle"
    ( cd dist && zip -r "Yapper-${VERSION}-win64.zip" "Yapper" >/dev/null )
    echo "==> .zip ready: dist/Yapper-${VERSION}-win64.zip"
    ;;
esac
echo "==> Build complete."
```

- [ ] Make the driver executable and confirm `pyinstaller` + a `release` extra are available. Add the `release` extra to `pyproject.toml` if Phase 0 did not (`release = ["pyinstaller>=6.0"]` under `[project.optional-dependencies]`).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && chmod +x scripts/build_release.sh && \
grep -nE 'release *=|pyinstaller' pyproject.toml
# Expected: a release extra listing pyinstaller. Add it if absent.
```

- [ ] Build on the target platform and verify the artifact exists. (Run on macOS for `.app`/`.dmg`, on Windows for `.zip`.)

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && ./scripts/build_release.sh && ls -la dist/
# Expected (mac): dist/Yapper.app and dist/Yapper-4.0.0-arm64.dmg; plist keys printed.
# Expected (win): dist/Yapper/ and dist/Yapper-4.0.0-win64.zip.
```

- [ ] Verify `dist/` stays gitignored so artifacts are never committed (it already is, via the `dist/` line in `.gitignore` — confirm).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git check-ignore dist/Yapper.spec >/dev/null 2>&1; git check-ignore dist; echo "dist ignored exit=$?"
# Expected: 'dist' is ignored (exit=0). Build outputs never get tracked.
```

- [ ] Commit the spec and driver.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add Yapper.spec scripts/build_release.sh pyproject.toml && \
git commit -m "build(release): add PyInstaller spec and unsigned build driver

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Release runbook + drafted notes + tag

Document the release checklist, draft the GitHub release notes, and tag v4.0.0. Spec §7: Gatekeeper `xattr` workaround documented.

**Files:**
- Create: `scripts/release.md`
- Create: `docs/RELEASE_NOTES_v4.0.0.md`

- [ ] Write the release runbook. File: `scripts/release.md`

````markdown
# Yapper v4.0.0 — Release Checklist

© 2026 Cloudelipute

## Pre-flight (must all pass)
- [ ] `git status --porcelain` empty (clean tree).
- [ ] `uv run pytest -q` green, coverage >= 70%.
- [ ] `uv run ruff check app tests` clean.
- [ ] `uv run pytest -q tests/qa` green (secrets, personal-info, metadata gates).
- [ ] Multi-agent review (scripts/qa_review.md) Pass 2 = zero CONFIRMED findings.
- [ ] macOS smoke (scripts/smoke_macos.md) complete.
- [ ] Windows smoke (scripts/smoke_windows.md) complete.

## Build artifacts (unsigned)
- [ ] macOS (M-series host): `./scripts/build_release.sh`
      -> dist/Yapper.app, dist/Yapper-4.0.0-arm64.dmg
- [ ] Windows host: `bash scripts/build_release.sh`
      -> dist/Yapper-4.0.0-win64.zip

## Gatekeeper note (ships in release body)
Unsigned `.app`: Sequoia/Tahoe removed right-click-Open. First launch:
`xattr -dr com.apple.quarantine /Applications/Yapper.app`
or System Settings -> Privacy & Security -> "Open Anyway".

## Tag + GitHub release
- [ ] `git tag -a v4.0.0 -m "Yapper v4.0.0 — cross-platform reimagining"`
- [ ] `git push origin v4.0.0`
- [ ] `gh release create v4.0.0 --draft --title "Yapper v4.0.0" \
        --notes-file docs/RELEASE_NOTES_v4.0.0.md \
        dist/Yapper-4.0.0-arm64.dmg dist/Yapper-4.0.0-win64.zip`
- [ ] Review the draft on GitHub; publish when artifacts attached.
````

- [ ] Write the drafted release notes. File: `docs/RELEASE_NOTES_v4.0.0.md`

````markdown
# Yapper v4.0.0 — Cross-Platform Reimagining

© 2026 Cloudelipute

Yapper is now first-class on **macOS Apple Silicon** and **Windows** from one
codebase, with a fully reimagined UI/UX and a "no AI slop" formatting engine
built for engineers.

## Highlights
- **Cross-platform:** macOS (M-series) + Windows, single codebase (PySide6/Qt).
- **Push-to-talk by default** (toggle and wake-word selectable) via pynput.
- **Recording HUD:** floating translucent pill with live waveform and
  idle→listening→transcribing→done states; Reduce-Motion aware.
- **No-slop formatting:** Technical mode never paraphrases — preserves
  identifiers, CLI flags, file paths, and code. Spoken-symbol expansion
  (`dash dash help` → `--help`) and vocabulary correction
  (`cube cuttle` → `kubectl`).
- **Engines:** cloud `gpt-4o-mini-transcribe` (default) or on-device
  (`mlx-whisper` on mac / `faster-whisper` on win, via the `[local]` extra).
- **Text model:** `gpt-5-nano` with `reasoning_effort='minimal'`
  (migrated off the deprecated `gpt-4.1-nano`).
- **Unicode-safe paste** insertion (emoji/CJK), clipboard restored after paste.
- **First-run wizard**, modern Settings, searchable History, native
  notifications (HUD is the always-available fallback).

## Install
**Clone-first (recommended):**
```
git clone https://github.com/cloudelipute/yapper.git
cd yapper && ./setup        # uv sync
./run.command   # macOS    |   run.bat   # Windows
# on-device models: uv sync --extra local
```

**Prebuilt (unsigned):** download the `.dmg` (macOS arm64) or `.zip` (Windows)
below.

### macOS first-launch (unsigned)
```
xattr -dr com.apple.quarantine /Applications/Yapper.app
```
or System Settings → Privacy & Security → **Open Anyway**.

### macOS permissions
Grant **Microphone**, **Accessibility**, and **Input Monitoring**, then
**quit & relaunch** (macOS re-reads permissions only at launch).

## Privacy
Bring-your-own-key. Your OpenAI API key stays in local `settings.json`; audio is
sent only to OpenAI when the cloud engine is selected, or stays on-device with
the `[local]` engine.

## Known limitations
- Builds are **unsigned** (no Apple notarization); see first-launch note.
- Notification Center may be unavailable on the unsigned mac build — the HUD
  covers all feedback.
- Linux is best-effort, not a release target.
````

- [ ] Verify the release notes contain no personal info (re-run the scrub gate, which scans all tracked files including the new docs).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && git add scripts/release.md docs/RELEASE_NOTES_v4.0.0.md && \
uv run pytest -q tests/qa/test_no_personal_info.py tests/qa/test_no_secrets.py
# Expected: gates pass (notes use 'cloudelipute' org, '© 2026 Cloudelipute', no email/handle).
```

- [ ] Commit the runbook and notes.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
git commit -m "docs(release): add release checklist and drafted v4.0.0 notes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] Tag the release (only after all pre-flight boxes in `scripts/release.md` are checked). // verify the v3 tags are not re-used.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
git tag -a v4.0.0 -m "Yapper v4.0.0 — cross-platform reimagining" && git tag | grep v4
# Expected: v4.0.0 appears. Push and draft the GitHub release per scripts/release.md when artifacts are built.
```

---

### Task 11: Final scrub verification (all gates green together)

The closing gate: confirm the whole tree passes every QA gate in one run, and that `.claude/` is absent from the tracked tree and the working directory ships nothing it shouldn't.

**Files:** none (verification only).

- [ ] Confirm `.claude/` is gitignored and not tracked.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
git ls-files | grep -c '^\.claude' ; git check-ignore .claude/ >/dev/null 2>&1; echo "claude_ignored_exit=$?"
# Expected: tracked-count line prints 0; claude_ignored_exit=0 (.claude/ ignored, not tracked).
```

- [ ] Run the entire QA gate suite together.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q tests/qa
# Expected: all secrets/personal-info/metadata tests pass.
```

- [ ] Run the full suite + lint one final time as the Phase 6 exit gate.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && uv run pytest -q && uv run ruff check app tests
# Expected: all green, coverage >= 70%, ruff clean. This is the Phase 6 DONE signal.
```

- [ ] Final manual grep that the only brand identifier remaining is `Cloudelipute` and no stray personal info slipped in via any phase's files.

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
git grep -nIE 'romitelli|\bromiteld\b|@(gmail|outlook|yahoo|hotmail|icloud)\.com|cloudelipute\.solutions' -- ':!tests/qa/*' ; echo "scrub_exit=$?"
# Expected: no matches; scrub_exit=1 (git grep returns 1 when nothing matches). Any match = a finding to fix.
```

- [ ] Confirm `Cloudelipute` brand attribution is present where expected (LICENSE + constants COPYRIGHT).

```bash
cd /home/romiteld/Development/Desktop_Apps/yapper-portable && \
grep -q 'Cloudelipute' LICENSE && grep -q '© 2026 Cloudelipute' app/core/constants.py && echo "brand_ok"
# Expected: prints brand_ok.
```

- [ ] No commit needed (verification-only). Phase 6 is complete when every box above is checked and the exit gate is green.

---

## Phase 6 Done Definition

- [ ] `uv run pytest -q` green with coverage ≥ 70% (Task 4/6).
- [ ] `uv run ruff check app tests` clean.
- [ ] `tests/qa/` gates (secrets, personal-info, release-metadata) all pass.
- [ ] Multi-agent review Pass 2 returns zero CONFIRMED findings across all four dimensions (Task 5).
- [ ] macOS M-series + Windows manual smoke checklists complete (Tasks 7–8).
- [ ] Unsigned `.app`/`.dmg` + `.zip` build successfully with correct Info.plist keys (Task 9).
- [ ] `v4.0.0` tagged with drafted release notes and Gatekeeper workaround documented (Task 10).
- [ ] Final scrub confirms only `© 2026 Cloudelipute` remains and `.claude/` is untracked (Task 11).
