#!/bin/bash
# Yapper - Installation script for macOS and Linux
# Copyright (c) 2026 Cloudelipute

echo ""
echo "╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐"
echo "╚╦╝├─┤├─┘├─┘├┤ ├┬┘"
echo " ╩ ┴ ┴┴  ┴  └─┘┴└─"
echo ""
echo "Yapper Installation Script"
echo "=========================="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect OS
OS="$(uname -s)"
echo "Detected OS: $OS"

# Find Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "Error: Python not found!"
    echo ""
    if [ "$OS" = "Darwin" ]; then
        echo "Install Python using Homebrew:"
        echo "  brew install python"
    else
        echo "Install Python using your package manager:"
        echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
        echo "  Fedora: sudo dnf install python3 python3-pip"
    fi
    exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PY_VERSION"
echo ""

# Install system dependencies based on OS
echo "Installing system dependencies..."
echo ""

if [ "$OS" = "Darwin" ]; then
    # macOS
    if command -v brew &> /dev/null; then
        echo "Installing PortAudio (for PyAudio)..."
        brew install portaudio
    else
        echo "Warning: Homebrew not found. Please install PortAudio manually."
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "  brew install portaudio"
    fi
elif [ "$OS" = "Linux" ]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        echo "Installing system packages (Ubuntu/Debian)..."
        sudo apt-get update
        sudo apt-get install -y python3-pyaudio portaudio19-dev python3-gi gir1.2-appindicator3-0.1
    elif command -v dnf &> /dev/null; then
        echo "Installing system packages (Fedora)..."
        sudo dnf install -y python3-pyaudio portaudio-devel
    elif command -v pacman &> /dev/null; then
        echo "Installing system packages (Arch)..."
        sudo pacman -S --noconfirm python-pyaudio portaudio
    else
        echo "Warning: Unknown package manager. Please install manually:"
        echo "  - portaudio (development files)"
        echo "  - python3-gi and AppIndicator (for system tray)"
    fi
fi

echo ""
echo "Installing Python dependencies..."
$PYTHON -m pip install --upgrade pip
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Installation complete!"
echo ""
echo "To run Yapper:"
echo "  ./run.sh          - Start in tray mode (default)"
echo "  ./run.sh console  - Start in console mode"
echo "  ./run.sh settings - Open settings"
echo ""

# Make scripts executable
chmod +x "$SCRIPT_DIR/run.sh"
chmod +x "$SCRIPT_DIR/install.sh"

echo "Note: On Linux, you may need to run with sudo for global hotkeys."
echo ""
