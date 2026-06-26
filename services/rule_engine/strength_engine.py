"""
Strength Engine (A1) — classical Shadbala-lite.

Computes a documented, classical numeric strength per planet, used by the
assessment engine to decide which factor *wins* when supporting and afflicting
factors conflict. This is NOT an arbitrary point system: every component is a
Shadbala sub-bala defined in Brihat Parashara Hora Shastra, measured in virupas
(60 virupas = 1 rupa).

Components computed here (all derivable from the data we actually have —
sidereal longitude, sign, house, retrograde flag, Sun position):

  - Uchcha Bala   (exaltation strength) : dist-from-debilitation / 3      [max 60]
  - Naisargika    (natural strength)    : fixed BPHS ranking              [max 60]
  - Dig Bala      (directional)         : graded by house from strong pt  [max 60]
  - Cheshta Bala  (motional)            : retrograde → high; else proxy   [max 60]
  - Paksha Bala   (lunar-phase, part of Kala Bala)                        [max 60]
  - Combustion penalty                  : subtractive when within 6° Sun

Omitted (require exact time-of-day / sunrise / ayanamsa precision we don't have):
  Ayana, Hora, Tribhaga, Nathonnatha, Abda/Masa/Vara, Yuddha, Drik bala.
  These are documented as omitted so the score is not overclaimed.

The total is normalized to 0..1 (`relative`) and banded (strong/moderate/weak)
so downstream logic stays classical-but-simple.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from utils.astro_constants import (
    DIG_BALA_STRONG_HOUSE, EXALTATION_DEGREE, NAISARGIKA_BALA,
    NATURAL_BENEFICS,
)

# Max virupas per component we compute (used for normalization).
_COMPONENT_MAX = {
    "uchcha": 60.0,
    "naisargika": 60.0,
    "dig": 60.0,
    "cheshta": 60.0,
    "paksha": 60.0,
}
_TOTAL_MAX = sum(_COMPONENT_MAX.values())  # 300 virupas of computed components

# Band thresholds on normalized 0..1 strength.
_STRONG = 0.60
_MODERATE = 0.40


@dataclass
class PlanetStrength:
    planet: str
    components: dict[str, float] = field(default_factory=dict)  # virupas per sub-bala
    combustion_penalty: float = 0.0
    total_virupas: float = 0.0
    relative: float = 0.0       # 0..1 normalized
    band: str = "moderate"      # "strong" | "moderate" | "weak"
    notes: list[str] = field(default_factory=list)


def _uchcha_bala(planet: str, longitude: float) -> float:
    """Exaltation strength: distance from the debilitation point / 3 (virupas)."""
    exalt = EXALTATION_DEGREE.get(planet)
    if exalt is None:
        return 30.0  # Rahu/Ketu — neutral baseline
    debilitation = (exalt + 180.0) % 360.0
    diff = abs(longitude - debilitation) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return round(diff / 3.0, 2)  # 0 at debilitation, 60 at exaltation


def _dig_bala(planet: str, house: int) -> float:
    """Directional strength: 60 at the strong house, 0 at the opposite house."""
    strong = DIG_BALA_STRONG_HOUSE.get(planet)
    if strong is None or not (1 <= house <= 12):
        return 30.0
    # Houses are 30° apart; max angular separation is 6 houses (180°).
    sep = abs(house - strong)
    sep = min(sep, 12 - sep)        # circular house distance, 0..6
    return round(60.0 * (1.0 - sep / 6.0), 2)


def _cheshta_bala(planet: str, is_retrograde: bool) -> float:
    """Motional strength. Retrograde planets are classically very strong in cheshta.
    Sun/Moon never retrograde — give them a neutral baseline."""
    if planet in ("Sun", "Moon", "Rahu", "Ketu"):
        return 30.0
    return 50.0 if is_retrograde else 25.0


def _paksha_bala(planet: str, sun_long: float, moon_long: float) -> float:
    """Lunar-phase strength (part of Kala Bala). Benefics gain strength as the
    Moon waxes (distance from Sun grows toward 180°); malefics gain as it wanes."""
    elong = abs(moon_long - sun_long) % 360.0
    if elong > 180.0:
        elong = 360.0 - elong
    waxing_fraction = elong / 180.0          # 0 at new moon, 1 at full moon
    benefic = planet in NATURAL_BENEFICS
    value = waxing_fraction if benefic else (1.0 - waxing_fraction)
    return round(60.0 * value, 2)


def _combustion_penalty(planet: str, longitude: float, sun_long: float) -> float:
    """Subtractive penalty when within 6° of the Sun (not for Sun/nodes/Moon)."""
    if planet in ("Sun", "Moon", "Rahu", "Ketu"):
        return 0.0
    sep = abs(longitude - sun_long) % 360.0
    if sep > 180.0:
        sep = 360.0 - sep
    if sep <= 6.0:
        # Closer = harsher; full 40 virupas at exact conjunction, 0 at 6°.
        return round(40.0 * (1.0 - sep / 6.0), 2)
    return 0.0


def compute_planet_strength(
    planet: str,
    chart: NormalizedChart,
    sun_long: float,
    moon_long: float,
) -> PlanetStrength:
    pos = chart.planets.get(planet)
    if not pos:
        return PlanetStrength(planet=planet, band="weak")

    components = {
        "uchcha": _uchcha_bala(planet, pos.longitude),
        "naisargika": NAISARGIKA_BALA.get(planet, 30.0),
        "dig": _dig_bala(planet, pos.house),
        "cheshta": _cheshta_bala(planet, pos.is_retrograde),
        "paksha": _paksha_bala(planet, sun_long, moon_long),
    }
    penalty = _combustion_penalty(planet, pos.longitude, sun_long)
    total = sum(components.values()) - penalty
    relative = max(0.0, min(1.0, total / _TOTAL_MAX))

    band = "strong" if relative >= _STRONG else "moderate" if relative >= _MODERATE else "weak"

    notes = []
    if pos.is_retrograde and planet not in ("Sun", "Moon"):
        notes.append("retrograde → high cheshta bala")
    if penalty > 0:
        notes.append("combust → strength reduced")
    if components["uchcha"] >= 54:
        notes.append("near exaltation")
    elif components["uchcha"] <= 6:
        notes.append("near debilitation")
    if components["dig"] >= 54:
        notes.append("strong Dig Bala")

    return PlanetStrength(
        planet=planet,
        components={k: round(v, 2) for k, v in components.items()},
        combustion_penalty=penalty,
        total_virupas=round(total, 2),
        relative=round(relative, 3),
        band=band,
        notes=notes,
    )


def compute_all_strengths(chart: NormalizedChart) -> dict[str, PlanetStrength]:
    sun = chart.planets.get("Sun")
    moon = chart.planets.get("Moon")
    sun_long = sun.longitude if sun else 0.0
    moon_long = moon.longitude if moon else 0.0
    return {
        name: compute_planet_strength(name, chart, sun_long, moon_long)
        for name in chart.planets
    }


def format_strengths_for_prompt(strengths: dict[str, PlanetStrength]) -> str:
    """Compact strength table for the prompt / debugging."""
    lines = ["[PLANETARY STRENGTH — Shadbala-lite, virupas]"]
    ranked = sorted(strengths.values(), key=lambda s: s.total_virupas, reverse=True)
    for s in ranked:
        note = f" ({'; '.join(s.notes)})" if s.notes else ""
        lines.append(f"  {s.planet}: {s.total_virupas:.0f}v  [{s.band}]{note}")
    return "\n".join(lines)
