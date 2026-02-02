#!/usr/bin/env python3
"""
Yapper Professional Installer
=============================
Modern GUI installer for Yapper Speech-to-Text

Copyright (c) 2026 Cloudelipute
"""

import os
import sys
import threading
import urllib.request
import zipfile
import subprocess
import shutil
from pathlib import Path

# Check for customtkinter, install if needed
try:
    import customtkinter as ctk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "-q"])
    import customtkinter as ctk

try:
    from PIL import Image, ImageDraw
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
    from PIL import Image, ImageDraw


# Configuration
PYTHON_VERSION = "3.11.9"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

PACKAGES = [
    ("openai", "OpenAI API Client"),
    ("keyboard", "Keyboard Hotkeys"),
    ("pyaudio", "Audio Recording"),
    ("pystray", "System Tray"),
    ("Pillow", "Image Processing"),
    ("customtkinter", "Modern UI"),
]

# Colors
BG_DARK = "#0a0a0f"
BG_CARD = "#12121a"
BG_CARD_HOVER = "#1a1a24"
ACCENT = "#6366f1"
ACCENT_HOVER = "#818cf8"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#a1a1aa"
SUCCESS = "#22c55e"
ERROR = "#ef4444"


class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window setup
        self.title("Yapper Installer")
        self.geometry("600x700")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)

        # Set appearance
        ctk.set_appearance_mode("dark")

        # Get script directory
        self.script_dir = Path(__file__).parent.parent.resolve()
        self.build_dir = self.script_dir / "build"
        self.dist_dir = self.script_dir / "dist"

        # State
        self.is_installing = False
        self.install_complete = False

        # Build UI
        self._create_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (300)
        y = (self.winfo_screenheight() // 2) - (350)
        self.geometry(f"600x700+{x}+{y}")

    def _create_ui(self):
        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=40, pady=30)

        # Logo/Icon area
        self._create_logo()

        # Title
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="Yapper",
            font=ctk.CTkFont(family="Segoe UI", size=42, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.title_label.pack(pady=(20, 5))

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.main_frame,
            text="Speech-to-Text • Powered by AI",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=TEXT_SECONDARY
        )
        self.subtitle_label.pack(pady=(0, 30))

        # Progress card
        self.progress_card = ctk.CTkFrame(
            self.main_frame,
            fg_color=BG_CARD,
            corner_radius=16
        )
        self.progress_card.pack(fill="x", pady=(0, 20))

        # Status label
        self.status_label = ctk.CTkLabel(
            self.progress_card,
            text="Ready to install",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.status_label.pack(pady=(25, 10), padx=25, anchor="w")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_card,
            width=480,
            height=8,
            corner_radius=4,
            fg_color="#27272a",
            progress_color=ACCENT
        )
        self.progress_bar.pack(pady=(0, 10), padx=25)
        self.progress_bar.set(0)

        # Detail label
        self.detail_label = ctk.CTkLabel(
            self.progress_card,
            text="Click Install to begin",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY
        )
        self.detail_label.pack(pady=(0, 25), padx=25, anchor="w")

        # Log area (collapsible)
        self.log_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=BG_CARD,
            corner_radius=16
        )
        self.log_frame.pack(fill="both", expand=True, pady=(0, 20))

        self.log_header = ctk.CTkLabel(
            self.log_frame,
            text="Installation Log",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        self.log_header.pack(pady=(15, 10), padx=20, anchor="w")

        self.log_text = ctk.CTkTextbox(
            self.log_frame,
            width=480,
            height=180,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#09090b",
            text_color=TEXT_SECONDARY,
            corner_radius=8,
            state="disabled"
        )
        self.log_text.pack(pady=(0, 15), padx=20)

        # Buttons frame
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(fill="x")

        # Install button
        self.install_btn = ctk.CTkButton(
            self.button_frame,
            text="Install",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            height=50,
            corner_radius=12,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._start_install
        )
        self.install_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))

        # Cancel/Close button
        self.cancel_btn = ctk.CTkButton(
            self.button_frame,
            text="Cancel",
            font=ctk.CTkFont(family="Segoe UI", size=16),
            height=50,
            corner_radius=12,
            fg_color="#27272a",
            hover_color="#3f3f46",
            text_color=TEXT_SECONDARY,
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="right", expand=True, fill="x", padx=(10, 0))

        # Version label
        self.version_label = ctk.CTkLabel(
            self.main_frame,
            text="Version 3.1.0 • © 2026 Cloudelipute",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#52525b"
        )
        self.version_label.pack(pady=(15, 0))

    def _create_logo(self):
        # Create a simple gradient logo
        logo_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        logo_frame.pack(pady=(10, 0))

        # Try to load icon, or create a placeholder
        icon_path = self.script_dir / "yapper.ico"
        if icon_path.exists():
            try:
                img = Image.open(str(icon_path))
                img = img.resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_image = ctk.CTkImage(img, size=(80, 80))
                logo_label = ctk.CTkLabel(logo_frame, image=self.logo_image, text="")
                logo_label.pack()
                return
            except Exception:
                pass

        # Fallback: create a nice gradient circle
        size = 80
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw gradient circle
        for i in range(size // 2, 0, -1):
            alpha = int(255 * (i / (size // 2)))
            color = (99, 102, 241, alpha)  # Indigo with gradient
            draw.ellipse([size//2-i, size//2-i, size//2+i, size//2+i], fill=color)

        # Add "Y" text
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = None
        draw.text((size//2, size//2), "Y", fill="white", anchor="mm", font=font)

        self.logo_image = ctk.CTkImage(img, size=(80, 80))
        logo_label = ctk.CTkLabel(logo_frame, image=self.logo_image, text="")
        logo_label.pack()

    def _log(self, message: str, level: str = "info"):
        self.log_text.configure(state="normal")

        if level == "success":
            prefix = "✓ "
        elif level == "error":
            prefix = "✗ "
        elif level == "warning":
            prefix = "! "
        else:
            prefix = "→ "

        self.log_text.insert("end", f"{prefix}{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update_idletasks()

    def _update_status(self, status: str, detail: str = ""):
        self.status_label.configure(text=status)
        if detail:
            self.detail_label.configure(text=detail)
        self.update_idletasks()

    def _update_progress(self, value: float):
        self.progress_bar.set(value)
        self.update_idletasks()

    def _start_install(self):
        if self.is_installing:
            return

        if self.install_complete:
            # Open dist folder
            if sys.platform == "win32":
                os.startfile(str(self.dist_dir))
            return

        self.is_installing = True
        self.install_btn.configure(state="disabled", text="Installing...")

        # Run installation in background thread
        thread = threading.Thread(target=self._run_install, daemon=True)
        thread.start()

    def _run_install(self):
        try:
            self._do_install()
            self.after(0, self._on_install_complete)
        except Exception as e:
            self.after(0, lambda: self._on_install_error(str(e)))

    def _do_install(self):
        total_steps = 6

        # Step 1: Prepare directories
        self.after(0, lambda: self._update_status("Preparing...", "Setting up directories"))
        self.after(0, lambda: self._update_progress(0.05))
        self.after(0, lambda: self._log("Preparing build directory"))

        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)
        python_dir = self.build_dir / "python"
        python_dir.mkdir()

        self.after(0, lambda: self._log("Build directory ready", "success"))
        self.after(0, lambda: self._update_progress(1/total_steps))

        # Step 2: Download Python
        self.after(0, lambda: self._update_status("Downloading Python", f"Python {PYTHON_VERSION} embeddable"))
        self.after(0, lambda: self._log(f"Downloading Python {PYTHON_VERSION}..."))

        python_zip = self.build_dir / "python.zip"
        self._download_file(PYTHON_URL, python_zip, 2/total_steps)

        self.after(0, lambda: self._log("Python downloaded", "success"))

        # Step 3: Extract Python
        self.after(0, lambda: self._update_status("Extracting Python", "Unpacking files..."))
        self.after(0, lambda: self._log("Extracting Python..."))

        with zipfile.ZipFile(python_zip, 'r') as zf:
            zf.extractall(python_dir)
        python_zip.unlink()

        # Configure Python for pip
        pth_file = python_dir / "python311._pth"
        if pth_file.exists():
            pth_file.write_text("python311.zip\n.\nLib\\site-packages\nimport site\n")

        self.after(0, lambda: self._log("Python extracted", "success"))
        self.after(0, lambda: self._update_progress(3/total_steps))

        # Step 4: Install pip
        self.after(0, lambda: self._update_status("Installing pip", "Package manager setup"))
        self.after(0, lambda: self._log("Installing pip..."))

        get_pip = self.build_dir / "get-pip.py"
        urllib.request.urlretrieve(GET_PIP_URL, get_pip)

        python_exe = python_dir / "python.exe"
        subprocess.run(
            [str(python_exe), str(get_pip), "--no-warn-script-location"],
            capture_output=True
        )
        get_pip.unlink()

        self.after(0, lambda: self._log("Pip installed", "success"))
        self.after(0, lambda: self._update_progress(3.5/total_steps))

        # Step 5: Install packages
        self.after(0, lambda: self._update_status("Installing packages", "This may take a few minutes"))

        for i, (package, name) in enumerate(PACKAGES):
            self.after(0, lambda n=name: self._log(f"Installing {n}..."))
            self.after(0, lambda n=name: self._update_status("Installing packages", n))

            subprocess.run(
                [str(python_exe), "-m", "pip", "install", package, "-q", "--no-warn-script-location"],
                capture_output=True
            )

            progress = (4 + (i + 1) / len(PACKAGES)) / total_steps
            self.after(0, lambda p=progress: self._update_progress(p))
            self.after(0, lambda n=name: self._log(f"{n} installed", "success"))

        # Step 6: Copy app files
        self.after(0, lambda: self._update_status("Finalizing", "Copying application files"))
        self.after(0, lambda: self._log("Copying application files..."))

        # Copy app
        app_src = self.script_dir / "app"
        app_dst = self.build_dir / "app"
        shutil.copytree(app_src, app_dst, ignore=shutil.ignore_patterns(
            '__pycache__', '*.pyc', 'settings.json'
        ))

        # Copy assets
        for filename in ["yapper.ico", "yapper_icon.png", "README.md"]:
            src = self.script_dir / filename
            if src.exists():
                shutil.copy(src, self.build_dir / filename)

        # Create directories
        (self.build_dir / "logs").mkdir(exist_ok=True)
        (self.build_dir / "sounds").mkdir(exist_ok=True)

        # Create launcher scripts
        self._create_launchers()

        self.after(0, lambda: self._log("Application files copied", "success"))
        self.after(0, lambda: self._update_progress(5.5/total_steps))

        # Create distribution
        self.after(0, lambda: self._update_status("Creating package", "Building distribution..."))
        self.after(0, lambda: self._log("Creating distribution package..."))

        self.dist_dir.mkdir(exist_ok=True)
        zip_path = self.dist_dir / "Yapper-Portable-Windows"

        if (self.dist_dir / "Yapper-Portable-Windows.zip").exists():
            (self.dist_dir / "Yapper-Portable-Windows.zip").unlink()

        shutil.make_archive(str(zip_path), 'zip', self.build_dir)

        size_mb = (self.dist_dir / "Yapper-Portable-Windows.zip").stat().st_size / (1024 * 1024)
        self.after(0, lambda: self._log(f"Package created ({size_mb:.1f} MB)", "success"))
        self.after(0, lambda: self._update_progress(1.0))

    def _download_file(self, url: str, dest: Path, target_progress: float):
        start_progress = self.progress_bar.get()

        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                fraction = downloaded / total_size
                current = start_progress + (target_progress - start_progress) * fraction
                self.after(0, lambda p=current: self._update_progress(p))

        urllib.request.urlretrieve(url, dest, progress_hook)

    def _create_launchers(self):
        # Yapper.bat
        (self.build_dir / "Yapper.bat").write_text(
            '@echo off\ncd /d "%~dp0"\nstart "" python\\pythonw.exe app\\yapper_tray.py\n'
        )

        # Yapper Console.bat
        (self.build_dir / "Yapper Console.bat").write_text(
            '@echo off\ntitle Yapper\ncd /d "%~dp0"\npython\\python.exe app\\yapper.py\npause\n'
        )

        # Settings.bat
        (self.build_dir / "Settings.bat").write_text(
            '@echo off\ncd /d "%~dp0"\nstart "" python\\pythonw.exe app\\settings_ui.py\n'
        )

        # First Run.bat
        (self.build_dir / "First Run.bat").write_text('''@echo off
title Yapper Setup
cd /d "%~dp0"
echo.
echo   Welcome to Yapper!
echo.
echo   You need an OpenAI API key to continue.
echo   Get one at: https://platform.openai.com/api-keys
echo.
python\\python.exe app\\settings_console.py
pause
''')

    def _on_install_complete(self):
        self.is_installing = False
        self.install_complete = True

        self._update_status("Installation Complete!", "Yapper is ready to use")
        self.status_label.configure(text_color=SUCCESS)
        self._log("=" * 40)
        self._log("Installation completed successfully!", "success")
        self._log(f"Output: {self.dist_dir / 'Yapper-Portable-Windows.zip'}")

        self.install_btn.configure(
            state="normal",
            text="Open Folder",
            fg_color=SUCCESS,
            hover_color="#16a34a"
        )
        self.cancel_btn.configure(text="Close")

    def _on_install_error(self, error: str):
        self.is_installing = False

        self._update_status("Installation Failed", error[:50])
        self.status_label.configure(text_color=ERROR)
        self._log(f"Error: {error}", "error")

        self.install_btn.configure(state="normal", text="Retry")
        self.cancel_btn.configure(text="Close")

    def _on_cancel(self):
        if self.is_installing:
            if not self.install_complete:
                return  # Don't allow cancel during install
        self.destroy()


def main():
    app = InstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
