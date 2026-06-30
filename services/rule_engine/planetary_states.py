"""
Planetary states (avasthas & conditions) — the per-planet, chart-SPECIFIC facts that make a
reading about *this* person rather than a generic "Mars in the 10th" placement.

Everything here is a deterministic function of the chart, so it is (a) identical every time the
same chart is read, and (b) specific to the individual. It surfaces classical conditions the
placement-level KB cannot express:

  - Combustion (Astangata): a planet too close to the Sun, its significations scorched.
  - Planetary war (Graha Yuddha): two true planets within 1°, one defeated.
  - Baladi avastha: infant/adolescent/young/old/dead by degree — how much result it can give.
  - Refined dignity: exalted / moolatrikona / own / friendly / neutral / enemy / debilitated,
    using the moolatrikona DEGREE range, not just the sign.

Sources: Brihat Parashara Hora Shastra (Graha Avastha, Astangata, Graha Yuddha chapters),
Phaladeepika, Saravali.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from utils.astro_constants import (
    DEBILITATION_SIGNS, EXALTATION_SIGNS, NATURAL_ENEMIES, NATURAL_FRIENDS, OWN_SIGNS,
    SIGN_RULERS, ZODIAC_SIGNS, combustion_orb,
)

# True planets that can be combust or wage planetary war (the luminaries and shadow planets
# are excluded — the Sun cannot combust itself, the nodes have no disc).
_TRUE_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# Moolatrikona degree ranges (within the moolatrikona sign), per BPHS. Outside the range but in
# the same sign the planet is merely in its own sign.
_MOOLATRIKONA_RANGE = {
    "Sun": ("Leo", 0.0, 20.0), "Moon": ("Taurus", 3.0, 30.0), "Mars": ("Aries", 0.0, 12.0),
    "Mercury": ("Virgo", 15.0, 20.0), "Jupiter": ("Sagittarius", 0.0, 10.0),
    "Venus": ("Libra", 0.0, 15.0), "Saturn": ("Aquarius", 0.0, 20.0),
}

# Strength ordering of dignities — used as the graha-yuddha victor proxy (see below).
_DIGNITY_RANK = {
    "exalted": 5, "moolatrikona": 4, "own sign": 3, "friendly sign": 2,
    "neutral sign": 1, "enemy sign": 0, "debilitated": -1,
}

_BALADI = ["Infant", "Adolescent", "Young", "Old", "Dead"]
# How much of its result a planet in each Baladi avastha can deliver.
_BALADI_POTENCY = {
    "Infant": "gives little of its result (immature)",
    "Adolescent": "gives a moderate part of its result",
    "Young": "gives its FULL result (peak potency)",
    "Old": "gives a weak, declining result",
    "Dead": "gives almost none of its result (dormant)",
}


@dataclass
class PlanetState:
    planet: str
    dignity: str = "neutral sign"
    combust: bool = False
    combust_orb: float = 0.0          # degrees from the Sun (when combust)
    war: bool = False
    war_won: bool = False
    war_with: str = ""
    avastha: str = ""                 # Baladi state
    avastha_effect: str = ""          # what that avastha means for its result
    retrograde: bool = False
    notes: list[str] = field(default_factory=list)


def _sep(a: float, b: float) -> float:
    """Angular separation 0–180° between two ecliptic longitudes."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def dignity_of(planet: str, sign: str, degree_in_sign: float = 0.0) -> str:
    """Refined classical dignity, accounting for the moolatrikona degree range."""
    if EXALTATION_SIGNS.get(planet) == sign:
        return "exalted"
    if DEBILITATION_SIGNS.get(planet) == sign:
        return "debilitated"
    mt = _MOOLATRIKONA_RANGE.get(planet)
    if mt and mt[0] == sign and mt[1] <= degree_in_sign < mt[2]:
        return "moolatrikona"
    if sign in OWN_SIGNS.get(planet, []):
        return "own sign"
    lord = SIGN_RULERS.get(sign, "")
    if lord and lord in NATURAL_FRIENDS.get(planet, []):
        return "friendly sign"
    if lord and lord in NATURAL_ENEMIES.get(planet, []):
        return "enemy sign"
    return "neutral sign"


def _baladi_avastha(sign: str, degree_in_sign: float) -> str:
    """Infant→Dead over 6° portions. In ODD signs the order runs infant→dead; in EVEN signs it
    is reversed (BPHS). Aries is the 1st (odd) sign."""
    if sign not in ZODIAC_SIGNS:
        return ""
    portion = min(4, int(degree_in_sign // 6.0))
    is_odd_sign = ZODIAC_SIGNS.index(sign) % 2 == 0   # Aries=index0 ⇒ odd
    if not is_odd_sign:
        portion = 4 - portion
    return _BALADI[portion]


def compute_planet_states(chart: NormalizedChart) -> dict[str, PlanetState]:
    """Per-planet states for the whole chart."""
    sun = chart.planets.get("Sun")
    states: dict[str, PlanetState] = {}

    for name, pos in chart.planets.items():
        st = PlanetState(
            planet=name,
            dignity=dignity_of(name, pos.sign, pos.degree_in_sign),
            retrograde=pos.is_retrograde,
        )
        # Combustion — true planets within their orb of the Sun.
        if name in _TRUE_PLANETS and sun is not None:
            orb = _sep(pos.longitude, sun.longitude)
            if orb <= combustion_orb(name, pos.is_retrograde):
                st.combust = True
                st.combust_orb = round(orb, 2)
                st.notes.append(
                    f"combust ({st.combust_orb}° from the Sun) — its significations are "
                    f"weakened/scorched"
                )
        # Baladi avastha.
        st.avastha = _baladi_avastha(pos.sign, pos.degree_in_sign)
        if st.avastha:
            st.avastha_effect = _BALADI_POTENCY.get(st.avastha, "")
        states[name] = st

    # Planetary war (Graha Yuddha): two true planets in the SAME sign within 1°. The classical
    # victor is the stronger/brighter (northern) planet; lacking celestial latitude here, we use
    # the better dignity as the strength proxy (a defensible deterministic rule), and only fall
    # back to the lower-longitude convention to break an exact tie. The loser is weakened.
    war_planets = [n for n in _TRUE_PLANETS if n in chart.planets]
    for i in range(len(war_planets)):
        for j in range(i + 1, len(war_planets)):
            a, b = war_planets[i], war_planets[j]
            pa, pb = chart.planets[a], chart.planets[b]
            if pa.sign == pb.sign and _sep(pa.longitude, pb.longitude) <= 1.0:
                ra = _DIGNITY_RANK.get(states[a].dignity, 1)
                rb = _DIGNITY_RANK.get(states[b].dignity, 1)
                if ra != rb:
                    winner, loser = (a, b) if ra > rb else (b, a)
                else:
                    winner, loser = (a, b) if pa.longitude <= pb.longitude else (b, a)
                for who, won in ((winner, True), (loser, False)):
                    s = states[who]
                    s.war = True
                    s.war_won = won
                    s.war_with = loser if won else winner
                    s.notes.append(
                        f"in planetary war (graha yuddha) with {(loser if won else winner)} — "
                        + ("victor (keeps its strength)" if won else "defeated (loses strength)")
                    )
    return states


def format_planet_states_for_prompt(states: dict[str, PlanetState]) -> str:
    """Only emit the NOTEWORTHY states (combust / at war / extreme avastha / strong dignity) so
    the block stays signal-dense and chart-specific."""
    notable: list[str] = []
    for name, st in states.items():
        bits: list[str] = []
        if st.dignity in ("exalted", "debilitated", "moolatrikona"):
            bits.append(st.dignity)
        if st.combust:
            bits.append(f"combust ({st.combust_orb}° from Sun)")
        if st.war:
            bits.append("won planetary war" if st.war_won else f"lost planetary war to {st.war_with}")
        if st.avastha in ("Young", "Dead", "Infant"):
            bits.append(f"{st.avastha} avastha — {st.avastha_effect}")
        if st.retrograde and name not in ("Rahu", "Ketu"):
            bits.append("retrograde (intensified, inward results)")
        if bits:
            notable.append(f"  {name}: " + "; ".join(bits))
    if not notable:
        return ""
    return "[PLANETARY STATES — chart-specific conditions]\n" + "\n".join(notable)
