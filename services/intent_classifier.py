import json
import logging

from config import settings
from utils.llm_client import get_llm_client
from models.intent import IntentCategory, IntentEntities, IntentResult

logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = """Classify a Vedic astrology question. Return only JSON with:
intent (placement_interpretation, topic_reading, dasha_query, transit_query,
yoga_query, timing_query, comparison_query, clarification, general_astrology,
or out_of_domain), confidence, entities (planets, houses, signs, dashas, topics,
time_references), requires_chart, requires_transits, requires_dasha,
retrieval_topics, and reasoning. Use canonical planet/sign names. Set
requires_chart=false only for general_astrology and out_of_domain."""


# Phrases that signal a DESCRIPTIVE / quality question ("what is X like?") rather than a
# timing or good-bad question. These want traits drawn from the significator's sign,
# dignity, and placement — not a favourable/challenged verdict.
_DESCRIPTIVE_MARKERS = (
    "how will my", "how is my", "how will be my", "what is my", "what will my",
    "what kind of", "what type of", "describe my", "qualities of", "nature of",
    "what is she like", "what is he like", "what will she", "what will he",
    "tell me about my", "personality of", "character of", "how would my",
)


def is_descriptive_query(message: str) -> bool:
    """Heuristic: is this a 'what is X like / describe X' question (traits, not timing)?"""
    m = message.lower()
    if any(marker in m for marker in _DESCRIPTIVE_MARKERS):
        # Exclude clear timing phrasings that also start with "when/should".
        if not any(t in m for t in ("when will", "should i", "is it a good time", "good time to")):
            return True
    return False


async def classify_intent(message: str, recent_turns: list[dict] | None = None) -> IntentResult:
    context = "\n".join(
        f"{turn.get('role', 'user')}: {str(turn.get('content', ''))[:200]}"
        for turn in (recent_turns or [])[-2:]
    )
    client = get_llm_client()
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_classifier_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Message: {message}\nRecent context:\n{context}"},
                ],
                temperature=0.1,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content or "{}")
            return IntentResult(
                intent=IntentCategory(data.get("intent", "general_astrology")),
                confidence=float(data.get("confidence", 0.5)),
                entities=IntentEntities(**data.get("entities", {})),
                requires_chart=bool(data.get("requires_chart", True)),
                requires_transits=bool(data.get("requires_transits", False)),
                requires_dasha=bool(data.get("requires_dasha", False)),
                retrieval_topics=data.get("retrieval_topics", []),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as exc:
            # Catch broadly (incl. RateLimitError / network errors) so a classifier
            # failure degrades to a sensible default instead of crashing the chat.
            logger.warning("Classification attempt %s failed: %s", attempt + 1, exc)
    return IntentResult(
        intent=IntentCategory.GENERAL_ASTROLOGY,
        confidence=0.3,
        requires_chart=True,
        retrieval_topics=[message[:80]],
    )
