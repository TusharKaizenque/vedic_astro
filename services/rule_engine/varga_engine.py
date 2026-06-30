"""
Varga (Divisional Chart) Engine — D1 of Phase D.

Computes divisional-chart signs deterministically from the D-1 sidereal longitudes
(no API call, no ephemeris needed — the vargas are a pure function of the longitude).
Classical principle: a significator must be strong in BOTH the Rasi (D-1) and the
relevant varga (D-9 marriage, D-10 career, D-7 children, D-2 wealth, D-24 education,
D-4 property). The assessment uses this as a corroboration / contradiction signal.

Implements the standard BPHS division rules for the vargas the topic map uses:
D2 Hora, D3 Drekkana, D4 Chaturthamsa, D7 Saptamsa, D9 Navamsa, D10 Dasamsa,
D24 Chaturvimsamsa. Unknown vargas return "" (no signal).
"""
from __future__ import annotations

from models.chart import NormalizedChart
from utils.astro_constants import (
    DEBILITATION_SIGNS, EXALTATION_SIGNS, NATURAL_ENEMIES, NATURAL_FRIENDS,
    OWN_SIGNS, SIGN_RULERS, ZODIAC_SIGNS,
)


def _sign_index(longitude: float) -> int:
    return int(longitude // 30) % 12


def _deg_in_sign(longitude: float) -> float:
    return longitude % 30.0


def _d2_hora(longitude: float) -> int:
    sign = _sign_index(longitude)
    first_half = _deg_in_sign(longitude) < 15.0
    odd = sign % 2 == 0   # Aries(index0)=odd sign
    # Odd signs: 1st half Leo(4), 2nd half Cancer(3). Even signs: reverse.
    if odd:
        return 4 if first_half else 3
    return 3 if first_half else 4


def _d3_drekkana(longitude: float) -> int:
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // 10)   # 0,1,2
    return (sign + part * 4) % 12               # same, 5th, 9th from sign


def _d4_chaturthamsa(longitude: float) -> int:
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // 7.5)  # 0..3
    return (sign + part * 3) % 12               # kendras from the sign


def _d7_saptamsa(longitude: float) -> int:
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // (30.0 / 7))   # 0..6
    start = sign if sign % 2 == 0 else (sign + 6) % 12   # odd: same; even: 7th
    return (start + part) % 12


def _d9_navamsa(longitude: float) -> int:
    # Compute from the in-sign degree (like the other vargas) to avoid the floating-point
    # boundary error of the continuous form at exact sign cusps (0°, 30°, 60° ...).
    # Start sign by modality: movable→same sign, fixed→9th from it, dual→5th from it
    # (equivalent to the element rule: fire→Aries, earth→Capricorn, air→Libra, water→Cancer).
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // (30.0 / 9))   # 0..8
    mod = sign % 3                                       # 0 movable, 1 fixed, 2 dual
    start = sign if mod == 0 else (sign + 8) % 12 if mod == 1 else (sign + 4) % 12
    return (start + part) % 12


def _d10_dasamsa(longitude: float) -> int:
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // 3.0)          # 0..9
    start = sign if sign % 2 == 0 else (sign + 8) % 12   # odd: same; even: 9th
    return (start + part) % 12


def _d24_chaturvimsamsa(longitude: float) -> int:
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // 1.25)          # 0..23
    start = 4 if sign % 2 == 0 else 3                     # odd: Leo; even: Cancer
    return (start + part) % 12


def _d12_dwadasamsa(longitude: float) -> int:
    sign = _sign_index(longitude)
    part = int(_deg_in_sign(longitude) // 2.5)           # 0..11
    return (sign + part) % 12                             # starts from the sign itself


# Trimsamsa (D30) lords per 1° unequal divisions, mapped to a representative sign.
# Odd signs: Mars 0-5, Saturn 5-10, Jupiter 10-18, Mercury 18-25, Venus 25-30.
# Even signs: Venus 0-5, Mercury 5-12, Jupiter 12-20, Saturn 20-25, Mars 25-30.
_TRIMSAMSA_SIGN = {  # ruler -> representative sign index for dignity lookup
    "Mars": 0, "Venus": 1, "Mercury": 5, "Saturn": 10, "Jupiter": 8,
}


def _d30_trimsamsa(longitude: float) -> int:
    sign = _sign_index(longitude)
    deg = _deg_in_sign(longitude)
    odd = sign % 2 == 0
    if odd:
        ruler = ("Mars" if deg < 5 else "Saturn" if deg < 10 else "Jupiter"
                 if deg < 18 else "Mercury" if deg < 25 else "Venus")
    else:
        ruler = ("Venus" if deg < 5 else "Mercury" if deg < 12 else "Jupiter"
                 if deg < 20 else "Saturn" if deg < 25 else "Mars")
    return _TRIMSAMSA_SIGN[ruler]


_VARGA_FUNCS = {
    "D2": _d2_hora, "D3": _d3_drekkana, "D4": _d4_chaturthamsa,
    "D7": _d7_saptamsa, "D9": _d9_navamsa, "D10": _d10_dasamsa,
    "D12": _d12_dwadasamsa, "D24": _d24_chaturvimsamsa, "D30": _d30_trimsamsa,
}


def varga_sign(longitude: float, varga: str) -> str:
    """Return the sign name of a planet in the given divisional chart, or '' if D1/unknown."""
    if varga == "D1":
        return ZODIAC_SIGNS[_sign_index(longitude)]
    func = _VARGA_FUNCS.get(varga)
    if not func:
        return ""
    return ZODIAC_SIGNS[func(longitude)]


def varga_positions(chart: NormalizedChart, varga: str) -> dict[str, str]:
    """{planet: varga_sign} for all planets in a divisional chart."""
    return {
        name: varga_sign(pos.longitude, varga)
        for name, pos in chart.planets.items()
    }


def sign_dignity(planet: str, sign: str) -> str:
    """Dignity of a planet in a sign (sign-only — no moolatrikona degree band)."""
    if not sign:
        return ""
    if EXALTATION_SIGNS.get(planet) == sign:
        return "exalted"
    if DEBILITATION_SIGNS.get(planet) == sign:
        return "debilitated"
    if sign in OWN_SIGNS.get(planet, []):
        return "own sign"
    ruler = SIGN_RULERS.get(sign, "")
    if ruler in NATURAL_FRIENDS.get(planet, []):
        return "friendly sign"
    if ruler in NATURAL_ENEMIES.get(planet, []):
        return "enemy sign"
    return "neutral sign"


def varga_dignity(planet: str, longitude: float, varga: str) -> str:
    """Dignity of a planet in its divisional-chart sign."""
    return sign_dignity(planet, varga_sign(longitude, varga))


_STRONG = {"exalted", "own sign", "moolatrikona"}
_WEAK = {"debilitated", "enemy sign"}


def varga_agreement(d1_dignity: str, varga_dig: str) -> str:
    """Compare D-1 dignity vs varga dignity → 'confirms' | 'contradicts' | 'neutral'.

    A factor strong in D-1 and strong in the varga is confirmed (vargottama-like);
    strong in D-1 but weak in the varga is contradicted (the promise weakens on closer
    inspection), and vice versa."""
    if not varga_dig:
        return "neutral"
    d1_strong = any(s in d1_dignity for s in _STRONG)
    d1_weak = any(w in d1_dignity for w in _WEAK)
    v_strong = varga_dig in _STRONG
    v_weak = varga_dig in _WEAK
    if (d1_strong and v_strong) or (d1_weak and v_weak):
        return "confirms"
    if (d1_strong and v_weak) or (d1_weak and v_strong):
        return "contradicts"
    return "neutral"
