"""Utilities for configuring application logging."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

_LOGGER_NAME = "recipe_converter"


def _configure_base_logger() -> logging.Logger:
    """Configure (once) the base logger used across the application."""

    base_logger = logging.getLogger(_LOGGER_NAME)
    if base_logger.handlers:
        return base_logger

    base_logger.setLevel(logging.INFO)
    base_logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    base_logger.addHandler(stream_handler)

    os.makedirs("logs", exist_ok=True)
    log_filename = (
        f"logs/recipe_converter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(formatter)
    base_logger.addHandler(file_handler)

    base_logger.debug("Logger configured with stream and file handlers")
    return base_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger that shares the base handler configuration."""

    base_logger = _configure_base_logger()
    if not name or name == _LOGGER_NAME:
        return base_logger

    return base_logger.getChild(name)


__all__ = ["get_logger"]
