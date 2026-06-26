"""
Conjunction Engine (B2).

Detects planets sharing a house (and, more tightly, a sign), and classifies the
quality of each conjunction. Conjunctions are decisive in Parashari reasoning:
a benefic conjunct the 10th lord supports career; a malefic conjunct it afflicts.
The significator engine uses this to enrich a factor's classification.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from utils.astro_constants import NATURAL_BENEFICS, NATURAL_MALEFICS


@dataclass
class Conjunction:
    house: int
    planets: list[str]                       # all planets in the house
    benefics: list[str] = field(default_factory=list)
    malefics: list[str] = field(default_factory=list)


def get_conjunctions(chart: NormalizedChart) -> dict[int, Conjunction]:
    """Return {house: Conjunction} for every house with 2+ planets."""
    by_house: dict[int, list[str]] = {}
    for name, pos in chart.planets.items():
        by_house.setdefault(pos.house, []).append(name)

    result: dict[int, Conjunction] = {}
    for house, planets in by_house.items():
        if len(planets) < 2:
            continue
        result[house] = Conjunction(
            house=house,
            planets=planets,
            benefics=[p for p in planets if p in NATURAL_BENEFICS],
            malefics=[p for p in planets if p in NATURAL_MALEFICS],
        )
    return result


def planets_conjunct(chart: NormalizedChart, planet: str) -> list[str]:
    """Return the planets sharing a house with `planet` (excluding itself)."""
    pos = chart.planets.get(planet)
    if not pos:
        return []
    return [
        name for name, other in chart.planets.items()
        if name != planet and other.house == pos.house
    ]


def conjunction_influence(chart: NormalizedChart, planet: str) -> str:
    """Net influence of a planet's conjunctions: benefic / malefic / mixed / none.

    A planet conjunct only benefics is supported; conjunct only malefics is
    afflicted; conjunct both is mixed.
    """
    companions = planets_conjunct(chart, planet)
    if not companions:
        return "none"
    has_benefic = any(c in NATURAL_BENEFICS for c in companions)
    has_malefic = any(c in NATURAL_MALEFICS for c in companions)
    if has_benefic and has_malefic:
        return "mixed"
    if has_benefic:
        return "benefic"
    if has_malefic:
        return "malefic"
    return "none"
