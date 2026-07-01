"""
Special sensitive points — currently the Bhrigu Bindu.

Bhrigu Bindu (popularised from the Chandra Kala Nadi / C. S. Patel) is the midpoint of Rahu
and the Moon: a karmic "destiny point" marking the house/area where life's pivotal, fated
events concentrate. It fructifies when its sign-lord's dasha runs or a slow planet (Jupiter,
Saturn, Rahu-Ketu) transits over it. Deterministic — computed from Rahu and Moon longitudes.
"""
from __future__ import annotations

from dataclasses import dataclass

from models.chart import NormalizedChart
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS

_HOUSE_THEME = {
    1: "the self, direction and identity", 2: "wealth, family and speech",
    3: "effort, courage and communication", 4: "home, roots and inner peace",
    5: "children, creativity and intelligence", 6: "service, health and overcoming rivals",
    7: "marriage and partnerships", 8: "transformation, upheaval and the hidden",
    9: "fortune, dharma and higher purpose", 10: "career, status and public action",
    11: "gains, networks and fulfilment", 12: "foreign lands, loss and liberation",
}


def _ord(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@dataclass
class BhriguBindu:
    longitude: float
    sign: str
    house_from_lagna: int
    sign_lord: str


def bhrigu_bindu(chart: NormalizedChart) -> BhriguBindu | None:
    rahu = chart.planets.get("Rahu")
    moon = chart.planets.get("Moon")
    if not rahu or not moon or chart.lagna_sign not in ZODIAC_SIGNS:
        return None
    r = rahu.longitude % 360.0
    m = moon.longitude % 360.0
    # Midpoint along the arc from Rahu forward to the Moon.
    bb_lon = (r + ((m - r) % 360.0) / 2.0) % 360.0
    sign_idx = int(bb_lon // 30) % 12
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign)
    house = ((sign_idx - lagna_idx) % 12) + 1
    sign = ZODIAC_SIGNS[sign_idx]
    return BhriguBindu(round(bb_lon, 2), sign, house, SIGN_RULERS.get(sign, ""))


def format_bhrigu_bindu_for_prompt(bb: BhriguBindu | None) -> str:
    if bb is None:
        return ""
    theme = _HOUSE_THEME.get(bb.house_from_lagna, "")
    return (
        "[BHRIGU BINDU — the Rahu-Moon destiny point; where pivotal, fated events concentrate]\n"
        f"Bhrigu Bindu in {bb.sign} (the {_ord(bb.house_from_lagna)} house), lord {bb.sign_lord} — "
        f"life's turning points cluster around {theme}. It activates when {bb.sign_lord}'s dasha "
        f"runs or a slow planet (Jupiter/Saturn/Rahu-Ketu) transits {bb.sign}."
    )
