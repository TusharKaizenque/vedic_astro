"""
Faithfulness verifier — the anti-hallucination check (research point R2 #9).

Grounding the prompt in a locked facts block reduces fabrication but doesn't eliminate it:
a model can still assert "Jupiter in the 5th" when the chart says the 8th. This module
decomposes generated prose into atomic, checkable claims — planet→house, planet→sign — and
validates each against the deterministic chart. Contradictions are returned so the caller
can log them (a hallucination metric) or surface a correction.

Deliberately conservative: it only flags claims it can match unambiguously to a placement,
so a correct reading is never wrongly accused. Lordship phrasing ("lord of the 5th",
"rules the 5th") is excluded — only literal placement ("in the 5th house") is checked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from models.chart import NormalizedChart
from utils.astro_constants import ZODIAC_SIGNS

_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
_PLANET_RE = "|".join(_PLANETS)
_SIGN_RE = "|".join(ZODIAC_SIGNS)

# "Jupiter in the 8th house" / "Mars posited in the 10th house" — placement, not lordship.
_HOUSE_CLAIM = re.compile(
    rf"\b({_PLANET_RE})\s+(?:is\s+)?(?:placed\s+|posited\s+|situated\s+)?"
    rf"in\s+the\s+(\d{{1,2}})(?:st|nd|rd|th)\s+house",
    re.IGNORECASE,
)
# Looser variant without "house": "Ketu in the 12th". Still requires the ordinal.
_HOUSE_CLAIM_SHORT = re.compile(
    rf"\b({_PLANET_RE})\s+in\s+the\s+(\d{{1,2}})(?:st|nd|rd|th)\b",
    re.IGNORECASE,
)
# "Mercury in Gemini" — planet in a named sign (placement).
_SIGN_CLAIM = re.compile(
    rf"\b({_PLANET_RE})\b\s+(?:is\s+)?(?:placed\s+|posited\s+|situated\s+)?in\s+({_SIGN_RE})\b",
    re.IGNORECASE,
)
# Phrases that mean lordship, not placement — skip a match if this precedes "in the Nth".
_LORDSHIP_GUARD = re.compile(r"lord|rule[sr]?|owns?", re.IGNORECASE)


@dataclass
class Contradiction:
    planet: str
    claim: str           # what the text asserted
    actual: str          # what the chart says
    kind: str            # "house" | "sign"


def _norm_planet(name: str) -> str:
    return name.capitalize()


def verify_response(text: str, chart: NormalizedChart) -> list[Contradiction]:
    """Return placement claims in `text` that contradict the chart. Empty list = faithful."""
    if not text:
        return []
    found: list[Contradiction] = []
    seen: set[tuple] = set()

    def _check_house(planet: str, house_str: str, snippet: str) -> None:
        planet = _norm_planet(planet)
        pos = chart.planets.get(planet)
        if not pos:
            return
        try:
            claimed = int(house_str)
        except ValueError:
            return
        if not (1 <= claimed <= 12):
            return
        if claimed != pos.house:
            key = (planet, "house", claimed)
            if key not in seen:
                seen.add(key)
                found.append(Contradiction(
                    planet=planet, claim=f"{planet} in the {claimed}th house",
                    actual=f"{planet} is in house {pos.house} ({pos.sign})", kind="house",
                ))

    for rx in (_HOUSE_CLAIM, _HOUSE_CLAIM_SHORT):
        for m in rx.finditer(text):
            # Skip if the matched span is lordship phrasing ("lord of ... in the 5th").
            window = text[max(0, m.start() - 20):m.start()]
            if _LORDSHIP_GUARD.search(window):
                continue
            _check_house(m.group(1), m.group(2), m.group(0))

    for m in _SIGN_CLAIM.finditer(text):
        planet = _norm_planet(m.group(1))
        claimed_sign = m.group(2).capitalize()
        pos = chart.planets.get(planet)
        if not pos or not pos.sign:
            continue
        if claimed_sign != pos.sign:
            key = (planet, "sign", claimed_sign)
            if key not in seen:
                seen.add(key)
                found.append(Contradiction(
                    planet=planet, claim=f"{planet} in {claimed_sign}",
                    actual=f"{planet} is in {pos.sign}", kind="sign",
                ))
    return found
