"""Yapper entry point — ``python -m app``.

© 2026 Cloudelipute

Phase 0 placeholder: prints version/banner. The PySide6 tray app
(``app.ui.app.main``) replaces this body in Phase 4.
"""

import sys

from app.core.constants import COPYRIGHT, VERSION


def main() -> int:
    """Run Yapper. Returns a process exit code."""
    print(f"Yapper {VERSION}")
    print(COPYRIGHT)
    print("The PySide6 app is wired up in Phase 4. Run the tests with: uv run pytest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
