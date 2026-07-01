"""
Bhava-lord placement interpreter — the spine of Phalita (predictive) Jyotisha.

Where each house LORD is placed tells you how that area of life actually plays out: "the lord
of the 10th (career) in the 11th (gains & networks)" is a concrete, chart-specific statement
that a generic "you have a 10th house" reading can never make. Per BPHS (Bhavesha-phala), a
house lord carries its house's matters INTO the house it occupies, coloured by the placement's
quality (kendra/trikona elevate, dusthana obstruct) and the planet's own dignity/state.

This is generated compositionally from house themes + placement quality, so it is deterministic
(identical every reading) and covers all 144 lord/house combinations without hand-authoring.
"""
from __future__ import annotations

from dataclasses import dataclass

from models.chart import NormalizedChart
from services.rule_engine.planetary_states import PlanetState
from utils.astro_constants import (
    DUSTHANA_HOUSES, KENDRA_HOUSES, SIGN_RULERS, TRIKONA_HOUSES,
)

# Concise theme of each bhava (for compositional blending).
HOUSE_THEMES = {
    1: "the self, vitality and life-direction", 2: "wealth, family and speech",
    3: "courage, siblings and self-effort", 4: "home, mother, property and inner peace",
    5: "intelligence, children and creativity", 6: "service, health, debts and rivals",
    7: "marriage, partnerships and public dealings", 8: "upheaval, longevity and hidden matters",
    9: "fortune, dharma, father and higher learning", 10: "career, status and public action",
    11: "gains, income and networks", 12: "loss, expenditure, foreign lands and liberation",
}


def _ord(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th' …"""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@dataclass
class BhavaLordReading:
    house: int                 # the house being ruled
    lord: str                  # its lord (planet)
    placed_house: int          # where the lord sits
    quality: str               # strengthened | supported | challenged | viparita | neutral
    statement: str


def _placement_quality(house: int, placed: int, dignity: str) -> str:
    """How the placement treats the ruled house's matters."""
    good_house = placed in (KENDRA_HOUSES + TRIKONA_HOUSES)
    bad_house = placed in DUSTHANA_HOUSES
    ruled_is_dusthana = house in DUSTHANA_HOUSES
    weak_dignity = dignity in ("debilitated", "enemy sign")
    strong_dignity = dignity in ("exalted", "moolatrikona", "own sign")

    if house == placed:
        return "strengthened"                       # lord in own house — anchors its matters
    if ruled_is_dusthana and bad_house:
        # Viparita Raja Yoga (Harsha/Sarala/Vimala): a 6/8/12 lord in a dusthana CAN turn
        # difficulty into gain — but only cleanly when the lord itself is not crippled. An
        # afflicted (debilitated/enemy) such lord reads as strain, not a reliable blessing.
        return "challenged" if weak_dignity else "viparita"
    if bad_house or weak_dignity:
        return "challenged"
    if good_house and strong_dignity:
        return "strengthened"
    if good_house:
        return "supported"
    return "neutral"


_QUALITY_PHRASE = {
    "strengthened": "this area is well-anchored and tends to deliver",
    "supported": "this area finds support and generally develops well",
    "challenged": "this area meets friction and asks for conscious effort",
    "viparita": "difficulty here can convert into gain over time (viparita raja yoga), "
                "especially while this planet stays otherwise unafflicted",
    "neutral": "this area unfolds steadily, with mixed influences",
}


def analyze_bhava_lords(
    chart: NormalizedChart, states: dict[str, PlanetState]
) -> list[BhavaLordReading]:
    out: list[BhavaLordReading] = []
    for house in range(1, 13):
        hdata = chart.houses.get(house)
        if not hdata:
            continue
        lord = SIGN_RULERS.get(hdata.sign, "")
        pos = chart.planets.get(lord)
        # Guard against a malformed placement (house outside 1–12) so one bad datum can't
        # KeyError and take down the whole rule engine / reading.
        if not lord or not pos or pos.house not in HOUSE_THEMES:
            continue
        dignity = states[lord].dignity if lord in states else ""
        quality = _placement_quality(house, pos.house, dignity)
        extra = []
        if dignity in ("exalted", "debilitated", "moolatrikona", "own sign"):
            extra.append(dignity)
        if lord in states and states[lord].combust:
            extra.append("combust")
        if pos.is_retrograde and lord not in ("Rahu", "Ketu"):
            extra.append("retrograde")
        cond = f" ({', '.join(extra)})" if extra else ""
        statement = (
            f"{_ord(house)} lord {lord}{cond} in the {_ord(pos.house)} house — "
            f"carries {HOUSE_THEMES[house]} into {HOUSE_THEMES[pos.house]}; "
            f"{_QUALITY_PHRASE[quality]}."
        )
        out.append(BhavaLordReading(house, lord, pos.house, quality, statement))
    return out


def format_bhava_lords_for_prompt(
    readings: list[BhavaLordReading], focus_houses: list[int] | None = None
) -> str:
    if not readings:
        return ""
    focus = set(focus_houses or [])
    if focus:
        # Focused question → show ONLY the topic's houses (and where each of their lords sits).
        # Dumping all 12 life areas for a career question is noise that dilutes the answer.
        lord_houses = {r.placed_house for r in readings if r.house in focus}
        chosen = [r for r in readings if r.house in focus or r.house in lord_houses]
        chosen.sort(key=lambda r: (r.house not in focus, r.house))
    else:
        # No focus (life-overview) → the whole set, in house order.
        chosen = sorted(readings, key=lambda r: r.house)
    if not chosen:
        return ""
    lines = ["[BHAVA-LORD PLACEMENTS — how each life area actually plays out (deterministic)]"]
    lines.extend(f"  • {r.statement}" for r in chosen)
    return "\n".join(lines)
