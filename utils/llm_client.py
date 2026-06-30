from openai import AsyncOpenAI

from config import settings

_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    """Return a memoized AsyncOpenAI client. Constructing one per call leaks an httpx
    connection pool each time and defeats connection reuse, so we build it once."""
    global _client
    if _client is None:
        kwargs: dict = {"api_key": settings.llm_api_key or settings.openai_api_key}
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        _client = AsyncOpenAI(**kwargs)
    return _client
