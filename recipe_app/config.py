"""Configuration helpers for environment-dependent services."""
from __future__ import annotations

import os
from functools import lru_cache

from github import Github  # type: ignore
from openai import OpenAI  # type: ignore

from .logging_config import get_logger

logger = get_logger(__name__)

RECIPES_FOLDER = os.getenv("RECIPES_FOLDER", "content/post")


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


__all__ = ["RECIPES_FOLDER", "get_openai_client", "get_github_repo"]
