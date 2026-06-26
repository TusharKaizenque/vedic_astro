"""
Dispositor / Chain Engine (B1).

Implements the deeper Parashari relational logic the significator engine was missing:

  - Dispositor chains: a planet's results flow to the lord of the sign it occupies;
    following the chain reveals where a house's energy ultimately "lands."
  - Argala (intervention): planets in the 2nd / 4th / 11th from a house intervene to
    support it; planets in the 12th / 10th / 3rd obstruct (virodha argala).
  - Bhavat Bhavam ("house from house"): the Nth house counted from the Nth house is a
    secondary seat of the same matter (e.g. the 10th from the 10th = 7th supports career).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from utils.astro_constants import SIGN_RULERS


def dispositor_of(chart: NormalizedChart, planet: str) -> str:
    """The lord of the sign a planet occupies (its dispositor)."""
    pos = chart.planets.get(planet)
    if not pos:
        return ""
    return SIGN_RULERS.get(pos.sign, "")


def dispositor_chain(chart: NormalizedChart, planet: str, max_depth: int = 6) -> list[str]:
    """Follow planet → dispositor → its dispositor … until a self-loop or cycle.

    A planet in its own sign disposes itself and terminates the chain. Returns the
    ordered chain starting from `planet` (inclusive)."""
    chain = [planet]
    current = planet
    seen = {planet}
    for _ in range(max_depth):
        disp = dispositor_of(chart, current)
        if not disp or disp == current:      # own sign → terminal
            break
        chain.append(disp)
        if disp in seen:                     # cycle (mutual reception or longer loop)
            break
        seen.add(disp)
        current = disp
    return chain


def _house_at_offset(from_house: int, offset: int) -> int:
    return ((from_house - 1 + offset - 1) % 12) + 1


@dataclass
class Argala:
    house: int
    supporting: list[str] = field(default_factory=list)   # planets in 2/4/11 from house
    obstructing: list[str] = field(default_factory=list)  # planets in 12/10/3 from house
    net: str = "neutral"                                   # supporting | obstructing | mixed | neutral


# Argala houses (from the house in question) and their counteracting (virodha) houses.
_ARGALA_HOUSES = {2: 12, 4: 10, 11: 3}   # support_offset -> obstruct_offset


def argala_on_house(chart: NormalizedChart, house: int) -> Argala:
    """Compute Argala (intervention) on a house.

    Planets in the 2nd, 4th, 11th from the house create argala (intervention).
    Each is counteracted by planets in the 12th, 10th, 3rd respectively (virodha argala).
    Net argala is supporting only where intervention is not fully counteracted."""
    support_houses = {_house_at_offset(house, off) for off in _ARGALA_HOUSES}
    obstruct_houses = {_house_at_offset(house, off) for off in _ARGALA_HOUSES.values()}

    supporting = [n for n, p in chart.planets.items() if p.house in support_houses]
    obstructing = [n for n, p in chart.planets.items() if p.house in obstruct_houses]

    if supporting and obstructing:
        net = "mixed"
    elif supporting:
        net = "supporting"
    elif obstructing:
        net = "obstructing"
    else:
        net = "neutral"
    return Argala(house=house, supporting=supporting, obstructing=obstructing, net=net)


def bhavat_bhavam(house: int) -> int:
    """The Nth house from the Nth house — a secondary seat of the same matter."""
    return _house_at_offset(house, house)


@dataclass
class ChainAnalysis:
    house: int
    lord: str
    lord_chain: list[str]               # dispositor chain from the house lord
    final_dispositor: str               # where the chain lands
    argala: Argala
    bhavat_bhavam_house: int
    bhavat_bhavam_lord: str


def _ord(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def format_chain_for_prompt(analysis: ChainAnalysis, topic: str) -> str:
    """Compact deeper-structure block the LLM can narrate."""
    a = analysis
    if not a.lord:
        return ""
    lines = [f"[DEEPER STRUCTURE — {topic} ({_ord(a.house)} house)]"]
    if len(a.lord_chain) > 1:
        lines.append(
            f"Dispositor chain: {' → '.join(a.lord_chain)} — the {_ord(a.house)} lord's "
            f"results ultimately flow to {a.final_dispositor}."
        )
    argala = a.argala
    if argala.net == "supporting":
        lines.append(f"Argala (intervention): supported by {', '.join(argala.supporting)} with no obstruction.")
    elif argala.net == "obstructing":
        lines.append(f"Argala (intervention): obstructed by {', '.join(argala.obstructing)} (virodha argala).")
    elif argala.net == "mixed":
        lines.append(
            f"Argala (intervention): supported by {', '.join(argala.supporting)} but "
            f"partly obstructed by {', '.join(argala.obstructing)}."
        )
    lines.append(
        f"Bhavat-Bhavam: the {_ord(a.bhavat_bhavam_house)} house (lord {a.bhavat_bhavam_lord}) "
        f"is the secondary seat of this matter."
    )
    return "\n".join(lines)


def analyze_house_chain(chart: NormalizedChart, house: int) -> ChainAnalysis:
    """Full relational analysis of a topic house: lord's dispositor chain, argala,
    and Bhavat-Bhavam secondary house."""
    hdata = chart.houses.get(house)
    lord = SIGN_RULERS.get(hdata.sign, "") if hdata else ""
    chain = dispositor_chain(chart, lord) if lord else []
    bb_house = bhavat_bhavam(house)
    bb_data = chart.houses.get(bb_house)
    bb_lord = SIGN_RULERS.get(bb_data.sign, "") if bb_data else ""
    return ChainAnalysis(
        house=house,
        lord=lord,
        lord_chain=chain,
        final_dispositor=chain[-1] if chain else "",
        argala=argala_on_house(chart, house),
        bhavat_bhavam_house=bb_house,
        bhavat_bhavam_lord=bb_lord,
    )
