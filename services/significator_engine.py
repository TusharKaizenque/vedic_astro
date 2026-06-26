"""
Significator Engine — Phase 3.

Deterministically identifies which chart factors are relevant to a given question.
No LLM. Same chart + same question always produces the same output.

Replaces reasoning_service.analyze_chart_for_question().
"""
from dataclasses import dataclass, field

from models.chart import NormalizedChart
from models.intent import IntentCategory, IntentResult
from services.rule_engine.aspect_engine import aspect_quality
from services.rule_engine.conjunction_engine import conjunction_influence, planets_conjunct
from services.rule_engine.dispositor_engine import dispositor_of
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.varga_engine import varga_dignity as _varga_dig
from services.rule_engine.yoga_detector import neecha_bhanga_planets
from utils.astro_constants import (
    DIG_BALA_HOUSES, FUNCTIONAL_NATURE_BY_LAGNA, NATURAL_MALEFICS,
    TOPIC_FAMILIES, TOPIC_HOUSE_MAP, TOPIC_KEYWORDS, TOPIC_PLANET_MAP, UPACHAYA_HOUSES,
)

# Maps topic → which varga (divisional chart) is most relevant.
# D1 = Rasi (birth chart), always used.
TOPIC_VARGA_MAP: dict[str, str] = {
    "career": "D10", "profession": "D10", "job": "D10", "business": "D10",  # D10 = karma/profession

    "marriage": "D9", "spouse": "D9", "relationship": "D9", "partner": "D9",
    "children": "D7", "child": "D7", "fertility": "D7",
    "wealth": "D2", "finance": "D2", "money": "D2",
    "education": "D24", "higher education": "D24",
    "property": "D4", "home": "D4",
    "spirituality": "D9", "moksha": "D9",
}

# Which dusthana houses afflict each topic's primary houses
TOPIC_AFFLICTING_HOUSES: dict[str, list[int]] = {
    "career":   [6, 8, 12],
    "marriage": [6, 8, 12],
    "children": [5],
    "health":   [6, 8],
    "finance":  [8, 12],
    "property": [8, 12],
}


@dataclass
class SignificatorFactor:
    """One astrologically relevant factor for the question topic."""
    role: str                       # e.g. "10th lord", "karaka Sun", "planets in 10th"
    planet: str
    placed_house: int
    sign: str
    dignity: str                    # from strength_calculator
    functional_nature: str          # benefic / malefic / yogakaraka / neutral / unknown
    dig_bala: bool                  # planet in its directionally strong house
    aspects_topic_house: bool       # does this planet aspect a primary topic house?
    kind: str                       # "supporting" | "afflicting" | "neutral"
    varga_dignity: str = ""         # dignity in relevant varga (D10 for career, etc.)
    yoga_links: list[str] = field(default_factory=list)   # yogas that involve this planet
    # Phase B enrichment
    neecha_bhanga: bool = False     # debilitation cancelled
    conjunctions: list[str] = field(default_factory=list)  # planets sharing its house
    conjunction_influence: str = "none"   # benefic | malefic | mixed | none
    aspect_quality: str = ""        # for aspectors: benefic | malefic | neutral
    dispositor: str = ""            # lord of the sign it occupies
    lords_house: int | None = None  # which house this planet lords (for house-lord factors)


@dataclass
class DashaActivation:
    maha_lord: str
    antar_lord: str
    maha_end: str
    antar_end: str
    maha_is_significator: bool      # maha lord is a topic significator
    antar_is_significator: bool
    maha_functional_nature: str
    antar_functional_nature: str
    activation_strength: str        # "strong" | "moderate" | "weak"


@dataclass
class SignificatorResult:
    topic: str
    primary_houses: list[int]
    karaka_planets: list[str]
    relevant_varga: str
    factors: list[SignificatorFactor]
    dasha_activation: DashaActivation
    relevant_yogas: list[str]
    relevant_doshas: list[str]
    planets_in_topic_houses: dict[int, list[str]]   # house → [planet names]
    aspects_on_topic_houses: dict[int, list[str]]   # house → [planets aspecting it]


def _ord(n: int) -> str:
    """Ordinal house label: 1st, 2nd, 3rd, 4th..."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _apply_conjunction(kind: str, influence: str) -> str:
    """A benefic conjunction lifts an afflicting/neutral factor; a malefic conjunction
    drags a supporting/neutral one. Mixed or none leaves it unchanged."""
    if influence == "benefic":
        if kind == "afflicting":
            return "neutral"
        if kind == "neutral":
            return "supporting"
    elif influence == "malefic":
        if kind == "supporting":
            return "neutral"
        if kind == "neutral":
            return "afflicting"
    return kind


def _classify_kind(
    planet: str,
    dignity: str,
    functional_nature: str,
    role_type: str,                 # "house_lord" | "karaka" | "occupant" | "aspector"
    placed_house: int,
    is_primary: bool,               # lords the MAIN topic house, or is a karaka
    is_afflicting_role: bool,       # lords/occupies a dusthana for this topic
    neecha_bhanga: bool = False,
    quality: str = "",              # aspect quality, for aspectors
    conj_influence: str = "none",
) -> str:
    """Categorise a factor as supporting / afflicting / neutral.

    Phase B — principled classification that respects:
    - Neecha Bhanga: a cancelled debilitation counts as strength, not weakness.
    - Upachaya rule: natural malefics in 3/6/10/11 GIVE results (e.g. Saturn in 10th
      is good for career), so they are supporting there, not afflicting.
    - Primary significators (main house lord / karaka) judged by strength & placement,
      not merely by functional malefic/benefic status (they carry the topic regardless).
    - Aspect quality: a benefic's aspect supports, a malefic's afflicts.
    - Conjunction influence then nudges the result.

    Still categorical — the numeric weighting happens later in the assessment engine.
    """
    is_strong = dignity in ("exalted", "moolatrikona", "own sign") or (
        "debilitated" in dignity and neecha_bhanga
    )
    is_weak = ("debilitated" in dignity and not neecha_bhanga) or "combust" in dignity
    is_func_benefic = functional_nature in ("benefic", "yogakaraka")
    is_func_malefic = functional_nature == "malefic"
    natural_malefic = planet in NATURAL_MALEFICS

    # --- Aspectors: driven by aspect quality ---
    if role_type == "aspector":
        if quality == "benefic":
            kind = "supporting"
        elif quality == "malefic":
            kind = "afflicting"
        else:
            kind = "neutral"
        return _apply_conjunction(kind, conj_influence)

    # --- Occupants of the topic house ---
    if role_type == "occupant":
        if natural_malefic and placed_house in UPACHAYA_HOUSES:
            kind = "supporting"             # malefics thrive in upachaya houses
        elif natural_malefic:
            kind = "neutral" if is_strong else "afflicting"
        else:                               # natural benefic occupant
            kind = "neutral" if is_weak else "supporting"
        return _apply_conjunction(kind, conj_influence)

    # --- Primary significators: main house lord OR karaka ---
    if is_primary:
        if is_afflicting_role:              # the topic's own lord hides in a dusthana
            kind = "neutral" if is_strong else "afflicting"
        elif is_strong:
            kind = "supporting"
        elif is_weak:
            kind = "afflicting"             # weak primary significator = topic lacks support
        elif is_func_malefic:
            kind = "neutral"                # functional malefic but still the topic's own lord
        else:
            kind = "supporting" if is_func_benefic else "neutral"
        return _apply_conjunction(kind, conj_influence)

    # --- Secondary house lords (incl. dusthana lords for the topic) ---
    if is_afflicting_role:
        kind = "neutral" if (is_strong and is_func_benefic) else "afflicting"
        return _apply_conjunction(kind, conj_influence)

    if is_strong and is_func_benefic:
        kind = "supporting"
    elif is_weak and is_func_malefic:
        kind = "afflicting"
    elif is_func_benefic:
        kind = "supporting"
    elif is_func_malefic:
        kind = "afflicting"
    else:
        kind = "neutral"
    return _apply_conjunction(kind, conj_influence)


def _varga_dignity(planet: str, chart: NormalizedChart, varga: str) -> str:
    """Compute the planet's dignity in the relevant divisional chart (D-9, D-10, ...)."""
    if varga == "D1":
        return ""
    pos = chart.planets.get(planet)
    if not pos:
        return ""
    return _varga_dig(planet, pos.longitude, varga)


def _yoga_links(planet: str, yogas: list[str], chart: NormalizedChart) -> list[str]:
    """Return yogas that are associated with this planet (name appears in yoga name or planet lords it)."""
    planet_lower = planet.lower()
    linked = []
    for yoga in yogas:
        if planet_lower in yoga.lower():
            linked.append(yoga)
    # Also link Panch Mahapurusha yogas to their planet
    panch_map = {
        "Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
        "Venus": "Malavya", "Saturn": "Shasha",
    }
    if panch_map.get(planet) in yogas:
        linked.append(panch_map[planet])
    return list(set(linked))


def _activation_strength(
    maha_is_sig: bool, antar_is_sig: bool,
    maha_fn: str, antar_fn: str,
) -> str:
    if maha_is_sig and antar_is_sig:
        return "strong"
    if maha_is_sig or antar_is_sig:
        return "moderate"
    return "weak"


def _canonical_topic(raw: str) -> str | None:
    """Map one free-form topic string to a canonical TOPIC_HOUSE_MAP key.

    Keyword groups are checked FIRST so synonyms collapse to one canonical topic
    ("job"/"profession"/"work" → "career"), then exact match for keys not covered by
    any keyword group. Returns None if nothing matches."""
    key = (raw or "").strip().lower()
    if not key:
        return None
    for canonical, keywords in TOPIC_KEYWORDS.items():
        if canonical in TOPIC_HOUSE_MAP and (key == canonical or any(kw in key for kw in keywords)):
            return canonical
    if key in TOPIC_HOUSE_MAP:
        return key
    return None


def _resolve_topic(intent: IntentResult) -> str:
    """Resolve a single canonical topic from the intent (robust to free-form output).

    Without normalization, strings like "professional life" silently default to house
    [1] (self), producing a confident but wrong-topic verdict. Falls back to the intent
    category's default topic when nothing matches."""
    for raw in list(intent.entities.topics) + list(intent.retrieval_topics):
        canonical = _canonical_topic(raw)
        if canonical:
            return canonical
    return _intent_to_topic(intent.intent)


def resolve_topics(intent: IntentResult, limit: int = 2) -> list[str]:
    """Resolve up to `limit` distinct canonical topics from the intent.

    Handles compound questions ("career and marriage") by normalizing each candidate
    topic string and de-duplicating, preserving order. Always returns at least one."""
    candidates = list(intent.entities.topics) + list(intent.retrieval_topics)
    resolved: list[str] = []
    used_families: list[set[str]] = []

    def _family(topic: str) -> set[str]:
        for fam in TOPIC_FAMILIES:
            if topic in fam:
                return fam
        return {topic}

    for raw in candidates:
        canonical = _canonical_topic(raw)
        if not canonical or canonical in resolved:
            continue
        fam = _family(canonical)
        if any(fam == used for used in used_families):
            continue   # a near-synonym topic from this family is already resolved
        resolved.append(canonical)
        used_families.append(fam)
        if len(resolved) >= limit:
            break
    if not resolved:
        resolved.append(_resolve_topic(intent))
    return resolved


def get_significators(
    intent: IntentResult,
    chart: NormalizedChart,
    rule_result: RuleEngineResult,
    topic: str | None = None,
) -> SignificatorResult:
    """Main entry point. Returns a fully structured SignificatorResult.

    If `topic` is given it is used directly (already canonical); otherwise it is
    resolved from the intent. Multi-topic callers pass an explicit topic per call."""

    # --- Resolve topic (robust to free-form classifier output) ---
    if topic is None:
        topic = _resolve_topic(intent)

    primary_houses = TOPIC_HOUSE_MAP.get(topic, [1])
    karaka_planets = TOPIC_PLANET_MAP.get(topic, [])
    relevant_varga = TOPIC_VARGA_MAP.get(topic, "D1")
    afflicting_houses = TOPIC_AFFLICTING_HOUSES.get(topic, [6, 8, 12])
    functional = rule_result.functional_nature  # may be empty if lagna not in table
    main_house = primary_houses[0] if primary_houses else 1
    neecha_set = neecha_bhanga_planets(chart)

    def _enrich(planet: str) -> dict:
        """Phase B per-planet context: neecha bhanga, conjunctions, dispositor."""
        return {
            "neecha_bhanga": planet in neecha_set,
            "conjunctions": planets_conjunct(chart, planet),
            "conjunction_influence": conjunction_influence(chart, planet),
            "dispositor": dispositor_of(chart, planet),
        }

    factors: list[SignificatorFactor] = []
    seen_planets: set[str] = set()

    # --- 1. House lord analysis ---
    for house_num in primary_houses:
        lord = rule_result.house_lords.get(house_num, "")
        if not lord or lord == "Unknown":
            continue
        pos = chart.planets.get(lord)
        if not pos:
            continue

        is_afflicting_lord = pos.house in afflicting_houses
        fn = functional.get(lord, "unknown")
        dignity = rule_result.planet_strengths.get(lord, "neutral sign")
        aspects_primary = any(
            h in rule_result.aspects_by_planet.get(lord, [])
            for h in primary_houses
        )
        enr = _enrich(lord)
        is_primary = house_num == main_house

        factors.append(SignificatorFactor(
            role=f"{_ord(house_num)} lord",
            planet=lord,
            placed_house=pos.house,
            sign=pos.sign,
            dignity=dignity,
            functional_nature=fn,
            dig_bala=DIG_BALA_HOUSES.get(lord) == pos.house,
            aspects_topic_house=aspects_primary,
            kind=_classify_kind(
                lord, dignity, fn, "house_lord", pos.house,
                is_primary=is_primary, is_afflicting_role=is_afflicting_lord,
                neecha_bhanga=enr["neecha_bhanga"],
                conj_influence=enr["conjunction_influence"],
            ),
            varga_dignity=_varga_dignity(lord, chart, relevant_varga),
            yoga_links=_yoga_links(lord, rule_result.yogas_present, chart),
            neecha_bhanga=enr["neecha_bhanga"],
            conjunctions=enr["conjunctions"],
            conjunction_influence=enr["conjunction_influence"],
            dispositor=enr["dispositor"],
            lords_house=house_num,
        ))
        seen_planets.add(lord)

    # --- 2. Karaka (significator) planet analysis ---
    for planet in karaka_planets:
        if planet in seen_planets:
            # Already captured as house lord — enrich the existing factor's role
            for f in factors:
                if f.planet == planet:
                    f.role = f"{f.role} + karaka"
            continue
        pos = chart.planets.get(planet)
        if not pos:
            continue

        fn = functional.get(planet, "unknown")
        dignity = rule_result.planet_strengths.get(planet, "neutral sign")
        is_in_afflicting = pos.house in afflicting_houses
        aspects_primary = any(
            h in rule_result.aspects_by_planet.get(planet, [])
            for h in primary_houses
        )
        enr = _enrich(planet)

        factors.append(SignificatorFactor(
            role="karaka",
            planet=planet,
            placed_house=pos.house,
            sign=pos.sign,
            dignity=dignity,
            functional_nature=fn,
            dig_bala=DIG_BALA_HOUSES.get(planet) == pos.house,
            aspects_topic_house=aspects_primary,
            kind=_classify_kind(
                planet, dignity, fn, "karaka", pos.house,
                is_primary=True, is_afflicting_role=is_in_afflicting,
                neecha_bhanga=enr["neecha_bhanga"],
                conj_influence=enr["conjunction_influence"],
            ),
            varga_dignity=_varga_dignity(planet, chart, relevant_varga),
            yoga_links=_yoga_links(planet, rule_result.yogas_present, chart),
            neecha_bhanga=enr["neecha_bhanga"],
            conjunctions=enr["conjunctions"],
            conjunction_influence=enr["conjunction_influence"],
            dispositor=enr["dispositor"],
        ))
        seen_planets.add(planet)

    # --- 3. Planets physically in topic houses ---
    planets_in_topic_houses: dict[int, list[str]] = {}
    for house_num in primary_houses:
        residents = [
            name for name, pos in chart.planets.items()
            if pos.house == house_num
        ]
        planets_in_topic_houses[house_num] = residents
        for planet in residents:
            if planet in seen_planets:
                continue
            pos = chart.planets[planet]
            fn = functional.get(planet, "unknown")
            dignity = rule_result.planet_strengths.get(planet, "neutral sign")
            enr = _enrich(planet)

            factors.append(SignificatorFactor(
                role=f"occupies {_ord(house_num)} house",
                planet=planet,
                placed_house=pos.house,
                sign=pos.sign,
                dignity=dignity,
                functional_nature=fn,
                dig_bala=DIG_BALA_HOUSES.get(planet) == pos.house,
                aspects_topic_house=False,
                kind=_classify_kind(
                    planet, dignity, fn, "occupant", house_num,
                    is_primary=False, is_afflicting_role=False,
                    neecha_bhanga=enr["neecha_bhanga"],
                    conj_influence=enr["conjunction_influence"],
                ),
                varga_dignity=_varga_dignity(planet, chart, relevant_varga),
                yoga_links=_yoga_links(planet, rule_result.yogas_present, chart),
                neecha_bhanga=enr["neecha_bhanga"],
                conjunctions=enr["conjunctions"],
                conjunction_influence=enr["conjunction_influence"],
                dispositor=enr["dispositor"],
            ))
            seen_planets.add(planet)

    # --- 4. Planets aspecting topic houses ---
    aspects_on_topic_houses: dict[int, list[str]] = {}
    for house_num in primary_houses:
        aspectors = rule_result.planets_aspecting_house.get(house_num, [])
        aspects_on_topic_houses[house_num] = aspectors
        for planet in aspectors:
            if planet in seen_planets:
                continue
            pos = chart.planets.get(planet)
            if not pos:
                continue
            fn = functional.get(planet, "unknown")
            dignity = rule_result.planet_strengths.get(planet, "neutral sign")
            enr = _enrich(planet)
            quality = aspect_quality(planet, fn)

            factors.append(SignificatorFactor(
                role=f"aspects {_ord(house_num)} house",
                planet=planet,
                placed_house=pos.house,
                sign=pos.sign,
                dignity=dignity,
                functional_nature=fn,
                dig_bala=DIG_BALA_HOUSES.get(planet) == pos.house,
                aspects_topic_house=True,
                kind=_classify_kind(
                    planet, dignity, fn, "aspector", pos.house,
                    is_primary=False, is_afflicting_role=False,
                    neecha_bhanga=enr["neecha_bhanga"], quality=quality,
                    conj_influence=enr["conjunction_influence"],
                ),
                varga_dignity=_varga_dignity(planet, chart, relevant_varga),
                yoga_links=_yoga_links(planet, rule_result.yogas_present, chart),
                neecha_bhanga=enr["neecha_bhanga"],
                conjunctions=enr["conjunctions"],
                conjunction_influence=enr["conjunction_influence"],
                aspect_quality=quality,
                dispositor=enr["dispositor"],
            ))
            seen_planets.add(planet)

    # --- 5. Dasha activation ---
    maha = rule_result.active_dasha.get("maha", "")
    antar = rule_result.active_dasha.get("antar", "")
    all_significators = {f.planet for f in factors} | set(karaka_planets)

    maha_is_sig = maha in all_significators or maha in [rule_result.house_lords.get(h) for h in primary_houses]
    antar_is_sig = antar in all_significators or antar in [rule_result.house_lords.get(h) for h in primary_houses]
    maha_fn = functional.get(maha, "unknown")
    antar_fn = functional.get(antar, "unknown")

    dasha_activation = DashaActivation(
        maha_lord=maha,
        antar_lord=antar,
        maha_end=rule_result.active_dasha.get("maha_end", ""),
        antar_end=rule_result.active_dasha.get("antar_end", ""),
        maha_is_significator=maha_is_sig,
        antar_is_significator=antar_is_sig,
        maha_functional_nature=maha_fn,
        antar_functional_nature=antar_fn,
        activation_strength=_activation_strength(maha_is_sig, antar_is_sig, maha_fn, antar_fn),
    )

    # --- 6. Filter relevant yogas and doshas ---
    topic_keywords = {topic} | set(karaka_planets) | {str(h) for h in primary_houses}
    relevant_yogas = _filter_relevant_yogas(rule_result.yogas_present, topic, karaka_planets, factors)
    relevant_doshas = _filter_relevant_doshas(rule_result.doshas_present, topic)

    return SignificatorResult(
        topic=topic,
        primary_houses=primary_houses,
        karaka_planets=karaka_planets,
        relevant_varga=relevant_varga,
        factors=factors,
        dasha_activation=dasha_activation,
        relevant_yogas=relevant_yogas,
        relevant_doshas=relevant_doshas,
        planets_in_topic_houses=planets_in_topic_houses,
        aspects_on_topic_houses=aspects_on_topic_houses,
    )


def _intent_to_topic(intent: IntentCategory) -> str:
    """Fall back topic from intent category when no entity topic is extracted."""
    mapping = {
        IntentCategory.DASHA_QUERY: "general",
        IntentCategory.YOGA_QUERY: "general",
        IntentCategory.TIMING_QUERY: "general",
        IntentCategory.PLACEMENT_INTERPRETATION: "general",
        IntentCategory.TOPIC_READING: "career",
        IntentCategory.GENERAL_ASTROLOGY: "general",
    }
    return mapping.get(intent, "general")


# Topic-yoga relevance map: which yogas matter for which topics
_YOGA_TOPIC_MAP: dict[str, list[str]] = {
    "career":       ["Dharma Karmadhipati", "Raja Yoga", "Ruchaka", "Shasha", "Amala",
                     "Budhaditya", "Bhadra", "Neecha Bhanga Raja", "Viparita Raja"],
    "marriage":     ["Gajakesari", "Malavya", "Hamsa", "Chandra-Mangala"],
    "wealth":       ["Dhana Yoga", "Lakshmi", "Gajakesari", "Hamsa"],
    "children":     ["Hamsa", "Gajakesari"],
    "health":       ["Kemadruma", "Viparita Raja"],
    "spirituality": ["Hamsa", "Lakshmi", "Saraswati", "Kaal Sarp"],
    "education":    ["Saraswati", "Budhaditya", "Bhadra"],
    "finance":      ["Dhana Yoga", "Lakshmi"],
}

_DOSHA_TOPIC_MAP: dict[str, list[str]] = {
    "career":     ["Shrapit Dosha", "Pitra Dosha", "Kaal Sarp Dosha"],
    "marriage":   ["Mangal Dosha", "Kaal Sarp Dosha"],
    "health":     ["Grahan Dosha", "Mangal Dosha"],
    "children":   ["Grahan Dosha"],
    "finance":    ["Shrapit Dosha", "Kaal Sarp Dosha"],
    "spirituality": ["Kaal Sarp Dosha"],
}


def _filter_relevant_yogas(
    yogas: list[str],
    topic: str,
    karakas: list[str],
    factors: list[SignificatorFactor],
) -> list[str]:
    """Return yogas relevant to this topic — by topic map or by planet involvement."""
    topic_yogas = set(_YOGA_TOPIC_MAP.get(topic, []))
    factor_planets = {f.planet for f in factors}

    result = []
    for yoga in yogas:
        if yoga in topic_yogas:
            result.append(yoga)
            continue
        # Panch Mahapurusha: relevant if that planet is a significator
        panch = {"Ruchaka": "Mars", "Bhadra": "Mercury", "Hamsa": "Jupiter",
                 "Malavya": "Venus", "Shasha": "Saturn"}
        if yoga in panch and panch[yoga] in factor_planets:
            result.append(yoga)
    return result


def _filter_relevant_doshas(doshas: list[str], topic: str) -> list[str]:
    topic_doshas = set(_DOSHA_TOPIC_MAP.get(topic, []))
    return [d for d in doshas if d in topic_doshas]


def format_significators_for_prompt(result: SignificatorResult) -> str:
    """Format the SignificatorResult into a prompt section string."""
    if not result.factors:
        return ""

    lines = [f"[CHART SIGNIFICATORS — {result.topic} analysis]"]
    lines.append(f"Primary houses: {', '.join(str(h) for h in result.primary_houses)}")
    lines.append(f"Karakas (significator planets): {', '.join(result.karaka_planets) or 'none'}")
    if result.relevant_varga and result.relevant_varga != "D1":
        lines.append(f"Divisional chart: {result.relevant_varga}")
    lines.append("")

    supporting = [f for f in result.factors if f.kind == "supporting"]
    afflicting = [f for f in result.factors if f.kind == "afflicting"]
    neutral = [f for f in result.factors if f.kind == "neutral"]

    if supporting:
        lines.append("Supporting factors:")
        for f in supporting:
            line = f"  + {f.planet} ({f.role}): house {f.placed_house}, {f.sign}, {f.dignity}"
            extras = []
            if f.functional_nature in ("benefic", "yogakaraka"):
                extras.append(f"functional {f.functional_nature}")
            if f.dig_bala:
                extras.append("Dig Bala")
            if f.varga_dignity:
                extras.append(f"{result.relevant_varga}: {f.varga_dignity}")
            if f.yoga_links:
                extras.append(f"yoga: {', '.join(f.yoga_links)}")
            if extras:
                line += f" [{', '.join(extras)}]"
            lines.append(line)

    if afflicting:
        lines.append("Afflicting factors:")
        for f in afflicting:
            line = f"  - {f.planet} ({f.role}): house {f.placed_house}, {f.sign}, {f.dignity}"
            extras = []
            if f.functional_nature == "malefic":
                extras.append("functional malefic")
            if "combust" in f.dignity:
                extras.append("combust")
            if f.varga_dignity:
                extras.append(f"{result.relevant_varga}: {f.varga_dignity}")
            if extras:
                line += f" [{', '.join(extras)}]"
            lines.append(line)

    if neutral:
        lines.append("Mixed / neutral factors:")
        for f in neutral:
            lines.append(f"  ~ {f.planet} ({f.role}): house {f.placed_house}, {f.sign}, {f.dignity}")

    lines.append("")
    # Dasha
    d = result.dasha_activation
    dasha_line = f"Dasha: {d.maha_lord} Mahadasha / {d.antar_lord} Antardasha (ends {d.antar_end})"
    dasha_line += f" — topic activation: {d.activation_strength}"
    if d.maha_is_significator:
        dasha_line += f" [{d.maha_lord} is a topic significator, fn: {d.maha_functional_nature}]"
    elif d.antar_is_significator:
        dasha_line += f" [{d.antar_lord} is a topic significator, fn: {d.antar_functional_nature}]"
    lines.append(dasha_line)

    if result.relevant_yogas:
        lines.append(f"Relevant yogas: {', '.join(result.relevant_yogas)}")
    if result.relevant_doshas:
        lines.append(f"Relevant doshas: {', '.join(result.relevant_doshas)}")

    return "\n".join(lines)
