"""Utility helpers shared between services."""
from __future__ import annotations

import re

from .logging_config import get_logger
from .prompts import TECHNICAL_TITLE_PATTERN

logger = get_logger(__name__)


def strip_markdown_fences(text: str) -> str:
    """Remove optional markdown code fences from the response text."""
    text = re.sub(r'^```(?:markdown)?\n', "", text)
    text = re.sub(r'\n```$', "", text)
    return text.strip()


def extract_technical_title(recipe_text: str, default: str = "untitled-recipe") -> str:
    """Extract the technical title from a recipe frontmatter block."""
    match = TECHNICAL_TITLE_PATTERN.search(recipe_text)
    if match:
        technical_title = match.group(1)
        logger.info("Extracted technical title: %s", technical_title)
        return technical_title

    logger.warning("Could not extract technical title, using default: %s", default)
    return default


__all__ = ["extract_technical_title", "strip_markdown_fences"]
