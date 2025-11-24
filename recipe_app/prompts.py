"""Prompt templates shared across the application."""
from __future__ import annotations

import re

RECIPE_PROMPT_TEMPLATE = """\
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

IMAGE_PROMPT_TEMPLATE = (
    "A cartoon sketch of the food, inspired by the illustrative style used in The Great British Bake Off, "
    "characterized by bold lines, vibrant colors, and a playful, whimsical feel. Never have text in the image."
    "It should depict {title} which is {description}. {extra_instructions}"
)

TECHNICAL_TITLE_PATTERN = re.compile(r'technical_title\s*=\s*"([^"]+)"')


__all__ = [
    "IMAGE_PROMPT_TEMPLATE",
    "RECIPE_PROMPT_TEMPLATE",
    "TECHNICAL_TITLE_PATTERN",
]
