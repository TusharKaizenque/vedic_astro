"""
Ashtakavarga Engine — D3 of Phase D.

Computes Bhinnashtakavarga (BAV, per-planet bindus) and Sarvashtakavarga (SAV, total
bindus per sign) from the D-1 chart, per BPHS Ch.66. These are the classics' own
*numeric* strength measure for a sign/house — a real, cited number (not an invented
score) that the assessment uses to corroborate the verdict for a topic house.

Reference benchmarks (SAV per sign, total = 337 across 12 signs, average ~28):
  >= 30 bindus → strong house     |  <= 25 bindus → weak house
"""
from __future__ import annotations

from models.chart import NormalizedChart
from utils.astro_constants import ASHTAKAVARGA_CONTRIBUTIONS, ZODIAC_SIGNS

_CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]
_BAV_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

SAV_STRONG = 30
SAV_WEAK = 25


def _sign_index(longitude: float) -> int:
    return int(longitude // 30) % 12


def _reference_index(chart: NormalizedChart, reference: str) -> int | None:
    if reference == "Lagna":
        if chart.lagna_sign in ZODIAC_SIGNS:
            return ZODIAC_SIGNS.index(chart.lagna_sign)
        return None
    pos = chart.planets.get(reference)
    return _sign_index(pos.longitude) if pos else None


def compute_bav(chart: NormalizedChart) -> dict[str, list[int]]:
    """Bhinnashtakavarga: {planet: [bindus per sign, 12 entries indexed Aries..Pisces]}."""
    bav: dict[str, list[int]] = {p: [0] * 12 for p in _BAV_PLANETS}
    for planet in _BAV_PLANETS:
        table = ASHTAKAVARGA_CONTRIBUTIONS.get(planet, {})
        for reference in _CONTRIBUTORS:
            ref_idx = _reference_index(chart, reference)
            if ref_idx is None:
                continue
            for house_num in table.get(reference, []):
                target = (ref_idx + house_num - 1) % 12
                bav[planet][target] += 1
    return bav


def compute_sav(chart: NormalizedChart) -> list[int]:
    """Sarvashtakavarga: total bindus per sign (12 entries, Aries..Pisces)."""
    bav = compute_bav(chart)
    sav = [0] * 12
    for planet in _BAV_PLANETS:
        for i in range(12):
            sav[i] += bav[planet][i]
    return sav


def _house_sign_index(chart: NormalizedChart, house: int) -> int | None:
    if chart.lagna_sign not in ZODIAC_SIGNS:
        return None
    lagna = ZODIAC_SIGNS.index(chart.lagna_sign)
    return (lagna + house - 1) % 12


def sav_for_house(chart: NormalizedChart, house: int, sav: list[int] | None = None) -> int:
    """SAV bindus in a whole-sign house (0 if lagna unknown)."""
    sav = sav if sav is not None else compute_sav(chart)
    idx = _house_sign_index(chart, house)
    return sav[idx] if idx is not None else 0


def bav_for_planet_in_house(chart: NormalizedChart, planet: str, house: int) -> int:
    """A planet's own BAV bindus in a whole-sign house."""
    idx = _house_sign_index(chart, house)
    if idx is None:
        return 0
    return compute_bav(chart).get(planet, [0] * 12)[idx]


def sav_band(bindus: int) -> str:
    """Classify a SAV value: strong / average / weak."""
    if bindus >= SAV_STRONG:
        return "strong"
    if bindus <= SAV_WEAK:
        return "weak"
    return "average"


def format_ashtakavarga_for_prompt(chart: NormalizedChart, houses: list[int]) -> str:
    """Compact SAV readout for the topic's primary houses."""
    sav = compute_sav(chart)
    lines = ["[ASHTAKAVARGA — Sarvashtakavarga bindus (classical numeric strength)]"]
    for h in houses:
        b = sav_for_house(chart, h, sav)
        lines.append(f"  House {h}: {b} bindus ({sav_band(b)})")
    lines.append("  (>=30 strong, <=25 weak, avg ~28; total 337)")
    return "\n".join(lines)
