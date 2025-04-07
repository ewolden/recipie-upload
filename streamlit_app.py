import os
import re
import requests
from openai import OpenAI
import streamlit as st
from bs4 import BeautifulSoup
from github import Github  # PyGithub
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------------
# 1. Configuration
#    You can store these in environment variables, streamlit secrets, or just inline
# ---------------------------------------------------------------------------------
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")  # e.g., "myuser/myrecipes"
RECIPES_FOLDER = "content/post"  # folder in your repo for recipe files

client = OpenAI(
    # This is the default and can be omitted
    api_key=os.getenv("OPENAI_API_KEY")
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
    image = "leave this field blank"
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
    - ALWAYS include the amount of each ingredient used throughout the recipe, make it bold for clrity.
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
    # response = client.responses.create(
    #     model="gpt-4.5-preview",
    #     input=prompt,
    #     instructions="You are transforming food recipes into a specific markdown format. Respond only with the converted recipe markdown, nothing else.",
    # )
    logging.info("Received response from OpenAI")
    #generated_text = response.output_text
    generated_text = """technical_title = "title"
          placeholder """
    return generated_text

def generate_recipe_image(recipe_text: str) -> str:
    """
    Generate an image using OpenAI (DALL·E) based on the recipe text.
    Here we try to identify a 'title' to pass as a prompt to DALL·E.
    """
    lines = recipe_text.splitlines()
    potential_title = lines[0] if lines else "Delicious Dish"
    
    # Clean prompt
    prompt_for_dalle = re.sub(r"[^a-zA-Z0-9\s]", "", potential_title)
    prompt_for_dalle = f"High-quality food photography of {prompt_for_dalle}, plated"
    
    dalle_response = client.Image.create(
        prompt=prompt_for_dalle,
        n=1,
        size="1024x1024"
    )
    return dalle_response["data"][0]["url"]

def create_github_pr(final_recipe: str, image_url: str, technical_title: str) -> str:
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
    new_branch_name = f"recipe/{technical_title}"  # random
    repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source.commit.sha)
    logging.info(f"Created a new branch: {new_branch_name} from master.")

    # 2) Prepare file contents
    file_name = f"{RECIPES_FOLDER}/{technical_title}/index.md"
    commit_message = f"Add new recipe {new_branch_name}"
    content = f"{final_recipe}"
    logging.info(f"Prepared file contents for {file_name}.")

    # 3) Create or update the file in the new branch
    repo.create_file(
        path=file_name,
        message=commit_message,
        content=content,
        branch=new_branch_name
    )
    logging.info(f"Created or updated the file {file_name} in branch {new_branch_name}.")

    # 4) Create Pull Request
    pr = repo.create_pull(
        title=f"New Recipe from script: {new_branch_name}",
        body="Auto-generated recipe PR. Please review.",
        head=new_branch_name,
        base="main"
    )
    logging.info(f"Pull request created: {pr.html_url}")

    return pr.html_url

# ---------------------------------------------------------------------------------
# 3. Streamlit app
# ---------------------------------------------------------------------------------
def main():
    st.title("Recipe Converter")
    
    with st.form("recipe_form"):
        st.write("Enter either a link to scrape a recipe or paste the recipe directly.")
        recipe_link = st.text_input("Recipe Link (optional)")
        recipe_text = st.text_area("Or, Paste Recipe Text Here (if no link was provided)", height=200)
        user_instructions = st.text_area("Additional Instructions/Comments (optional)", height=100)
        
        submitted = st.form_submit_button("Convert & Submit to GitHub")
    
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
            
            # Extract technical name from markdown
            technical_title = re.search(r"technical_title = \"(.*?)\"", final_recipe)
            if technical_title:
                technical_title = technical_title.group(1)
            else:
                st.error("Could not extract technical title from the recipe.")
                return
            
            #with st.spinner("Generating recipe image (DALL·E)..."):
            #    image_url = generate_recipe_image(final_recipe)
            image_url = None
            
            with st.spinner("Creating GitHub branch, committing, and opening PR..."):
                pr_url = create_github_pr(final_recipe, image_url, technical_title)
            
            st.success("Recipe successfully processed and pull request created!")
            st.markdown(f"**Pull Request URL**: [{pr_url}]({pr_url})")
            st.markdown(f"**Image URL**: [{image_url}]({image_url})")
            st.write("---")
            st.write("### Generated Recipe:")
            st.code(final_recipe)
        
        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
