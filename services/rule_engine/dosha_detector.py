from models.chart import NormalizedChart
from utils.astro_constants import EXALTATION_SIGNS, OWN_SIGNS, SIGN_RULERS

_MANGAL_HOUSES = (1, 2, 4, 7, 8, 12)


def _house_from(reference_house: int, target_house: int) -> int:
    """Position (1-12) of target_house counted from reference_house."""
    return ((target_house - reference_house) % 12) + 1


def detect_mangal_dosha(chart: NormalizedChart) -> bool:
    """Mangal (Kuja/Manglik) Dosha: Mars in the 1st/2nd/4th/7th/8th/12th — checked from the
    LAGNA, the MOON, and VENUS (the three classical reference points). Cancelled when Mars
    is in its own sign or exalted (a common, widely-accepted cancellation)."""
    mars = chart.planets.get("Mars")
    if not mars:
        return False
    # Common cancellation: Mars dignified (own sign or exalted) neutralises the dosha.
    if mars.sign in OWN_SIGNS.get("Mars", []) or EXALTATION_SIGNS.get("Mars") == mars.sign:
        return False

    references = [1]  # lagna is house 1
    moon = chart.planets.get("Moon")
    venus = chart.planets.get("Venus")
    if moon:
        references.append(moon.house)
    if venus:
        references.append(venus.house)
    return any(_house_from(ref, mars.house) in _MANGAL_HOUSES for ref in references)


def detect_kaal_sarp_dosha(chart: NormalizedChart) -> bool:
    from services.rule_engine.yoga_detector import detect_kaal_sarp
    return detect_kaal_sarp(chart)


def detect_pitra_dosha(chart: NormalizedChart) -> bool:
    """Pitra Dosha (ancestral karma): NODE-driven affliction of the father/9th significations.
    Triggers on: the Sun (father karaka) conjunct Rahu/Ketu, OR a node in the 9th house, OR
    the 9th lord conjunct a node. (Saturn alone in the 9th is NOT Pitra dosha.)"""
    node_houses = {chart.planets[p].house for p in ("Rahu", "Ketu") if p in chart.planets}
    sun = chart.planets.get("Sun")
    if sun and sun.house in node_houses:
        return True
    if 9 in node_houses:
        return True
    ninth_lord = SIGN_RULERS.get(chart.houses[9].sign)
    lord_pos = chart.planets.get(ninth_lord) if ninth_lord else None
    if lord_pos and lord_pos.house in node_houses:
        return True
    return False


def detect_shrapit_dosha(chart: NormalizedChart) -> bool:
    saturn, rahu = chart.planets.get("Saturn"), chart.planets.get("Rahu")
    return bool(saturn and rahu and saturn.house == rahu.house)


def detect_grahan_dosha(chart: NormalizedChart) -> bool:
    sun, moon = chart.planets.get("Sun"), chart.planets.get("Moon")
    rahu, ketu = chart.planets.get("Rahu"), chart.planets.get("Ketu")
    if not rahu or not ketu:
        return False
    shadows = {rahu.house, ketu.house}
    return bool((sun and sun.house in shadows) or (moon and moon.house in shadows))


def detect_all_doshas(chart: NormalizedChart) -> list[str]:
    checks = (
        (detect_mangal_dosha, "Mangal Dosha"),
        (detect_kaal_sarp_dosha, "Kaal Sarp Dosha"),
        (detect_pitra_dosha, "Pitra Dosha"),
        (detect_shrapit_dosha, "Shrapit Dosha"),
        (detect_grahan_dosha, "Grahan Dosha"),
    )
    return [name for predicate, name in checks if predicate(chart)]
