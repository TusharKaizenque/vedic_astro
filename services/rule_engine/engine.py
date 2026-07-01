from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.aspect_engine import get_aspects_by_planet, planets_aspecting_house
from services.rule_engine.bhava_lords import BhavaLordReading, analyze_bhava_lords
from services.rule_engine.dosha_detector import detect_all_doshas
from services.rule_engine.planetary_states import (
    PlanetState, compute_planet_states, format_planet_states_for_prompt,
)
from services.rule_engine.strength_calculator import calculate_all_strengths
from services.rule_engine.yoga_analysis import (
    YogaReading, analyze_yogas, format_yoga_analysis_for_prompt,
)
from services.rule_engine.varga_engine import (
    vargottama_planets, vimshopaka_bala, vimshopaka_band,
)
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
    # Depth layer: per-planet states (combust/war/avastha/dignity) + graded yogas + bhava lords.
    planet_states: dict[str, PlanetState] = field(default_factory=dict)
    yoga_readings: list[YogaReading] = field(default_factory=list)
    bhava_lords: list[BhavaLordReading] = field(default_factory=list)
    vargottama: list[str] = field(default_factory=list)
    vimshopaka: dict[str, float] = field(default_factory=dict)


def run_rule_engine(chart: NormalizedChart) -> RuleEngineResult:
    house_lords = {n: SIGN_RULERS.get(h.sign, "Unknown") for n, h in chart.houses.items()}
    aspects = get_aspects_by_planet(chart)
    aspecting: dict[int, list[str]] = {h: planets_aspecting_house(chart, h) for h in range(1, 13)}
    functional = FUNCTIONAL_NATURE_BY_LAGNA.get(chart.lagna_sign, {})
    dig_bala = [
        name for name, pos in chart.planets.items()
        if DIG_BALA_HOUSES.get(name) == pos.house
    ]
    states = compute_planet_states(chart)
    yogas = detect_all_yogas(chart)

    result = RuleEngineResult(
        yogas_present=yogas,
        planet_states=states,
        yoga_readings=analyze_yogas(chart, yogas, states),
        bhava_lords=analyze_bhava_lords(chart, states),
        vargottama=vargottama_planets(chart),
        vimshopaka=vimshopaka_bala(chart),
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


def format_rule_result_for_prompt(
    result: RuleEngineResult, broad: bool = False, focus_planets: set[str] | None = None
) -> str:
    # NOTE ON REDUNDANCY: each planet's dignity, its retrograde flag, and the active-dasha
    # lords/dates are ALREADY printed authoritatively in the [NATAL CHART] block. Repeating them
    # here just made the narrator restate the chart, so this block now carries ONLY facts that
    # appear nowhere else: doshas, functional (lagna-specific) nature, yogas, and planetary states.
    lines = [
        "[VERIFIED CHART FACTS — deterministic rule engine]",
        f"Doshas present: {', '.join(result.doshas_present) or 'None detected'}",
    ]
    if broad and result.dig_bala_planets:
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
    # Graded, chart-specific yoga readings replace the old bare name list. Fewer for a focused
    # question (the strongest few + any topic-relevant ones), more for a whole-life reading.
    yoga_block = format_yoga_analysis_for_prompt(
        result.yoga_readings, limit=10 if broad else 6, focus_planets=focus_planets)
    if yoga_block:
        lines.append(yoga_block)
    elif not result.yogas_present:
        lines.append("Yogas present: None detected")
    # Per-planet states (combustion, planetary war, avastha, notable dignity).
    states_block = format_planet_states_for_prompt(result.planet_states, focus_planets=focus_planets)
    if states_block:
        lines.append(states_block)
    # Divisional strength meta (Vargottama, Vimshopaka) is DISTINCT from rasi dignity (D9 sameness
    # / Shadvarga composite), so it must not vanish — but showing it for ALL planets on a focused
    # question is chart-wide noise. So: broad reading → all standouts; focused reading → only the
    # TOPIC's significators (relevant strength, no noise).
    focus = focus_planets or set()
    vargottama = result.vargottama if broad else [p for p in result.vargottama if p in focus]
    if vargottama:
        lines.append("Vargottama (same sign in D1 & Navamsa — very strong): " + ", ".join(vargottama))
    if result.vimshopaka:
        ranked = sorted(result.vimshopaka.items(), key=lambda kv: kv[1], reverse=True)
        if broad:
            strong = [f"{p} ({v}, {vimshopaka_band(v)})" for p, v in ranked if v >= 10]
            weak = [f"{p} ({v}, {vimshopaka_band(v)})" for p, v in ranked if v < 5]
            if strong:
                lines.append("Vimshopaka Bala — divisionally strongest: " + ", ".join(strong))
            if weak:
                lines.append("Vimshopaka Bala — divisionally weakest: " + ", ".join(weak))
        elif focus:
            rel = [f"{p} ({v}, {vimshopaka_band(v)})" for p, v in ranked if p in focus]
            if rel:
                lines.append("Vimshopaka Bala (divisional strength of the key planets): "
                             + ", ".join(rel))
    # NB: the bhava-lord placements are emitted as their OWN section in prompt_builder (focused
    # on the topic's houses and given higher priority), so they survive token-budget trimming.
    return "\n".join(lines)
