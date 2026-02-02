@echo off
setlocal

REM ============================================
REM   YAPPER SETTINGS
REM   Copyright (c) 2026 Cloudelipute
REM ============================================

title Yapper Settings

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

REM Run Settings
python\python.exe app\settings_console.py
