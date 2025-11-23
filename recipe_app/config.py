"""Configuration helpers for environment-dependent services."""
from __future__ import annotations

import os
from functools import lru_cache

from github import Github  # type: ignore
from openai import OpenAI  # type: ignore

from .logging_config import get_logger

logger = get_logger(__name__)

RECIPES_FOLDER = os.getenv("RECIPES_FOLDER", "content/post")

OPENAI_MODELS = {
    "recipe_conversion": os.getenv(
        "OPENAI_MODEL_RECIPE_CONVERSION", "gpt-5.1-2025-11-13"
    ),
    "text_extraction_image": os.getenv(
        "OPENAI_MODEL_TEXT_EXTRACTION_IMAGE", "gpt-5.1-2025-11-13"
    ),
    "text_extraction_link": os.getenv(
        "OPENAI_MODEL_TEXT_EXTRACTION_LINK", "gpt-5.1-2025-11-13"
    ),
    "image_generation": os.getenv(
        "OPENAI_MODEL_IMAGE_GENERATION", "gpt-image-1"
    ),
}


def get_openai_model(service: str) -> str:
    """Return configured OpenAI model name for a given service."""
    try:
        return OPENAI_MODELS[service]
    except KeyError as exc:  # pragma: no cover - defensive branch
        message = f"OpenAI model not configured for '{service}'."
        logger.error(message)
        raise RuntimeError(message) from exc


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Instantiate (and cache) an OpenAI client with environment credentials."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        message = "OPENAI_API_KEY environment variable is not set."
        logger.error(message)
        raise RuntimeError(message)

    logger.debug("Creating OpenAI client")
    return OpenAI(api_key=api_key)

@lru_cache(maxsize=1)
def get_openai_image_client() -> OpenAI:
    """Instantiate (and cache) an OpenAI client with environment credentials."""
    api_key = os.getenv("OPENAI_API_KEY_IMAGE")
    if not api_key:
        message = "OPENAI_API_KEY_IMAGE environment variable is not set."
        logger.error(message)
        raise RuntimeError(message)

    logger.debug("Creating OpenAI client")
    return OpenAI(api_key=api_key)

@lru_cache(maxsize=1)
def get_github_repo():
    """Return an authenticated GitHub repository instance."""
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    repo_name = os.getenv("GITHUB_REPO_NAME")
    missing = [
        name
        for name, value in {
            "GITHUB_ACCESS_TOKEN": token,
            "GITHUB_REPO_NAME": repo_name,
        }.items()
        if not value
    ]

    if missing:
        message = (
            "Missing required environment variables for GitHub integration: "
            + ", ".join(missing)
        )
        logger.error(message)
        raise RuntimeError(message)

    logger.debug("Authenticating with GitHub repository %s", repo_name)
    github_client = Github(token)
    return github_client.get_repo(repo_name)


__all__ = [
    "RECIPES_FOLDER",
    "OPENAI_MODELS",
    "get_openai_client",
    "get_github_repo",
    "get_openai_model",
]
