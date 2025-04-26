# external
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )
    openai_api_key: str
    # pinecone_api_key: str = None
    # pinecone_host: str = None
    # supabase_url: str = None
    # supabase_key: str = None


class Ingredient(BaseModel):
    name: str
    volume: Optional[str] = None
    weight: Optional[str] = None
    can_not_eat: bool = False


class Product(BaseModel):
    type: str
    name: str
    price: str
    store: str
    image_url: Optional[str] = None


class Recipe(BaseModel):
    title: Optional[str] = None
    ingredients: list[Ingredient] = []
    url: Optional[str] = None
    text: Optional[str] = None


class RecipeInput(BaseModel):
    allergies: str = "None"
    dietary_preferences: str = ""
    recipe_link: Optional[str] = None
    ingredients: Optional[str] = None


class IngredientList(BaseModel):
    ingredients: List[Dict[str, Any]]


class ProductList(BaseModel):
    products: List[Dict[str, Any]]
