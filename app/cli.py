"""Single-shot CLI dictation path (`python -m app --once`). No Qt loop.

© 2026 Cloudelipute
"""

from __future__ import annotations

import time

from core import Settings, get_logger, setup_logging
from ui.controller import Controller

logger = get_logger("cli")


def _build_controller(settings: Settings) -> Controller:
    return Controller(settings)


def run_once(settings: Settings, duration: float = 5.0) -> int:
    """Record for `duration` seconds, transcribe, and type once. Returns exit code."""
    if not settings.get("api_key"):
        logger.error("No API key set. Run `python -m app` to configure.")
        return 2
    controller = _build_controller(settings)
    controller.start_recording()
    time.sleep(duration)
    controller.stop_recording()
    controller._await_processing(timeout=60.0)
    return 0


def cli_main(argv: list[str] | None = None) -> int:
    import argparse
    setup_logging()
    parser = argparse.ArgumentParser(prog="yapper")
    parser.add_argument("--once", action="store_true",
                        help="Single-shot record+type, no tray")
    parser.add_argument("--seconds", type=float, default=5.0,
                        help="Recording window for --once")
    args = parser.parse_args(argv)
    settings = Settings().load()
    if args.once:
        return run_once(settings, duration=args.seconds)
    from ui.app import main as ui_main
    return ui_main()
