@echo off
setlocal

REM ============================================
REM   CREATE YAPPER DESKTOP SHORTCUTS
REM   Copyright (c) 2026 Cloudelipute
REM ============================================

cd /d "%~dp0"

set SCRIPT_DIR=%~dp0
set ICON_PATH=%SCRIPT_DIR%yapper.ico

echo.
echo   Creating desktop shortcuts...
echo.

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
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"
cscript //nologo "%TEMP%\CreateShortcut.vbs"
del "%TEMP%\CreateShortcut.vbs"
echo   ✓ Created Yapper shortcut

REM Create Settings shortcut
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Yapper Settings.lnk
set TARGET_PATH=%SCRIPT_DIR%Settings.bat

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcut.vbs"
echo sLinkFile = "%SHORTCUT_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\CreateShortcut.vbs"
echo oLink.TargetPath = "%TARGET_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.IconLocation = "%ICON_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Description = "Yapper Settings - Cloudelipute" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"
cscript //nologo "%TEMP%\CreateShortcut.vbs"
del "%TEMP%\CreateShortcut.vbs"
echo   ✓ Created Yapper Settings shortcut

echo.
echo   Done! Check your desktop.
echo.
pause
