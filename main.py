# external
from fastapi import FastAPI, Request, Form
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
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/input-recipe", response_class=HTMLResponse)
async def input_recipe_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("input_recipe.html", {"request": request})


@app.post("/submit-recipe")
async def submit_recipe(
    request: Request,
    allergies: str = Form("None"),
    dietary_preferences: str = Form(""),
    recipe_link: Optional[str] = Form(None),
    ingredients: Optional[str] = Form(None),
) -> HTMLResponse:
    return await recipe.handle_recipe_input(
        request, allergies, dietary_preferences, recipe_link, ingredients
    )


@app.get("/replacements", response_class=HTMLResponse)
async def replacements_page(request: Request) -> HTMLResponse:
    return await recipe.handle_replacements(request)


@app.post("/process-replacements")
async def process_replacements(request: Request) -> HTMLResponse:
    return await recipe.process_replacements(request)


@app.get("/process-shopping", response_class=HTMLResponse)
async def process_shopping(request: Request) -> HTMLResponse:
    return await recipe.handle_shopping_list(request)


@app.get("/api/ingredients")
async def api_ingredients() -> List[Dict[str, Any]]:
    return await recipe.get_ingredients()


@app.get("/api/products")
async def api_products() -> List[Dict[str, Any]]:
    return await recipe.get_products()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
