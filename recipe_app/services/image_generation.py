"""Utilities for generating and compressing recipe illustration images."""
from __future__ import annotations
from altair.vegalite.v5.schema.channels import Description

import io
import re
import time
import base64

import requests
from PIL import Image

from ..config import get_openai_image_client, get_openai_model
from ..logging_config import get_logger
from ..prompts import IMAGE_PROMPT_TEMPLATE

logger = get_logger(__name__)


def generate_recipe_image(recipe_text: str, extra_instructions: str = "") -> bytes:
    """Generate an illustration for the recipe using the OpenAI Images API."""
    title_match = re.search(r'title\s*=\s*"([^"]+)"', recipe_text)
    description_match = re.search(r'description\s*=\s*"([^"]+)"', recipe_text)
    potential_title = title_match.group(1) if title_match else "Food Recipe"
    potential_description = description_match.group(1) if description_match else "Delicious food"
    logger.info("Extracted recipe title and description for image generation: '%s', '%s'", potential_title, potential_description)

    prompt_for_dalle = IMAGE_PROMPT_TEMPLATE.format(
        title=potential_title,
        description=potential_description,
        extra_instructions=extra_instructions or "",
    )

    logger.info("Generating image with prompt: '%s'", prompt_for_dalle)
    start_time = time.time()

    client = get_openai_image_client()
    response = client.images.generate(
        model=get_openai_model("image_generation"),
        prompt=prompt_for_dalle,
        size="1024x1024",
        quality="medium",
        output_format="jpeg",
        moderation='low',
        n=1,
    )

    elapsed_time = time.time() - start_time
    logger.info("Image generation completed in %.2f seconds", elapsed_time)

    image_bytes = base64.b64decode(response.data[0].b64_json)

    image = Image.open(io.BytesIO(image_bytes))
    if image.mode in ("RGBA", "P"):
        logger.debug("Converting image to RGB mode")
        image = image.convert("RGB")

    compressed_io = io.BytesIO()
    image.save(compressed_io, format="JPEG", quality=75, optimize=True)

    compressed_image_bytes = compressed_io.getvalue()
    original_size = len(image_bytes)
    compressed_size = len(compressed_image_bytes)
    logger.info(
        "Image compressed: %.1fKB -> %.1fKB (%.1f%%)",
        original_size / 1024,
        compressed_size / 1024,
        (compressed_size / original_size) * 100,
    )

    return compressed_image_bytes


__all__ = ["generate_recipe_image"]
