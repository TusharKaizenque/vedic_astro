"""
Life Overview — whole-chart synthesis for broad questions.

A question like "how was my life until now?" or "what will I do in life?" is NOT about one
house — it needs the dominant themes of the *entire* chart. The single-topic pipeline
collapses such questions to one house and gives generic answers. This module instead:

  - finds the DOMINANT planets (by Shadbala),
  - scores EVERY life domain for prominence (SAV + significator strength + yogas) and
    surfaces the emphasized ones (incl. spirituality/occult, which users said got missed),
  - flags the spiritual/occult signal explicitly,
  - lays out the dasha LIFE-TIMELINE (past chapters → current → coming) and what each
    period activates.

It reuses the existing deterministic engines — nothing here is fuzzy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from models.intent import IntentCategory, IntentEntities, IntentResult
from services.assessment_engine import assess_topic
from services.chart_signatures import (
    ChartSignature, detect_signatures, format_signatures_for_prompt,
)
from services.rule_engine.ashtakavarga_engine import compute_sav, sav_for_house
from services.significator_engine import get_significators
from utils.astro_constants import (
    SIGN_RULERS, VIMSHOTTARI_ORDER, VIMSHOTTARI_YEARS, ZODIAC_SIGNS,
)
from utils.significations import life_area, professions_for, traits_for

_DOMAINS = ["career", "marriage", "wealth", "health", "education", "children", "spirituality"]
_BIG_YOGAS = {
    "Raja Yoga", "Dharma Karmadhipati", "Neecha Bhanga Raja", "Viparita Raja",
    "Dhana Yoga", "Lakshmi", "Gajakesari", "Ruchaka", "Bhadra", "Hamsa", "Malavya",
    "Shasha", "Saraswati", "Maha Bhagya", "Chatussagara", "Maha Parivartana",
}
_YEAR_DAYS = 365.25

# General life themes and their chart signals. Whatever the chart emphasizes most surfaces —
# spirituality is just one theme among many, not a special case.
_THEME_SIGNALS: list[tuple[str, dict]] = [
    ("career & public standing",            {"houses": [10],      "planets": ["Sun", "Saturn", "Mars"], "yogas": ["Raja Yoga", "Dharma Karmadhipati", "Amala", "Ruchaka", "Shasha"]}),
    ("wealth & resources",                  {"houses": [2, 11],   "planets": ["Jupiter", "Venus"],       "yogas": ["Dhana Yoga", "Lakshmi", "Kalanidhi"]}),
    ("relationships & partnership",         {"houses": [7],       "planets": ["Venus"],                  "yogas": ["Malavya"]}),
    ("knowledge, learning & wisdom",        {"houses": [4, 5, 9], "planets": ["Mercury", "Jupiter"],     "yogas": ["Saraswati", "Budhaditya", "Bhadra"]}),
    ("spirituality & the occult",           {"houses": [12, 9, 8],"planets": ["Ketu", "Jupiter"],        "yogas": ["Hamsa", "Pravrajya", "Sannyasa"]}),
    ("foreign lands & unconventional paths",{"houses": [12, 9],   "planets": ["Rahu"],                   "yogas": []}),
    ("power, status & recognition",         {"houses": [10, 1],   "planets": ["Sun"],                    "yogas": ["Raja Yoga", "Ruchaka", "Shasha"]}),
    ("creativity & self-expression",        {"houses": [5],       "planets": ["Venus", "Mercury"],       "yogas": []}),
    ("service, healing & overcoming adversity", {"houses": [6],   "planets": ["Mars", "Saturn"],         "yogas": ["Viparita Raja"]}),
    ("transformation, research & hidden matters", {"houses": [8], "planets": ["Ketu", "Saturn", "Mars"], "yogas": ["Viparita Raja"]}),
    ("home, property & roots",              {"houses": [4],       "planets": ["Moon", "Mars"],           "yogas": []}),
    ("communication, courage & enterprise", {"houses": [3],       "planets": ["Mercury", "Mars"],        "yogas": []}),
]


@dataclass
class LifeChapter:
    lord: str
    start_year: int
    end_year: int
    phase: str                 # past | current | future
    domains: list[str] = field(default_factory=list)


@dataclass
class LifeOverview:
    dominant_planets: list[str] = field(default_factory=list)
    prominent_domains: list[tuple[str, str]] = field(default_factory=list)  # (topic, direction)
    standout_themes: list[str] = field(default_factory=list)   # whatever the chart emphasizes most
    signatures: list[ChartSignature] = field(default_factory=list)  # specific, multi-factor verdicts
    key_yogas: list[str] = field(default_factory=list)
    chapters: list[LifeChapter] = field(default_factory=list)


def _band_score(band: str) -> int:
    return {"strong": 3, "moderate": 2, "weak": 1}.get(band, 1)


def _domain_prominence(topic, chart, rules, strengths):
    """Return (assessment, prominence_score) for a domain — how emphasized it is."""
    intent = IntentResult(intent=IntentCategory.TOPIC_READING,
                          entities=IntentEntities(topics=[topic]))
    sig = get_significators(intent, chart, rules, topic=topic)
    grounded = 0.5
    assessment = assess_topic(sig, strengths, rules, grounded, chart=chart)
    sav = sav_for_house(chart, sig.primary_houses[0]) if sig.primary_houses else 0
    sav_score = 3 if sav >= 30 else 2 if sav >= 26 else 1
    yoga_score = len(sig.relevant_yogas)
    main_lord = next((f for f in sig.factors if f.lords_house == (sig.primary_houses[0] if sig.primary_houses else 0)), None)
    lord_score = _band_score(strengths[main_lord.planet].band) if (main_lord and main_lord.planet in strengths) else 1
    prominence = sav_score + yoga_score + lord_score + (2 if assessment.direction == "favourable" else 0)
    return assessment, prominence


def _standout_themes(chart, rules, strengths, sav) -> list[str]:
    """Score every life theme from the chart's own signals and return the strongest ones —
    whatever they are (wealth, power, spirituality, foreign, service…). No theme is
    privileged; a theme surfaces only if the chart genuinely emphasizes it."""
    occupants: dict[int, int] = {}
    for p in chart.planets.values():
        occupants[p.house] = occupants.get(p.house, 0) + 1

    def _band(planet: str) -> int:
        s = strengths.get(planet)
        return {"strong": 3, "moderate": 2, "weak": 1}.get(s.band, 1) if s else 1

    scored: list[tuple[str, float, list[str]]] = []
    for name, sig in _THEME_SIGNALS:
        score = 0.0
        evidence: list[str] = []
        for h in sig["houses"]:
            bindus = sav_for_house(chart, h, sav)
            if bindus >= 30:
                score += 3; evidence.append(f"{h}th house strong by Ashtakavarga ({bindus})")
            elif bindus >= 26:
                score += 1.5
            occ = occupants.get(h, 0)
            if occ:
                score += occ * 1.5
                if occ >= 2:
                    evidence.append(f"{occ} planets in the {h}th house")
            lord = rules.house_lords.get(h)
            if lord and strengths.get(lord) and strengths[lord].band == "strong":
                score += 2; evidence.append(f"its lord {lord} is strong")
        for planet in sig["planets"]:
            b = _band(planet)
            score += b
            if b == 3:
                evidence.append(f"{planet} is strong")
        present_yogas = [y for y in sig["yogas"] if y in rules.yogas_present]
        if present_yogas:
            score += 2.5 * len(present_yogas)
            evidence.append(f"yoga(s): {', '.join(present_yogas)}")
        scored.append((name, score, evidence))

    scored.sort(key=lambda t: t[1], reverse=True)
    if not scored:
        return []
    top = scored[0][1]
    # Surface themes that are clearly emphasized (within range of the strongest, score>0).
    out = []
    for name, score, evidence in scored:
        if score <= 0 or score < top * 0.6 or len(out) >= 4:
            continue
        ev = f" ({'; '.join(evidence[:2])})" if evidence else ""
        out.append(f"{name}{ev}")
    return out


def _lord_domains(lord, rules, chart) -> list[str]:
    """Plain life-areas a dasha lord activates: the houses it rules + the house it sits in."""
    houses = sorted(h for h, l in rules.house_lords.items() if l == lord)
    pos = chart.planets.get(lord)
    if pos and pos.house not in houses:
        houses.append(pos.house)
    # Condense to short area words (first noun of life_area).
    out = []
    for h in houses[:3]:
        area = life_area(h).replace("your ", "").split(",")[0].split(" and ")[0]
        out.append(area)
    return out


def _maha_timeline(maha_lord, maha_start_iso, birth_iso, now: datetime) -> list[tuple[str, int, int]]:
    """Maha-dasha sequence (lord, start_year, end_year) from ~birth to current+2."""
    try:
        cur_start = datetime.fromisoformat(maha_start_iso).replace(tzinfo=None)
        birth = datetime.fromisoformat(birth_iso).replace(tzinfo=None) if birth_iso else None
    except (ValueError, TypeError):
        return []
    if maha_lord not in VIMSHOTTARI_ORDER:
        return []
    idx = VIMSHOTTARI_ORDER.index(maha_lord)
    # Walk backward to (just before) birth.
    periods: list[tuple[str, datetime, datetime]] = []
    start, i = cur_start, idx
    for _ in range(9):
        prev_i = (i - 1) % len(VIMSHOTTARI_ORDER)
        prev_lord = VIMSHOTTARI_ORDER[prev_i]
        prev_start = start - timedelta(days=VIMSHOTTARI_YEARS[prev_lord] * _YEAR_DAYS)
        periods.insert(0, (prev_lord, prev_start, start))
        start, i = prev_start, prev_i
        if birth and prev_start <= birth:
            break
    # Current + 2 future.
    end = cur_start + timedelta(days=VIMSHOTTARI_YEARS[maha_lord] * _YEAR_DAYS)
    periods.append((maha_lord, cur_start, end))
    s, i = end, idx
    for _ in range(2):
        ni = (i + 1) % len(VIMSHOTTARI_ORDER)
        nl = VIMSHOTTARI_ORDER[ni]
        ne = s + timedelta(days=VIMSHOTTARI_YEARS[nl] * _YEAR_DAYS)
        periods.append((nl, s, ne))
        s, i = ne, ni
    # Trim to those overlapping birth..future, return (lord, start_year, end_year)
    out = []
    for lord, ps, pe in periods:
        if birth and pe < birth:
            continue
        out.append((lord, ps.year, pe.year))
    return out


def build_life_overview(chart, rules, strengths, now: datetime) -> LifeOverview:
    ov = LifeOverview()

    # Dominant planets by Shadbala (top 3 by relative strength).
    ranked = sorted(strengths.values(), key=lambda s: s.relative, reverse=True)
    ov.dominant_planets = [s.planet for s in ranked[:3] if s.planet not in ("Rahu", "Ketu")][:3]

    # Score every domain; surface the most emphasized.
    scored = []
    for topic in _DOMAINS:
        assessment, prom = _domain_prominence(topic, chart, rules, strengths)
        scored.append((topic, assessment.direction, prom))
    scored.sort(key=lambda t: t[2], reverse=True)
    ov.prominent_domains = [(t, d) for t, d, _ in scored[:4]]

    # Key yogas present.
    ov.key_yogas = [y for y in rules.yogas_present if y in _BIG_YOGAS]

    # The strongest standout themes — whatever the chart emphasizes (general, unbiased).
    sav = compute_sav(chart)
    ov.standout_themes = _standout_themes(chart, rules, strengths, sav)

    # Specific, multi-factor life signatures (extreme wealth, struggle, occult, delay…).
    ov.signatures = detect_signatures(chart, rules, strengths, sav)

    # Dasha life-timeline.
    timeline = _maha_timeline(chart.dasha.maha_dasha_lord, chart.dasha.maha_dasha_start,
                              f"{chart.birth_data.date}T00:00:00", now)
    for lord, sy, ey in timeline:
        phase = "past" if ey <= now.year else "current" if sy <= now.year < ey else "future"
        ov.chapters.append(LifeChapter(lord=lord, start_year=sy, end_year=ey, phase=phase,
                                       domains=_lord_domains(lord, rules, chart)))
    return ov


def format_life_overview_for_prompt(ov: LifeOverview) -> str:
    lines = []
    # Lead with the specific, highly-supported signatures — these carry the individuality.
    sig_block = format_signatures_for_prompt(ov.signatures)
    if sig_block:
        lines.append(sig_block)
        lines.append("")
    lines.append("[LIFE OVERVIEW — whole-chart synthesis: raw material for PART 1; rewrite as prose]")
    if ov.dominant_planets:
        traits = "; ".join(f"{p} ({', '.join(traits_for(p, 2))})" for p in ov.dominant_planets)
        lines.append(f"- strongest planets driving the life: {traits}")
        # Field hint from the single strongest planet.
        prof = professions_for(ov.dominant_planets[0], 3)
        if prof:
            lines.append(f"- natural leanings of the strongest planet: {', '.join(prof)}")
    if ov.standout_themes:
        lines.append("- what stands out most strongly in THIS chart (lead the reading with these):")
        for theme in ov.standout_themes:
            lines.append(f"    * {theme}")
    if ov.prominent_domains:
        doms = "; ".join(f"{t} ({d})" for t, d in ov.prominent_domains)
        lines.append(f"- life areas and their outlook: {doms}")
    if ov.key_yogas:
        lines.append(f"- defining yogas in the chart: {', '.join(ov.key_yogas)}")
    if ov.chapters:
        lines.append("- life chapters by MAHADASHA (major multi-year period; what each emphasizes):")
        for c in ov.chapters:
            dom = ", ".join(c.domains) or "general life themes"
            lines.append(f"    {c.lord} Mahadasha ({c.start_year}-{c.end_year}, {c.phase}): {dom}")
        lines.append("  (These are MAJOR periods. Do not call them 'sub-periods'. A sub-period "
                     "(antardasha) is a shorter span WITHIN one mahadasha.)")
    return "\n".join(lines)
