"""Recipe formatting helpers backed by the OpenAI API."""
from __future__ import annotations

from datetime import datetime
import re
import time

from ..config import get_openai_client
from ..logging_config import get_logger
from ..models import RecipeConversionResult
from ..prompts import RECIPE_PROMPT_TEMPLATE
from ..utils import extract_technical_title, strip_markdown_fences

logger = get_logger(__name__)


def call_openai_for_recipe(prompt: str) -> str:
    """Send a prompt to OpenAI and return the formatted recipe text."""
    start_time = time.time()
    logger.info("Sending prompt to OpenAI - Length: %s characters", len(prompt))

    client = get_openai_client()
    response = client.responses.create(
        model="gpt-4.1-2025-04-14",
        input=prompt,
        instructions=(
            "You are transforming food recipes into a specific markdown format. "
            "Respond only with the converted recipe in plain markdown without code fences or syntax highlighting markers."
        ),
    )

    elapsed_time = time.time() - start_time
    logger.info("Received response from OpenAI in %.2f seconds", elapsed_time)

    cleaned_response = strip_markdown_fences(response.output_text)
    logger.debug("Response after cleaning: First 100 chars: %s...", cleaned_response[:100])

    today_date = datetime.today().strftime("%Y-%m-%d")
    cleaned_response = re.sub(
        r'(date\s*=\s*)"[^"]*"',
        f'\\1"{today_date}"',
        cleaned_response,
    )

    return cleaned_response


def convert_recipe(recipe_text: str, user_instructions: str) -> RecipeConversionResult:
    """Call OpenAI to format a recipe and extract its technical title."""
    logger.info(
        "Reformatting recipe with OpenAI. Text length: %s chars", len(recipe_text)
    )
    prompt = RECIPE_PROMPT_TEMPLATE.format(
        recipe_text=recipe_text,
        user_instructions=user_instructions or "",
    )

    formatted_recipe = call_openai_for_recipe(prompt)
    technical_title = extract_technical_title(formatted_recipe)
    return RecipeConversionResult(formatted_recipe, technical_title)


__all__ = ["call_openai_for_recipe", "convert_recipe"]
