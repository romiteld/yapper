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
