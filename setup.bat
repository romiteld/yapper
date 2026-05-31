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
