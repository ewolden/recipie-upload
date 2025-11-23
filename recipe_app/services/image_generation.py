"""Utilities for generating and compressing recipe illustration images."""
from __future__ import annotations

import io
import re
import time

import requests
from PIL import Image

from ..config import get_openai_image_client, get_openai_model
from ..logging_config import get_logger
from ..prompts import IMAGE_PROMPT_TEMPLATE

logger = get_logger(__name__)


def generate_recipe_image(recipe_text: str, extra_instructions: str = "") -> bytes:
    """Generate an illustration for the recipe using the OpenAI Images API."""
    title_match = re.search(r'title\s*=\s*"([^"]+)"', recipe_text)
    potential_title = title_match.group(1) if title_match else "Food Recipe"
    logger.info("Extracted recipe title for image generation: '%s'", potential_title)

    prompt_for_dalle = IMAGE_PROMPT_TEMPLATE.format(
        title=potential_title,
        extra_instructions=extra_instructions or "",
    )

    logger.info("Generating image with prompt: '%s'", prompt_for_dalle)
    start_time = time.time()

    client = get_openai_image_client()
    response = client.images.generate(
        model=get_openai_model("image_generation"),
        prompt=prompt_for_dalle,
        size="1024x1024",
        quality="high",
        n=1,
    )

    elapsed_time = time.time() - start_time
    logger.info("Image generation completed in %.2f seconds", elapsed_time)

    image_url = response.data[0].url
    logger.info("Downloading generated image")

    image_response = requests.get(image_url)
    image_response.raise_for_status()

    image = Image.open(io.BytesIO(image_response.content))
    if image.mode in ("RGBA", "P"):
        logger.debug("Converting image to RGB mode")
        image = image.convert("RGB")

    compressed_io = io.BytesIO()
    image.save(compressed_io, format="JPEG", quality=75, optimize=True)

    compressed_image_bytes = compressed_io.getvalue()
    original_size = len(image_response.content)
    compressed_size = len(compressed_image_bytes)
    logger.info(
        "Image compressed: %.1fKB -> %.1fKB (%.1f%%)",
        original_size / 1024,
        compressed_size / 1024,
        (compressed_size / original_size) * 100,
    )

    return compressed_image_bytes


__all__ = ["generate_recipe_image"]
