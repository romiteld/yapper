"""Yapper PySide6 UI package.

© 2026 Cloudelipute
"""

__all__ = ["YapperApp", "main"]


def __getattr__(name):  # PEP 562 lazy attribute access
    if name in ("YapperApp", "main"):
        from .app import YapperApp, main
        return {"YapperApp": YapperApp, "main": main}[name]
    raise AttributeError(name)
