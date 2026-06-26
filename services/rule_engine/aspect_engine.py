"""Graha drishti (planetary aspect) engine — Parashara system.

All planets cast a full aspect on the 7th house from themselves.
Mars, Jupiter, and Saturn have additional special aspects.
Rahu/Ketu aspects are debated; we follow the common school (5th and 9th).
"""
from models.chart import NormalizedChart
from utils.astro_constants import NATURAL_BENEFICS, NATURAL_MALEFICS

SPECIAL_ASPECTS: dict[str, list[int]] = {
    "Mars":    [4, 7, 8],
    "Jupiter": [5, 7, 9],
    "Saturn":  [3, 7, 10],
    "Rahu":    [5, 7, 9],
    "Ketu":    [5, 7, 9],
}

_DEFAULT_ASPECTS = [7]


def _aspected_houses(from_house: int, offsets: list[int]) -> list[int]:
    return [((from_house - 1 + offset - 1) % 12) + 1 for offset in offsets]


def get_aspects_by_planet(chart: NormalizedChart) -> dict[str, list[int]]:
    """Return {planet_name: [list of house numbers it aspects]}."""
    result: dict[str, list[int]] = {}
    for planet, pos in chart.planets.items():
        offsets = SPECIAL_ASPECTS.get(planet, _DEFAULT_ASPECTS)
        result[planet] = _aspected_houses(pos.house, offsets)
    return result


def planets_aspecting_house(chart: NormalizedChart, house: int) -> list[str]:
    """Return names of all planets that cast an aspect on `house`."""
    aspects = get_aspects_by_planet(chart)
    return [planet for planet, houses in aspects.items() if house in houses]


def houses_aspected_by_planet(chart: NormalizedChart, planet: str) -> list[int]:
    """Return all house numbers aspected by `planet`."""
    pos = chart.planets.get(planet)
    if not pos:
        return []
    offsets = SPECIAL_ASPECTS.get(planet, _DEFAULT_ASPECTS)
    return _aspected_houses(pos.house, offsets)


def aspect_quality(planet: str, functional_nature: str = "") -> str:
    """Classify the quality of a planet's aspect as benefic / malefic / neutral.

    Functional nature (for this lagna) takes precedence over natural nature, because
    a functional benefic's aspect helps the topic even if the planet is a natural
    malefic, and vice versa. Falls back to natural nature when functional is unknown.
    """
    if functional_nature in ("benefic", "yogakaraka"):
        return "benefic"
    if functional_nature == "malefic":
        return "malefic"
    # Fall back to natural nature
    if planet in NATURAL_BENEFICS:
        return "benefic"
    if planet in NATURAL_MALEFICS:
        return "malefic"
    return "neutral"
