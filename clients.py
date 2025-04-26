# external
import httpx
from openai import AsyncOpenAI
from pinecone import PineconeAsyncio
from supabase import acreate_client

# internal
from models import Setting


openai_client = None
# pinecone_index = None
http_client = None
# supabase_client = None


async def setup_clients() -> None:
    global openai_client

    settings = Setting()

    http_client = httpx.AsyncClient()
    openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key, http_client=http_client
    )


async def close_clients() -> None:
    global http_client
    if http_client:
        await http_client.aclose()
