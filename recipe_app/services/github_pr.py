"""Utilities for writing recipe content to GitHub and opening pull requests."""
from __future__ import annotations

from ..config import RECIPES_FOLDER, get_github_repo
from ..logging_config import get_logger

logger = get_logger(__name__)


def create_github_pr(final_recipe: str, compressed_image_bytes: bytes, technical_title: str) -> str:
    """Create a new recipe branch, commit files, and open a pull request."""
    logger.info(
        "Starting GitHub PR creation process for recipe: %s", technical_title
    )

    repo = get_github_repo()
    logger.info(
        "Successfully authenticated with GitHub and accessed repo %s", repo.full_name
    )

    source = repo.get_branch("master")
    new_branch_name = f"recipe/{technical_title}"
    logger.info("Creating new branch '%s' from master", new_branch_name)
    repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source.commit.sha)

    file_name = f"{RECIPES_FOLDER}/{technical_title}/index.md"
    commit_message = f"Add new recipe {technical_title}"
    content = final_recipe.encode("utf-8")
    logger.info(
        "Prepared recipe content for %s - Size: %s bytes", file_name, len(content)
    )

    recipe_file = repo.create_file(
        path=file_name,
        message=commit_message,
        content=content,
        branch=new_branch_name,
    )
    logger.info(
        "Created recipe file: %s in branch %s", file_name, new_branch_name
    )
    logger.debug("File SHA: %s", recipe_file["content"].sha)

    image_file_path = f"{RECIPES_FOLDER}/{technical_title}/image.jpg"
    commit_message_image = f"Add image for recipe {technical_title}"

    image_file = repo.create_file(
        path=image_file_path,
        message=commit_message_image,
        content=compressed_image_bytes,
        branch=new_branch_name,
    )
    logger.info(
        "Uploaded image to %s - Size: %.1fKB",
        image_file_path,
        len(compressed_image_bytes) / 1024,
    )
    logger.debug("Image file SHA: %s", image_file["content"].sha)

    pr = repo.create_pull(
        title=f"New Recipe: {technical_title}",
        body=f"Auto-generated recipe PR for {technical_title}. Please review.",
        head=new_branch_name,
        base="master",
    )
    logger.info("Pull request created successfully: %s", pr.html_url)
    return pr.html_url


__all__ = ["create_github_pr"]
