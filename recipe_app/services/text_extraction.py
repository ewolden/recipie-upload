"""Text extraction helpers for images and external links."""
from __future__ import annotations

import base64
import time

import requests

from ..config import get_openai_client, get_openai_model
from ..logging_config import get_logger
from ..utils import strip_markdown_fences

logger = get_logger(__name__)


def extract_text_from_image(image_bytes: bytes, extra_instructions: str = "") -> str:
    """Extract visible text from an uploaded image using OpenAI vision."""
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    logger.info(
        "Processing image for text extraction - Size: %.1fKB",
        len(image_bytes) / 1024,
    )

    start_time = time.time()
    logger.info("Sending image to OpenAI for text extraction")

    client = get_openai_client()
    response = client.responses.create(
        model=get_openai_model("text_extraction_image"),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are an AI assistant that extracts all visible text from the provided image. "
                            "Extract all recipe details including ingredients, instructions, and cooking times. "
                            f"{extra_instructions}"
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{base64_image}",
                    },
                ],
            }
        ],
    )

    elapsed_time = time.time() - start_time
    logger.info("Text extraction completed in %.2f seconds", elapsed_time)

    extracted_text = strip_markdown_fences(response.output_text)
    logger.info(
        "Extracted %s characters of text from image",
        len(extracted_text),
    )
    logger.debug("First 100 chars of extracted text: %s...", extracted_text[:100])
    return extracted_text


def extract_text_from_link(link: str, extra_instructions: str = "") -> str:
    """Send raw HTML content to OpenAI to extract recipe information."""
    logger.info("Fetching content from URL: %s", link)
    response = requests.get(link)
    response.raise_for_status()

    page_html = response.text
    logger.info(
        "Successfully retrieved HTML content - Size: %.1fKB",
        len(page_html) / 1024,
    )

    start_time = time.time()
    logger.info("Sending HTML to OpenAI for recipe extraction")

    client = get_openai_client()
    openai_response = client.responses.create(
        model=get_openai_model("text_extraction_link"),
        input=page_html,
        instructions=(
            "You are an AI assistant that extracts the food recipe from this raw HTML.\n"
            "Extract all recipe details including title, ingredients, instructions, and cooking times.\n"
            f"{extra_instructions}"
        ),
    )

    elapsed_time = time.time() - start_time
    logger.info("Recipe extraction from HTML completed in %.2f seconds", elapsed_time)

    extracted_text = strip_markdown_fences(openai_response.output_text).strip()
    logger.info(
        "Extracted %s characters of recipe text from URL",
        len(extracted_text),
    )
    logger.debug("First 100 chars of extracted recipe: %s...", extracted_text[:100])
    return extracted_text


__all__ = ["extract_text_from_image", "extract_text_from_link"]
