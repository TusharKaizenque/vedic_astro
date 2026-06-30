"""
Coverage guarantee — make sure the narration actually mentions every very-high signature.

The signature engine surfaces the chart's strongest, most-supported themes and the prompt is
told to LEAD with them. That's soft. This module is the hard backstop: after the reading
streams, it checks whether each required signature actually appears in the prose (by theme
keywords, since the narrative paraphrases). Any that were dropped are handed to a short,
plain-language continuation so a strongly-indicated theme is never silently omitted.

Mirrors the faithfulness verifier, but checks for COMPLETENESS rather than correctness.
"""
from __future__ import annotations

import logging

from config import settings
from services.chart_signatures import ChartSignature
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# Each signature label carries a UNIQUE fragment (e.g. only the marriage label contains
# "marriage", only the delayed-success label contains "perseverance"), so fragment→keywords
# never collides — important because the marriage label also contains the word "delay".
_THEME_RULES: dict[str, set[str]] = {
    "wealth": {"wealth", "rich", "afflu", "prosper", "money", "financ", "abundan", "fortune"},
    "struggle": {"struggle", "hardship", "obstacle", "setback", "difficult", "adversit",
                 "resilien", "perseverance"},
    "perseverance": {"delay", "patien", "gradual", "matur", "slow", "eventual", "persever",
                     "later in life"},
    "spiritual": {"spiritual", "occult", "mystic", "inward", "meditat", "detach", "moksha",
                  "liberation", "seclus", "philosoph", "metaphys"},
    "marriage": {"marriage", "marri", "partner", "spouse", "relationship"},
    "eminence": {"authorit", "eminence", "prominen", "status", "leadership", "recogn",
                 "power", "fame", "public", "high position", "influen"},
    "intellect": {"intellect", "intelligen", "scholar", "learning", "knowledge", "analytic",
                  "sharp mind", "wisdom", "studious"},
    "constitution": {"health", "illness", "constitution", "vitality", "body", "wellbeing",
                     "physical", "energy levels"},
    "foreign": {"foreign", "abroad", "relocat", "overseas", "away from", "distant land",
                "settle elsewhere"},
    "adversity": {"adversit", "crisis", "reversal", "turnaround", "comeback", "rise through"},
}


def _keyset(label: str) -> set[str] | None:
    low = label.lower()
    for fragment, keywords in _THEME_RULES.items():
        if fragment in low:
            return keywords
    return None


def is_covered(text: str, signature: ChartSignature) -> bool:
    """True if the prose plausibly mentions the signature's theme (or theme is unmapped)."""
    keywords = _keyset(signature.label)
    if not keywords:
        return True  # no mapping → don't force a continuation for an unknown theme
    low = text.lower()
    return any(k in low for k in keywords)


def missing_signatures(text: str, signatures: list[ChartSignature]) -> list[ChartSignature]:
    """Signatures whose theme never surfaced in the narration."""
    return [s for s in signatures if not is_covered(text, s)]


_ADDENDUM_SYSTEM = (
    "You are continuing a Vedic astrology reading already shown to the user. In 2-4 sentences "
    "of plain, second-person language — NO headers, NO planet/house names, NO Sanskrit, NO "
    "jargon — naturally continue the reading to bring out the strongly-indicated themes below "
    "that it has not yet covered. Do not repeat earlier points, do not restate the chart, do "
    "not announce that you are adding anything. Just continue the reading as flowing prose."
)


async def generate_addendum(missing: list[ChartSignature]) -> str:
    """Best-effort short continuation covering the dropped themes. Returns '' on any failure
    (the main reading already stands) — coverage is additive, never a hard dependency."""
    if not missing:
        return ""
    themes = "\n".join(f"- {s.label}: {'; '.join(s.evidence[:3])}" for s in missing)
    try:
        resp = await get_llm_client().chat.completions.create(
            model=settings.openai_synthesis_model,
            messages=[
                {"role": "system", "content": _ADDENDUM_SYSTEM},
                {"role": "user", "content": f"Themes to weave in:\n{themes}"},
            ],
            temperature=0.6,
            max_tokens=320,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.warning("Coverage addendum generation failed; leaving reading as-is", exc_info=True)
        return ""
