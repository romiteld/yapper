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
