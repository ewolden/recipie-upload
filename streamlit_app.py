"""Streamlit entrypoint for the recipe conversion workflow."""

from __future__ import annotations

import streamlit as st

from recipe_app.logging_config import get_logger
from recipe_app.session_state import initialize_session_state
from recipe_app.services.github_pr import create_github_pr
from recipe_app.services.image_generation import generate_recipe_image
from recipe_app.services.recipe_conversion import convert_recipe
from recipe_app.services.text_extraction import (
    extract_text_from_image,
    extract_text_from_link,
)

logger = get_logger(__name__)


def render_image_extraction_section() -> None:
    """Allow the user to upload an image and extract text from it."""
    st.subheader("Extract Text from Uploaded Image")
    uploaded_image = st.file_uploader(
        "Upload an image (JPEG/PNG)", type=["jpg", "jpeg", "png"]
    )

    if uploaded_image is None:
        return

    image_bytes = uploaded_image.read()
    logger.info(
        "Image uploaded: %s - Size: %.1fKB",
        uploaded_image.name,
        len(image_bytes) / 1024,
    )

    st.image(image_bytes, caption="Uploaded Image Preview", use_container_width=True)
    extra_instructions = st.text_input(
        "Extra instructions for text extraction", ""
    )

    if st.button("Extract Text"):
        logger.info(
            "Text extraction requested for image with extra instructions: '%s'",
            extra_instructions,
        )
        with st.spinner("Extracting text from image..."):
            try:
                extracted_text = extract_text_from_image(
                    image_bytes, extra_instructions
                )
                st.session_state.extracted_text = extracted_text
                logger.info("Text extraction successful")
                st.success("Extraction successful!")
                st.write("**Extracted Text:**")
                st.write(extracted_text)
            except Exception as exc:  # noqa: BLE001 - Streamlit surface
                logger.error("Text extraction failed: %s", exc, exc_info=True)
                st.error(f"Error extracting text: {exc}")


def render_recipe_form() -> None:
    """Render the initial recipe conversion form."""
    with st.form("recipe_form"):
        st.write("Enter either a link to scrape a recipe or paste the recipe directly.")
        recipe_link = st.text_input("Recipe Link (optional)")
        recipe_text = st.text_area(
            "Or, Paste Recipe Text Here (if no link was provided)",
            value=st.session_state.extracted_text,
            height=200,
        )
        user_instructions = st.text_area(
            "Additional Instructions/Comments (optional)", height=100
        )
        submitted = st.form_submit_button("Convert & Preview")

    if not submitted:
        return

    logger.info("Recipe conversion form submitted")

    if not recipe_link and not recipe_text.strip():
        logger.warning("No recipe link or text provided")
        st.error("Please provide either a link or some recipe text.")
        return

    if recipe_link:
        logger.info("Processing recipe from link: %s", recipe_link)
        try:
            with st.spinner("Scraping recipe from provided link..."):
                recipe_text = extract_text_from_link(recipe_link)
                logger.info("Successfully extracted recipe from link")
        except Exception as exc:  # noqa: BLE001 - Streamlit surface
            logger.error("Failed to extract recipe from link: %s", exc, exc_info=True)
            st.error(f"Error scraping recipe: {exc}")
            return

    if not recipe_text.strip():
        logger.warning("No recipe text found after processing")
        st.error("No recipe text found or scraping failed.")
        return

    try:
        with st.spinner("Calling OpenAI to reformat recipe..."):
            conversion = convert_recipe(recipe_text, user_instructions)
        st.session_state.final_recipe = conversion.formatted_recipe
        st.session_state.technical_title = conversion.technical_title
        logger.info("Recipe successfully reformatted")
    except Exception as exc:  # noqa: BLE001 - Streamlit surface
        logger.error("Recipe conversion failed: %s", exc, exc_info=True)
        st.error(f"An error occurred: {exc}")
        return

    logger.info("Automatically generating recipe image")
    with st.spinner("Generating recipe image..."):
        try:
            compressed_image_bytes = generate_recipe_image(
                st.session_state.final_recipe, ""
            )
            st.session_state.compressed_image_bytes = compressed_image_bytes
            logger.info("Recipe image generated successfully")
        except Exception as exc:  # noqa: BLE001 - Streamlit surface
            logger.error("Image generation failed: %s", exc, exc_info=True)
            st.error(f"Error generating image: {exc}")

    logger.info("Rerunning app to move to preview step")
    st.rerun()


def render_recipe_preview() -> None:
    """Render the recipe preview, editing, image regeneration, and PR creation flow."""
    logger.info("Displaying recipe preview page")
    st.subheader("Preview & Edit Recipe")

    edited_recipe = st.text_area(
        "Edit your recipe in Markdown below:",
        value=st.session_state.final_recipe,
        height=400,
    )

    st.markdown("---")
    st.markdown("### Preview (Markdown Rendered)")
    st.markdown(edited_recipe)
    st.markdown("---")

    if edited_recipe != st.session_state.final_recipe:
        logger.info("Recipe text edited by user")
        st.session_state.final_recipe = edited_recipe

    st.subheader("Recipe Image")
    if st.session_state.compressed_image_bytes:
        st.image(st.session_state.compressed_image_bytes, use_container_width=True)
    else:
        st.write("No image generated yet.")
        logger.warning("No image available for preview")

    with st.form("image_generation_form"):
        extra_instructions = st.text_input(
            "Extra instructions for image generation:", ""
        )
        gen_image_submitted = st.form_submit_button("Regenerate Image")

    if gen_image_submitted:
        logger.info(
            "Image regeneration requested with instructions: '%s'",
            extra_instructions,
        )
        with st.spinner("Generating recipe image..."):
            try:
                compressed_image_bytes = generate_recipe_image(
                    st.session_state.final_recipe,
                    extra_instructions,
                )
                st.session_state.compressed_image_bytes = compressed_image_bytes
                logger.info("Image regenerated successfully")
                st.success("Image regenerated successfully!")
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - Streamlit surface
                logger.error("Image regeneration failed: %s", exc, exc_info=True)
                st.error(f"Error regenerating image: {exc}")

    st.subheader("Create Pull Request")
    if st.button("Create Pull Request"):
        logger.info("Pull request creation requested")

        if not st.session_state.compressed_image_bytes:
            logger.warning("Attempted to create PR without an image")
            st.error("Please generate an image before creating a pull request.")
            return

        with st.spinner("Creating GitHub branch, committing, and opening PR..."):
            try:
                pr_url = create_github_pr(
                    st.session_state.final_recipe,
                    st.session_state.compressed_image_bytes,
                    st.session_state.technical_title,
                )
                logger.info("Pull request created successfully: %s", pr_url)
                st.success("Recipe successfully processed and pull request created!")
                st.markdown(f"**Pull Request URL**: [{pr_url}]({pr_url})")

                if st.button("Start New Recipe"):
                    logger.info("User requested to start a new recipe")
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    logger.info("Session state cleared")
                    st.rerun()
            except Exception as exc:  # noqa: BLE001 - Streamlit surface
                logger.error("Pull request creation failed: %s", exc, exc_info=True)
                st.error(f"An error occurred while creating the PR: {exc}")


def main() -> None:
    """Primary Streamlit entrypoint."""
    initialize_session_state()

    st.title("Recipe Converter")
    logger.info("Application started/refreshed")

    render_image_extraction_section()

    if not st.session_state.final_recipe:
        render_recipe_form()
    else:
        render_recipe_preview()


if __name__ == "__main__":
    logger.info("=== Recipe Converter Application Starting ===")
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - top-level Streamlit error handler
        logger.critical("Unhandled exception in main application: %s", exc, exc_info=True)
        st.error(f"A critical error occurred: {exc}")
    logger.info("=== Application execution completed ===")
