from openai import AsyncOpenAI
from config import settings


def get_llm_client() -> AsyncOpenAI:
    kwargs: dict = {"api_key": settings.llm_api_key or settings.openai_api_key}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return AsyncOpenAI(**kwargs)
