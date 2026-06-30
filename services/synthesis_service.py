import logging
from collections.abc import AsyncGenerator

from config import settings
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# User-facing failure messages streamed when synthesis can't complete. They are surfaced to
# the user (so they get feedback) but the router uses these markers to AVOID persisting a
# failed reading as if it were real conversation history.
_ERR_GENERIC = "\n\nI encountered an error generating your reading. Please try again."
_ERR_LIMIT = ("\n\nThe astrology AI service has reached its daily usage limit. "
              "Your chart analysis is complete, but the written summary can't be "
              "generated right now — please try again later.")
ERROR_MARKERS = (_ERR_GENERIC, _ERR_LIMIT)


def is_error_reply(text: str) -> bool:
    """True if the streamed text ended in a synthesis-failure sentinel (don't persist it)."""
    return any(text.rstrip().endswith(m.rstrip()) for m in ERROR_MARKERS)


async def _stream_with_model(
    messages: list[dict], model: str, max_tokens: int = 2400
) -> AsyncGenerator[str, None]:
    # Low temperature: the verdict and chart facts are deterministic, so we want a faithful,
    # repeatable narration — NOT creative variation. High temp was the main reason re-asking
    # the same question produced different (and drifting) answers.
    stream = await get_llm_client().chat.completions.create(
        model=model, messages=messages, temperature=0.35, max_tokens=max_tokens, stream=True,
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
            yield _ERR_GENERIC
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
            yield _ERR_LIMIT
        else:
            yield _ERR_GENERIC


async def generate_reading(messages: list[dict], max_tokens: int = 2400) -> str:
    """Non-streamed full reading (the DRAFT for the verification pass). Tries the primary, then
    the fallback model on ANY primary failure (not only rate-limits), and returns the same
    user-facing error sentinel as stream_response on total failure (never a bare '')."""
    primary = settings.openai_synthesis_model
    fallback = settings.openai_reasoning_model
    attempts = [(primary, max_tokens, messages)]
    if fallback and fallback != primary:
        attempts.append((fallback, 1500, _trim_messages(messages, 3800)))
    last_exc: Exception | None = None
    for model, mt, msgs in attempts:
        try:
            resp = await get_llm_client().chat.completions.create(
                model=model, messages=msgs, temperature=0.35, max_tokens=mt,
            )
            text = resp.choices[0].message.content or ""
            if text:
                return text
        except Exception as exc:
            last_exc = exc
            logger.warning("Draft synthesis on '%s' failed: %s", model, exc)
    return _ERR_LIMIT if (last_exc and _is_rate_limit(last_exc)) else _ERR_GENERIC


async def generate_response(messages: list[dict]) -> str:
    response = await get_llm_client().chat.completions.create(
        model=settings.openai_classifier_model,
        messages=messages,
        temperature=0.3,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""
