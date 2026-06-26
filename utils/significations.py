"""
Significations (Phase F) — domain maps that turn chart factors into concrete,
plain-language meaning. These encode the classical karakatva (significations) of
planets, houses, and signs from BPHS / Phaladeepika / Saravali so the outcome engine
can say "engineering, drive, leadership" instead of "Mars, karaka, moderate strength".
"""
from __future__ import annotations

# ── Planet → professions / fields (BPHS karakatva + traditional vocations) ──────────
PLANET_PROFESSIONS: dict[str, list[str]] = {
    "Sun": ["government service", "administration", "politics", "medicine", "leadership roles", "civil service"],
    "Moon": ["public-facing work", "hospitality", "nursing & care", "psychology", "trade in liquids/food", "travel"],
    "Mars": ["engineering", "defense & military", "surgery", "sports & athletics", "real estate", "technical trades"],
    "Mercury": ["writing & publishing", "commerce & trade", "software & IT", "accounting", "teaching", "analysis & consulting"],
    "Jupiter": ["teaching & academia", "law", "finance & banking", "advisory roles", "philosophy & religion", "counseling"],
    "Venus": ["arts & music", "entertainment & media", "fashion & design", "luxury & beauty", "diplomacy", "hospitality"],
    "Saturn": ["construction & mining", "agriculture", "law & administration", "heavy industry", "service & labor", "long-term institutions"],
    "Rahu": ["technology", "aviation & foreign trade", "research", "unconventional fields", "media & photography", "speculation"],
    "Ketu": ["research & investigation", "spirituality & healing", "alternative medicine", "IT & precision work", "the occult"],
}

# ── Planet → temperament / personality traits (for self & spouse description) ───────
PLANET_TRAITS: dict[str, list[str]] = {
    "Sun": ["confident", "principled", "authoritative", "proud", "self-driven"],
    "Moon": ["emotional", "nurturing", "adaptable", "sensitive", "caring"],
    "Mars": ["energetic", "courageous", "assertive", "competitive", "direct"],
    "Mercury": ["intelligent", "communicative", "witty", "analytical", "adaptable"],
    "Jupiter": ["wise", "optimistic", "ethical", "generous", "well-learned"],
    "Venus": ["charming", "artistic", "refined", "affectionate", "diplomatic"],
    "Saturn": ["disciplined", "patient", "hardworking", "serious", "responsible"],
    "Rahu": ["ambitious", "unconventional", "intense", "foreign-leaning"],
    "Ketu": ["detached", "introspective", "spiritual", "intuitive"],
}

# ── House → plain life-area meaning ─────────────────────────────────────────────────
HOUSE_LIFE_AREA: dict[int, str] = {
    1: "your self, body, vitality and overall personality",
    2: "your wealth, savings, family and speech",
    3: "your courage, skills, communication and siblings",
    4: "your home, mother, property, education and inner comfort",
    5: "your children, creativity, intelligence and romance",
    6: "your daily work, health, debts, competition and obstacles",
    7: "your spouse, marriage and close partnerships",
    8: "longevity, sudden change, inheritance and hidden matters",
    9: "your fortune, higher learning, father, dharma and long journeys",
    10: "your career, public standing, authority and reputation",
    11: "your gains, income, aspirations and networks",
    12: "expenses, foreign lands, isolation, spirituality and rest",
}

# ── Sign → nature keywords + element/modality ───────────────────────────────────────
SIGN_NATURE: dict[str, dict[str, str]] = {
    "Aries":       {"keywords": "assertive, pioneering, energetic", "element": "fire", "modality": "movable"},
    "Taurus":      {"keywords": "steady, practical, security-seeking", "element": "earth", "modality": "fixed"},
    "Gemini":      {"keywords": "communicative, curious, versatile", "element": "air", "modality": "dual"},
    "Cancer":      {"keywords": "nurturing, emotional, protective", "element": "water", "modality": "movable"},
    "Leo":         {"keywords": "proud, creative, commanding", "element": "fire", "modality": "fixed"},
    "Virgo":       {"keywords": "analytical, meticulous, service-minded", "element": "earth", "modality": "dual"},
    "Libra":       {"keywords": "harmonious, relational, aesthetic", "element": "air", "modality": "movable"},
    "Scorpio":     {"keywords": "intense, secretive, transformative", "element": "water", "modality": "fixed"},
    "Sagittarius": {"keywords": "philosophical, adventurous, principled", "element": "fire", "modality": "dual"},
    "Capricorn":   {"keywords": "ambitious, disciplined, pragmatic", "element": "earth", "modality": "movable"},
    "Aquarius":    {"keywords": "unconventional, humanitarian, independent", "element": "air", "modality": "fixed"},
    "Pisces":      {"keywords": "compassionate, imaginative, spiritual", "element": "water", "modality": "dual"},
}

# How a planet's profession signature shifts when it is retrograde (Phase J nuance).
RETROGRADE_FLAVOR = "an unconventional or self-taught route into"


def professions_for(planet: str, limit: int = 4) -> list[str]:
    return PLANET_PROFESSIONS.get(planet, [])[:limit]


def traits_for(planet: str, limit: int = 3) -> list[str]:
    return PLANET_TRAITS.get(planet, [])[:limit]


def life_area(house: int) -> str:
    return HOUSE_LIFE_AREA.get(house, f"the {house}th house matters")


def sign_keywords(sign: str) -> str:
    return SIGN_NATURE.get(sign, {}).get("keywords", "")
