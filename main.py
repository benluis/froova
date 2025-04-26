# external
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

# internal
import clients
import recipe


@asynccontextmanager
async def lifespan(app: FastAPI):
    await clients.setup_clients()
    yield
    await clients.close_clients()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the main SPA page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/submit-recipe")
async def submit_recipe(
    request: Request,
    allergies: str = Form("None"),
    dietary_preferences: str = Form(""),
    recipe_link: Optional[str] = Form(None),
    ingredients: Optional[str] = Form(None),
):
    """Process recipe input and return structured ingredient data as JSON"""
    try:
        input_data = recipe.RecipeInput(
            allergies=allergies,
            dietary_preferences=dietary_preferences,
            recipe_link=recipe_link,
            ingredients=ingredients,
        )

        if not input_data.recipe_link and not input_data.ingredients:
            raise ValueError("Please provide either a recipe link or ingredients")

        dietary_restrictions: str = f"Allergies: {input_data.allergies}, Preferences: {input_data.dietary_preferences}"

        if input_data.recipe_link:
            recipe_text: str = await recipe.save_recipe_from_url(input_data.recipe_link)
            recipe.data_store.ingredients_df = await recipe.extract_ingredients_from_text(
                recipe_text, dietary_restrictions
            )
        else:
            recipe.data_store.ingredients_df = await recipe.extract_ingredients_from_text(
                input_data.ingredients, dietary_restrictions
            )

        if recipe.data_store.ingredients_df.empty:
            raise ValueError("Failed to extract ingredients from provided content")

        # Find alternatives for ingredients that can't be eaten
        for index, row in recipe.data_store.ingredients_df.iterrows():
            if row.get("can_not_eat", False):
                alternatives = await recipe.suggest_alternatives(row["name"])
                recipe.data_store.ingredients_df.at[index, "alternatives"] = alternatives
            else:
                recipe.data_store.ingredients_df.at[index, "alternatives"] = []

        # Return JSON response instead of HTML template
        return {
            "success": True,
            "ingredients": recipe.data_store.ingredients_df.to_dict("records")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing recipe: {str(e)}"
        )


@app.get("/api/ingredients")
async def get_ingredients_api():
    """Get the current ingredients list as JSON"""
    try:
        ingredients = await recipe.get_ingredients()
        return ingredients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/alternatives")
async def get_alternatives_api(ingredient: str = Form(...)):
    """Get alternative ingredients for a specific ingredient"""
    try:
        alternatives = await recipe.suggest_alternatives(ingredient)
        return {"alternatives": alternatives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products")
async def get_products_api():
    """Get products for the current ingredients"""
    try:
        products = await recipe.get_products()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Legacy routes can be removed once SPA is fully implemented
@app.get("/input-recipe", response_class=HTMLResponse)
async def input_recipe_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("input_recipe.html", {"request": request})


@app.get("/replacements", response_class=HTMLResponse)
async def replacements_page(request: Request) -> HTMLResponse:
    return await recipe.handle_replacements(request)


@app.post("/process-replacements")
async def process_replacements(request: Request) -> HTMLResponse:
    return await recipe.process_replacements(request)


@app.get("/process-shopping", response_class=HTMLResponse)
async def process_shopping(request: Request) -> HTMLResponse:
    return await recipe.handle_shopping_list(request)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)