from models.chart import NormalizedChart


def detect_mangal_dosha(chart: NormalizedChart) -> bool:
    # TODO: ASTROLOGY EXPERT REQUIRED — Add Moon/Venus reference and cancellation rules.
    mars = chart.planets.get("Mars")
    return bool(mars and mars.house in (1, 2, 4, 7, 8, 12))


def detect_kaal_sarp_dosha(chart: NormalizedChart) -> bool:
    from services.rule_engine.yoga_detector import detect_kaal_sarp
    return detect_kaal_sarp(chart)


def detect_pitra_dosha(chart: NormalizedChart) -> bool:
    # TODO: ASTROLOGY EXPERT REQUIRED — Confirm the accepted aspect/house definitions.
    sun, rahu = chart.planets.get("Sun"), chart.planets.get("Rahu")
    return bool(sun and rahu and sun.house == rahu.house)


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
