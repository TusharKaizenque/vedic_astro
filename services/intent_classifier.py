import json
import logging
import re

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
# DESCRIPTIVE mode is for "what is this PERSON like" (spouse/child traits), not "how is my
# career" (a verdict). So it requires a person-subject OR an explicit trait word — otherwise
# "how is my career" would wrongly suppress the verdict.
_PERSON_SUBJECTS = (
    "spouse", "wife", "husband", "partner", "fiance", "fiancé", "fiancee",
    "boyfriend", "girlfriend", "children", "child", "son", "daughter", "kids",
)
_TRAIT_WORDS = (
    "personality", "character", "temperament", "qualities", "kind of person",
    "what kind of person", "look like", "appearance", "nature of",
)
_DESCRIBE_FRAMES = (
    "what is", "what will", "what does", "what's", "how is", "how will", "how would",
    "will my", "is my", "describe", "tell me about", "what type of", "what kind of",
)
# Explicit "describe / what kind of" requests are descriptive for ANY subject (a life-area
# or a person) — they ask for the nature/type, not a good-or-bad verdict.
_EXPLICIT_DESCRIBE = (
    "describe my", "describe the", "describe his", "describe her",
    "what kind of", "what type of", "what sort of",
)


# Broad "whole life" questions → multi-domain synthesis. STRONG markers always route to
# overview; WEAK markers ("overall", "future") do so ONLY when no specific topic is named,
# so "what is my overall CAREER outlook" stays a career question.
_LIFE_OVERVIEW_STRONG = (
    "my life", "about my life", "tell me about myself", "about me", "who am i",
    "what should i do with my life", "life path", "life purpose", "my purpose",
    "until now", "so far", "my journey", "whole life", "my destiny", "what does my life",
    "kind of person", "what kind of life", "read my chart", "complete reading",
    "tell me everything", "full reading", "entire life",
)
_LIFE_OVERVIEW_WEAK = ("overall", "general reading", "my future", "in the future", "what will i do")
_TOPIC_KEYWORDS = (
    "career", "job", "profession", "work", "business", "marriage", "married", "wife",
    "husband", "spouse", "partner", "relationship", "wealth", "money", "finance", "rich",
    "income", "health", "illness", "disease", "education", "study", "studies", "exam",
    "children", "child", "kids", "pregnan", "love", "romance", "property", "foreign",
    "marry", "marrying", "divorce",
)

# Deterministic timing backstop — fires regardless of the LLM classifier, so a missed
# classification can't silently drop the transit/forward-dasha pipeline.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_TIMING_PHRASES = (
    "when will", "when can", "when do", "when am i", "when is", "when shall",
    "what year", "which year", "how long until", "how long till", "years from now",
    "by what age", "at what age", "next year", "this year", "coming year",
    "next month", "coming months", "in coming",
)
_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")


def is_life_overview_query(message: str) -> bool:
    """Broad life-overview question → whole-chart synthesis across all domains."""
    m = message.lower()
    if any(marker in m for marker in _LIFE_OVERVIEW_STRONG):
        return True
    if any(marker in m for marker in _LIFE_OVERVIEW_WEAK) and not any(t in m for t in _TOPIC_KEYWORDS):
        return True
    return False


def is_descriptive_query(message: str) -> bool:
    """Is this a 'what is this PERSON like / describe X' question (traits, not a verdict/timing)?"""
    m = message.lower()
    # Timing/should-I framings are never descriptive.
    if any(t in m for t in ("when will", "should i", "is it a good time", "good time to")):
        return False
    # Explicit trait words or "describe/what kind of" → descriptive regardless of subject.
    if any(w in m for w in _TRAIT_WORDS) or any(w in m for w in _EXPLICIT_DESCRIBE):
        return True
    # A person-subject combined with a describe-frame ("what will my wife be like",
    # "will my spouse be educated", "is my husband ...").
    if any(s in m for s in _PERSON_SUBJECTS) and any(f in m for f in _DESCRIBE_FRAMES):
        return True
    return False


# Deterministic topic backstop — the LLM classifier often returns empty/ wrong topics
# (e.g. "what will my spouse be like" → no topic → defaults to career). Keyword detection
# guarantees the right topic bundle (and thus the spouse engine, wealth analysis, etc.).
_TOPIC_KEYWORDS_MAP: dict[str, tuple[str, ...]] = {
    "marriage": ("spouse", "wife", "husband", "partner", "marriage", "married", "marry",
                 "relationship", "fiance", "fiancé", "girlfriend", "boyfriend", "divorce"),
    "career": ("career", "job", "profession", "occupation", "business"),
    "wealth": ("wealth", "money", "finance", "financial", "rich", "income", "fortune", "savings"),
    "health": ("health", "illness", "disease", "ailment", "sickness"),
    "children": ("children", "child", "kids", "son", "daughter", "pregnan", "progeny", "conceive"),
    "education": ("education", "study", "studies", "exam", "college", "academic", "degree"),
    "spirituality": ("spiritual", "spirituality", "moksha", "occult", "meditation", "enlighten"),
}


def _augment_topics(result: IntentResult, message: str) -> IntentResult:
    """Add any keyword-detected topic the classifier missed, so routing is robust."""
    m = message.lower()
    existing = set(result.entities.topics)
    for topic, kws in _TOPIC_KEYWORDS_MAP.items():
        if topic not in existing and any(k in m for k in kws):
            result.entities.topics.append(topic)
            existing.add(topic)
    return result


def _augment_timing(result: IntentResult, message: str) -> IntentResult:
    """OR a deterministic timing signal into the (possibly LLM-derived) result, so an
    explicit year/month or 'when will…' always activates transits + forward dasha."""
    m = message.lower()
    years = [mt.group(0) for mt in _YEAR_RE.finditer(message)]
    months = [mo for mo in _MONTHS if mo in m]
    if years or months or any(p in m for p in _TIMING_PHRASES):
        result.requires_transits = True
        refs = list(result.entities.time_references)
        for tok in years + months:
            if tok not in refs:
                refs.append(tok)
        result.entities.time_references = refs
    return result


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
            # The LLM occasionally returns entities as a list or fields as scalars —
            # coerce defensively so a malformed shape degrades gracefully.
            ent = data.get("entities")
            ent = ent if isinstance(ent, dict) else {}
            ent = {k: (v if isinstance(v, list) else [v]) for k, v in ent.items() if v}
            retr = data.get("retrieval_topics", [])
            retr = retr if isinstance(retr, list) else [retr]
            result = IntentResult(
                intent=IntentCategory(data.get("intent", "general_astrology")),
                confidence=float(data.get("confidence", 0.5)),
                entities=IntentEntities(**ent),
                requires_chart=bool(data.get("requires_chart", True)),
                requires_transits=bool(data.get("requires_transits", False)),
                requires_dasha=bool(data.get("requires_dasha", False)),
                retrieval_topics=retr,
                reasoning=data.get("reasoning", ""),
            )
            return _augment_topics(_augment_timing(result, message), message)
        except Exception as exc:
            # Catch broadly (incl. RateLimitError / network errors) so a classifier
            # failure degrades to a sensible default instead of crashing the chat.
            logger.warning("Classification attempt %s failed: %s", attempt + 1, exc)
    # Fallback path still gets the deterministic timing + topic backstops.
    return _augment_topics(
        _augment_timing(
            IntentResult(
                intent=IntentCategory.GENERAL_ASTROLOGY,
                confidence=0.3,
                requires_chart=True,
                retrieval_topics=[message[:80]],
            ),
            message,
        ),
        message,
    )
