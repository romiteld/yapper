@echo off
setlocal EnableDelayedExpansion

title Yapper Portable Builder

echo.
echo   ======================================
echo      YAPPER PORTABLE BUILDER
echo   ======================================
echo.
echo   This will create a fully portable
echo   distribution with embedded Python.
echo.
echo   Press any key to start...
pause >nul

:: Configuration
set PYTHON_VERSION=3.11.9
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip
set BUILD_DIR=%~dp0build
set DIST_DIR=%~dp0dist
set PYTHON_DIR=%BUILD_DIR%\python

:: Clean build directory
echo.
echo   [1/6] Preparing build directory...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"
mkdir "%PYTHON_DIR%"

:: Download Python
echo   [2/6] Downloading Python %PYTHON_VERSION%...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%BUILD_DIR%\python.zip'}"

if not exist "%BUILD_DIR%\python.zip" (
    echo   ERROR: Failed to download Python
    pause
    exit /b 1
)

:: Extract Python
echo   [3/6] Extracting Python...
powershell -Command "Expand-Archive -Path '%BUILD_DIR%\python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
del "%BUILD_DIR%\python.zip"

:: Enable pip support
echo   [4/6] Configuring Python and installing packages...

:: Modify python311._pth to enable site-packages
set PTH_FILE=%PYTHON_DIR%\python311._pth
if exist "%PTH_FILE%" (
    echo python311.zip> "%PTH_FILE%"
    echo .>> "%PTH_FILE%"
    echo Lib\site-packages>> "%PTH_FILE%"
    echo import site>> "%PTH_FILE%"
)

:: Download and run get-pip.py
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%BUILD_DIR%\get-pip.py'}"
"%PYTHON_DIR%\python.exe" "%BUILD_DIR%\get-pip.py" --no-warn-script-location
del "%BUILD_DIR%\get-pip.py"

:: Install packages
echo         Installing openai...
"%PYTHON_DIR%\python.exe" -m pip install openai -q --no-warn-script-location
echo         Installing keyboard...
"%PYTHON_DIR%\python.exe" -m pip install keyboard -q --no-warn-script-location
echo         Installing pyaudio...
"%PYTHON_DIR%\python.exe" -m pip install pyaudio -q --no-warn-script-location
echo         Installing pystray...
"%PYTHON_DIR%\python.exe" -m pip install pystray -q --no-warn-script-location
echo         Installing Pillow...
"%PYTHON_DIR%\python.exe" -m pip install Pillow -q --no-warn-script-location
echo         Installing customtkinter...
"%PYTHON_DIR%\python.exe" -m pip install customtkinter -q --no-warn-script-location

:: Copy application files
echo   [5/6] Copying application files...
xcopy "%~dp0app" "%BUILD_DIR%\app\" /E /I /Q /Y
if exist "%BUILD_DIR%\app\settings.json" del "%BUILD_DIR%\app\settings.json"
if exist "%BUILD_DIR%\app\__pycache__" rmdir /s /q "%BUILD_DIR%\app\__pycache__"
if exist "%BUILD_DIR%\app\core\__pycache__" rmdir /s /q "%BUILD_DIR%\app\core\__pycache__"

copy "%~dp0yapper.ico" "%BUILD_DIR%\" >nul 2>&1
copy "%~dp0yapper_icon.png" "%BUILD_DIR%\" >nul 2>&1
copy "%~dp0README.md" "%BUILD_DIR%\" >nul 2>&1
copy "%~dp0requirements.txt" "%BUILD_DIR%\" >nul 2>&1

mkdir "%BUILD_DIR%\logs" 2>nul
mkdir "%BUILD_DIR%\sounds" 2>nul

:: Create launcher scripts
echo   [6/6] Creating launcher scripts...

:: Yapper.bat
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" python\pythonw.exe app\yapper_tray.py
) > "%BUILD_DIR%\Yapper.bat"

:: Yapper Console.bat
(
echo @echo off
echo title Yapper - Console Mode
echo cd /d "%%~dp0"
echo python\python.exe app\yapper.py
echo pause
) > "%BUILD_DIR%\Yapper Console.bat"

:: Settings.bat
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" python\pythonw.exe app\settings_ui.py
) > "%BUILD_DIR%\Settings.bat"

:: First Run.bat
(
echo @echo off
echo title Yapper - First Time Setup
echo cd /d "%%~dp0"
echo.
echo echo.
echo echo   ========================================
echo echo        YAPPER - FIRST TIME SETUP
echo echo   ========================================
echo echo.
echo echo   Welcome to Yapper!
echo echo.
echo echo   You need an OpenAI API key to use Yapper.
echo echo   Get one at: https://platform.openai.com/api-keys
echo echo.
echo echo   Press any key to open Settings...
echo pause ^>nul
echo python\python.exe app\settings_console.py
echo echo.
echo echo   Setup complete! Run Yapper.bat to start.
echo echo.
echo pause
) > "%BUILD_DIR%\First Run.bat"

:: Create README
(
echo YAPPER - Speech to Text
echo =======================
echo.
echo QUICK START:
echo   1. Run "First Run.bat" to set up your API key
echo   2. Run "Yapper.bat" to start
echo.
echo USAGE:
echo   - Press F8 to start/stop recording, OR
echo   - Say "Yapper start" / "Yapper stop"
echo.
echo FILES:
echo   Yapper.bat          - Run in system tray ^(default^)
echo   Yapper Console.bat  - Run in console mode
echo   Settings.bat        - Change settings
echo   First Run.bat       - First-time setup
echo.
echo Get your API key at: https://platform.openai.com/api-keys
echo.
echo Copyright ^(c^) 2026 Cloudelipute
) > "%BUILD_DIR%\README.txt"

:: Create zip distribution
echo.
echo   Creating distribution package...
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
set ZIP_NAME=Yapper-Portable-Windows

:: Use PowerShell to create zip
powershell -Command "Compress-Archive -Path '%BUILD_DIR%\*' -DestinationPath '%DIST_DIR%\%ZIP_NAME%.zip' -Force"

:: Get file size
for %%A in ("%DIST_DIR%\%ZIP_NAME%.zip") do set SIZE=%%~zA
set /a SIZE_MB=%SIZE%/1048576

echo.
echo   ========================================
echo         BUILD COMPLETE!
echo   ========================================
echo.
echo   Output: %DIST_DIR%\%ZIP_NAME%.zip
echo   Size:   ~%SIZE_MB% MB
echo.
echo   To share:
echo     1. Upload to GitHub Releases, or
echo     2. Share the zip file directly
echo.
echo   Users just need to:
echo     1. Extract the zip anywhere
echo     2. Run "First Run.bat" to set API key
echo     3. Run "Yapper.bat" to start!
echo.

:: Ask if user wants to open dist folder
set /p OPEN_FOLDER="   Open output folder? (Y/N): "
if /i "%OPEN_FOLDER%"=="Y" explorer "%DIST_DIR%"

echo.
echo   Done!
echo.
pause
