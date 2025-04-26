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
from models import RecipeInput, RecipeAnalysisResult, ReplacementsResult, ReplacementsProcessedResult, ShoppingListResult


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
        result = await recipe.handle_recipe_input(
            request=request,
            allergies=allergies,
            dietary_preferences=dietary_preferences,
            recipe_link=recipe_link,
            ingredients=ingredients,
        )

        return {
            "success": result.success,
            "ingredients": result.ingredients,
            "message": result.message,
        }
    except HTTPException:
        raise
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


@app.get("/replacements")
async def replacements_page(request: Request) -> ReplacementsResult:
    return await recipe.handle_replacements(request)


@app.post("/process-replacements")
async def process_replacements(request: Request) -> ReplacementsProcessedResult:
    return await recipe.process_replacements(request)


@app.get("/process-shopping")
async def process_shopping(request: Request) -> ShoppingListResult:
    return await recipe.handle_shopping_list(request)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
