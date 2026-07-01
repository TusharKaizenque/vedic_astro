"""
Karakamsha — the Navamsa (D9) sign occupied by the Atmakaraka (the soul planet, highest by
degree). In Jaimini it reveals the soul's deepest purpose (and, with the planets around it, the
Ishta Devata / spiritual direction). Deterministic: Atmakaraka + its D9 sign + the planets that
share that D9 sign.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.varga_engine import varga_positions, varga_sign
from utils.jaimini import atmakaraka

# Soul-purpose theme of the Atmakaraka planet.
_AK_PURPOSE = {
    "Sun": "self-realization through authority, leadership and integrity",
    "Moon": "growth through care, emotional wisdom and connection to people",
    "Mars": "mastery through courage, discipline and decisive action",
    "Mercury": "purpose through intellect, communication, learning and skill",
    "Jupiter": "purpose through wisdom, teaching, dharma and guidance",
    "Venus": "purpose through relationship, art, devotion and refinement",
    "Saturn": "purpose through service, perseverance, detachment and work for others",
}
# What a planet SHARING the Karakamsha adds to the soul's expression (classical Karakamsha results).
_IN_KARAKAMSHA = {
    "Sun": "administrative or political power, a place of authority",
    "Moon": "a caring, popular, emotionally attuned public role",
    "Mars": "technical, martial or competitive competence",
    "Mercury": "skill in trade, writing, mathematics or communication",
    "Jupiter": "deep knowledge, spiritual teaching, counsel and respect",
    "Venus": "the arts, comforts, beauty and refined pleasures",
    "Saturn": "work through hardship, service to the masses, endurance and renunciation",
    "Rahu": "foreign, unconventional, technological or research paths",
    "Ketu": "spirituality, moksha, healing and mathematical/occult depth",
}


@dataclass
class KarakamshaReading:
    atmakaraka: str
    karakamsha_sign: str
    purpose: str
    companions: list[str] = field(default_factory=list)
    flavors: list[str] = field(default_factory=list)


def build_karakamsha(chart: NormalizedChart) -> KarakamshaReading | None:
    ak = atmakaraka(chart)
    ak_pos = chart.planets.get(ak)
    if not ak or not ak_pos:
        return None
    ks_sign = varga_sign(ak_pos.longitude, "D9")
    if not ks_sign:
        return None
    d9 = varga_positions(chart, "D9")
    companions = [n for n, sign in d9.items() if sign == ks_sign and n != ak]
    flavors = [_IN_KARAKAMSHA[c] for c in companions if c in _IN_KARAKAMSHA]
    return KarakamshaReading(
        atmakaraka=ak, karakamsha_sign=ks_sign,
        purpose=_AK_PURPOSE.get(ak, "the soul's individual path"),
        companions=companions, flavors=flavors,
    )


def format_karakamsha_for_prompt(reading: KarakamshaReading | None) -> str:
    if reading is None:
        return ""
    lines = [
        "[KARAKAMSHA — the soul's purpose (the Atmakaraka's Navamsa)]",
        f"Atmakaraka (soul planet): {reading.atmakaraka}; Karakamsha in {reading.karakamsha_sign} "
        f"— core purpose: {reading.purpose}.",
    ]
    if reading.flavors:
        lines.append("  Expressed through: " + "; ".join(reading.flavors) + ".")
    return "\n".join(lines)
