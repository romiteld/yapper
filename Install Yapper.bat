@echo off
title Yapper Installer
cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Python not found. Downloading portable Python...
    echo.

    :: Download Python embeddable
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python_temp.zip'}"

    :: Extract to temp location
    powershell -Command "Expand-Archive -Path 'python_temp.zip' -DestinationPath 'python_installer' -Force"
    del python_temp.zip

    :: Configure for pip
    echo python311.zip> python_installer\python311._pth
    echo .>> python_installer\python311._pth
    echo Lib\site-packages>> python_installer\python311._pth
    echo import site>> python_installer\python311._pth

    :: Install pip
    powershell -Command "& {Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'}"
    python_installer\python.exe get-pip.py --no-warn-script-location >nul 2>&1
    del get-pip.py

    :: Install customtkinter and pillow for the installer UI
    python_installer\python.exe -m pip install customtkinter Pillow -q --no-warn-script-location

    :: Run installer with embedded Python
    python_installer\pythonw.exe installer\installer.py

    :: Cleanup
    rmdir /s /q python_installer
) else (
    :: Python available, check for dependencies
    python -c "import customtkinter" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing UI dependencies...
        pip install customtkinter Pillow -q
    )

    :: Run installer
    pythonw installer\installer.py
)
