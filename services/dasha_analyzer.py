"""
Dasha Analyzer (B3).

The old logic only asked "is the dasha lord a topic significator?" — binary.
Real Parashari timing reads the *promise* of the dasha lord: the results a period
delivers are a function of the lord's house placement, the houses it lords, its
dignity/strength, the yogas it joins, and the houses it aspects. This module makes
that analysis explicit for the Maha / Antar / Pratyantar lords.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.strength_engine import PlanetStrength
from utils.astro_constants import TOPIC_AFFLICTING_HOUSES


@dataclass
class DashaLordAnalysis:
    lord: str
    level: str                          # "Mahadasha" | "Antardasha" | "Pratyantardasha"
    placed_house: int
    lords_houses: list[int] = field(default_factory=list)
    dignity: str = ""
    strength_band: str = ""
    functional_nature: str = ""
    is_topic_significator: bool = False
    placed_in_afflicting: bool = False  # lord sits in a dusthana/difficult house for the topic
    aspects_topic_houses: list[int] = field(default_factory=list)
    yogas: list[str] = field(default_factory=list)
    reading: str = ""


def _houses_lorded(rule_result: RuleEngineResult, planet: str) -> list[int]:
    return sorted(h for h, lord in rule_result.house_lords.items() if lord == planet)


def _yogas_for_planet(planet: str, yogas: list[str]) -> list[str]:
    panch = {"Ruchaka": "Mars", "Bhadra": "Mercury", "Hamsa": "Jupiter",
             "Malavya": "Venus", "Shasha": "Saturn"}
    out = []
    for y in yogas:
        if planet.lower() in y.lower() or panch.get(y) == planet:
            out.append(y)
    return out


def _ord(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _read(a: DashaLordAnalysis, topic: str) -> str:
    # Rahu/Ketu rule no sign, so they own no house.
    if a.lords_houses:
        lordship = "lords the " + ", ".join(_ord(h) for h in a.lords_houses) + " house"
    elif a.lord in ("Rahu", "Ketu"):
        lordship = "rules no house (a shadow graha)"
    else:
        lordship = "rules no house"
    base = (
        f"{a.lord} ({a.level} lord) sits in the {_ord(a.placed_house)} house, {lordship}, "
        f"dignity {a.dignity or 'n/a'}, strength {a.strength_band or 'n/a'}"
    )
    if a.functional_nature and a.functional_nature != "unknown":
        base += f", functional {a.functional_nature}"
    base += "."
    if a.is_topic_significator:
        base += f" It is a significator for {topic}, so its period directly activates {topic} matters"
        if a.placed_in_afflicting:
            # Sitting in a dusthana/difficult house for the topic: it activates the matter, but
            # through friction/obstacles — not a smooth, favourable activation.
            base += (
                f", but from the {_ord(a.placed_house)} (a difficult house for {topic}) — so the "
                f"period stirs {topic} through challenges and obstacles rather than ease."
            )
        elif a.strength_band == "strong":
            base += " with strength."
        elif a.strength_band == "weak":
            base += ", but its weakness tempers the results."
        else:
            base += "."
    else:
        base += f" It is not a primary {topic} significator; its period activates {topic} only indirectly"
        if a.aspects_topic_houses:
            houses = ", ".join(_ord(h) for h in a.aspects_topic_houses)
            base += f" (it does aspect the {houses} house)."
        else:
            base += "."
    if a.yogas:
        base += f" It participates in: {', '.join(a.yogas)}."
    return base


def analyze_dasha(
    chart: NormalizedChart,
    rule_result: RuleEngineResult,
    strengths: dict[str, PlanetStrength],
    topic: str,
    topic_houses: list[int],
    karakas: list[str],
) -> list[DashaLordAnalysis]:
    levels = [
        ("Mahadasha", rule_result.active_dasha.get("maha", "")),
        ("Antardasha", rule_result.active_dasha.get("antar", "")),
        ("Pratyantardasha", rule_result.active_dasha.get("pratyantara", "")),
    ]
    analyses: list[DashaLordAnalysis] = []
    for level, lord in levels:
        a = _analyze_lord(chart, rule_result, strengths, topic, topic_houses, karakas, lord, level)
        if a:
            analyses.append(a)
    return analyses


def _analyze_lord(chart, rule_result, strengths, topic, topic_houses, karakas, lord, level):
    if not lord:
        return None
    pos = chart.planets.get(lord)
    if not pos:
        return None
    lorded = _houses_lorded(rule_result, lord)
    st = strengths.get(lord)
    aspects = rule_result.aspects_by_planet.get(lord, [])
    is_sig = (
        lord in karakas
        or bool(set(lorded) & set(topic_houses))
        or pos.house in topic_houses
    )
    afflicting_houses = TOPIC_AFFLICTING_HOUSES.get(topic, [6, 8, 12])
    a = DashaLordAnalysis(
        lord=lord, level=level, placed_house=pos.house, lords_houses=lorded,
        dignity=rule_result.planet_strengths.get(lord, ""),
        strength_band=st.band if st else "",
        functional_nature=rule_result.functional_nature.get(lord, "unknown"),
        is_topic_significator=is_sig,
        placed_in_afflicting=pos.house in afflicting_houses,
        aspects_topic_houses=[h for h in aspects if h in topic_houses],
        yogas=_yogas_for_planet(lord, rule_result.yogas_present),
    )
    a.reading = _read(a, topic)
    return a


def analyze_projected_dasha(
    chart, rule_result, strengths, topic, topic_houses, karakas, projection,
) -> str:
    """Forward-looking dasha reading for a future-dated question (#1 fix).

    `projection` is a DashaProjection. Describes the period the native will be in at the
    target date and what its antar lord signifies for the topic."""
    from utils.formatting import format_date

    if projection is None:
        return ""
    when = projection.target.strftime("%Y")
    header = (
        f"[FUTURE DASHA — projected for {when}]\n"
        f"  By {when} the period is {projection.maha_lord} Mahadasha / "
        f"{projection.antar_lord} Antardasha "
        f"({format_date(projection.antar_start)} – {format_date(projection.antar_end)})."
    )
    if not projection.is_future:
        header += " (This is still the current period.)"
    # Analyze the antar lord that will be running then.
    a = _analyze_lord(
        chart, rule_result, strengths, topic, topic_houses, karakas,
        projection.antar_lord, "Antardasha",
    )
    if a:
        header += f"\n  {a.reading}"
    return header


def format_dasha_analysis_for_prompt(analyses: list[DashaLordAnalysis]) -> str:
    if not analyses:
        return ""
    lines = ["[DASHA ANALYSIS — chart-specific timing]"]
    for a in analyses:
        lines.append(f"  {a.reading}")
    return "\n".join(lines)
