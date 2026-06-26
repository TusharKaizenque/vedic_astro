from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.aspect_engine import get_aspects_by_planet, planets_aspecting_house
from services.rule_engine.dosha_detector import detect_all_doshas
from services.rule_engine.strength_calculator import calculate_all_strengths
from services.rule_engine.yoga_detector import detect_all_yogas
from utils.astro_constants import (
    DIG_BALA_HOUSES, DUSTHANA_HOUSES, FUNCTIONAL_NATURE_BY_LAGNA,
    KENDRA_HOUSES, SIGN_RULERS, TRIKONA_HOUSES,
)


@dataclass
class RuleEngineResult:
    yogas_present: list[str] = field(default_factory=list)
    doshas_present: list[str] = field(default_factory=list)
    planet_strengths: dict[str, str] = field(default_factory=dict)
    house_lords: dict[int, str] = field(default_factory=dict)
    active_dasha: dict[str, str] = field(default_factory=dict)
    kendra_planets: list[str] = field(default_factory=list)
    trikona_planets: list[str] = field(default_factory=list)
    dusthana_planets: list[str] = field(default_factory=list)
    retrograde_planets: list[str] = field(default_factory=list)
    # New fields
    functional_nature: dict[str, str] = field(default_factory=dict)
    dig_bala_planets: list[str] = field(default_factory=list)
    aspects_by_planet: dict[str, list[int]] = field(default_factory=dict)
    planets_aspecting_house: dict[int, list[str]] = field(default_factory=dict)


def run_rule_engine(chart: NormalizedChart) -> RuleEngineResult:
    house_lords = {n: SIGN_RULERS.get(h.sign, "Unknown") for n, h in chart.houses.items()}
    aspects = get_aspects_by_planet(chart)
    aspecting: dict[int, list[str]] = {h: planets_aspecting_house(chart, h) for h in range(1, 13)}
    functional = FUNCTIONAL_NATURE_BY_LAGNA.get(chart.lagna_sign, {})
    dig_bala = [
        name for name, pos in chart.planets.items()
        if DIG_BALA_HOUSES.get(name) == pos.house
    ]

    result = RuleEngineResult(
        yogas_present=detect_all_yogas(chart),
        doshas_present=detect_all_doshas(chart),
        planet_strengths=calculate_all_strengths(chart),
        house_lords=house_lords,
        active_dasha={
            "maha": chart.dasha.maha_dasha_lord,
            "antar": chart.dasha.antar_dasha_lord,
            "pratyantara": chart.dasha.pratyantara_dasha_lord or "",
            "maha_end": chart.dasha.maha_dasha_end,
            "antar_end": chart.dasha.antar_dasha_end,
        },
        functional_nature=functional,
        dig_bala_planets=dig_bala,
        aspects_by_planet=aspects,
        planets_aspecting_house=aspecting,
    )
    for name, pos in chart.planets.items():
        if pos.house in KENDRA_HOUSES:
            result.kendra_planets.append(name)
        if pos.house in TRIKONA_HOUSES:
            result.trikona_planets.append(name)
        if pos.house in DUSTHANA_HOUSES:
            result.dusthana_planets.append(name)
        if pos.is_retrograde:
            result.retrograde_planets.append(name)
    return result


def format_rule_result_for_prompt(result: RuleEngineResult) -> str:
    lines = [
        "[VERIFIED CHART FACTS — deterministic rule engine]",
        f"Yogas present: {', '.join(result.yogas_present) or 'None detected'}",
        f"Doshas present: {', '.join(result.doshas_present) or 'None detected'}",
        "Planet strengths:",
    ]
    lines.extend(f"  {planet}: {strength}" for planet, strength in result.planet_strengths.items())
    if result.retrograde_planets:
        lines.append(f"Retrograde planets: {', '.join(result.retrograde_planets)}")
    if result.dig_bala_planets:
        lines.append(f"Dig Bala (directional strength): {', '.join(result.dig_bala_planets)}")
    if result.functional_nature:
        benefics = [p for p, n in result.functional_nature.items() if n in ("benefic", "yogakaraka")]
        malefics = [p for p, n in result.functional_nature.items() if n == "malefic"]
        yogakarakas = [p for p, n in result.functional_nature.items() if n == "yogakaraka"]
        if yogakarakas:
            lines.append(f"Yogakaraka planet(s): {', '.join(yogakarakas)}")
        if benefics:
            lines.append(f"Functional benefics: {', '.join(benefics)}")
        if malefics:
            lines.append(f"Functional malefics: {', '.join(malefics)}")
    lines.append(f"Active dasha: {result.active_dasha.get('maha')} MD / {result.active_dasha.get('antar')} AD")
    return "\n".join(lines)
