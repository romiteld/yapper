"""Yapper transcription engines.

© 2026 Cloudelipute
"""

from ..logger import get_logger
from .base import TranscriptionEngine
from .cloud import CloudEngine
from .local import LocalEngine, LocalEngineUnavailable

logger = get_logger("engines")

__all__ = [
    "TranscriptionEngine",
    "CloudEngine",
    "LocalEngine",
    "LocalEngineUnavailable",
    "get_engine",
]


def get_engine(settings) -> TranscriptionEngine:
    """Build the engine selected by settings.

    Args:
        settings: a core.config.Settings instance.

    Returns:
        A configured TranscriptionEngine (CloudEngine or LocalEngine).
    """
    engine = settings.get("engine")
    if engine == "local":
        model = settings.get("local_stt_model")
        logger.info(f"Using LocalEngine (model={model})")
        return LocalEngine(model=model)

    # Default: cloud.
    from ..api import APIClient
    api = APIClient(api_key=settings.get("api_key"))
    model = settings.get("cloud_stt_model")
    logger.info(f"Using CloudEngine (model={model})")
    return CloudEngine(api_client=api, model=model)
