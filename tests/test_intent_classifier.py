import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.intent import IntentCategory
from services.intent_classifier import classify_intent


def _completion(content: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


@pytest.mark.asyncio
async def test_classify_marriage_question():
    payload = {
        "intent": "topic_reading", "confidence": 0.95,
        "entities": {"houses": [7], "topics": ["marriage"]},
        "requires_chart": True, "requires_transits": False, "requires_dasha": True,
        "retrieval_topics": ["marriage", "7th house", "Venus"], "reasoning": "Marriage topic",
    }
    with patch("services.intent_classifier.get_llm_client") as get_client:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_completion(json.dumps(payload)))
        get_client.return_value = client
        result = await classify_intent("What does my chart say about marriage?")
    assert result.intent == IntentCategory.TOPIC_READING
    assert result.confidence == 0.95
    assert result.requires_dasha


@pytest.mark.asyncio
async def test_fallback_on_json_error():
    with patch("services.intent_classifier.get_llm_client") as get_client:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_completion("not json {"))
        get_client.return_value = client
        result = await classify_intent("some question")
    assert result.intent == IntentCategory.GENERAL_ASTROLOGY
    assert result.confidence == 0.3
