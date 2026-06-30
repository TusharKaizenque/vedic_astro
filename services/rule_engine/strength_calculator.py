from models.chart import NormalizedChart
from utils.astro_constants import (
    DEBILITATION_SIGNS, EXALTATION_SIGNS, MOOLATRIKONA_SIGNS,
    NATURAL_ENEMIES, NATURAL_FRIENDS, OWN_SIGNS, SIGN_RULERS, combustion_orb,
)


def get_planet_strength(planet: str, sign: str, degree: float = 0.0) -> str:
    if EXALTATION_SIGNS.get(planet) == sign:
        return "exalted"
    if DEBILITATION_SIGNS.get(planet) == sign:
        return "debilitated"
    ranges = {
        "Sun": (0, 20), "Moon": (4, 30), "Mars": (0, 12), "Mercury": (16, 20),
        "Jupiter": (0, 10), "Venus": (0, 15), "Saturn": (0, 20),
    }
    if MOOLATRIKONA_SIGNS.get(planet) == sign and ranges.get(planet, (0, 30))[0] <= degree <= ranges.get(planet, (0, 30))[1]:
        return "moolatrikona"
    if sign in OWN_SIGNS.get(planet, []):
        return "own sign"
    ruler = SIGN_RULERS.get(sign, "")
    if ruler in NATURAL_FRIENDS.get(planet, []):
        return "friendly sign"
    if ruler in NATURAL_ENEMIES.get(planet, []):
        return "enemy sign"
    return "neutral sign"


def calculate_all_strengths(chart: NormalizedChart) -> dict[str, str]:
    strengths = {}
    sun = chart.planets.get("Sun")
    for name, pos in chart.planets.items():
        value = get_planet_strength(name, pos.sign, pos.degree_in_sign)
        # Combustion: within the planet's own classical orb of the Sun (Moon can combust too).
        if sun and name not in ("Sun", "Rahu", "Ketu"):
            separation = abs(pos.longitude - sun.longitude)
            separation = min(separation, 360 - separation)
            if separation <= combustion_orb(name, pos.is_retrograde):
                value += " (combust)"
        strengths[name] = value
    return strengths
