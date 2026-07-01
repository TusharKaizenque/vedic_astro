"""
Arudha Lagna analysis — the public image, status and reputation (how the world PERCEIVES the
native), as distinct from the true self shown by the lagna.

Classical reading: the Arudha Lagna (AL) sign and its lord set the persona; benefics in or
aspecting the AL give an esteemed, prosperous, well-regarded image; malefics give a
formidable, feared, or struggling one; an empty, unaspected AL gives a private/understated
public presence. Wealth-as-perceived (the visible affluence) is read from the 2nd and 11th
from the AL. Deterministic — a function of the chart only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from utils.arudha import arudha_lagna_index
from utils.astro_constants import NATURAL_BENEFICS, NATURAL_MALEFICS, SIGN_RULERS, ZODIAC_SIGNS


def _ord(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@dataclass
class ArudhaReading:
    al_sign: str
    al_house_from_lagna: int
    al_lord: str
    al_lord_house: int
    occupants: list[str] = field(default_factory=list)
    wealth_image_planets: list[str] = field(default_factory=list)
    tone: str = ""
    notes: list[str] = field(default_factory=list)


def build_arudha_reading(chart: NormalizedChart) -> ArudhaReading | None:
    al_idx = arudha_lagna_index(chart)
    if al_idx is None:
        return None
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign)
    al_sign = ZODIAC_SIGNS[al_idx]
    al_house = ((al_idx - lagna_idx) % 12) + 1
    al_lord = SIGN_RULERS.get(al_sign, "")
    al_lord_pos = chart.planets.get(al_lord)
    al_lord_house = al_lord_pos.house if al_lord_pos else 0

    occupants = [n for n, p in chart.planets.items() if p.sign == al_sign]
    benefics = [n for n in occupants if n in NATURAL_BENEFICS]
    malefics = [n for n in occupants if n in NATURAL_MALEFICS]
    # Visible wealth: planets in the 2nd and 11th from the AL.
    dhana_signs = {ZODIAC_SIGNS[(al_idx + 1) % 12], ZODIAC_SIGNS[(al_idx + 10) % 12]}
    wealth_planets = [n for n, p in chart.planets.items() if p.sign in dhana_signs]

    if benefics and not malefics:
        tone = "an esteemed, well-regarded and prosperous public image"
    elif malefics and not benefics:
        tone = "a formidable or hard-won public image — respected through strength or struggle"
    elif benefics and malefics:
        tone = "a mixed public image — admired in some ways, contested in others"
    else:
        tone = "an understated, private public presence — the world sees less than the reality"

    reading = ArudhaReading(
        al_sign=al_sign, al_house_from_lagna=al_house, al_lord=al_lord,
        al_lord_house=al_lord_house, occupants=occupants,
        wealth_image_planets=[p for p in wealth_planets if p in NATURAL_BENEFICS],
        tone=tone,
    )
    if benefics:
        reading.notes.append(f"benefic(s) {', '.join(benefics)} shape the image → repute and grace")
    if malefics:
        reading.notes.append(f"malefic(s) {', '.join(malefics)} shape the image → power, edge, or friction")
    return reading


def format_arudha_for_prompt(reading: ArudhaReading | None) -> str:
    if reading is None:
        return ""
    lines = ["[ARUDHA LAGNA — public image & reputation (how the world perceives you, vs the "
             "true self of the lagna)]"]
    lines.append(
        f"Arudha Lagna in {reading.al_sign} (the {_ord(reading.al_house_from_lagna)} from lagna), "
        f"lord {reading.al_lord} in the {_ord(reading.al_lord_house)} house — {reading.tone}."
    )
    for n in reading.notes:
        lines.append(f"  - {n}")
    if reading.wealth_image_planets:
        lines.append(f"  - visible affluence supported by {', '.join(reading.wealth_image_planets)} "
                     f"(benefics in the 2nd/11th from the Arudha).")
    return "\n".join(lines)
