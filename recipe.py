# built-in
import json
from typing import List, Dict, Any, Optional

# external
from fastapi import HTTPException, Request, Form
import httpx
from bs4 import BeautifulSoup
import pandas as pd

# internal
import clients
from scraper import scrape_and_get_products, Store
from models import RecipeInput, RecipeAnalysisResult, ReplacementsResult, ReplacementsProcessedResult, ShoppingListResult


class RecipeDataStore:
    def __init__(self):
        self.ingredients_df = pd.DataFrame()
        self.products_df = pd.DataFrame()
        self.replacement_df = pd.DataFrame()


data_store = RecipeDataStore()


async def handle_recipe_input(
        request: Request,
        allergies: str = Form("None"),
        dietary_preferences: str = Form(""),
        recipe_link: Optional[str] = Form(None),
        ingredients: Optional[str] = Form(None),
) -> RecipeAnalysisResult:
    """
    Main handler for recipe input, processes recipe from either link or raw text.
    Returns structured data instead of HTML.
    """
    try:
        input_data = RecipeInput(
            allergies=allergies,
            dietary_preferences=dietary_preferences,
            recipe_link=recipe_link,
            ingredients=ingredients,
        )

        if not input_data.recipe_link and not input_data.ingredients:
            raise ValueError("Please provide either a recipe link or ingredients")

        dietary_restrictions: str = f"Allergies: {input_data.allergies}, Preferences: {input_data.dietary_preferences}"

        if input_data.recipe_link:
            recipe_text: str = await get_recipe_content(input_data.recipe_link)
            data_store.ingredients_df = await extract_ingredients_from_text(
                recipe_text, dietary_restrictions
            )
        else:
            data_store.ingredients_df = await extract_ingredients_from_text(
                input_data.ingredients, dietary_restrictions
            )

        if data_store.ingredients_df.empty:
            raise ValueError("Failed to extract ingredients from provided content")

        # Return structured data instead of template
        return RecipeAnalysisResult(
            success=True,
            ingredients=data_store.ingredients_df.to_dict("records")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing recipe: {str(e)}"
        )


async def get_recipe_content(url: str) -> str:
    """
    Download and extract text from a recipe webpage asynchronously.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            return extract_text_from_html(response.text)
    except httpx.RequestError as e:
        raise ValueError(f"Error fetching recipe URL: {e}")


def extract_text_from_html(html: str) -> str:
    """
    Extract readable text from HTML content.
    """
    soup = BeautifulSoup(html, 'html.parser')

    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)

    return text


async def extract_ingredients_from_text(recipe_text: str, dietary_restrictions: str) -> pd.DataFrame:
    """
    Extract ingredients from recipe text using OpenAI and format into a DataFrame.
    Includes both original ingredients and alternatives in a single API call.

    Args:
        recipe_text: Text containing recipe ingredients
        dietary_restrictions: String containing allergy and dietary preference info

    Returns:
        DataFrame containing structured ingredient information with alternatives
    """
    if not recipe_text or recipe_text.strip() == "":
        return pd.DataFrame()

    try:
        response = await clients.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                    "You are a recipe analyzer that identifies ingredients and their compatibility with dietary restrictions. "
                    "Extract every ingredient with quantities from the recipe, determine if each is compatible with "
                    "the provided dietary restrictions, and suggest alternatives for incompatible ingredients."},
                {"role": "user", "content":
                    f"Analyze this recipe and identify all ingredients:\n\n{recipe_text}\n\n"
                    f"Dietary restrictions to consider: {dietary_restrictions}"}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "extract_ingredients",
                        "description": "Extract ingredients from recipe with dietary compatibility",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ingredients": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                                "type": "string",
                                                "description": "The name of the ingredient"
                                            },
                                            "volume": {
                                                "type": "string",
                                                "description": "Volume measurement (e.g., '1 cup', '2 tbsp')",
                                                "nullable": True
                                            },
                                            "weight": {
                                                "type": "string",
                                                "description": "Weight measurement (e.g., '200g', '1 lb')",
                                                "nullable": True
                                            },
                                            "can_not_eat": {
                                                "type": "boolean",
                                                "description": "Whether the ingredient conflicts with dietary restrictions"
                                            },
                                            "reason": {
                                                "type": "string",
                                                "description": "Reason why the ingredient conflicts with dietary restrictions",
                                                "nullable": True
                                            },
                                            "alternatives": {
                                                "type": "array",
                                                "items": {
                                                    "type": "string"
                                                },
                                                "description": "Alternative ingredients that meet dietary restrictions"
                                            }
                                        },
                                        "required": ["name", "can_not_eat"]
                                    }
                                }
                            },
                            "required": ["ingredients"]
                        }
                    }
                }
            ],
            tool_choice={"type": "function", "function": {"name": "extract_ingredients"}}
        )

        args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        ingredients_list = args.get("ingredients", [])

        if not ingredients_list:
            print("No ingredients extracted")
            return pd.DataFrame()

        df = pd.DataFrame(ingredients_list)

        if 'alternatives' not in df.columns:
            df['alternatives'] = [[] for _ in range(len(df))]
        if 'reason' not in df.columns:
            df['reason'] = ""

        return df

    except Exception as e:
        print(f"Error extracting ingredients: {e}")
        return pd.DataFrame()


async def get_ingredients() -> List[Dict[str, Any]]:
    """Get the current ingredients list as dictionary records"""
    if data_store.ingredients_df.empty:
        return []
    return data_store.ingredients_df.to_dict("records")


async def get_products() -> List[Dict[str, Any]]:
    """Get products from stores by scraping product information"""
    try:
        if data_store.ingredients_df.empty:
            return []

        ingredient_names = data_store.ingredients_df["name"].tolist()

        products = await scrape_and_get_products(
            ingredient_names,
            stores=[Store.WALMART, Store.TARGET]
        )

        return products
    except Exception as e:
        print(f"Error getting products: {e}")
        return []


async def handle_replacements(request: Request) -> ReplacementsResult:
    """Return replacement options in a structured format"""
    try:
        ingredients = await get_ingredients()
        return ReplacementsResult(
            success=True,
            ingredients=ingredients
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_replacements(request: Request) -> ReplacementsProcessedResult:
    """Process user selected replacements and return structured results"""
    form_data = await request.form()
    replacements = []

    for key, value in form_data.items():
        if key.startswith("replace_") and value:
            ingredient_idx = int(key.split("_")[1])
            original = data_store.ingredients_df.iloc[ingredient_idx]["name"]
            replacements.append({"original": original, "replacement": value})

    for replacement in replacements:
        idx = data_store.ingredients_df[data_store.ingredients_df["name"] == replacement["original"]].index
        if not idx.empty:
            data_store.ingredients_df.at[idx[0], "name"] = replacement["replacement"]
            data_store.ingredients_df.at[idx[0], "can_not_eat"] = False

    return ReplacementsProcessedResult(
        success=True,
        replacements=replacements
    )


async def handle_shopping_list(request: Request) -> ShoppingListResult:
    """Generate and return shopping list data in structured format"""
    try:
        ingredients = await get_ingredients()
        products = await get_products()

        return ShoppingListResult(
            success=True,
            ingredients=ingredients,
            products=products
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))