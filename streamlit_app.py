import os
import re
import requests
from openai import OpenAI
import streamlit as st
from bs4 import BeautifulSoup
from github import Github  # PyGithub
import logging
from PIL import Image
import io

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------
# 1. Configuration
#    You can store these in environment variables, streamlit secrets, or just inline
# ---------------------------------------------------------------------------------
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")  # e.g., "myuser/myrecipes"
RECIPES_FOLDER = "content/post"  # folder in your repo for recipe files

client = OpenAI(
    # This is the default and can be omitted
    api_key=os.getenv("OPENAI_API_KEY"),
)

# ---------------------------------------------------------------------------------
# 2. Helper functions
# ---------------------------------------------------------------------------------
def scrape_recipe(url: str) -> str:
    """
    Fetch the page and attempt to extract a 'recipe' section.
    This is basic and may need adaptation for your specific sites.
    """
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Example selectors (adjust to your needs)
    possible_selectors = [
        "div.recipe",
        "div.recipe-content",
        "div.post-content",
        "article.recipe",
    ]
    for sel in possible_selectors:
        recipe_section = soup.select_one(sel)
        if recipe_section:
            return recipe_section.get_text(separator="\n", strip=True)
    
    # Fallback if no obvious section
    return soup.get_text(separator="\n", strip=True)

def call_openai_for_recipe(recipe_text: str, user_instructions: str) -> str:
    """
    Call the OpenAI ChatCompletion API (GPT-3.5 / GPT-4) to reformat the recipe
    using the user instructions as context.
    """
    prompt = f"""
    You are transforming food recipes into a specific markdown format. You will try to make the instructions as concise as possible. In the method, make sure to include the amounts required in each step in bold along with the ingredient. This is the format I want to end up with, commented for your ease. Put any times in the frontmatter, in these 4 categories: prepTime, cookTime, chillTime, restTime. Make sure to include all the fields specified. Remove any "sales" pitch from the title, such as quick, easy, tasty etc. Give some suggested tags for this recipe in the tags array in the frontmatter:

    +++
    author = "Eivind Halmøy Wolden"
    title = "Title"
    technical_title = "title"
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
    logging.info("Sending prompt to OpenAI")
    response = client.responses.create(
        model="gpt-4.5-preview",
        input=prompt,
        instructions="You are transforming food recipes into a specific markdown format. Respond only with the converted recipe markdown, nothing else.",
    )
    logging.info("Received response from OpenAI")
    return response.output_text

def generate_recipe_image(recipe_text: str, extra_instructions: str = "") -> str:
    """
    Generate an image using OpenAI (DALL·E) based on the recipe text and
    some user-provided instructions (extra_instructions).
    """
    # We'll try to identify the recipe title from the final_recipe text
    # as a naive approach. You can refine as needed.
    title_match = re.search(r"title\s*=\s*\"([^\"]+)\"", recipe_text)
    try:
        potential_title = title_match.group(1) if title_match else ValueError("Title not found in recipe text.")
    except ValueError as e:
        logging.error(f"Error extracting title from recipe text: {e}")

    # Additional instructions from user
    prompt_for_dalle = (
        f"A cartoon sketch of the food, inspired by the illustrative style of Tom Hovey, characterized by bold lines, vibrant colors, and a playful, whimsical feel. It should depict a {potential_title}. {extra_instructions}"
    )
    
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt_for_dalle,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image = Image.open(io.BytesIO(requests.get(response.data[0].url).content))
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Compress and save the image
    compressed_io = io.BytesIO()
    image.save(compressed_io, format='JPEG', quality=75, optimize=True)

    # Get the compressed bytes
    compressed_image_bytes = compressed_io.getvalue()

    return compressed_image_bytes

def create_github_pr(final_recipe: str, compressed_image_bytes: str, technical_title: str) -> str:
    """
    Create a branch, commit the recipe as a Markdown file, and open a pull request.
    Returns the PR URL.
    """
    logging.info("Starting the process to create a GitHub PR.")
    g = Github(GITHUB_ACCESS_TOKEN)
    repo = g.get_repo(GITHUB_REPO_NAME)
    logging.info("Authenticated with GitHub and accessed the repository.")

    # 1) Create a new branch from default (e.g. "main")
    source = repo.get_branch("master")
    new_branch_name = f"recipe/{technical_title}"
    repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source.commit.sha)
    logging.info(f"Created a new branch: {new_branch_name} from master.")

    # 2) Prepare file contents
    file_name = f"{RECIPES_FOLDER}/{technical_title}/index.md"
    commit_message = f"Add new recipe {new_branch_name}"
    
    content = final_recipe.encode("utf-8")  # must be bytes
    logging.info(f"Prepared file contents for {file_name}.")

    # 3) Create or update the file in the new branch
    repo.create_file(
        path=file_name,
        message=commit_message,
        content=content,
        branch=new_branch_name
    )
    logging.info(f"Created or updated the file {file_name} in branch {new_branch_name}.")

    # 4) Upload image
    # Define the file path for the image within your repository.
    image_file_path = f"{RECIPES_FOLDER}/{technical_title}/image.jpg"

    # Set a commit message for the image file
    commit_message_image = f"Add image for recipe {technical_title}"

    # Create the image file in the new branch
    repo.create_file(
        path=image_file_path,
        message=commit_message_image,
        content=compressed_image_bytes,  # Image content must be in bytes.
        branch=new_branch_name
    )
    logging.info(f"Uploaded image to {image_file_path} in branch {new_branch_name}.")

    # 5) Create Pull Request
    pr = repo.create_pull(
        title=f"New Recipe from script: {new_branch_name}",
        body="Auto-generated recipe PR. Please review.",
        head=new_branch_name,
        base="master"
    )
    logging.info(f"Pull request created: {pr.html_url}")

    return pr.html_url

# ---------------------------------------------------------------------------------
# 3. Streamlit app
# ---------------------------------------------------------------------------------

def main():
    # We will use session_state to hold intermediate data between steps
    if "final_recipe" not in st.session_state:
        st.session_state.final_recipe = ""
    if "compressed_image_bytes" not in st.session_state:
        st.session_state.compressed_image_bytes = ""
    if "technical_title" not in st.session_state:
        st.session_state.technical_title = ""

    st.title("Recipe Converter")

    # ---------------------------------------------------------------------------------
    # STEP 1: If we do NOT have a final recipe, show the input form.
    # ---------------------------------------------------------------------------------
    if not st.session_state.final_recipe:
        with st.form("recipe_form"):
            st.write("Enter either a link to scrape a recipe or paste the recipe directly.")
            recipe_link = st.text_input("Recipe Link (optional)")
            recipe_text = st.text_area("Or, Paste Recipe Text Here (if no link was provided)", height=200)
            user_instructions = st.text_area("Additional Instructions/Comments (optional)", height=100)
            submitted = st.form_submit_button("Convert & Preview")

        if submitted:
            # Validate input
            if not recipe_link and not recipe_text.strip():
                st.error("Please provide either a link or some recipe text.")
                return
            
            if recipe_link:
                try:
                    with st.spinner("Scraping recipe from provided link..."):
                        recipe_text = scrape_recipe(recipe_link)
                except Exception as e:
                    st.error(f"Error scraping recipe: {e}")
                    return
            
            if not recipe_text.strip():
                st.error("No recipe text found or scraping failed.")
                return
            
            try:
                with st.spinner("Calling OpenAI to reformat recipe..."):
                    final_recipe = call_openai_for_recipe(recipe_text, user_instructions)
                
                # Attempt to parse out the technical title from the final_recipe
                technical_title_search = re.search(r'technical_title\s*=\s*"([^"]+)"', final_recipe)
                if technical_title_search:
                    technical_title = technical_title_search.group(1)
                else:
                    technical_title = "untitled-recipe"
                
                # Store results in session_state
                st.session_state.final_recipe = final_recipe
                st.session_state.technical_title = technical_title
                # We'll skip generating an image automatically here, 
                # letting the user do it in the preview step.
                
                st.rerun()  # move to next step
            except Exception as e:
                st.error(f"An error occurred: {e}")

    # ---------------------------------------------------------------------------------
    # STEP 2: We have a final recipe. Show a preview, let user adjust, generate image, etc.
    # ---------------------------------------------------------------------------------
    else:
        st.subheader("Preview & Edit Recipe")
        # We'll show the user two text areas:
        # 1. The front matter (between +++ +++)
        # 2. The body (rest of the text)
        # Or simpler: just let them edit the entire thing in one text area. 
        # We'll also show a markdown preview of the entire text below.

        edited_recipe = st.text_area("Edit your recipe in Markdown below:", 
                                     value=st.session_state.final_recipe, 
                                     height=400)
        
        # Show a "Preview" (rendered Markdown) below. We'll replace the front matter +++ blocks with a table or we can just show it raw as well.
        # For clarity, let's just preview the entire text as raw Markdown. 
        st.markdown("---")
        st.markdown("### Preview (Markdown Rendered)")
        # Because frontmatter may cause issues in pure st.markdown, let's slice out the front matter for a nicer preview.
        # But simplest is just show the entire text and let Streamlit do its best:
        st.markdown(edited_recipe)
        st.markdown("---")
        
        # Update session_state if the user modifies the text area
        st.session_state.final_recipe = edited_recipe

        # Handle image generation or display
        st.subheader("Recipe Image")
        # Show the current image if available
        if st.session_state.compressed_image_bytes:
            st.image(st.session_state.compressed_image_bytes, use_container_width=True)
        else:
            st.write("No image generated yet.")
        
        # Provide controls for generating or regenerating an image
        with st.form("image_generation_form"):
            extra_instructions = st.text_input("Extra instructions for image generation:", "")
            gen_image_submitted = st.form_submit_button("Generate/Regenerate Image")
        
        if gen_image_submitted:
            with st.spinner("Generating recipe image..."):
                compressed_image_bytes = generate_recipe_image(st.session_state.final_recipe, extra_instructions)
                st.session_state.compressed_image_bytes = compressed_image_bytes
            st.rerun()

        # Once user is satisfied, they can create the PR
        st.subheader("Create Pull Request")
        if st.button("Create Pull Request"):
            with st.spinner("Creating GitHub branch, committing, and opening PR..."):
                try:
                    pr_url = create_github_pr(
                        st.session_state.final_recipe,
                        st.session_state.compressed_image_bytes,
                        st.session_state.technical_title
                    )
                    st.success("Recipe successfully processed and pull request created!")
                    st.markdown(f"**Pull Request URL**: [{pr_url}]({pr_url})")
                except Exception as e:
                    st.error(f"An error occurred while creating the PR: {e}")

if __name__ == "__main__":
    main()