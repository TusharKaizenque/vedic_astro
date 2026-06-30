"""
Jaimini Chara Karakas (Phase J).

The Atmakaraka (highest-degree planet) and Amatyakaraka (second-highest) are core Jaimini
significators. The Amatyakaraka (AmK) is the classical co-indicator of career/profession —
adding it to the career field analysis sharpens the "what field" conclusion beyond the
Parashari 10th-house karakas alone.
"""
from __future__ import annotations

_SEVEN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def chara_karaka_order(chart) -> list[str]:
    """Planets ordered by degree-in-sign descending → [Atmakaraka, Amatyakaraka, ...].

    Uses the 7-karaka scheme (Sun–Saturn). Rahu, if desired, would use 30°−degree; we keep
    the common 7-planet scheme for stability."""
    degs = []
    for p in _SEVEN:
        pos = chart.planets.get(p)
        if pos is not None:
            degs.append((p, pos.degree_in_sign))
    degs.sort(key=lambda kv: kv[1], reverse=True)
    return [p for p, _ in degs]


def atmakaraka(chart) -> str:
    order = chara_karaka_order(chart)
    return order[0] if order else ""


def amatyakaraka(chart) -> str:
    order = chara_karaka_order(chart)
    return order[1] if len(order) > 1 else ""


def darakaraka(chart) -> str:
    """The Darakaraka (DK) — the chara karaka with the LOWEST degree-in-sign (last in the
    order). In Jaimini it signifies the spouse's soul / inner nature."""
    order = chara_karaka_order(chart)
    return order[-1] if order else ""
