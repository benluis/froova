# built-in
import json
import asyncio

# external
import httpx
from fastapi import HTTPException, Request
from pinecone import QueryResponse

# internal
from models import SearchParams, Repository, SearchResult
import clients


async def handle_search(request: Request, q: str = "") -> SearchResult:
    try:
        search_params: SearchParams = await extract_keywords(q)

        github_results: list[Repository] = await search_github(search_params, limit=10)
        await parallel_upsert(github_results)
        pinecone_results: QueryResponse = await search_pinecone(q, top_k=5)
        results: SearchResult = SearchResult(
            pinecone_results=pinecone_results.matches,
            github_results=github_results,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def embed_text(text: str) -> list[float]:
    if not text:
        raise ValueError("Cannot embed empty text")

    text: str = text.replace("\n", " ")
    try:
        response = await clients.openai_client.embeddings.create(
            input=text, model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error embedding text: {e}")
        raise RuntimeError(f"Failed to generate embedding: {str(e)}")


async def extract_keywords(nl_query: str) -> SearchParams:
    if not nl_query or nl_query.strip() == "":
        raise ValueError("Empty search query")

    try:
        response = await clients.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Extract search parameters from this query about code. Return a JSON with 'keywords' and 'languages'.",
                },
                {"role": "user", "content": nl_query},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "extract_params",
                        "description": "Extract search parameters",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "keywords": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "languages": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["keywords", "languages"],
                        },
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "extract_params"}},
        )

        args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        keywords: list[str] = args.get("keywords")
        languages: list[str] = args.get("languages", [])

        if not keywords:
            raise ValueError("Failed to extract meaningful keywords from query")

        return SearchParams(keywords=keywords, languages=languages)
    except Exception as e:
        print(f"Error extracting search parameters: {e}")
        raise RuntimeError(f"Failed to extract search parameters: {str(e)}")


async def search_github(
    search_params: SearchParams, limit: int = 10
) -> list[Repository]:
    if not search_params.keywords:
        raise ValueError("No search keywords provided")

    token: str = clients.github_token
    base_url: str = "https://api.github.com/search/repositories"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    query: str = " ".join(search_params.keywords)
    if search_params.languages:
        for lang in search_params.languages:
            query += f" language:{lang}"

    params: dict[str, str | int] = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": limit,
    }

    try:
        response = await clients.http_client.get(
            base_url, headers=headers, params=params
        )
        response.raise_for_status()

        repo_data: list[dict] = response.json().get("items", [])
        repos: list[Repository] = []

        for repo in repo_data:
            repos.append(
                Repository(
                    id=str(repo["id"]),
                    full_name=repo["full_name"],
                    html_url=repo["html_url"],
                    description=repo.get("description") or repo["full_name"],
                    language=repo.get("language") or "Unknown",
                    stargazers_count=repo.get("stargazers_count", 0),
                )
            )
        return repos
    except httpx.HTTPStatusError as e:
        print(f"GitHub API error: {e}")
        raise RuntimeError(f"GitHub API returned error: {e.response.status_code}")
    except Exception as e:
        print(f"GitHub search error: {e}")
        raise RuntimeError(f"Failed to search GitHub: {str(e)}")


async def search_pinecone(query_text: str, top_k: int = 3):
    if not query_text:
        raise ValueError("Empty search query for Pinecone")

    try:
        query_vector: list[float] = await embed_text(query_text)
        response = await clients.pinecone_index.query(
            vector=query_vector, top_k=top_k, namespace="", include_metadata=True
        )
        return response
    except Exception as e:
        print(f"Pinecone search error: {e}")
        raise RuntimeError(f"Failed to search Pinecone: {str(e)}")


async def parallel_upsert(repositories: list[Repository]) -> None:
    if not repositories:
        return

    try:
        embedding_tasks = [embed_text(repo.description) for repo in repositories]
        embeddings: list[list[float] | Exception] = await asyncio.gather(
            *embedding_tasks, return_exceptions=True
        )
        pinecone_records = []
        for i, embedding in enumerate(embeddings):
            if isinstance(embedding, Exception):
                continue

            repo: Repository = repositories[i]
            pinecone_records.append(
                {
                    "id": repo.id,
                    "values": embedding,
                    "metadata": {
                        "full_name": repo.full_name,
                        "url": repo.html_url,
                        "description": repo.description,
                        "language": repo.language,
                        "stars": repo.stargazers_count,
                    },
                }
            )

        await clients.pinecone_index.upsert(vectors=pinecone_records)
    except Exception as e:
        print(f"Error in parallel upsert: {e}")
        raise RuntimeError(f"Failed to upsert data to Pinecone: {str(e)}")
