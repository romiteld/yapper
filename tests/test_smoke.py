"""Smoke tests: the package imports and reports the v4 version.

© 2026 Cloudelipute
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_version_is_4():
    from app.core.constants import VERSION

    assert VERSION == "4.0.0"
