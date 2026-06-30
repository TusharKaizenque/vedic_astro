import logging
from collections.abc import AsyncGenerator

from config import settings
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)


async def _stream_with_model(
    messages: list[dict], model: str, max_tokens: int = 2400
) -> AsyncGenerator[str, None]:
    stream = await get_llm_client().chat.completions.create(
        model=model, messages=messages, temperature=0.72, max_tokens=max_tokens, stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content


def _is_rate_limit(exc: Exception) -> bool:
    return "rate_limit" in str(exc).lower() or "429" in str(exc)


def _approx_tokens(text: str) -> int:
    return len(text) // 4  # rough chars-per-token estimate, good enough for budgeting


def _trim_messages(messages: list[dict], max_input_tokens: int) -> list[dict]:
    """Shrink the prompt to fit a tighter-budget fallback model (e.g. 8b at 6k TPM).

    Keeps every message but truncates the single largest one (the context-heavy system
    prompt with retrieved chunks), preserving its head (instructions + chart/verdict) and
    tail (output-format rules) — the bulky middle retrieval context is what gets cut."""
    total = sum(_approx_tokens(m.get("content", "")) for m in messages)
    if total <= max_input_tokens:
        return messages
    trimmed = [dict(m) for m in messages]
    idx = max(range(len(trimmed)), key=lambda i: len(trimmed[i].get("content", "")))
    others = total - _approx_tokens(trimmed[idx]["content"])
    allowed_chars = max(2000, (max_input_tokens - others)) * 4
    content = trimmed[idx]["content"]
    if len(content) > allowed_chars:
        head = content[: int(allowed_chars * 0.7)]
        tail = content[-int(allowed_chars * 0.3):]
        trimmed[idx]["content"] = (
            head + "\n\n[... supporting detail trimmed to fit the fallback model ...]\n\n" + tail
        )
    return trimmed


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

    # Primary was rate-limited — retry once on the fallback model. The fallback (8b) has a
    # tight per-minute token cap, so trim the prompt to fit and cap output accordingly,
    # otherwise the fallback 413s on large prompts and the reading never completes.
    try:
        logger.info("Retrying synthesis on fallback model '%s'", fallback)
        fb_messages = _trim_messages(messages, max_input_tokens=3800)
        async for token in _stream_with_model(fb_messages, fallback, max_tokens=1500):
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
