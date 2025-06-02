import os
import re
import requests
from openai import OpenAI
import streamlit as st
from github import Github  # PyGithub
import logging
from PIL import Image
import io
import base64
import time
from datetime import datetime
import sys

# ---------------------------------------------------------------------------------
# 1. Enhanced Logging Configuration
# ---------------------------------------------------------------------------------
# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure a rotating file handler with timestamp in filename
log_filename = f"logs/recipe_converter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging to both file and console with detailed formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("recipe_converter")

# ---------------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------------
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")  # e.g., "myuser/myrecipes"
RECIPES_FOLDER = "content/post"  # folder in your repo for recipe files

client = OpenAI(
    # This is the default and can be omitted
    api_key=os.getenv("OPENAI_API_KEY"),
)

# ---------------------------------------------------------------------------------
# 3. Helper functions
# ---------------------------------------------------------------------------------

def strip_markdown_fences(text: str) -> str:
    """
    Removes markdown code fences (```markdown and ```) from the beginning and end of text.
    """
    # Remove leading markdown fences with optional language identifier
    text = re.sub(r'^```(?:markdown)?\n', '', text)
    # Remove trailing markdown fences
    text = re.sub(r'\n```$', '', text)
    return text.strip()

def call_openai_for_recipe(recipe_text: str, user_instructions: str) -> str:
    """
    Call the OpenAI ChatCompletion API (GPT-3.5 / GPT-4) to reformat the recipe
    using the user instructions as context.
    """
    logger.info("Preparing OpenAI prompt for recipe conversion")
    prompt = f"""
    You are transforming food recipes into a specific markdown format. You will try to make the instructions as concise as possible. In the method, make sure to include the amounts required in each step in bold along with the ingredient. This is the format I want to end up with, commented for your ease. Put any times in the frontmatter, in these 4 categories: prepTime, cookTime, chillTime, restTime. Make sure to include all the fields specified. Remove any "sales" pitch from the title, such as quick, easy, tasty etc. Give some suggested tags for this recipe in the tags array in the frontmatter:

    +++
    author = "Eivind Halmøy Wolden"
    title = "Title Goes Here"
    technical_title = "title-goes-here"
    date = "Insert todays date here in YYYY-MM-DD format"
    description = "One sentence description of the recipe"
    tags = [
        
    ]
    categories = [
        
    ]
    image = "image.jpg"
    prepTime = "How long does the preparation of the ingredients take"
    cookTime = "How long is the cooking time"
    recipeYield = "How many portions does this recipe yield"
    ingredients = [ Ingredients listed alphabetically
    ]
    +++

    ## Title
    ### Ingredients for title
    Ingredient | Quantity | How
    ---|---|---
    Ingredients listed by time they are used. Here are some examples:
    Wild mushrooms      | 300 g        | in chunks
    Champignon          | 200 g        | in chunks
    Onion               | 1            | finley chopped
    Butter              | 2 tbsp       | 
    Fresh thyme         | 1 sprig      | finley chopped
    Cream (12%)         | 1            | 
    Soy Sauce           | to taste     | 

    ### Method for title
    #### Step 1
    List each step. Making sure to bold any ingredients and amounts in the step. Some examples:

    #### Step 2
    In a skillet, melt **2 tbsp butter** at high heat until lightly browned.

    #### Step 3
    Add **500 g mushrooms** to skillet and cook at high heat for 3 mins. Add finely chopped **onion**. Cook until golden.

    #### Step 4
    Add finely chopped **sprig of thyme** and **300 ml cream** and reduce heat to medium.

    #### Step 5
    Let boil for a few minutes until thickened. Add **soy sauce**, **salt**, and **pepper** to taste. 

    ## Notes:
    Any additional notes for the recipe, such as frigde life, reheating instructions etc.

    ----------
    Remember:
    - ALWAYS alphabetize the ingredients in the front matter, don't include amounts
    - ALWAYS put ingredients in the order they are used in the ingredients list
    - ALWAYS include the amount of each ingredient used throughout the recipe, make it bold for clarity.
    - Inches should be converted to cm (rounded)
    - Farenheit should be converted to Celcius
    - oz should be converted to grams (rounded to 10 grams)
    - Do not convert amounts in tbsp, tsp, cups.
    - lbs should be converted to grams (rounded to 10 grams)
    - Be concise
    - Remove sales pitchy things
    - Respond in English
    - Remove kosher and just leave salt from any mention of kosher salt.
    - Give suggested tags
    - The author should always be Eivind Halmøy Wolden
    - The technical title should be a shortened version of the title, with no spaces and all lowercase

    Additional user instructions: {user_instructions}

    Recipe Text:
    {recipe_text}
    """
    
    try:
        start_time = time.time()
        logger.info(f"Sending prompt to OpenAI - Length: {len(prompt)} characters")
        
        response = client.responses.create(
            model="gpt-4.1-2025-04-14",
            input=prompt,
            instructions="You are transforming food recipes into a specific markdown format. Respond only with the converted recipe in plain markdown without code fences or syntax highlighting markers.",
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Received response from OpenAI in {elapsed_time:.2f} seconds")
        
        # Remove markdown code fences if they exist
        cleaned_response = strip_markdown_fences(response.output_text)
        logger.debug(f"Response after cleaning: First 100 chars: {cleaned_response[:100]}...")

        # Fix the date in the frontmatter
        today_date = datetime.today().strftime("%Y-%m-%d")
        cleaned_response = re.sub(
            r'(date\s*=\s*)"[^"]*"', 
            f'\\1"{today_date}"', 
            cleaned_response
        )
        
        return cleaned_response
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {str(e)}", exc_info=True)
        raise

def generate_recipe_image(recipe_text: str, extra_instructions: str = "") -> bytes:
    """
    Generate an image using OpenAI (DALL·E) based on the recipe text and
    some user-provided instructions (extra_instructions).
    """
    # We'll try to identify the recipe title from the final_recipe text
    title_match = re.search(r"title\s*=\s*\"([^\"]+)\"", recipe_text)
    try:
        potential_title = title_match.group(1) if title_match else "Food Recipe"
        logger.info(f"Extracted recipe title for image generation: '{potential_title}'")
    except (ValueError, AttributeError) as e:
        logger.error(f"Error extracting title from recipe text: {e}", exc_info=True)
        potential_title = "Food Recipe"
        logger.info(f"Using default title for image generation: '{potential_title}'")

    # Additional instructions from user
    prompt_for_dalle = (
        f"A cartoon sketch of the food, inspired by the illustrative style of Tom Hovey, characterized by bold lines, vibrant colors, and a playful, whimsical feel. It should depict {potential_title}. {extra_instructions}"
    )
    
    logger.info(f"Generating image with prompt: '{prompt_for_dalle}'")
    start_time = time.time()
    
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt_for_dalle,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Image generation completed in {elapsed_time:.2f} seconds")
        
        # Download the generated image
        image_url = response.data[0].url
        logger.info(f"Downloading image")
        
        image_response = requests.get(image_url)
        image_response.raise_for_status()  # Ensure we got a valid response
        
        image = Image.open(io.BytesIO(image_response.content))
        if image.mode in ("RGBA", "P"):
            logger.debug("Converting image to RGB mode")
            image = image.convert("RGB")

        # Compress and save the image
        compressed_io = io.BytesIO()
        image.save(compressed_io, format='JPEG', quality=75, optimize=True)
        
        # Get the compressed bytes
        compressed_image_bytes = compressed_io.getvalue()
        original_size = len(image_response.content)
        compressed_size = len(compressed_image_bytes)
        logger.info(f"Image compressed: {original_size/1024:.1f}KB - {compressed_size/1024:.1f}KB ({compressed_size/original_size*100:.1f}%)")
        
        return compressed_image_bytes
    except Exception as e:
        logger.error(f"Error in image generation: {str(e)}", exc_info=True)
        raise

def create_github_pr(final_recipe: str, compressed_image_bytes: bytes, technical_title: str) -> str:
    """
    Create a branch, commit the recipe as a Markdown file, and open a pull request.
    Returns the PR URL.
    """
    logger.info(f"Starting GitHub PR creation process for recipe: {technical_title}")
    try:
        g = Github(GITHUB_ACCESS_TOKEN)
        repo = g.get_repo(GITHUB_REPO_NAME)
        logger.info(f"Successfully authenticated with GitHub and accessed repo: {GITHUB_REPO_NAME}")

        # 1) Create a new branch from default (e.g. "main")
        source = repo.get_branch("master")
        new_branch_name = f"recipe/{technical_title}"
        logger.info(f"Creating new branch '{new_branch_name}' from master")
        
        repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source.commit.sha)
        logger.info(f"Created new branch: {new_branch_name}")

        # 2) Prepare file contents
        file_name = f"{RECIPES_FOLDER}/{technical_title}/index.md"
        commit_message = f"Add new recipe {technical_title}"
        
        content = final_recipe.encode("utf-8")  # must be bytes
        logger.info(f"Prepared recipe content for {file_name} - Size: {len(content)} bytes")

        # 3) Create or update the file in the new branch
        try:
            recipe_file = repo.create_file(
                path=file_name,
                message=commit_message,
                content=content,
                branch=new_branch_name
            )
            logger.info(f"Created recipe file: {file_name} in branch {new_branch_name}")
            logger.debug(f"File SHA: {recipe_file['content'].sha}")
        except Exception as e:
            logger.error(f"Error creating recipe file: {str(e)}", exc_info=True)
            raise

        # 4) Upload image
        # Define the file path for the image within your repository.
        image_file_path = f"{RECIPES_FOLDER}/{technical_title}/image.jpg"
        commit_message_image = f"Add image for recipe {technical_title}"

        try:
            # Create the image file in the new branch
            image_file = repo.create_file(
                path=image_file_path,
                message=commit_message_image,
                content=compressed_image_bytes,
                branch=new_branch_name
            )
            logger.info(f"Uploaded image to {image_file_path} - Size: {len(compressed_image_bytes)/1024:.1f}KB")
            logger.debug(f"Image file SHA: {image_file['content'].sha}")
        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}", exc_info=True)
            raise

        # 5) Create Pull Request
        try:
            pr = repo.create_pull(
                title=f"New Recipe: {technical_title}",
                body=f"Auto-generated recipe PR for {technical_title}. Please review.",
                head=new_branch_name,
                base="master"
            )
            logger.info(f"Pull request created successfully: {pr.html_url}")
            return pr.html_url
        except Exception as e:
            logger.error(f"Error creating pull request: {str(e)}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"GitHub PR creation failed: {str(e)}", exc_info=True)
        raise

def extract_text_from_image(image_bytes: bytes, extra_instructions: str = "") -> str:
    """
    Extracts text from an image using OpenAI. 
    Accepts raw image bytes as input and returns the extracted text.

    :param image_bytes: Raw bytes of the image file.
    :param extra_instructions: Additional instructions to guide the OCR/vision model.
    :return: A string containing the extracted text from the image.
    """
    # Convert the raw image bytes to base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    logger.info(f"Processing image for text extraction - Size: {len(image_bytes)/1024:.1f}KB")

    try:
        start_time = time.time()
        logger.info("Sending image to OpenAI for text extraction")
        
        # Send a request to OpenAI
        response = client.responses.create(
            model="gpt-4.1-mini-2025-04-14", 
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
                            )
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    ]
                }
            ]
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Text extraction completed in {elapsed_time:.2f} seconds")
        
        # Clean the extracted text
        extracted_text = strip_markdown_fences(response.output_text)
        text_length = len(extracted_text)
        logger.info(f"Extracted {text_length} characters of text from image")
        logger.debug(f"First 100 chars of extracted text: {extracted_text[:100]}...")
        
        return extracted_text
    except Exception as e:
        logger.error(f"Error extracting text from image: {str(e)}", exc_info=True)
        raise

def extract_text_from_link(link: str, extra_instructions: str = "") -> str:
    """
    Sends the raw HTML content of a link to OpenAI for text extraction,
    avoiding any local parsing libraries (e.g. BeautifulSoup).
    The function returns only the text that OpenAI deems relevant.

    :param link: URL of the webpage to extract text from.
    :param extra_instructions: Additional guidance for OpenAI on how to process the text.
    :return: Extracted text as a string.
    """
    logger.info(f"Fetching content from URL: {link}")
    try:
        response = requests.get(link)
        response.raise_for_status()  # Check if the request was successful
        page_html = response.text
        html_size = len(page_html)
        logger.info(f"Successfully retrieved HTML content - Size: {html_size/1024:.1f}KB")
        
        start_time = time.time()
        logger.info("Sending HTML to OpenAI for recipe extraction")
        
        openai_response = client.responses.create(
            model="gpt-4o-2024-08-06",
            input=page_html,
            instructions=(
                "You are an AI assistant that extracts the food recipe from this raw HTML.\n"
                "Extract all recipe details including title, ingredients, instructions, and cooking times.\n"
                f"{extra_instructions}"
            ),
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Recipe extraction from HTML completed in {elapsed_time:.2f} seconds")
        
        # Clean the extracted text
        extracted_text = strip_markdown_fences(openai_response.output_text).strip()
        text_length = len(extracted_text)
        logger.info(f"Extracted {text_length} characters of recipe text from URL")
        logger.debug(f"First 100 chars of extracted recipe: {extracted_text[:100]}...")
        
        return extracted_text
    except requests.RequestException as e:
        logger.error(f"Error fetching URL {link}: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error extracting recipe from HTML: {str(e)}", exc_info=True)
        raise

# ---------------------------------------------------------------------------------
# 4. Streamlit app
# ---------------------------------------------------------------------------------

def main():
    # Initialize session state variables
    if "final_recipe" not in st.session_state:
        st.session_state.final_recipe = ""
    if "compressed_image_bytes" not in st.session_state:
        st.session_state.compressed_image_bytes = None
    if "technical_title" not in st.session_state:
        st.session_state.technical_title = ""
    if "extracted_text" not in st.session_state:
        st.session_state.extracted_text = ""

    st.title("Recipe Converter")
    logger.info("Application started/refreshed")
    
    # ---------------------------------------------------------------------------------
    # Image Upload and Text Extraction Section
    # ---------------------------------------------------------------------------------
    st.subheader("Extract Text from Uploaded Image")
    uploaded_image = st.file_uploader("Upload an image (JPEG/PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_image is not None:
        # Read the raw bytes of the uploaded image
        image_bytes = uploaded_image.read()
        logger.info(f"Image uploaded: {uploaded_image.name} - Size: {len(image_bytes)/1024:.1f}KB")

        # Display the uploaded image in Streamlit
        st.image(image_bytes, caption="Uploaded Image Preview", use_container_width=True)

        # Add a text input for any extra instructions you may want to pass
        extra_instructions = st.text_input("Extra instructions for text extraction", "")

        if st.button("Extract Text"):
            logger.info(f"Text extraction requested for image with extra instructions: '{extra_instructions}'")
            with st.spinner("Extracting text from image..."):
                try:
                    extracted_text = extract_text_from_image(image_bytes, extra_instructions)
                    st.session_state.extracted_text = extracted_text  # Store in session state
                    logger.info("Text extraction successful")
                    st.success("Extraction successful!")
                    st.write("**Extracted Text:**")
                    st.write(extracted_text)
                except Exception as e:
                    logger.error(f"Text extraction failed: {str(e)}", exc_info=True)
                    st.error(f"Error extracting text: {e}")

    # ---------------------------------------------------------------------------------
    # STEP 1: If we do NOT have a final recipe, show the input form.
    # ---------------------------------------------------------------------------------
    if not st.session_state.final_recipe:
        with st.form("recipe_form"):
            st.write("Enter either a link to scrape a recipe or paste the recipe directly.")
            recipe_link = st.text_input("Recipe Link (optional)")
            # If we have extracted text, use it as the default value for the recipe text input
            recipe_text = st.text_area(
                "Or, Paste Recipe Text Here (if no link was provided)", 
                value=st.session_state.extracted_text,  # Use extracted text if available
                height=200
            )
            user_instructions = st.text_area("Additional Instructions/Comments (optional)", height=100)
            submitted = st.form_submit_button("Convert & Preview")

        if submitted:
            logger.info("Recipe conversion form submitted")
            # Validate input
            if not recipe_link and not recipe_text.strip():
                logger.warning("No recipe link or text provided")
                st.error("Please provide either a link or some recipe text.")
                return
            
            if recipe_link:
                logger.info(f"Processing recipe from link: {recipe_link}")
                try:
                    with st.spinner("Scraping recipe from provided link..."):
                        recipe_text = extract_text_from_link(recipe_link)
                        logger.info("Successfully extracted recipe from link")
                except Exception as e:
                    logger.error(f"Failed to extract recipe from link: {str(e)}", exc_info=True)
                    st.error(f"Error scraping recipe: {e}")
                    return
            
            if not recipe_text.strip():
                logger.warning("No recipe text found after processing")
                st.error("No recipe text found or scraping failed.")
                return
            
            try:
                logger.info(f"Reformatting recipe with OpenAI. Text length: {len(recipe_text)} chars")
                with st.spinner("Calling OpenAI to reformat recipe..."):
                    final_recipe = call_openai_for_recipe(recipe_text, user_instructions)
                    logger.info("Recipe successfully reformatted")
                
                # Attempt to parse out the technical title from the final_recipe
                technical_title_search = re.search(r'technical_title\s*=\s*"([^"]+)"', final_recipe)
                if technical_title_search:
                    technical_title = technical_title_search.group(1)
                    logger.info(f"Extracted technical title: {technical_title}")
                else:
                    technical_title = "untitled-recipe"
                    logger.warning(f"Could not extract technical title, using default: {technical_title}")
                
                # Store results in session_state
                st.session_state.final_recipe = final_recipe
                st.session_state.technical_title = technical_title
                
                # Automatically generate an image right after recipe conversion
                logger.info("Automatically generating recipe image")
                with st.spinner("Generating recipe image..."):
                    try:
                        compressed_image_bytes = generate_recipe_image(final_recipe, "")
                        st.session_state.compressed_image_bytes = compressed_image_bytes
                        logger.info("Recipe image generated successfully")
                    except Exception as e:
                        logger.error(f"Image generation failed: {str(e)}", exc_info=True)
                        st.error(f"Error generating image: {e}")
                        # Continue even if image generation fails
                
                logger.info("Rerunning app to move to preview step")
                st.rerun()  # move to next step
            except Exception as e:
                logger.error(f"Recipe conversion failed: {str(e)}", exc_info=True)
                st.error(f"An error occurred: {e}")

    # ---------------------------------------------------------------------------------
    # STEP 2: We have a final recipe. Show a preview, let user adjust, regenerate image, etc.
    # ---------------------------------------------------------------------------------
    else:
        logger.info("Displaying recipe preview page")
        st.subheader("Preview & Edit Recipe")

        edited_recipe = st.text_area("Edit your recipe in Markdown below:", 
                                     value=st.session_state.final_recipe, 
                                     height=400)
        
        # Show a "Preview" (rendered Markdown) below
        st.markdown("---")
        st.markdown("### Preview (Markdown Rendered)")
        st.markdown(edited_recipe)
        st.markdown("---")
        
        # Update session_state if the user modifies the text area
        if edited_recipe != st.session_state.final_recipe:
            logger.info("Recipe text edited by user")
            st.session_state.final_recipe = edited_recipe

        # Handle image display and regeneration
        st.subheader("Recipe Image")
        
        # Show the current image if available
        if st.session_state.compressed_image_bytes:
            st.image(st.session_state.compressed_image_bytes, use_container_width=True)
        else:
            st.write("No image generated yet.")
            logger.warning("No image available for preview")
        
        # Provide controls for regenerating the image
        with st.form("image_generation_form"):
            extra_instructions = st.text_input("Extra instructions for image generation:", "")
            gen_image_submitted = st.form_submit_button("Regenerate Image")
        
        if gen_image_submitted:
            logger.info(f"Image regeneration requested with instructions: '{extra_instructions}'")
            with st.spinner("Generating recipe image..."):
                try:
                    compressed_image_bytes = generate_recipe_image(st.session_state.final_recipe, extra_instructions)
                    st.session_state.compressed_image_bytes = compressed_image_bytes
                    logger.info("Image regenerated successfully")
                    st.success("Image regenerated successfully!")
                    st.rerun()  # Refresh to show the new image
                except Exception as e:
                    logger.error(f"Image regeneration failed: {str(e)}", exc_info=True)
                    st.error(f"Error regenerating image: {e}")

        # Once user is satisfied, they can create the PR
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
                        st.session_state.technical_title
                    )
                    logger.info(f"Pull request created successfully: {pr_url}")
                    st.success("Recipe successfully processed and pull request created!")
                    st.markdown(f"**Pull Request URL**: [{pr_url}]({pr_url})")
                    
                    # Reset session state to allow for a new recipe
                    if st.button("Start New Recipe"):
                        logger.info("User requested to start a new recipe")
                        for key in st.session_state.keys():
                            del st.session_state[key]
                        logger.info("Session state cleared")
                        st.rerun()
                        
                except Exception as e:
                    logger.error(f"Pull request creation failed: {str(e)}", exc_info=True)
                    st.error(f"An error occurred while creating the PR: {e}")

if __name__ == "__main__":
    logger.info("=== Recipe Converter Application Starting ===")
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception in main application: {str(e)}", exc_info=True)
        st.error(f"A critical error occurred: {str(e)}")
    logger.info("=== Application execution completed ===")