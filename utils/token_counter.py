from functools import lru_cache

import tiktoken

MODEL_ENCODING_MAP = {
    "gpt-4o": "o200k_base", "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base", "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}


@lru_cache(maxsize=8)
def _get_encoding(model: str):
    return tiktoken.get_encoding(MODEL_ENCODING_MAP.get(model, "o200k_base"))


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    return len(_get_encoding(model).encode(text))


def count_messages_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    return 2 + sum(
        4 + count_tokens(str(m.get("role", "")), model)
        + count_tokens(str(m.get("content", "")), model)
        for m in messages
    )


def trim_to_budget(text: str, max_tokens: int, model: str = "gpt-4o") -> str:
    encoding = _get_encoding(model)
    return encoding.decode(encoding.encode(text)[:max_tokens])
