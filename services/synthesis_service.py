import logging
from collections.abc import AsyncGenerator

from config import settings
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)


async def _stream_with_model(messages: list[dict], model: str) -> AsyncGenerator[str, None]:
    stream = await get_llm_client().chat.completions.create(
        model=model, messages=messages, temperature=0.72, max_tokens=1500, stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content


def _is_rate_limit(exc: Exception) -> bool:
    return "rate_limit" in str(exc).lower() or "429" in str(exc)


async def stream_response(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Stream the synthesis. If the primary model is rate-limited, fall back to the
    smaller/faster model (separate quota bucket) so the reading still completes."""
    primary = settings.openai_synthesis_model
    fallback = settings.openai_reasoning_model  # e.g. llama-3.1-8b-instant — separate TPD

    emitted = False
    try:
        async for token in _stream_with_model(messages, primary):
            emitted = True
            yield token
        return
    except Exception as exc:
        logger.warning("Primary synthesis model '%s' failed: %s", primary, exc)
        # Don't restart on the fallback if we already streamed part of an answer
        # (would duplicate text); only fall back on a clean rate-limit before output.
        if emitted or not (_is_rate_limit(exc) and fallback and fallback != primary):
            yield "\n\nI encountered an error generating your reading. Please try again."
            return

    # Primary was rate-limited — retry once on the fallback model.
    try:
        logger.info("Retrying synthesis on fallback model '%s'", fallback)
        async for token in _stream_with_model(messages, fallback):
            yield token
    except Exception as exc:
        logger.exception("Fallback synthesis also failed")
        if _is_rate_limit(exc):
            yield ("\n\nThe astrology AI service has reached its daily usage limit. "
                   "Your chart analysis is complete, but the written summary can't be "
                   "generated right now — please try again later.")
        else:
            yield "\n\nI encountered an error generating your reading. Please try again."


async def generate_response(messages: list[dict]) -> str:
    response = await get_llm_client().chat.completions.create(
        model=settings.openai_classifier_model,
        messages=messages,
        temperature=0.3,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""
