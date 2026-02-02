#!/usr/bin/env python3
"""
Yapper Portable Builder
=======================
Creates a fully portable Windows distribution with embedded Python.

Usage:
    python build_portable.py

This script will:
1. Download Python 3.11 embeddable for Windows
2. Install pip and all dependencies
3. Create a ready-to-distribute portable package

Copyright (c) 2026 Cloudelipute
"""

import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.11.9"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Directories
SCRIPT_DIR = Path(__file__).parent.resolve()
BUILD_DIR = SCRIPT_DIR / "build"
DIST_DIR = SCRIPT_DIR / "dist"
PYTHON_DIR = BUILD_DIR / "python"

# Required packages
PACKAGES = [
    "openai",
    "keyboard",
    "pyaudio",
    "pystray",
    "Pillow",
    "customtkinter",
    "pyautogui",
    "pyperclip",
]


def print_header():
    print()
    print("╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐  Builder")
    print("╚╦╝├─┤├─┘├─┘├┤ ├┬┘")
    print(" ╩ ┴ ┴┴  ┴  └─┘┴└─")
    print()
    print("Building portable Windows distribution...")
    print("=" * 50)
    print()


def download_file(url: str, dest: Path, desc: str):
    """Download a file with progress."""
    print(f"Downloading {desc}...")

    def progress_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, downloaded * 100 // total_size)
            bar = "█" * (percent // 2) + "░" * (50 - percent // 2)
            print(f"\r  [{bar}] {percent}%", end="", flush=True)

    urllib.request.urlretrieve(url, dest, progress_hook)
    print()


def setup_python():
    """Download and setup embedded Python."""
    print("Step 1: Setting up embedded Python")
    print("-" * 40)

    # Clean and create build directory
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    PYTHON_DIR.mkdir()

    # Download Python embeddable
    python_zip = BUILD_DIR / "python.zip"
    download_file(PYTHON_URL, python_zip, f"Python {PYTHON_VERSION}")

    # Extract
    print("  Extracting Python...")
    with zipfile.ZipFile(python_zip, 'r') as zf:
        zf.extractall(PYTHON_DIR)
    python_zip.unlink()

    # Enable pip by modifying python311._pth
    pth_file = PYTHON_DIR / f"python{PYTHON_VERSION.replace('.', '')[:2]}._pth"
    if not pth_file.exists():
        pth_file = PYTHON_DIR / "python311._pth"

    if pth_file.exists():
        print("  Enabling pip support...")
        content = pth_file.read_text()
        # Uncomment import site
        content = content.replace("#import site", "import site")
        # Add Lib\site-packages
        if "Lib\\site-packages" not in content:
            content += "\nLib\\site-packages\n"
        pth_file.write_text(content)

    print("  Python setup complete!")
    print()


def install_pip():
    """Install pip into embedded Python."""
    print("Step 2: Installing pip")
    print("-" * 40)

    python_exe = PYTHON_DIR / "python.exe"
    get_pip = BUILD_DIR / "get-pip.py"

    # Download get-pip.py
    download_file(GET_PIP_URL, get_pip, "get-pip.py")

    # Install pip
    print("  Installing pip...")
    result = subprocess.run(
        [str(python_exe), str(get_pip), "--no-warn-script-location"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  Error: {result.stderr}")
        sys.exit(1)

    get_pip.unlink()
    print("  Pip installed!")
    print()


def install_packages():
    """Install required packages."""
    print("Step 3: Installing packages")
    print("-" * 40)

    python_exe = PYTHON_DIR / "python.exe"

    for package in PACKAGES:
        print(f"  Installing {package}...")
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", package,
             "--no-warn-script-location", "-q"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"    Warning: {result.stderr.strip()}")

    print("  All packages installed!")
    print()


def copy_app_files():
    """Copy application files to build directory."""
    print("Step 4: Copying application files")
    print("-" * 40)

    # Copy app folder
    app_src = SCRIPT_DIR / "app"
    app_dst = BUILD_DIR / "app"

    print("  Copying app/...")
    shutil.copytree(app_src, app_dst, ignore=shutil.ignore_patterns(
        '__pycache__', '*.pyc', 'settings.json'
    ))

    # Copy other files
    files_to_copy = [
        "yapper.ico",
        "yapper_icon.png",
        "README.md",
        "requirements.txt",
    ]

    for filename in files_to_copy:
        src = SCRIPT_DIR / filename
        if src.exists():
            print(f"  Copying {filename}...")
            shutil.copy(src, BUILD_DIR / filename)

    # Create logs and sounds directories
    (BUILD_DIR / "logs").mkdir(exist_ok=True)
    (BUILD_DIR / "sounds").mkdir(exist_ok=True)

    print("  Files copied!")
    print()


def create_batch_files():
    """Create Windows batch launcher files."""
    print("Step 5: Creating launcher scripts")
    print("-" * 40)

    # Yapper.bat - Main launcher (tray mode)
    yapper_bat = BUILD_DIR / "Yapper.bat"
    yapper_bat.write_text('''@echo off
title Yapper - Speech to Text
cd /d "%~dp0"
start "" pythonw.exe app\\yapper_tray.py
''')
    print("  Created Yapper.bat")

    # Yapper Console.bat - Console mode
    console_bat = BUILD_DIR / "Yapper Console.bat"
    console_bat.write_text('''@echo off
title Yapper Console Mode
cd /d "%~dp0"
python\\python.exe app\\yapper.py
pause
''')
    print("  Created Yapper Console.bat")

    # Settings.bat
    settings_bat = BUILD_DIR / "Settings.bat"
    settings_bat.write_text('''@echo off
title Yapper Settings
cd /d "%~dp0"
python\\python.exe app\\settings_ui.py
''')
    print("  Created Settings.bat")

    # Settings Console.bat (fallback)
    settings_console_bat = BUILD_DIR / "Settings Console.bat"
    settings_console_bat.write_text('''@echo off
title Yapper Settings
cd /d "%~dp0"
python\\python.exe app\\settings_console.py
pause
''')
    print("  Created Settings Console.bat")

    # First Run.bat - For first-time setup
    first_run_bat = BUILD_DIR / "First Run.bat"
    first_run_bat.write_text('''@echo off
title Yapper - First Time Setup
cd /d "%~dp0"
echo.
echo   ==============================
echo      YAPPER FIRST TIME SETUP
echo   ==============================
echo.
echo   Welcome to Yapper!
echo.
echo   You need to set up your OpenAI API key.
echo   Get one at: https://platform.openai.com/api-keys
echo.
echo   Opening Settings...
echo.
python\\python.exe app\\settings_console.py
echo.
echo   Setup complete! You can now run Yapper.bat
echo.
pause
''')
    print("  Created First Run.bat")

    print("  Launchers created!")
    print()


def create_distribution():
    """Create the final distribution zip."""
    print("Step 6: Creating distribution package")
    print("-" * 40)

    # Create dist directory
    DIST_DIR.mkdir(exist_ok=True)

    # Create zip file
    zip_name = f"Yapper-Portable-v3.1.0-Windows"
    zip_path = DIST_DIR / f"{zip_name}.zip"

    print(f"  Creating {zip_name}.zip...")

    # Remove old zip if exists
    if zip_path.exists():
        zip_path.unlink()

    # Create zip
    shutil.make_archive(
        str(DIST_DIR / zip_name),
        'zip',
        BUILD_DIR
    )

    # Get size
    size_mb = zip_path.stat().st_size / (1024 * 1024)

    print(f"  Created: {zip_path}")
    print(f"  Size: {size_mb:.1f} MB")
    print()


def main():
    print_header()

    # Check we're not on Windows (can't run embedded Python)
    # But we can still download and package it

    try:
        setup_python()
        install_pip()
        install_packages()
        copy_app_files()
        create_batch_files()
        create_distribution()

        print("=" * 50)
        print("BUILD COMPLETE!")
        print("=" * 50)
        print()
        print(f"Distribution created at:")
        print(f"  {DIST_DIR / 'Yapper-Portable-v3.1.0-Windows.zip'}")
        print()
        print("To share:")
        print("  1. Upload the zip file to GitHub Releases")
        print("  2. Or share directly with users")
        print()
        print("Users just need to:")
        print("  1. Extract the zip")
        print("  2. Run 'First Run.bat' to set up API key")
        print("  3. Run 'Yapper.bat' to start")
        print()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
