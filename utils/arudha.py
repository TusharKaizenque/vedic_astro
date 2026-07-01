"""
Arudha padas (Jaimini) — the "image" or projected reflection of a house.

A house shows the reality; its ARUDHA shows how that reality is PERCEIVED by the world. The
Arudha Lagna (AL, arudha of the 1st) is the public image / status / reputation — often very
different from the true self shown by the lagna. Computed purely from sign indices.

Rule (BPHS/Jaimini): count from the house to its lord, then the same count again from the
lord. Exception: if the resulting pada falls in the house itself or the 7th from it (an
"invisible" pada), take the 10th from that pada instead.
"""
from __future__ import annotations

from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS


def arudha_pada(house_idx: int, lord_idx: int) -> int:
    """Arudha sign-index of a house, given the house's sign-index and its lord's sign-index."""
    pada = (2 * lord_idx - house_idx) % 12
    if pada == house_idx or pada == (house_idx + 6) % 12:
        pada = (pada + 9) % 12
    return pada


def arudha_lagna_index(chart) -> int | None:
    """Sign-index (0=Aries) of the Arudha Lagna, or None if the lagna/lord is unresolved."""
    if chart.lagna_sign not in ZODIAC_SIGNS:
        return None
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign)
    lord = SIGN_RULERS.get(chart.lagna_sign, "")
    lord_pos = chart.planets.get(lord)
    if not lord_pos or lord_pos.sign not in ZODIAC_SIGNS:
        return None
    return arudha_pada(lagna_idx, ZODIAC_SIGNS.index(lord_pos.sign))
