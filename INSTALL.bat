@echo off
setlocal enabledelayedexpansion

REM ============================================
REM   YAPPER FIRST-TIME SETUP
REM   Copyright (c) 2026 Cloudelipute
REM ============================================

title Yapper - First Time Setup

cd /d "%~dp0"

echo.
echo   ╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐
echo   ╚╦╝├─┤├─┘├─┘├┤ ├┬┘
echo    ╩ ┴ ┴┴  ┴  └─┘┴└─
echo.
echo   ========================================
echo      FIRST-TIME SETUP (One Time Only)
echo   ========================================
echo   Copyright (c) 2026 Cloudelipute
echo.
echo   This will:
echo     1. Install required components
echo     2. Create desktop shortcut
echo     3. Configure your API key
echo.
echo   Please wait, this takes 2-3 minutes...
echo.
pause

REM Check if already installed
if exist "python\Lib\site-packages\pystray" (
    echo.
    echo   Already installed! Opening settings...
    goto :open_settings
)

cls
echo.
echo   ╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐
echo   ╚╦╝├─┤├─┘├─┘├┤ ├┬┘
echo    ╩ ┴ ┴┴  ┴  └─┘┴└─
echo.
echo   Installing components... Please wait.
echo.

echo   [1/6] Setting up pip...
python\python.exe python\get-pip.py --no-warn-script-location -q 2>nul
echo         Done.

echo   [2/6] Installing OpenAI...
python\python.exe -m pip install openai -q --no-warn-script-location 2>nul
echo         Done.

echo   [3/6] Installing keyboard...
python\python.exe -m pip install keyboard -q --no-warn-script-location 2>nul
echo         Done.

echo   [4/6] Installing system tray...
python\python.exe -m pip install pystray -q --no-warn-script-location 2>nul
echo         Done.

echo   [5/6] Installing image support...
python\python.exe -m pip install Pillow -q --no-warn-script-location 2>nul
echo         Done.

echo   [6/6] Installing audio...
python\python.exe -m pip install pyaudio -q --no-warn-script-location 2>nul
echo         Done.

echo.
echo   All components installed!
echo.

REM Create desktop shortcut
echo   Creating desktop shortcut...

set SCRIPT_DIR=%~dp0
set ICON_PATH=%SCRIPT_DIR%yapper.ico

REM Create Yapper shortcut
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Yapper.lnk
set TARGET_PATH=%SCRIPT_DIR%Yapper.bat

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcut.vbs"
echo sLinkFile = "%SHORTCUT_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\CreateShortcut.vbs"
echo oLink.TargetPath = "%TARGET_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.IconLocation = "%ICON_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Description = "Yapper - Speech to Text by Cloudelipute" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WindowStyle = 7 >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"
cscript //nologo "%TEMP%\CreateShortcut.vbs" 2>nul
del "%TEMP%\CreateShortcut.vbs" 2>nul
echo   - Yapper shortcut created on Desktop

echo.

:open_settings
echo   ========================================
echo   Now let's configure your API key...
echo   ========================================
echo.

REM Run console settings
python\python.exe app\settings_console.py

echo.
echo   ========================================
echo   SETUP COMPLETE!
echo   ========================================
echo.
echo   Yapper will now run in your system tray!
echo.
echo   Look for the Yapper icon near your clock.
echo   Right-click it for options.
echo.
echo   Press F8 to start/stop recording.
echo.

REM Launch Yapper
echo   Starting Yapper...
start "" /B python\pythonw.exe app\yapper_tray.py

echo.
echo   Yapper is now running in your system tray!
echo   You can close this window.
echo.
pause
