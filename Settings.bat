@echo off
setlocal

REM ============================================
REM   YAPPER SETTINGS
REM   Copyright (c) 2026 Cloudelipute
REM ============================================

cd /d "%~dp0"

REM Check if first-time setup is needed
if not exist "python\Lib\site-packages\openai" (
    echo.
    echo   First-time setup required!
    echo   Please run INSTALL.bat first.
    echo.
    pause
    exit /b 1
)

REM Run Settings UI (not console)
start "" python\pythonw.exe app\settings_ui.py
