"""
Embeddings client — independent of the LLM provider (Groq has no embeddings endpoint).

Uses OpenAI text-embedding-3-small by default.
Configure via EMBEDDING_API_KEY + EMBEDDING_BASE_URL to use any OpenAI-compatible
embedding provider (e.g. a local model served via LM Studio, Ollama, etc.).
If no embedding key is available, returns [] so the system degrades to text-only search.
"""
import asyncio
import logging

from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)
_client: AsyncOpenAI | None = None
# Free embedding tiers (e.g. Jina) cap concurrent requests — serialize to 2 at a time
# so multi-topic retrieval doesn't trip the provider's concurrency limit.
_semaphore = asyncio.Semaphore(2)


def _get_client() -> AsyncOpenAI | None:
    global _client
    if _client is not None:
        return _client
    api_key = settings.embedding_api_key or settings.openai_api_key
    if not api_key or api_key.startswith("test-"):
        return None
    kwargs: dict = {"api_key": api_key}
    if settings.embedding_base_url:
        kwargs["base_url"] = settings.embedding_base_url
    _client = AsyncOpenAI(**kwargs)
    return _client


async def embed(text: str) -> list[float]:
    """Generate an embedding vector for text. Returns [] if embeddings unavailable."""
    client = _get_client()
    if client is None:
        return []
    try:
        async with _semaphore:
            resp = await client.embeddings.create(
                model=settings.embedding_model,
                input=text,
                dimensions=settings.embedding_dimensions,
            )
        return resp.data[0].embedding
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        return []


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts. Returns list of [] on failure."""
    client = _get_client()
    if client is None:
        return [[] for _ in texts]
    try:
        resp = await client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
            dimensions=settings.embedding_dimensions,
        )
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]
    except Exception as exc:
        logger.warning("Batch embedding failed: %s", exc)
        return [[] for _ in texts]
