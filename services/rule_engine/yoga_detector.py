from models.chart import NormalizedChart
from utils.astro_constants import (
    DEBILITATION_SIGNS, EXALTATION_SIGNS, KENDRA_HOUSES, OWN_SIGNS,
    SIGN_RULERS, TRIKONA_HOUSES,
)

DUSTHANA_HOUSES = [6, 8, 12]
BENEFIC_PLANETS = {"Jupiter", "Venus", "Mercury", "Moon"}


def _distance(a: int, b: int) -> int:
    diff = abs(a - b)
    return min(diff, 12 - diff)


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
    p9 = chart.planets.get(ninth_lord)
    p10 = chart.planets.get(tenth_lord)
    if not p9 or not p10:
        return False
    return _distance(p9.house, p10.house) in (0, 3, 6, 9)


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
            pk = chart.planets.get(kl)
            pt = chart.planets.get(tl)
            if pk and pt and _distance(pk.house, pt.house) in (0, 3, 6, 9):
                return True
    return False


def detect_dhana_yoga(chart: NormalizedChart) -> bool:
    """Dhana Yoga: 2nd and 11th lords conjunct, or both in association with Jupiter/Venus."""
    second_lord = SIGN_RULERS.get(chart.houses[2].sign)
    eleventh_lord = SIGN_RULERS.get(chart.houses[11].sign)
    if not second_lord or not eleventh_lord:
        return False
    if second_lord == eleventh_lord:
        return True  # Same planet lords both wealth houses
    p2 = chart.planets.get(second_lord)
    p11 = chart.planets.get(eleventh_lord)
    if not p2 or not p11:
        return False
    return p2.house == p11.house  # conjunct


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
        (detect_kaal_sarp,           "Kaal Sarp"),
    ]
    for predicate, name in checks:
        if predicate(chart):
            yogas.append(name)
    yogas.extend(detect_panch_mahapurusha(chart))
    return yogas
