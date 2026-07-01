"""
Sudarshana Chakra — read a house from ALL THREE references at once: the Lagna, the Moon, and
the Sun. A matter is genuinely strong only when it is well-supported from more than one of these
vantage points; support from just one is a weaker promise. This is the classical multi-vantage
'confirmation' principle applied to a single topic house.

Deterministic: for the topic house counted from each of the three lagnas, weigh the natural
benefic vs malefic planets occupying (or opposing) that sign, plus the house lord's dignity.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.planetary_states import dignity_of
from utils.astro_constants import (
    NATURAL_BENEFICS, NATURAL_MALEFICS, SIGN_RULERS, ZODIAC_SIGNS,
)

_STRONG_DIGNITY = {"exalted", "moolatrikona", "own sign"}
_WEAK_DIGNITY = {"debilitated", "enemy sign"}


@dataclass
class SudarshanaReading:
    house: int
    per_reference: dict[str, str] = field(default_factory=dict)   # "Lagna"/"Moon"/"Sun" -> verdict
    confirmations: int = 0                                        # count of supportive vantages


def _house_tone(chart: NormalizedChart, ref_sign: str, house: int) -> str:
    """Verdict for `house` counted from `ref_sign`: supported / afflicted / mixed / clear."""
    if ref_sign not in ZODIAC_SIGNS:
        return "clear"
    ref_idx = ZODIAC_SIGNS.index(ref_sign)
    target_idx = (ref_idx + house - 1) % 12
    target_sign = ZODIAC_SIGNS[target_idx]
    opposite_sign = ZODIAC_SIGNS[(target_idx + 6) % 12]     # planets in the 7th aspect back
    ben = mal = 0
    for name, pos in chart.planets.items():
        if pos.sign == target_sign:                         # occupying
            ben += name in NATURAL_BENEFICS
            mal += name in NATURAL_MALEFICS
        elif pos.sign == opposite_sign:                     # aspecting (opposition)
            ben += 0.5 * (name in NATURAL_BENEFICS)
            mal += 0.5 * (name in NATURAL_MALEFICS)
    # House lord's dignity nudges the tone.
    lord = SIGN_RULERS.get(target_sign, "")
    lp = chart.planets.get(lord)
    if lp:
        dig = dignity_of(lord, lp.sign, lp.degree_in_sign)
        if dig in _STRONG_DIGNITY:
            ben += 1
        elif dig in _WEAK_DIGNITY:
            mal += 1
    if ben and ben > mal:
        return "supported"
    if mal and mal > ben:
        return "afflicted"
    if ben and mal:
        return "mixed"
    return "clear"


def sudarshana_reading(chart: NormalizedChart, house: int) -> SudarshanaReading:
    moon = chart.planets.get("Moon")
    sun = chart.planets.get("Sun")
    refs = {
        "Lagna": chart.lagna_sign,
        "Moon": moon.sign if moon else "",
        "Sun": sun.sign if sun else "",
    }
    reading = SudarshanaReading(house=house)
    for name, sign in refs.items():
        if not sign:
            continue
        verdict = _house_tone(chart, sign, house)
        reading.per_reference[name] = verdict
        if verdict == "supported":
            reading.confirmations += 1
    return reading


def format_sudarshana_for_prompt(reading: SudarshanaReading, topic: str) -> str:
    if not reading.per_reference:
        return ""
    parts = ", ".join(f"{ref}: {v}" for ref, v in reading.per_reference.items())
    n = reading.confirmations
    total = len(reading.per_reference)
    if n >= 2:
        verdict = f"strongly confirmed — supported from {n} of {total} vantage points"
    elif n == 1:
        verdict = "partially confirmed — supported from only one vantage point"
    else:
        verdict = "not confirmed from any vantage point — a weaker promise for this matter"
    return (
        f"[SUDARSHANA CHAKRA — the {topic} house ({reading.house}th) read from Lagna, Moon and "
        f"Sun together]\n  {parts}. This matter is {verdict}."
    )
