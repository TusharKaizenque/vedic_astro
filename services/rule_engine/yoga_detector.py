from models.chart import NormalizedChart
from utils.astro_constants import (
    DEBILITATION_SIGNS, EXALTATION_SIGNS, KENDRA_HOUSES, NATURAL_BENEFICS,
    NATURAL_MALEFICS, OWN_SIGNS, SIGN_RULERS, TRIKONA_HOUSES,
)

DUSTHANA_HOUSES = [6, 8, 12]
BENEFIC_PLANETS = {"Jupiter", "Venus", "Mercury", "Moon"}


def _house_from(reference_house: int, target_house: int) -> int:
    """Position (1-12) of target_house counted from reference_house."""
    return ((target_house - reference_house) % 12) + 1


def _distance(a: int, b: int) -> int:
    diff = abs(a - b)
    return min(diff, 12 - diff)


def _in_sambandha(chart: NormalizedChart, p1_name: str, p2_name: str) -> bool:
    """Two planets form a classical RELATIONSHIP (sambandha): conjunction (same house),
    graha-drishti (either aspects the other's house, incl. Mars/Jupiter/Saturn special
    aspects), or parivartana (sign exchange). Mere mutual-kendra placement WITHOUT an
    aspect is NOT a relationship — counting it over-generates Raja yogas."""
    from services.rule_engine.aspect_engine import houses_aspected_by_planet

    p1 = chart.planets.get(p1_name)
    p2 = chart.planets.get(p2_name)
    if not p1 or not p2:
        return False
    if p1.house == p2.house:                                        # conjunction
        return True
    if p2.house in houses_aspected_by_planet(chart, p1_name) or \
            p1.house in houses_aspected_by_planet(chart, p2_name):  # graha-drishti
        return True
    if SIGN_RULERS.get(p1.sign) == p2_name and SIGN_RULERS.get(p2.sign) == p1_name:  # exchange
        return True
    return False


def _mutual_kendra(a: str, b: str, chart: NormalizedChart) -> bool:
    p1, p2 = chart.planets.get(a), chart.planets.get(b)
    return bool(p1 and p2 and _distance(p1.house, p2.house) in (0, 3, 6, 9))


def _is_dignified(planet: str, sign: str) -> bool:
    return sign in OWN_SIGNS.get(planet, []) or EXALTATION_SIGNS.get(planet) == sign


def _is_debilitated(planet: str, sign: str) -> bool:
    return DEBILITATION_SIGNS.get(planet) == sign


# ---------------------------------------------------------------------------
# Existing yogas
# ---------------------------------------------------------------------------

def detect_gajakesari(chart: NormalizedChart) -> bool:
    return _mutual_kendra("Moon", "Jupiter", chart)


def detect_budhaditya(chart: NormalizedChart) -> bool:
    sun, mercury = chart.planets.get("Sun"), chart.planets.get("Mercury")
    return bool(sun and mercury and sun.house == mercury.house)


def detect_chandra_mangala(chart: NormalizedChart) -> bool:
    return _mutual_kendra("Moon", "Mars", chart)


def detect_adhi_yoga(chart: NormalizedChart) -> bool:
    moon = chart.planets.get("Moon")
    if not moon:
        return False
    targets = {((moon.house + offset - 1) % 12) + 1 for offset in (5, 6, 7)}
    return all(chart.planets.get(p) and chart.planets[p].house in targets for p in ("Venus", "Mercury", "Jupiter"))


def detect_panch_mahapurusha(chart: NormalizedChart) -> list[str]:
    mapping = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa", "Venus": "Malavya", "Saturn": "Shasha"}
    return [
        yoga for planet, yoga in mapping.items()
        if (pos := chart.planets.get(planet))
        and pos.house in KENDRA_HOUSES
        and (pos.sign in OWN_SIGNS.get(planet, []) or EXALTATION_SIGNS.get(planet) == pos.sign)
    ]


def detect_kaal_sarp(chart: NormalizedChart) -> bool:
    rahu, ketu = chart.planets.get("Rahu"), chart.planets.get("Ketu")
    if not rahu or not ketu:
        return False
    arc: set[int] = set()
    house = rahu.house
    while house != ketu.house:
        arc.add(house)
        house = house % 12 + 1
    planet_houses = [chart.planets[p].house for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn") if p in chart.planets]
    other = set(range(1, 13)) - arc - {rahu.house, ketu.house}
    return bool(planet_houses) and (all(h in arc for h in planet_houses) or all(h in other for h in planet_houses))


# ---------------------------------------------------------------------------
# New yogas
# ---------------------------------------------------------------------------

def detect_neecha_bhanga_raja(chart: NormalizedChart) -> bool:
    """Neecha Bhanga Raja Yoga: debilitated planet's debilitation is cancelled,
    turning it into a source of strength.

    Classical conditions (any one suffices):
    1. The lord of the sign of debilitation is in kendra from lagna or Moon.
    2. The planet that would exalt in the debilitated planet's sign is in kendra.
    3. The debilitated planet is in kendra from lagna.
    4. The debilitated planet's dispositor aspects it.
    """
    lagna_sign = chart.lagna_sign
    lagna_house = 1
    moon = chart.planets.get("Moon")

    for planet, pos in chart.planets.items():
        if not _is_debilitated(planet, pos.sign):
            continue
        deb_sign = pos.sign
        # Lord of sign of debilitation
        deb_sign_lord = SIGN_RULERS.get(deb_sign, "")
        deb_lord_pos = chart.planets.get(deb_sign_lord)
        # Planet that exalts in the debilitation sign
        exalting_planet = next(
            (p for p, s in EXALTATION_SIGNS.items() if s == deb_sign), None
        )
        exalting_pos = chart.planets.get(exalting_planet) if exalting_planet else None

        # Condition 1: deb sign lord in kendra from lagna
        if deb_lord_pos and deb_lord_pos.house in KENDRA_HOUSES:
            return True
        # Condition 2: exalting planet in kendra from lagna
        if exalting_pos and exalting_pos.house in KENDRA_HOUSES:
            return True
        # Condition 3: debilitated planet itself in kendra
        if pos.house in KENDRA_HOUSES:
            return True
        # Condition 4: deb sign lord in kendra from Moon
        if moon and deb_lord_pos and _distance(moon.house, deb_lord_pos.house) in (0, 3, 6, 9):
            return True
    return False


def neecha_bhanga_planets(chart: NormalizedChart) -> set[str]:
    """Return the set of debilitated planets whose debilitation is cancelled.

    Uses the same four classical conditions as detect_neecha_bhanga_raja, but
    reports *which* planets are cancelled (so the significator engine can treat a
    cancelled-debilitated planet as effectively strong rather than weak)."""
    moon = chart.planets.get("Moon")
    cancelled: set[str] = set()
    for planet, pos in chart.planets.items():
        if not _is_debilitated(planet, pos.sign):
            continue
        deb_sign = pos.sign
        deb_sign_lord = SIGN_RULERS.get(deb_sign, "")
        deb_lord_pos = chart.planets.get(deb_sign_lord)
        exalting_planet = next((p for p, s in EXALTATION_SIGNS.items() if s == deb_sign), None)
        exalting_pos = chart.planets.get(exalting_planet) if exalting_planet else None

        if deb_lord_pos and deb_lord_pos.house in KENDRA_HOUSES:
            cancelled.add(planet)
        elif exalting_pos and exalting_pos.house in KENDRA_HOUSES:
            cancelled.add(planet)
        elif pos.house in KENDRA_HOUSES:
            cancelled.add(planet)
        elif moon and deb_lord_pos and _distance(moon.house, deb_lord_pos.house) in (0, 3, 6, 9):
            cancelled.add(planet)
    return cancelled


def detect_viparita_raja(chart: NormalizedChart) -> bool:
    """Viparita Raja Yoga: lord of a dusthana (6/8/12) placed in another dusthana.
    This turns bad-house energy inward, paradoxically conferring strength.
    """
    for planet, pos in chart.planets.items():
        # Find which house(s) this planet lords
        owned_houses = [
            h for h, hdata in chart.houses.items()
            if SIGN_RULERS.get(hdata.sign) == planet
        ]
        lords_a_dusthana = any(h in DUSTHANA_HOUSES for h in owned_houses)
        if lords_a_dusthana and pos.house in DUSTHANA_HOUSES:
            # Ensure the planet is NOT in the house it lords (that would be own-house, not viparita)
            if pos.house not in owned_houses:
                return True
    return False


def detect_dharma_karmadhipati(chart: NormalizedChart) -> bool:
    """Dharma Karmadhipati Yoga: lords of 9th (dharma) and 10th (karma) conjunct
    or in mutual kendra — one of the strongest raja yogas for career and fortune.
    """
    ninth_lord = SIGN_RULERS.get(chart.houses[9].sign)
    tenth_lord = SIGN_RULERS.get(chart.houses[10].sign)
    if not ninth_lord or not tenth_lord or ninth_lord == tenth_lord:
        return False
    return _in_sambandha(chart, ninth_lord, tenth_lord)


def detect_raja_yoga(chart: NormalizedChart) -> bool:
    """General Raja Yoga: lord of a kendra and lord of a trikona conjunct or in mutual kendra."""
    kendra_lords = {SIGN_RULERS.get(chart.houses[h].sign) for h in KENDRA_HOUSES}
    trikona_lords = {SIGN_RULERS.get(chart.houses[h].sign) for h in TRIKONA_HOUSES}
    # Exclude lagna lord from both (it's already a trikona lord — avoid trivial self-match)
    pairs_checked: set[tuple] = set()
    for kl in kendra_lords:
        for tl in trikona_lords:
            if kl == tl or not kl or not tl:
                continue
            pair = tuple(sorted([kl, tl]))
            if pair in pairs_checked:
                continue
            pairs_checked.add(pair)
            if _in_sambandha(chart, kl, tl):
                return True
    return False


def detect_dhana_yoga(chart: NormalizedChart) -> bool:
    """Dhana Yoga: the lords of the 2nd and 11th (the wealth houses) are linked — by
    conjunction, mutual aspect (opposition), or sign exchange (parivartana). Same planet
    lording both also qualifies."""
    second_lord = SIGN_RULERS.get(chart.houses[2].sign)
    eleventh_lord = SIGN_RULERS.get(chart.houses[11].sign)
    if not second_lord or not eleventh_lord:
        return False
    if second_lord == eleventh_lord:
        return True  # same planet lords both wealth houses
    p2 = chart.planets.get(second_lord)
    p11 = chart.planets.get(eleventh_lord)
    if not p2 or not p11:
        return False
    if p2.house == p11.house:
        return True                                   # conjunction
    if _distance(p2.house, p11.house) == 6:
        return True                                   # mutual 7th aspect (opposition)
    if p2.house == 11 and p11.house == 2:
        return True                                   # parivartana (2nd & 11th lords exchange)
    return False


def detect_lakshmi_yoga(chart: NormalizedChart) -> bool:
    """Lakshmi Yoga: 9th lord in own or exalted sign, placed in kendra or trikona."""
    ninth_lord = SIGN_RULERS.get(chart.houses[9].sign)
    if not ninth_lord:
        return False
    pos = chart.planets.get(ninth_lord)
    if not pos:
        return False
    return _is_dignified(ninth_lord, pos.sign) and pos.house in (KENDRA_HOUSES + TRIKONA_HOUSES)


def detect_saraswati_yoga(chart: NormalizedChart) -> bool:
    """Saraswati Yoga: Jupiter, Venus, AND Mercury all in kendra/trikona in own/exalted sign."""
    for planet in ("Jupiter", "Venus", "Mercury"):
        pos = chart.planets.get(planet)
        if not pos:
            return False
        if pos.house not in (KENDRA_HOUSES + TRIKONA_HOUSES):
            return False
        if not _is_dignified(planet, pos.sign):
            return False
    return True


def detect_kemadruma(chart: NormalizedChart) -> bool:
    """Kemadruma Yoga: Moon with NO planets in the 2nd or 12th from it.
    Cancelled if: any planet is in kendra from Moon, OR Moon is in kendra from lagna.

    This is an adverse yoga giving instability and lack of support.
    We return True only if present AND NOT cancelled.
    """
    moon = chart.planets.get("Moon")
    if not moon:
        return False
    second_from_moon = (moon.house % 12) + 1
    twelfth_from_moon = ((moon.house - 2) % 12) + 1
    planets_excl_moon_rahu_ketu = [
        p for name, p in chart.planets.items()
        if name not in ("Moon", "Rahu", "Ketu")
    ]
    # Check if any planet is in 2nd or 12th from Moon
    flanking = any(p.house in (second_from_moon, twelfth_from_moon) for p in planets_excl_moon_rahu_ketu)
    if flanking:
        return False
    # Check cancellations
    # 1. Any planet in kendra from Moon
    planets_in_kendra_from_moon = any(
        _distance(moon.house, p.house) in (0, 3, 6, 9)
        for p in planets_excl_moon_rahu_ketu
    )
    if planets_in_kendra_from_moon:
        return False
    # 2. Moon itself in kendra from lagna
    if moon.house in KENDRA_HOUSES:
        return False
    return True


def detect_sunapha(chart: NormalizedChart) -> bool:
    """Sunapha Yoga: planet(s) in 2nd from Moon (excluding Sun, Rahu, Ketu)."""
    moon = chart.planets.get("Moon")
    if not moon:
        return False
    second_from_moon = (moon.house % 12) + 1
    return any(
        p.house == second_from_moon
        for name, p in chart.planets.items()
        if name not in ("Moon", "Sun", "Rahu", "Ketu")
    )


def detect_anapha(chart: NormalizedChart) -> bool:
    """Anapha Yoga: planet(s) in 12th from Moon (excluding Sun, Rahu, Ketu)."""
    moon = chart.planets.get("Moon")
    if not moon:
        return False
    twelfth_from_moon = ((moon.house - 2) % 12) + 1
    return any(
        p.house == twelfth_from_moon
        for name, p in chart.planets.items()
        if name not in ("Moon", "Sun", "Rahu", "Ketu")
    )


# ---------------------------------------------------------------------------
# Lunar & solar yogas (planets flanking the Moon / Sun)
# ---------------------------------------------------------------------------

def _flanking(chart: NormalizedChart, ref: str, exclude: set[str]) -> tuple[bool, bool]:
    """Whether eligible planets sit in the 2nd and 12th from a reference planet."""
    pos = chart.planets.get(ref)
    if not pos:
        return False, False
    second = (pos.house % 12) + 1
    twelfth = ((pos.house - 2) % 12) + 1
    elig = [p for n, p in chart.planets.items() if n not in exclude]
    return (any(p.house == second for p in elig), any(p.house == twelfth for p in elig))


def detect_durudhara(chart: NormalizedChart) -> bool:
    """Planets (excl. Sun/nodes) in BOTH 2nd and 12th from the Moon — wealth & support."""
    has2, has12 = _flanking(chart, "Moon", {"Moon", "Sun", "Rahu", "Ketu"})
    return has2 and has12


def detect_vesi(chart: NormalizedChart) -> bool:
    """Planet (excl. Moon/nodes) in the 2nd from the Sun."""
    has2, _ = _flanking(chart, "Sun", {"Sun", "Moon", "Rahu", "Ketu"})
    return has2


def detect_vasi(chart: NormalizedChart) -> bool:
    """Planet (excl. Moon/nodes) in the 12th from the Sun."""
    _, has12 = _flanking(chart, "Sun", {"Sun", "Moon", "Rahu", "Ketu"})
    return has12


def detect_ubhayachari(chart: NormalizedChart) -> bool:
    """Planets on both sides of the Sun (2nd and 12th) — all-round success."""
    has2, has12 = _flanking(chart, "Sun", {"Sun", "Moon", "Rahu", "Ketu"})
    return has2 and has12


# ---------------------------------------------------------------------------
# Kartari (scissor) yogas — planets flanking the lagna
# ---------------------------------------------------------------------------

def detect_shubha_kartari(chart: NormalizedChart) -> bool:
    """Natural benefics in both the 2nd and 12th houses — protective 'good scissors'."""
    h2 = any(p.house == 2 and n in NATURAL_BENEFICS for n, p in chart.planets.items())
    h12 = any(p.house == 12 and n in NATURAL_BENEFICS for n, p in chart.planets.items())
    return h2 and h12


def detect_papa_kartari(chart: NormalizedChart) -> bool:
    """Natural malefics in both the 2nd and 12th houses — afflicting 'bad scissors'."""
    h2 = any(p.house == 2 and n in NATURAL_MALEFICS for n, p in chart.planets.items())
    h12 = any(p.house == 12 and n in NATURAL_MALEFICS for n, p in chart.planets.items())
    return h2 and h12


# ---------------------------------------------------------------------------
# Other classical yogas
# ---------------------------------------------------------------------------

def detect_amala(chart: NormalizedChart) -> bool:
    """Amala Yoga: a natural benefic in the 10th from the lagna or from the Moon — a
    spotless reputation and lasting fame."""
    moon = chart.planets.get("Moon")
    tenth_from_moon = ((moon.house + 8) % 12) + 1 if moon else None
    for n, p in chart.planets.items():
        if n in NATURAL_BENEFICS and (p.house == 10 or (tenth_from_moon and p.house == tenth_from_moon)):
            return True
    return False


def detect_shakata(chart: NormalizedChart) -> bool:
    """Shakata Yoga: the Moon in the 6th, 8th, or 12th from Jupiter — fluctuating fortunes."""
    moon, jup = chart.planets.get("Moon"), chart.planets.get("Jupiter")
    if not moon or not jup:
        return False
    return _house_from(jup.house, moon.house) in (6, 8, 12)


def detect_guru_mangala(chart: NormalizedChart) -> bool:
    """Guru-Mangala Yoga: Jupiter and Mars conjunct or in mutual aspect (including their
    special aspects) — drive guided by wisdom."""
    jup, mars = chart.planets.get("Jupiter"), chart.planets.get("Mars")
    if not jup or not mars:
        return False
    if jup.house == mars.house:
        return True
    from services.rule_engine.aspect_engine import houses_aspected_by_planet
    jup_aspects = houses_aspected_by_planet(chart, "Jupiter")
    mars_aspects = houses_aspected_by_planet(chart, "Mars")
    return mars.house in jup_aspects and jup.house in mars_aspects


def detect_kahala(chart: NormalizedChart) -> bool:
    """Kahala Yoga: 4th and 9th lords in mutual kendra — energy, courage and command."""
    l4 = SIGN_RULERS.get(chart.houses[4].sign)
    l9 = SIGN_RULERS.get(chart.houses[9].sign)
    if not l4 or not l9 or l4 == l9:
        return False
    p4, p9 = chart.planets.get(l4), chart.planets.get(l9)
    return bool(p4 and p9 and _distance(p4.house, p9.house) in (0, 3, 6, 9))


def detect_kalanidhi(chart: NormalizedChart) -> bool:
    """Kalanidhi Yoga: Jupiter in the 2nd or 5th, joined or aspected by Mercury and Venus —
    wealth, learning and refinement."""
    jup = chart.planets.get("Jupiter")
    if not jup or jup.house not in (2, 5):
        return False

    def influences(name: str) -> bool:
        p = chart.planets.get(name)
        if not p:
            return False
        return p.house == jup.house or _house_from(p.house, jup.house) == 7
    return influences("Mercury") and influences("Venus")


def detect_maha_bhagya(chart: NormalizedChart) -> bool:
    """Maha Bhagya Yoga: for a day birth, lagna, Sun and Moon all in odd signs; for a night
    birth, all in even signs — great fortune and good character."""
    from utils.astro_constants import ZODIAC_SIGNS
    try:
        hour = int(chart.birth_data.time.split(":")[0])
    except Exception:
        return False
    is_day = 6 <= hour < 18
    signs = [chart.lagna_sign,
             chart.planets["Sun"].sign if "Sun" in chart.planets else "",
             chart.planets["Moon"].sign if "Moon" in chart.planets else ""]
    idxs = [ZODIAC_SIGNS.index(s) for s in signs if s in ZODIAC_SIGNS]
    if len(idxs) < 3:
        return False
    odd = all(i % 2 == 0 for i in idxs)    # Aries(0) is an odd sign
    even = all(i % 2 == 1 for i in idxs)
    return odd if is_day else even


def detect_chatussagara(chart: NormalizedChart) -> bool:
    """Chatussagara Yoga: planets occupying all four kendras (1,4,7,10) — all-round prosperity."""
    occupied = {p.house for p in chart.planets.values()}
    return all(k in occupied for k in (1, 4, 7, 10))


def find_parivartana(chart: NormalizedChart) -> list[str]:
    """Parivartana (sign-exchange) yogas: two planets each occupying the other's sign.
    Classified by the houses involved: Maha (good houses), Dainya (a dusthana), Khala (3rd)."""
    found: list[str] = []
    seen: set[tuple] = set()
    for n1, p1 in chart.planets.items():
        if n1 in ("Rahu", "Ketu"):
            continue
        l1 = SIGN_RULERS.get(p1.sign)
        if not l1 or l1 == n1:
            continue
        p2 = chart.planets.get(l1)
        if not p2 or SIGN_RULERS.get(p2.sign) != n1:
            continue
        pair = tuple(sorted([n1, l1]))
        if pair in seen:
            continue
        seen.add(pair)
        houses = {p1.house, p2.house}
        if houses & {6, 8, 12}:
            found.append("Dainya Parivartana")
        elif 3 in houses:
            found.append("Khala Parivartana")
        else:
            found.append("Maha Parivartana")
    return list(dict.fromkeys(found))


def detect_all_yogas(chart: NormalizedChart) -> list[str]:
    yogas = []
    checks = [
        (detect_gajakesari,          "Gajakesari"),
        (detect_budhaditya,          "Budhaditya"),
        (detect_chandra_mangala,     "Chandra-Mangala"),
        (detect_adhi_yoga,           "Adhi"),
        (detect_neecha_bhanga_raja,  "Neecha Bhanga Raja"),
        (detect_viparita_raja,       "Viparita Raja"),
        (detect_dharma_karmadhipati, "Dharma Karmadhipati"),
        (detect_raja_yoga,           "Raja Yoga"),
        (detect_dhana_yoga,          "Dhana Yoga"),
        (detect_lakshmi_yoga,        "Lakshmi"),
        (detect_saraswati_yoga,      "Saraswati"),
        (detect_kemadruma,           "Kemadruma"),
        (detect_sunapha,             "Sunapha"),
        (detect_anapha,              "Anapha"),
        (detect_durudhara,           "Durudhara"),
        (detect_kaal_sarp,           "Kaal Sarp"),
        (detect_vesi,                "Vesi"),
        (detect_vasi,                "Vasi"),
        (detect_ubhayachari,         "Ubhayachari"),
        (detect_shubha_kartari,      "Shubha Kartari"),
        (detect_papa_kartari,        "Papa Kartari"),
        (detect_amala,               "Amala"),
        (detect_shakata,             "Shakata"),
        (detect_guru_mangala,        "Guru-Mangala"),
        (detect_kahala,              "Kahala"),
        (detect_kalanidhi,           "Kalanidhi"),
        (detect_maha_bhagya,         "Maha Bhagya"),
        (detect_chatussagara,        "Chatussagara"),
    ]
    for predicate, name in checks:
        if predicate(chart):
            yogas.append(name)
    yogas.extend(detect_panch_mahapurusha(chart))
    yogas.extend(find_parivartana(chart))
    return yogas
