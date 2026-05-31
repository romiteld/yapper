"""Yapper UI theme — dark QSS + Cloudelipute pink accent.

© 2026 Cloudelipute
"""

ACCENT = "#ec2a8e"
ACCENT_DIM = "#b81f6f"
BG = "#16131a"
BG_RAISED = "#211c29"
BG_INPUT = "#2c2533"
FG = "#f2eef6"
FG_MUTED = "#9b90a8"
BORDER = "#3a3142"

# Recording state -> indicator color (tray icon dot + HUD pill glow).
STATE_COLORS = {
    "idle": "#6b6275",
    "listening": ACCENT,
    "transcribing": "#f4b740",
    "done": "#3ddc84",
}


def qss() -> str:
    """Return the shared dark stylesheet for all Yapper windows."""
    return f"""
    QWidget {{
        background-color: {BG};
        color: {FG};
        font-family: "Segoe UI", -apple-system, "Helvetica Neue", sans-serif;
        font-size: 13px;
    }}
    QFrame#Sidebar {{
        background-color: {BG_RAISED};
        border-right: 1px solid {BORDER};
    }}
    QLabel#Title {{ font-size: 20px; font-weight: 600; }}
    QLabel#Muted {{ color: {FG_MUTED}; }}
    QPushButton {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 7px 14px;
    }}
    QPushButton:hover {{ border-color: {ACCENT}; }}
    QPushButton#Primary {{
        background-color: {ACCENT};
        border: none;
        color: white;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background-color: {ACCENT_DIM}; }}
    QPushButton#NavItem {{
        text-align: left;
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 9px 12px;
    }}
    QPushButton#NavItem:checked {{
        background-color: {ACCENT};
        color: white;
    }}
    QLineEdit, QComboBox, QPlainTextEdit, QSpinBox, QListWidget {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px 9px;
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border-color: {ACCENT};
    }}
    QCheckBox::indicator:checked {{ background-color: {ACCENT}; }}
    """
