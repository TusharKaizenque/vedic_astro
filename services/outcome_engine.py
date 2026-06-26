"""
Outcome / Signature Engine (Phase G).

Turns the deterministic verdict + significator factors + domain maps into a structured,
plain-language LifeOutcome: the field/nature, the trajectory, the result pattern, and the
strengths/challenges in lived terms. This is the spine the synthesis LLM narrates — it is
what makes the answer about the person's life, not about planets. Still fully deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services.assessment_engine import TopicAssessment
from services.rule_engine.strength_engine import PlanetStrength
from services.significator_engine import SignificatorResult
from utils.significations import (
    RETROGRADE_FLAVOR, life_area, professions_for, sign_keywords, traits_for,
)

# Topics where naming a professional FIELD is meaningful.
_FIELD_TOPICS = {"career", "business", "profession", "job"}
# Topics that are about a PERSON, where temperament traits matter.
_PERSON_TOPICS = {"marriage", "relationship", "spouse"}

_STRONG = {"strong"}
_WEAK = {"weak"}


@dataclass
class LifeOutcome:
    topic: str
    headline: str = ""
    field_candidates: list[str] = field(default_factory=list)
    nature: str = ""
    trajectory: str = ""               # short label
    trajectory_text: str = ""          # sentence
    result_pattern: str = ""           # income/gains (career/wealth)
    strengths: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)   # for person topics


def _band_weight(band: str) -> float:
    return {"strong": 1.0, "moderate": 0.6, "weak": 0.3}.get(band, 0.5)


def _topic_shapers(significators, strengths, amatyakaraka: str = "") -> list[tuple[str, float]]:
    """Rank the planets that shape the topic house: lord, occupants, karakas, aspectors.
    Own-sign / exalted planets get a dignity boost so the chart's standout planet leads.
    For career, the Jaimini Amatyakaraka is added as a strong co-significator (Phase J)."""
    main = significators.primary_houses[0] if significators.primary_houses else 10
    contributors: dict[str, float] = {}
    dignity_by_planet = {f.planet: f.dignity for f in significators.factors}

    def _add(planet: str, role_weight: float):
        if planet in ("Rahu", "Ketu") and planet not in significators.karaka_planets:
            role_weight *= 0.7
        st = strengths.get(planet)
        w = role_weight * _band_weight(st.band if st else "moderate")
        if dignity_by_planet.get(planet) in ("exalted", "own sign", "moolatrikona"):
            w += 0.2   # the chart's dignified planet stands out for field/nature
        contributors[planet] = max(contributors.get(planet, 0.0), w)

    lord = next((f.planet for f in significators.factors if f.lords_house == main), None)
    if lord:
        _add(lord, 1.0)
    for planet in significators.planets_in_topic_houses.get(main, []):
        _add(planet, 0.9)
    for planet in significators.karaka_planets:
        _add(planet, 0.8)
    for planet in significators.aspects_on_topic_houses.get(main, []):
        _add(planet, 0.5)
    if amatyakaraka:
        _add(amatyakaraka, 0.85)   # Jaimini career co-significator
    return sorted(contributors.items(), key=lambda kv: kv[1], reverse=True)


def _field_candidates(significators, strengths, chart, amk: str = "") -> list[str]:
    """Professional fields from the top topic-shaping planets."""
    fields: list[str] = []
    for planet, _w in _topic_shapers(significators, strengths, amk)[:3]:
        retro = chart.planets.get(planet)
        is_retro = bool(retro and retro.is_retrograde and planet not in ("Sun", "Moon"))
        for prof in professions_for(planet, 3):
            if prof not in fields:
                fields.append(f"{RETROGRADE_FLAVOR} {prof}" if is_retro and len(fields) == 0 else prof)
    return fields[:6]


def _nature(significators, strengths, chart, amk: str = "") -> str:
    """One plain sentence on the character of the matter, led by the strongest shaper
    (same planet pool that drives the field, so nature and field stay coherent)."""
    shapers = _topic_shapers(significators, strengths, amk)
    if not shapers:
        return ""
    lead_planet = shapers[0][0]
    lead_factor = next((f for f in significators.factors if f.planet == lead_planet), None)
    traits = traits_for(lead_planet, 2)
    bits = ", ".join(t for t in traits if t)
    nature = f"shaped most by {lead_planet} — {bits}"
    sign_kw = sign_keywords(lead_factor.sign) if lead_factor else ""
    if sign_kw:
        nature += f", expressed in a manner that is {sign_kw}"
    return nature


def _trajectory(significators, assessment, strengths) -> tuple[str, str]:
    direction = assessment.direction
    main = significators.primary_houses[0] if significators.primary_houses else 10
    factors = significators.factors
    primary = [f for f in factors if f.lords_house == main or f.role == "karaka"]
    in_dusthana = any(f.placed_house in (6, 8, 12) for f in primary)
    neecha_bhanga = any(f.neecha_bhanga for f in primary)
    has_yogas = bool(significators.relevant_yogas)

    if neecha_bhanga:
        return "late-bloom", ("a pattern of early obstacles followed by a notable rise — "
                              "what begins as a weakness becomes a source of strength")
    if direction == "favourable":
        base = ("a steadily rising path where your own effort and merit are rewarded"
                if not in_dusthana else
                "real success that arrives through upheaval and reinvention rather than a straight line")
        if has_yogas:
            base += "; the chart carries combinations capable of lifting you to real prominence"
        return ("steady-rise" if not in_dusthana else "transformative"), base
    if direction == "challenged":
        return "effortful", ("a demanding path where results come slowly and through sustained "
                             "persistence; obstacles are a recurring theme to be outlasted")
    return "mixed", ("genuine achievement interwoven with recurring friction — strong support on "
                     "one side, real obstacles on the other, so progress comes in waves")


def _result_pattern(significators, strengths, rule_result) -> str:
    """Income / gains pattern from the 2nd & 11th lords (career/wealth topics)."""
    house_lords = rule_result.house_lords
    bands = []
    for h in (2, 11):
        lord = house_lords.get(h)
        st = strengths.get(lord) if lord else None
        if st:
            bands.append(st.band)
    if not bands:
        return ""
    if all(b == "strong" for b in bands):
        return "Earnings tend to be steady and to grow well over time."
    if any(b == "weak" for b in bands):
        return "Income can be uneven or hard-won; financial stability needs deliberate effort."
    return "Earnings are moderate and build gradually with consistent work."


def _governs(f) -> str:
    """Short phrase for what a factor governs in the native's life."""
    if f.lords_house:
        return life_area(f.lords_house)
    if "occupies" in f.role:
        return life_area(f.placed_house)
    return "this area"


def _plain_strength(f) -> str:
    """A supporting factor → its lived gift (positive traits + what it governs)."""
    traits = " & ".join(traits_for(f.planet, 2)) or f.planet
    if "karaka" in f.role:
        return f"{traits} as the natural significator of this area ({f.planet})"
    if "aspects" in f.role:
        return f"{traits}, a benefic influence on this area ({f.planet})"
    return f"{traits}, shaping {_governs(f)} ({f.planet})"


def _plain_challenge(f, strengths) -> str:
    """An afflicting factor → the lived friction it brings (area of difficulty, not nice traits)."""
    st = strengths.get(f.planet)
    weak = " and is itself under strain" if st and st.band == "weak" else ""
    gov = _governs(f)
    if "karaka" in f.role:
        return f"strain on this area's natural significator{weak} ({f.planet})"
    if gov != "this area":
        return f"friction connected to {gov}{weak} ({f.planet})"
    return f"an obstructing influence on this area{weak} ({f.planet})"


def derive_outcome(
    topic: str,
    significators: SignificatorResult,
    assessment: TopicAssessment,
    strengths: dict[str, PlanetStrength],
    chart,
    rule_result,
) -> LifeOutcome:
    out = LifeOutcome(topic=topic)
    is_field = topic in _FIELD_TOPICS
    is_person = topic in _PERSON_TOPICS

    # Jaimini Amatyakaraka — career co-significator (only relevant for field topics).
    amk = ""
    if is_field:
        from utils.jaimini import amatyakaraka
        amk = amatyakaraka(chart)
        out.field_candidates = _field_candidates(significators, strengths, chart, amk)
        out.result_pattern = _result_pattern(significators, strengths, rule_result)
    out.nature = _nature(significators, strengths, chart, amk)
    out.trajectory, out.trajectory_text = _trajectory(significators, assessment, strengths)

    # Strengths / challenges in plain language (top 3 each).
    sup = [f for f in significators.factors if f.kind == "supporting"]
    aff = [f for f in significators.factors if f.kind == "afflicting"]
    sup.sort(key=lambda f: _band_weight(strengths.get(f.planet).band if strengths.get(f.planet) else "moderate"), reverse=True)
    aff.sort(key=lambda f: _band_weight(strengths.get(f.planet).band if strengths.get(f.planet) else "moderate"), reverse=True)
    out.strengths = [_plain_strength(f) for f in sup[:3]]
    out.challenges = [_plain_challenge(f, strengths) for f in aff[:3]]

    if is_person:
        # Spouse/partner temperament from the 7th lord + Venus.
        seventh = next((f for f in significators.factors if f.lords_house == 7), None)
        venus = chart.planets.get("Venus")
        trait_set: list[str] = []
        if seventh:
            trait_set += traits_for(seventh.planet, 2)
            if seventh.sign:
                trait_set.append(sign_keywords(seventh.sign))
        if venus:
            trait_set.append(sign_keywords(venus.sign))
        out.traits = [t for t in dict.fromkeys(trait_set) if t]

    # Headline
    direction_word = {"favourable": "well-supported", "mixed": "a mix of real support and real friction",
                      "challenged": "demanding and obstacle-prone"}.get(assessment.direction, "")
    if is_field and out.field_candidates:
        out.headline = (f"Your {topic} is {direction_word}; you are most suited to "
                        f"{', '.join(out.field_candidates[:3])}.")
    elif is_person and out.traits:
        out.headline = f"Your spouse is likely {', '.join(out.traits[:3])}."
    else:
        out.headline = f"Your {topic} is {direction_word}."
    return out


def format_outcome_for_prompt(out: LifeOutcome) -> str:
    """Raw synthesis material for PART 1. The LLM must REWRITE this into flowing prose —
    not copy the labels or the (Planet) tags (those belong only in PART 2)."""
    lines = [
        f"[LIFE OUTCOME — {out.topic}: raw material for PART 1. Rewrite into 2-3 natural "
        f"paragraphs of plain English. Do NOT print these labels or the (Planet) tags here.]"
    ]
    lines.append(f"- core read: {out.headline}")
    if out.field_candidates:
        lines.append(f"- likely fields/domains: {', '.join(out.field_candidates)}")
    if out.nature:
        lines.append(f"- character of the work/matter: {out.nature}")
    if out.trajectory_text:
        lines.append(f"- how it unfolds over life: {out.trajectory_text}")
    if out.result_pattern:
        lines.append(f"- result/income pattern: {out.result_pattern}")
    if out.traits:
        lines.append(f"- likely temperament of the person: {', '.join(out.traits)}")
    if out.strengths:
        lines.append("- strengths to lean on: " + "; ".join(out.strengths))
    if out.challenges:
        lines.append("- real challenges to manage: " + "; ".join(out.challenges))
    return "\n".join(lines)
