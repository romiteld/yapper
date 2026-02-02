#!/bin/bash
# Yapper - Cross-platform launcher script for macOS and Linux
# Copyright (c) 2026 Cloudelipute

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"

# Detect OS
OS="$(uname -s)"

# Find Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "Error: Python not found. Please install Python 3.8+"
    exit 1
fi

# Check Python version
PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Using Python $PY_VERSION"

# Install dependencies if needed
install_deps() {
    echo "Installing dependencies..."
    $PYTHON -m pip install --upgrade pip
    $PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt"
}

# Show help
show_help() {
    echo ""
    echo "╦ ╦┌─┐┌─┐┌─┐┌─┐┬─┐"
    echo "╚╦╝├─┤├─┘├─┘├┤ ├┬┘"
    echo " ╩ ┴ ┴┴  ┴  └─┘┴└─"
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  (none)      Run Yapper in tray mode (default)"
    echo "  console     Run Yapper in console mode"
    echo "  settings    Open settings UI"
    echo "  install     Install dependencies"
    echo "  help        Show this help"
    echo ""
    echo "Platform: $OS"
    echo ""
}

# Main
case "$1" in
    console)
        echo "Starting Yapper (console mode)..."
        if [ "$OS" = "Linux" ]; then
            if [ "$EUID" -ne 0 ]; then
                echo "Note: On Linux, global hotkeys require root privileges."
                echo "Running with sudo..."
                sudo -E $PYTHON "$APP_DIR/yapper.py"
            else
                $PYTHON "$APP_DIR/yapper.py"
            fi
        else
            $PYTHON "$APP_DIR/yapper.py"
        fi
        ;;
    settings)
        echo "Opening settings..."
        $PYTHON "$APP_DIR/settings_ui.py"
        ;;
    install)
        install_deps
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Starting Yapper (tray mode)..."
        if [ "$OS" = "Linux" ]; then
            if [ "$EUID" -ne 0 ]; then
                echo "Note: On Linux, global hotkeys require root privileges."
                echo "Running with sudo..."
                sudo -E $PYTHON "$APP_DIR/yapper_tray.py"
            else
                $PYTHON "$APP_DIR/yapper_tray.py"
            fi
        else
            $PYTHON "$APP_DIR/yapper_tray.py"
        fi
        ;;
esac
