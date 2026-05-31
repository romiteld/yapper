"""`python -m app` entry point.

© 2026 Cloudelipute
"""

import sys
from pathlib import Path

# Ensure `app/` (this dir) is importable as the source root for bare imports.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from cli import cli_main  # noqa: E402


def main() -> int:
    """Entry point for `python -m app` and the `yapper` script."""
    return cli_main()


if __name__ == "__main__":
    sys.exit(cli_main())
