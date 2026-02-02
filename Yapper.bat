@echo off
setlocal

REM ============================================
REM   YAPPER - System Tray Speech to Text
REM   Copyright (c) 2026 Cloudelipute
REM ============================================

cd /d "%~dp0"

REM Check if first-time setup is needed
if not exist "python\Lib\site-packages\openai" (
    echo.
    echo   First-time setup required!
    echo   Running INSTALL.bat...
    echo.
    call INSTALL.bat
    exit /b
)

REM Run Yapper system tray app (no console window)
start "" /B python\pythonw.exe app\yapper_tray.py
