# built-in
import os
import requests
from io import StringIO
from pathlib import Path
from typing import List, Dict, Any, Optional

# external
import pypdf
from fastapi import HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import asyncio

# internal
import clients
from models import RecipeInput
from scraper import scrape_and_get_products, Store

templates = Jinja2Templates(directory="templates")


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
) -> HTMLResponse:
    """
    Main handler for recipe input, processes recipe from either link or raw text.
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

        dietary_restrictions: str = (
            f"Allergies: {input_data.allergies}, Preferences: {input_data.dietary_preferences}"
        )

        if input_data.recipe_link:
            recipe_text: str = await save_recipe_from_url(input_data.recipe_link)
            data_store.ingredients_df = await extract_ingredients_from_text(
                recipe_text, dietary_restrictions
            )
        else:
            data_store.ingredients_df = await extract_ingredients_from_text(
                input_data.ingredients, dietary_restrictions
            )

        if data_store.ingredients_df.empty:
            raise ValueError("Failed to extract ingredients from provided content")

        return templates.TemplateResponse(
            "ingredients.html",
            {
                "request": request,
                "ingredients": data_store.ingredients_df.to_dict("records"),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing recipe: {str(e)}"
        )


async def save_recipe_from_url(url: str) -> str:
    """Download a recipe webpage and save its content for OpenAI processing."""
    if not url:
        raise ValueError("Empty URL provided")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Create a local HTTP client instead of relying on the global one
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            html_content = response.text

        # Create directory for recipes
        os.makedirs("recipes", exist_ok=True)

        # Save HTML content
        html_path = os.path.join("recipes", "recipe_source.html")

        def write_file(path, content):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(write_file, html_path, html_content)

        # Process with BeautifulSoup
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'form']):
            element.decompose()

        # Try structured data first (Schema.org)
        recipe_json = soup.select_one('script[type="application/ld+json"]')
        if recipe_json:
            import json
            try:
                data = json.loads(recipe_json.string)
                if isinstance(data, dict) and ('recipeIngredient' in data or 'recipe' in data):
                    ingredients = data.get('recipeIngredient') or data.get('recipe', {}).get('recipeIngredient', [])
                    instructions = data.get('recipeInstructions') or data.get('recipe', {}).get('recipeInstructions',
                                                                                                '')
                    if ingredients:
                        ingredients_text = "\n".join(ingredients)
                        formatted_text = f"Ingredients:\n{ingredients_text}\n\nInstructions:\n{instructions}"

                        text_path = os.path.join("recipes", "recipe_text.txt")
                        await asyncio.to_thread(write_file, text_path, formatted_text)

                        return formatted_text
            except Exception as e:
                print(f"Error parsing JSON-LD: {e}")

        # Find recipe content in common containers
        recipe_content = None
        selectors = ['div[class*="recipe"]', 'div[class*="ingredients"]', 'article', 'main', 'div[class*="content"]']

        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                if len(element.get_text(strip=True)) > 200:
                    recipe_content = element
                    break
            if recipe_content:
                break

        # Fallback to body if no specific recipe content found
        if not recipe_content:
            recipe_content = soup.find("main") or soup.find("body")

        # Extract and clean text
        text = recipe_content.get_text(separator="\n\n") if recipe_content else soup.get_text(separator="\n\n")
        formatted_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

        # Save text
        text_path = os.path.join("recipes", "recipe_text.txt")
        await asyncio.to_thread(write_file, text_path, formatted_text)

        return formatted_text

    except Exception as e:
        print(f"Error in save_recipe_from_url: {str(e)}")
        raise RuntimeError(f"Error processing recipe URL: {str(e)}")


def get_recipe_content(url: str) -> str:
    """Get recipe content from a URL, whether it's a PDF or HTML webpage."""
    if not url:
        raise ValueError("Empty URL provided")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()

        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            pdf_path = save_pdf(url)
            return extract_text_from_pdf(pdf_path)
        else:
            return extract_text_from_html(response.text)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download content: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error processing URL: {str(e)}")


def extract_text_from_html(html: str) -> str:
    """Extract recipe content from HTML."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, and navigation elements
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()

        # Get main content or article
        main_content = soup.find("main") or soup.find("article") or soup.find("body")
        if main_content:
            text = main_content.get_text(separator="\n")

            # Clean up text
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            return text

        return soup.get_text(separator="\n")
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from HTML: {str(e)}")


def save_pdf(url: str) -> str:
    """Download and save a PDF from a URL."""
    if not url:
        raise ValueError("Empty URL provided")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/pdf" not in content_type and not url.lower().endswith(".pdf"):
            raise ValueError(
                f"URL does not appear to point to a PDF file. Please ensure you're sharing a direct link to a PDF file."
            )

        os.makedirs("pdfs", exist_ok=True)
        pdf_path = os.path.join("pdfs", "recipe.pdf")
        with open(pdf_path, "wb") as f:
            f.write(response.content)

        if not os.path.getsize(pdf_path) > 0:
            raise ValueError("Downloaded PDF file is empty")

        return pdf_path
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download PDF: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error saving PDF: {str(e)}")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file with enhanced robustness for web-printed PDFs."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")

    try:
        text = ""
        with open(pdf_path, "rb") as f:
            try:
                pdf_reader = pypdf.PdfReader(f)

                if len(pdf_reader.pages) == 0:
                    raise ValueError("PDF file contains no pages")

                for i, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as page_err:
                        print(
                            f"Warning: Could not extract text from page {i + 1}: {page_err}"
                        )
                        continue

                if not text.strip():
                    print("Text extraction failed, trying OCR approach...")
            except Exception as e:
                raise ValueError(f"Invalid or corrupted PDF file: {str(e)}")

        if not text.strip():
            raise ValueError(
                "No text could be extracted from PDF. Please ensure the PDF contains selectable text, not just images."
            )

        return text
    except ValueError as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {str(e)}")


async def extract_ingredients_from_text(
    text: str, dietary_restrictions: str
) -> pd.DataFrame:
    """Extract structured ingredient data from text using AI."""
    try:
        prompt = (
            f"Extract ingredients from the following recipe text. "
            f"Consider these dietary restrictions: {dietary_restrictions}\n\n"
            f"Return a JSON array with objects containing 'name', 'volume', 'weight', and 'can_not_eat' (boolean) fields.\n\n"
            f"Recipe text:\n{text}"
        )

        response = await clients.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Extract structured ingredient data from recipe text.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        import json

        data = json.loads(content)

        if "ingredients" not in data:
            return pd.DataFrame(columns=["name", "volume", "weight", "can_not_eat"])

        return pd.DataFrame(data["ingredients"])
    except Exception as e:
        print(f"Error extracting ingredients: {e}")
        return pd.DataFrame(columns=["name", "volume", "weight", "can_not_eat"])


async def handle_replacements(request: Request) -> HTMLResponse:
    """Handle replacements page rendering."""
    try:
        if data_store.ingredients_df.empty:
            raise ValueError("No ingredients found. Please submit a recipe first.")

        data_store.replacement_df = data_store.ingredients_df.copy()

        for index, row in data_store.replacement_df.iterrows():
            if row.get("can_not_eat", False):
                alternatives = await suggest_alternatives(row["name"])
                data_store.replacement_df.at[index, "alternatives"] = alternatives
            else:
                data_store.replacement_df.at[index, "alternatives"] = []

        return templates.TemplateResponse(
            "replacements.html",
            {
                "request": request,
                "ingredients": data_store.replacement_df.to_dict("records"),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error handling replacements: {str(e)}"
        )


async def suggest_alternatives(ingredient_name: str) -> List[str]:
    """Suggest alternative ingredients using AI."""
    try:
        response = await clients.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Suggest alternative ingredients."},
                {
                    "role": "user",
                    "content": f"Suggest 3 alternatives for {ingredient_name} that are commonly available.",
                },
            ],
        )

        content = response.choices[0].message.content
        alternatives = [alt.strip() for alt in content.split(",")]
        return alternatives[:3]
    except Exception as e:
        print(f"Error suggesting alternatives: {e}")
        return ["Alternative not available"]


async def process_replacements(request: Request) -> HTMLResponse:
    """Process user-selected replacements."""
    try:
        form_data = await request.form()

        updated_df = data_store.ingredients_df.copy()

        for key, value in form_data.items():
            if key.startswith("replacement_") and value:
                idx = int(key.replace("replacement_", ""))

                if idx < len(updated_df):
                    original_ingredient = updated_df.iloc[idx]["name"]
                    updated_df.at[idx, "name"] = value
                    updated_df.at[idx, "original_ingredient"] = original_ingredient
                    updated_df.at[idx, "can_not_eat"] = False

        data_store.ingredients_df = updated_df

        return templates.TemplateResponse(
            "replacements_processed.html",
            {"request": request, "message": "Replacements processed successfully"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing replacements: {str(e)}"
        )


async def handle_shopping_list(request: Request) -> HTMLResponse:
    """
    Handle shopping list generation and display.
    """
    try:
        products = await get_products()

        products_by_store = {}
        for product in products:
            store = product.get("store", "Unknown")
            if store not in products_by_store:
                products_by_store[store] = []
            products_by_store[store].append(product)

        return templates.TemplateResponse(
            "shopping_list.html",
            {
                "request": request,
                "products": products,
                "products_by_store": products_by_store,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating shopping list: {str(e)}"
        )


async def get_ingredients() -> List[Dict[str, Any]]:
    """
    Get the current ingredients list.

    Returns:
        List of ingredient dictionaries
    """
    try:
        if data_store.ingredients_df.empty:
            return []

        return data_store.ingredients_df.to_dict("records")
    except Exception as e:
        print(f"Error getting ingredients: {e}")
        return []


async def get_products() -> List[Dict[str, Any]]:
    """
    Get products from stores by scraping product information in parallel.

    Returns:
        List of product dictionaries
    """
    try:
        if data_store.ingredients_df.empty:
            return []

        ingredient_names = data_store.ingredients_df["name"].tolist()

        if not ingredient_names:
            return []

        products = await scrape_and_get_products(
            product_names=ingredient_names,
            stores=[Store.WALMART, Store.TARGET, Store.SPROUTS, Store.LIDL],
        )

        data_store.products_df = pd.DataFrame(products)

        return products
    except Exception as e:
        print(f"Error getting products: {e}")
        return []
