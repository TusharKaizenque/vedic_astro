"""
Nakshatra (lunar mansion) engine.

The 27 nakshatras are the foundation of Vedic prediction — Vimshottari dasha itself is
keyed to the Moon's nakshatra, and each planet's nakshatra adds a layer of meaning beyond
its sign. This module computes a planet's nakshatra, pada (quarter), and nakshatra lord
deterministically from its sidereal longitude (no API dependency), and provides the
classical traits used for temperament/description.

Each nakshatra spans 13°20' (360/27). Each is divided into 4 padas of 3°20'. The nakshatra
lord follows the Vimshottari order (Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn,
Mercury), repeating three times across the 27.
"""
from __future__ import annotations

from utils.astro_constants import VIMSHOTTARI_ORDER

_NAK_SPAN = 360.0 / 27.0          # 13°20'
_PADA_SPAN = _NAK_SPAN / 4.0      # 3°20'

NAKSHATRAS: list[str] = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]

# Classical temperament keywords per nakshatra (for personality / spouse description).
NAKSHATRA_TRAITS: dict[str, str] = {
    "Ashwini": "quick, energetic, healing and pioneering",
    "Bharani": "intense, disciplined and transformative",
    "Krittika": "sharp, determined and purifying",
    "Rohini": "creative, charming and growth-oriented",
    "Mrigashira": "curious, gentle and searching",
    "Ardra": "sharp-minded, intense and transformative",
    "Punarvasu": "optimistic, philosophical and renewing",
    "Pushya": "nourishing, dutiful and steady",
    "Ashlesha": "penetrating, strategic and intuitive",
    "Magha": "regal, proud and tradition-honoring",
    "Purva Phalguni": "warm, pleasure-loving and generous",
    "Uttara Phalguni": "reliable, helpful and principled",
    "Hasta": "skillful, clever and dexterous",
    "Chitra": "artistic, charismatic and brilliant",
    "Swati": "independent, adaptable and diplomatic",
    "Vishakha": "goal-driven, ambitious and determined",
    "Anuradha": "devoted, friendly and disciplined",
    "Jyeshtha": "protective, responsible and private",
    "Mula": "investigative, intense and getting-to-the-root",
    "Purva Ashadha": "persuasive, proud and unstoppable",
    "Uttara Ashadha": "virtuous, persevering and a natural leader",
    "Shravana": "attentive, learned and well-connected",
    "Dhanishta": "ambitious, rhythmic and prosperous",
    "Shatabhisha": "independent, healing and secretive",
    "Purva Bhadrapada": "idealistic, intense and visionary",
    "Uttara Bhadrapada": "wise, patient and compassionate",
    "Revati": "nurturing, gentle and spiritually inclined",
}


def nakshatra_index(longitude: float) -> int:
    """0-based nakshatra index (0=Ashwini … 26=Revati)."""
    return int((longitude % 360.0) // _NAK_SPAN) % 27


def nakshatra_of(longitude: float) -> str:
    return NAKSHATRAS[nakshatra_index(longitude)]


def pada_of(longitude: float) -> int:
    """Pada (quarter) 1-4 within the nakshatra."""
    within = (longitude % 360.0) % _NAK_SPAN
    return int(within // _PADA_SPAN) + 1


def nakshatra_lord(longitude: float) -> str:
    """The Vimshottari ruling planet of the nakshatra at this longitude."""
    return VIMSHOTTARI_ORDER[nakshatra_index(longitude) % 9]


def nakshatra_lord_by_name(name: str) -> str:
    if name not in NAKSHATRAS:
        return ""
    return VIMSHOTTARI_ORDER[NAKSHATRAS.index(name) % 9]


def traits_of(name: str) -> str:
    return NAKSHATRA_TRAITS.get(name, "")
