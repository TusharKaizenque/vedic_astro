"""
Strength Engine — full Shadbala (the six-fold strength), BPHS Ch.27.

Replaces the earlier "Shadbala-lite". Computes the six balas in virupas (60 virupas =
1 rupa) and a normalized total used by the assessment/outcome engines:

  1. Sthana Bala  (positional)  = Uchcha + Saptavargaja + Ojayugma + Kendradi + Drekkana
  2. Dig Bala     (directional)
  3. Kala Bala    (temporal)    = Paksha + Nathonnatha  [Ayana/Hora/Tribhaga/Vara omitted —
                                  they need exact sunrise & ephemeris speed we don't have]
  4. Cheshta Bala (motional)    [retrograde-based proxy; true cheshta needs daily speed]
  5. Naisargika   (natural)
  6. Drik Bala    (aspectual)   = net benefic vs malefic aspects received

Components needing precise time-of-day / true planetary speed are documented as
approximations rather than faked.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.aspect_engine import get_aspects_by_planet
from services.rule_engine.varga_engine import sign_dignity, varga_sign
from utils.astro_constants import (
    DEBILITATION_SIGNS, DIG_BALA_STRONG_HOUSE, EXALTATION_DEGREE, NAISARGIKA_BALA,
    NATURAL_BENEFICS, NATURAL_MALEFICS, ZODIAC_SIGNS, combustion_orb,
)

# Classical required Shadbala (virupas) per planet — a planet's strength is judged
# RELATIVE to its own requirement (BPHS), not an absolute. We compute a partial Shadbala
# (some Kala sub-balas omitted) but the measured totals calibrate well against the full
# classical requirements empirically, so no extra scaling is applied.
_REQUIRED_FULL = {
    "Sun": 390.0, "Moon": 360.0, "Mars": 300.0, "Mercury": 420.0,
    "Jupiter": 390.0, "Venus": 330.0, "Saturn": 300.0, "Rahu": 300.0, "Ketu": 300.0,
}
_REQUIRED_SCALE = 1.0
# Bands on the ratio (measured total / requirement).
_STRONG = 1.0
_MODERATE = 0.90

_SAPTAVARGA = ["D1", "D2", "D3", "D7", "D9", "D12", "D30"]
_DIGNITY_POINTS = {
    "exalted": 30.0, "moolatrikona": 45.0, "own sign": 30.0,
    "friendly sign": 15.0, "neutral sign": 7.5, "enemy sign": 3.75,
    "debilitated": 1.875, "": 7.5,
}
_DIURNAL = {"Sun", "Jupiter", "Venus"}
_NOCTURNAL = {"Moon", "Mars", "Saturn"}
_DREKKANA = {1: {"Sun", "Mars", "Jupiter"}, 2: {"Mercury", "Saturn"}, 3: {"Moon", "Venus"}}

# Sum of component maxima, for normalization.
_MAX = {"sthana": 60 + 210 + 30 + 60 + 15, "dig": 60, "kala": 120,
        "cheshta": 60, "naisargika": 60, "drik": 60}
_TOTAL_MAX = float(sum(_MAX.values()))


@dataclass
class PlanetStrength:
    planet: str
    components: dict[str, float] = field(default_factory=dict)   # the six balas (virupas)
    combustion_penalty: float = 0.0
    total_virupas: float = 0.0
    relative: float = 0.0
    band: str = "moderate"
    notes: list[str] = field(default_factory=list)


# ── Sthana Bala sub-components ──────────────────────────────────────────────────
def _uchcha(planet: str, longitude: float) -> float:
    exalt = EXALTATION_DEGREE.get(planet)
    if exalt is None:
        return 30.0
    debilitation = (exalt + 180.0) % 360.0
    diff = abs(longitude - debilitation) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return round(diff / 3.0, 2)


def _saptavargaja(planet: str, longitude: float, d1_sign: str) -> float:
    from services.rule_engine.strength_calculator import get_planet_strength
    total = 0.0
    for varga in _SAPTAVARGA:
        if varga == "D1":
            # Use the degree-aware dignity so the moolatrikona tier (45) can fire.
            dignity = get_planet_strength(planet, d1_sign, longitude % 30.0)
        else:
            dignity = sign_dignity(planet, varga_sign(longitude, varga))
        total += _DIGNITY_POINTS.get(dignity, 7.5)
    return round(total, 2)


def _ojayugma(planet: str, longitude: float, sign: str) -> float:
    rasi_idx = ZODIAC_SIGNS.index(sign) if sign in ZODIAC_SIGNS else 0
    nav_sign = varga_sign(longitude, "D9")
    nav_idx = ZODIAC_SIGNS.index(nav_sign) if nav_sign in ZODIAC_SIGNS else 0
    prefers_even = planet in ("Moon", "Venus")
    score = 0.0
    rasi_even = rasi_idx % 2 == 1     # index 1=Taurus is an even sign
    nav_even = nav_idx % 2 == 1
    if rasi_even == prefers_even:
        score += 15.0
    if nav_even == prefers_even:
        score += 15.0
    return score


def _kendradi(house: int) -> float:
    if house in (1, 4, 7, 10):
        return 60.0
    if house in (2, 5, 8, 11):
        return 30.0
    return 15.0


def _drekkana(planet: str, deg_in_sign: float) -> float:
    drek = 1 if deg_in_sign < 10 else 2 if deg_in_sign < 20 else 3
    return 15.0 if planet in _DREKKANA[drek] else 0.0


# ── Dig Bala ─────────────────────────────────────────────────────────────────────
def _dig(planet: str, house: int) -> float:
    strong = DIG_BALA_STRONG_HOUSE.get(planet)
    if strong is None or not (1 <= house <= 12):
        return 30.0
    sep = abs(house - strong)
    sep = min(sep, 12 - sep)
    return round(60.0 * (1.0 - sep / 6.0), 2)


# ── Kala Bala sub-components ──────────────────────────────────────────────────────
def _paksha(planet: str, sun_long: float, moon_long: float) -> float:
    elong = abs(moon_long - sun_long) % 360.0
    if elong > 180.0:
        elong = 360.0 - elong
    waxing = elong / 180.0
    value = waxing if planet in NATURAL_BENEFICS else (1.0 - waxing)
    return round(60.0 * value, 2)


def _nathonnatha(planet: str, birth_hour: float) -> float:
    """Day/night strength. Approximated from the birth hour (no sunrise data):
    diurnal planets peak at noon, nocturnal at midnight; Mercury always strong."""
    if planet == "Mercury":
        return 60.0
    f = abs(birth_hour - 12.0) / 12.0     # 0 at noon, 1 at midnight
    if planet in _DIURNAL:
        return round(60.0 * (1.0 - f), 2)
    if planet in _NOCTURNAL:
        return round(60.0 * f, 2)
    return 30.0


# ── Cheshta Bala ──────────────────────────────────────────────────────────────────
def _cheshta(planet: str, is_retro: bool) -> float:
    if planet in ("Sun", "Moon", "Rahu", "Ketu"):
        return 30.0
    return 50.0 if is_retro else 25.0


# ── Drik Bala (aspectual) ─────────────────────────────────────────────────────────
def _drik(planet: str, chart: NormalizedChart, aspects: dict[str, list[int]]) -> float:
    pos = chart.planets.get(planet)
    if not pos:
        return 30.0
    score = 30.0   # neutral baseline
    for other, houses in aspects.items():
        if other == planet:
            continue
        if pos.house in houses:
            if other in NATURAL_BENEFICS:
                score += 10.0
            elif other in NATURAL_MALEFICS:
                score -= 10.0
    return round(max(0.0, min(60.0, score)), 2)


def _combustion_penalty(planet: str, longitude: float, sun_long: float,
                        is_retro: bool = False) -> float:
    if planet in ("Sun", "Rahu", "Ketu"):
        return 0.0
    orb = combustion_orb(planet, is_retro)
    if orb <= 0:
        return 0.0
    sep = abs(longitude - sun_long) % 360.0
    if sep > 180.0:
        sep = 360.0 - sep
    if sep <= orb:
        return round(40.0 * (1.0 - sep / orb), 2)   # harsher the closer to the Sun
    return 0.0


def _birth_hour(chart: NormalizedChart) -> float:
    try:
        h, m = chart.birth_data.time.split(":")[:2]
        return int(h) + int(m) / 60.0
    except Exception:
        return 12.0


def compute_planet_strength(
    planet: str, chart: NormalizedChart, sun_long: float, moon_long: float,
    aspects: dict[str, list[int]] | None = None, birth_hour: float = 12.0,
    neecha_bhanga: bool = False,
) -> PlanetStrength:
    pos = chart.planets.get(planet)
    if not pos:
        return PlanetStrength(planet=planet, band="weak")
    aspects = aspects if aspects is not None else get_aspects_by_planet(chart)

    sthana = round(
        _uchcha(planet, pos.longitude)
        + _saptavargaja(planet, pos.longitude, pos.sign)
        + _ojayugma(planet, pos.longitude, pos.sign)
        + _kendradi(pos.house)
        + _drekkana(planet, pos.degree_in_sign), 2)
    dig = _dig(planet, pos.house)
    kala = round(_paksha(planet, sun_long, moon_long) + _nathonnatha(planet, birth_hour), 2)
    cheshta = _cheshta(planet, pos.is_retrograde)
    naisargika = NAISARGIKA_BALA.get(planet, 30.0)
    drik = _drik(planet, chart, aspects)

    penalty = _combustion_penalty(planet, pos.longitude, sun_long, pos.is_retrograde)
    components = {"sthana": sthana, "dig": dig, "kala": kala,
                  "cheshta": cheshta, "naisargika": naisargika, "drik": drik}
    total = round(sum(components.values()) - penalty, 2)

    # Ratio to this planet's (scaled) required Shadbala — the classical strength measure.
    required = _REQUIRED_FULL.get(planet, 300.0) * _REQUIRED_SCALE
    ratio = total / required if required else 0.0
    band = "strong" if ratio >= _STRONG else "moderate" if ratio >= _MODERATE else "weak"
    # `relative` (0..1) feeds the verdict weighting — spread the ratio across a usable range.
    relative = round(max(0.0, min(1.0, ratio / 1.25)), 3)

    notes = []
    if pos.is_retrograde and planet not in ("Sun", "Moon"):
        notes.append("retrograde → high cheshta bala")
    if penalty > 0:
        notes.append("combust → strength reduced")
    if _uchcha(planet, pos.longitude) >= 54:
        notes.append("near exaltation")
    elif _uchcha(planet, pos.longitude) <= 6:
        notes.append("near debilitation")
    if dig >= 54:
        notes.append("strong Dig Bala")
    if drik <= 15:
        notes.append("afflicted by malefic aspects")
    elif drik >= 50:
        notes.append("strengthened by benefic aspects")

    # A debilitated planet (without Neecha Bhanga cancellation) must not be reported as
    # "strong" purely from positional bonuses — that contradicts its dignity and wrongly
    # fires "lord is strong" signatures. Cap the BAND (the categorical label); the raw
    # `relative` capacity is left intact for ranking.
    if DEBILITATION_SIGNS.get(planet) == pos.sign and not neecha_bhanga and band == "strong":
        band = "moderate"
        notes.append("debilitated (uncancelled) → band capped at moderate")

    return PlanetStrength(
        planet=planet, components=components, combustion_penalty=penalty,
        total_virupas=total, relative=relative, band=band, notes=notes,
    )


def compute_all_strengths(chart: NormalizedChart) -> dict[str, PlanetStrength]:
    from services.rule_engine.yoga_detector import neecha_bhanga_planets

    sun = chart.planets.get("Sun")
    moon = chart.planets.get("Moon")
    sun_long = sun.longitude if sun else 0.0
    moon_long = moon.longitude if moon else 0.0
    aspects = get_aspects_by_planet(chart)
    hour = _birth_hour(chart)
    nb = neecha_bhanga_planets(chart)  # debilitation-cancelled planets stay eligible for "strong"
    return {
        name: compute_planet_strength(
            name, chart, sun_long, moon_long, aspects, hour, neecha_bhanga=name in nb
        )
        for name in chart.planets
    }


def format_strengths_for_prompt(strengths: dict[str, PlanetStrength]) -> str:
    lines = ["[PLANETARY STRENGTH — Shadbala, virupas]"]
    for s in sorted(strengths.values(), key=lambda s: s.total_virupas, reverse=True):
        note = f" ({'; '.join(s.notes)})" if s.notes else ""
        lines.append(f"  {s.planet}: {s.total_virupas:.0f}v  [{s.band}]{note}")
    return "\n".join(lines)
