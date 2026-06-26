"""Deterministic Parashari astrology constants."""

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SANSKRIT_TO_ENGLISH: dict[str, str] = {
    "Mesha": "Aries", "Vrishabha": "Taurus", "Mithuna": "Gemini",
    "Karka": "Cancer", "Simha": "Leo", "Kanya": "Virgo",
    "Tula": "Libra", "Vrischika": "Scorpio", "Dhanu": "Sagittarius",
    "Makara": "Capricorn", "Kumbha": "Aquarius", "Meena": "Pisces",
}

SIGN_TO_NUMBER = {sign: i + 1 for i, sign in enumerate(ZODIAC_SIGNS)}
NUMBER_TO_SIGN = {i + 1: sign for i, sign in enumerate(ZODIAC_SIGNS)}
SIGN_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}
EXALTATION_SIGNS = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn", "Mercury": "Virgo",
    "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra",
}
DEBILITATION_SIGNS = {
    "Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer", "Mercury": "Pisces",
    "Jupiter": "Capricorn", "Venus": "Virgo", "Saturn": "Aries",
}
# Exact deep-exaltation longitude (0-360, sidereal) per BPHS. Debilitation is 180° opposite.
# Used for classical Uchcha Bala (exaltation strength) = dist-from-debilitation / 3 virupas.
EXALTATION_DEGREE = {
    "Sun": 10.0,      # Aries 10°
    "Moon": 33.0,     # Taurus 3°  (30 + 3)
    "Mars": 298.0,    # Capricorn 28° (270 + 28)
    "Mercury": 165.0, # Virgo 15° (150 + 15)
    "Jupiter": 95.0,  # Cancer 5° (90 + 5)
    "Venus": 357.0,   # Pisces 27° (330 + 27)
    "Saturn": 200.0,  # Libra 20° (180 + 20)
}
# Naisargika (natural) Bala in virupas — fixed ranking, BPHS (60/7 multiples).
NAISARGIKA_BALA = {
    "Sun": 60.0, "Moon": 51.43, "Venus": 42.86, "Jupiter": 34.29,
    "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57,
    "Rahu": 8.57, "Ketu": 8.57,
}
# Dig Bala: house where each planet has FULL directional strength (60 virupas).
# Strength fades to 0 at the opposite house. (Same data as DIG_BALA_HOUSES, used for grading.)
DIG_BALA_STRONG_HOUSE = {
    "Jupiter": 1, "Mercury": 1, "Sun": 10, "Mars": 10,
    "Saturn": 7, "Moon": 4, "Venus": 4,
}
# Natural benefics vs malefics (for Paksha Bala and aspect-quality weighting).
NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
NATURAL_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
OWN_SIGNS = {
    "Sun": ["Leo"], "Moon": ["Cancer"], "Mars": ["Aries", "Scorpio"],
    "Mercury": ["Gemini", "Virgo"], "Jupiter": ["Sagittarius", "Pisces"],
    "Venus": ["Taurus", "Libra"], "Saturn": ["Capricorn", "Aquarius"],
    "Rahu": [], "Ketu": [],
}
MOOLATRIKONA_SIGNS = {
    "Sun": "Leo", "Moon": "Taurus", "Mars": "Aries", "Mercury": "Virgo",
    "Jupiter": "Sagittarius", "Venus": "Libra", "Saturn": "Aquarius",
}
NATURAL_FRIENDS = {
    "Sun": ["Moon", "Mars", "Jupiter"], "Moon": ["Sun", "Mercury"],
    "Mars": ["Sun", "Moon", "Jupiter"], "Mercury": ["Sun", "Venus"],
    "Jupiter": ["Sun", "Moon", "Mars"], "Venus": ["Mercury", "Saturn"],
    "Saturn": ["Mercury", "Venus"], "Rahu": ["Venus", "Saturn", "Mercury"],
    "Ketu": ["Mars", "Venus", "Saturn"],
}
NATURAL_ENEMIES = {
    "Sun": ["Venus", "Saturn"], "Moon": ["Rahu", "Ketu"], "Mars": ["Mercury"],
    "Mercury": ["Moon"], "Jupiter": ["Mercury", "Venus"], "Venus": ["Sun", "Moon"],
    "Saturn": ["Sun", "Moon", "Mars"], "Rahu": ["Sun", "Moon", "Mars"],
    "Ketu": ["Sun", "Moon", "Mercury"],
}
KENDRA_HOUSES = [1, 4, 7, 10]
TRIKONA_HOUSES = [1, 5, 9]
DUSTHANA_HOUSES = [6, 8, 12]
UPACHAYA_HOUSES = [3, 6, 10, 11]
MARAKA_HOUSES = [2, 7]
TOPIC_HOUSE_MAP = {
    "career": [10, 6, 2, 11], "profession": [10, 6, 2, 11],
    "job": [10, 6, 2, 11], "business": [10, 7, 2, 11],
    "marriage": [7, 2, 11, 5], "spouse": [7, 2, 11],
    "relationship": [7, 5, 2, 11], "partner": [7, 5], "love": [5, 7],
    "children": [5, 9], "child": [5, 9], "fertility": [5],
    "health": [1, 6, 8], "disease": [6, 8], "illness": [6, 8], "body": [1],
    "finance": [2, 11, 8, 12], "money": [2, 11], "wealth": [2, 11, 9],
    "income": [2, 11], "property": [4, 12], "home": [4], "land": [4],
    "education": [4, 5, 9], "learning": [4, 5], "higher education": [9, 5],
    "siblings": [3, 11], "brother": [3], "sister": [3, 11],
    "parents": [4, 9, 10], "father": [9, 10], "mother": [4],
    "spirituality": [12, 9, 8], "moksha": [12, 8, 4],
    "foreign": [9, 12], "travel": [3, 9, 12], "abroad": [9, 12],
    "litigation": [6, 12], "enemies": [6, 12], "loans": [6, 8, 12],
    "debt": [6, 8, 12], "inheritance": [8, 2], "occult": [8, 12],
    "research": [8, 12], "government": [9, 10], "politics": [10, 9],
    "creativity": [5], "arts": [5, 12], "sports": [3, 6],
    "communication": [3], "writing": [3, 5],
}
TOPIC_PLANET_MAP = {
    # Career karakas: Saturn (karma karaka, primary) + Sun (authority/rajya) + Mars (drive).
    # Mercury removed — it is a karaka for intellect/commerce, not career broadly.
    "career": ["Saturn", "Sun", "Mars"],
    "business": ["Mercury", "Mars", "Sun"],   # commerce + enterprise + leadership
    "marriage": ["Venus", "Jupiter", "Moon"], "children": ["Jupiter", "Moon"],
    "health": ["Sun", "Mars", "Moon"], "finance": ["Jupiter", "Venus", "Mercury"],
    "property": ["Mars", "Moon"], "education": ["Mercury", "Jupiter"],
    "siblings": ["Mars", "Mercury"], "parents": ["Sun", "Moon"],
    "father": ["Sun"], "mother": ["Moon"], "spirituality": ["Jupiter", "Ketu", "Saturn"],
    "foreign": ["Rahu", "Jupiter", "Saturn"], "creativity": ["Venus", "Mercury", "Moon"],
    "government": ["Sun"], "occult": ["Ketu", "Saturn"],
}
# Keyword → canonical topic key. Used to normalize free-form topic strings from the
# LLM intent classifier (e.g. "professional life", "getting married") to a key that
# exists in TOPIC_HOUSE_MAP. Checked by substring; first match wins per group.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "career": ["career", "profession", "job", "work", "occupation", "vocation", "employment"],
    "business": ["business", "startup", "entrepreneur", "venture", "self-employ"],
    "marriage": ["marriage", "marry", "married", "spouse", "wife", "husband", "wedding"],
    "relationship": ["relationship", "partner", "love", "romance", "dating", "girlfriend", "boyfriend"],
    "children": ["children", "child", "kids", "progeny", "fertility", "conceive", "pregnan"],
    "health": ["health", "illness", "disease", "sickness", "medical", "body", "wellbeing"],
    "wealth": ["wealth", "money", "rich", "prosperity", "affluence"],
    "finance": ["finance", "income", "earning", "savings", "financial"],
    "education": ["education", "study", "studies", "学", "learning", "exam", "college", "degree", "academ"],
    "property": ["property", "house", "home", "real estate", "land", "vehicle"],
    "spirituality": ["spiritual", "moksha", "enlightenment", "meditation", "religion", "dharma", "liberation"],
    "foreign": ["foreign", "abroad", "overseas", "immigration", "relocat"],
    "litigation": ["litigation", "lawsuit", "court", "legal case", "dispute"],
    "siblings": ["sibling", "brother", "sister"],
    "father": ["father", "dad", "paternal"],
    "mother": ["mother", "mom", "maternal"],
}
# Topic families: near-synonymous topics that should not be double-analyzed in one
# question (e.g. "startup" resolving to BOTH career and business). resolve_topics keeps
# at most one topic per family.
TOPIC_FAMILIES: list[set[str]] = [
    {"career", "business"},
    {"marriage", "relationship"},
    {"wealth", "finance"},
    {"education"},
    {"children"},
    {"health"},
    {"spirituality"},
    {"property"},
]
VIMSHOTTARI_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIMSHOTTARI_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
# Functional benefic/malefic nature per lagna (Parashara system).
# Lordship of kendra (1,4,7,10) by natural benefics creates functional malefics (kendradhipati dosha).
# Trikona lords (1,5,9) are always functional benefics.
# Lords of dusthana (6,8,12) are functional malefics.
# Yogakaraka: a planet that lords BOTH a kendra and a trikona simultaneously — strongest benefic.
# Rahu/Ketu behave as the lord of the sign they occupy or conjoin.
FUNCTIONAL_NATURE_BY_LAGNA: dict[str, dict[str, str]] = {
    "Aries": {
        # Mars: 1+8 lord — lagna lord (1) dominates; benefic (NOT yogakaraka — it lords no
        #   separate kendra 4/7/10 + trikona 5/9 pair)
        # Sun: 5th lord (trikona) — benefic
        # Moon: 4th lord (kendra) — kendradhipati but natural benefic; neutral
        # Mercury: 3+6 lord — 6=dusthana; malefic
        # Jupiter: 9+12 lord — 9=trikona wins; benefic
        # Venus: 2+7 lord — 7=kendra (kendradhipati on natural benefic); malefic
        # Saturn: 10+11 lord — 10=kendra, natural malefic; malefic
        "Mars": "benefic", "Sun": "benefic", "Moon": "neutral",
        "Mercury": "malefic", "Jupiter": "benefic", "Venus": "malefic", "Saturn": "malefic",
    },
    "Taurus": {
        # Venus: 1+6 lord — 1=trikona but 6=dusthana cancels some; net neutral-benefic
        # Mercury: 2+5 lord — 5=trikona; benefic
        # Moon: 3rd lord — neutral/upachaya
        # Sun: 4th lord — kendra; kendradhipati natural benefic; neutral
        # Mars: 7+12 lord — 7=kendra, 12=dusthana; malefic
        # Jupiter: 8+11 lord — 8=dusthana; malefic
        # Saturn: 9+10 lord — 9=trikona + 10=kendra = yogakaraka
        "Venus": "benefic", "Mercury": "benefic", "Moon": "neutral",
        "Sun": "neutral", "Mars": "malefic", "Jupiter": "malefic", "Saturn": "yogakaraka",
    },
    "Gemini": {
        # Mercury: 1+4 lord — 1=trikona, 4=kendra; kendradhipati (natural benefic); net neutral
        # Venus: 5+12 lord — 5=trikona; benefic
        # Saturn: 8+9 lord — 9=trikona wins; benefic
        # Mars: 6+11 lord — 6=dusthana; malefic
        # Moon: 2nd lord — neutral
        # Sun: 3rd lord — neutral
        # Jupiter: 7+10 lord — kendra lords (natural benefic); kendradhipati; malefic
        "Mercury": "neutral", "Venus": "benefic", "Saturn": "benefic",
        "Mars": "malefic", "Moon": "neutral", "Sun": "neutral", "Jupiter": "malefic",
    },
    "Cancer": {
        # Moon: 1st lord (trikona); benefic
        # Mars: 5+10 lord — 5=trikona + 10=kendra = yogakaraka
        # Jupiter: 6+9 lord — 9=trikona wins; benefic (6 weakens slightly)
        # Venus: 4+11 lord — 4=kendra; kendradhipati (natural benefic); neutral
        # Mercury: 3+12 lord — 12=dusthana; malefic
        # Sun: 2nd lord — neutral
        # Saturn: 7+8 lord — 7=kendra + 8=dusthana; malefic
        "Moon": "benefic", "Mars": "yogakaraka", "Jupiter": "benefic",
        "Venus": "neutral", "Mercury": "malefic", "Sun": "neutral", "Saturn": "malefic",
    },
    "Leo": {
        # Sun: 1st lord (trikona); benefic
        # Mars: 4+9 lord — 9=trikona + 4=kendra = yogakaraka
        # Jupiter: 5+8 lord — 5=trikona; benefic (8 weakens)
        # Moon: 12th lord — dusthana; malefic
        # Mercury: 2+11 lord — neutral
        # Venus: 3+10 lord — 10=kendra; kendradhipati (natural benefic); malefic
        # Saturn: 6+7 lord — 6=dusthana + 7=kendra; malefic
        "Sun": "benefic", "Mars": "yogakaraka", "Jupiter": "benefic",
        "Moon": "malefic", "Mercury": "neutral", "Venus": "malefic", "Saturn": "malefic",
    },
    "Virgo": {
        # Mercury: 1+10 lord — 1=trikona + 10=kendra; kendradhipati (natural benefic); net neutral
        # Venus: 2+9 lord — 9=trikona; benefic
        # Saturn: 5+6 lord — 5=trikona; benefic (6 weakens slightly)
        # Mars: 3+8 lord — 8=dusthana; malefic
        # Moon: 11th lord — neutral
        # Sun: 12th lord — dusthana; malefic
        # Jupiter: 4+7 lord — kendra lords (natural benefic); kendradhipati; malefic
        "Mercury": "neutral", "Venus": "benefic", "Saturn": "benefic",
        "Mars": "malefic", "Moon": "neutral", "Sun": "malefic", "Jupiter": "malefic",
    },
    "Libra": {
        # Venus: 1+8 lord — 1=trikona; benefic (8 weakens slightly)
        # Saturn: 4+5 lord — 5=trikona + 4=kendra = yogakaraka
        # Mercury: 9+12 lord — 9=trikona; benefic
        # Moon: 10th lord — kendra; kendradhipati (natural benefic); neutral
        # Sun: 11th lord — neutral
        # Mars: 2+7 lord — 7=kendra (natural malefic in kendra); malefic
        # Jupiter: 3+6 lord — 6=dusthana; malefic
        "Venus": "benefic", "Saturn": "yogakaraka", "Mercury": "benefic",
        "Moon": "neutral", "Sun": "neutral", "Mars": "malefic", "Jupiter": "malefic",
    },
    "Scorpio": {
        # Mars: 1+6 lord — 1=trikona; benefic (6 weakens)
        # Moon: 9th lord (trikona); benefic
        # Sun: 10th lord (kendra); kendradhipati (natural benefic); neutral
        # Jupiter: 2+5 lord — 5=trikona; benefic
        # Mercury: 8+11 lord — 8=dusthana; malefic
        # Venus: 7+12 lord — 7=kendra + 12=dusthana; malefic
        # Saturn: 3+4 lord — 4=kendra; kendradhipati (natural malefic); malefic
        "Mars": "benefic", "Moon": "benefic", "Sun": "neutral",
        "Jupiter": "benefic", "Mercury": "malefic", "Venus": "malefic", "Saturn": "malefic",
    },
    "Sagittarius": {
        # Jupiter: 1+4 lord — 1=trikona + 4=kendra; kendradhipati (natural benefic); neutral
        # Mars: 5+12 lord — 5=trikona; benefic
        # Sun: 9th lord (trikona); benefic
        # Moon: 8th lord — dusthana; malefic
        # Mercury: 7+10 lord — kendra lords (natural benefic); kendradhipati; malefic
        # Venus: 6+11 lord — 6=dusthana; malefic
        # Saturn: 2+3 lord — neutral
        "Jupiter": "neutral", "Mars": "benefic", "Sun": "benefic",
        "Moon": "malefic", "Mercury": "malefic", "Venus": "malefic", "Saturn": "neutral",
    },
    "Capricorn": {
        # Saturn: 1+2 lord — 1=trikona; benefic
        # Venus: 5+10 lord — 5=trikona + 10=kendra = yogakaraka
        # Mercury: 6+9 lord — 9=trikona wins; benefic
        # Moon: 7th lord — kendra; kendradhipati (natural benefic); neutral
        # Sun: 8th lord — dusthana; malefic
        # Mars: 4+11 lord — 4=kendra; kendradhipati (natural malefic); malefic
        # Jupiter: 3+12 lord — 12=dusthana; malefic
        "Saturn": "benefic", "Venus": "yogakaraka", "Mercury": "benefic",
        "Moon": "neutral", "Sun": "malefic", "Mars": "malefic", "Jupiter": "malefic",
    },
    "Aquarius": {
        # Saturn: 1+12 lord — 1=trikona; benefic
        # Venus: 4+9 lord — 9=trikona + 4=kendra = yogakaraka
        # Mars: 3+10 lord — 10=kendra; neutral (malefic in kendra but trine energy from 10)
        # Moon: 6th lord — dusthana; malefic
        # Sun: 7th lord — kendra; kendradhipati (natural benefic); neutral
        # Mercury: 5+8 lord — 5=trikona; benefic (8 weakens slightly)
        # Jupiter: 2+11 lord — neutral
        "Saturn": "benefic", "Venus": "yogakaraka", "Mars": "neutral",
        "Moon": "malefic", "Sun": "neutral", "Mercury": "benefic", "Jupiter": "neutral",
    },
    "Pisces": {
        # Jupiter: 1+10 lord — 1=trikona + 10=kendra; kendradhipati (natural benefic); neutral
        # Mars: 2+9 lord — 9=trikona; benefic
        # Moon: 5th lord (trikona); benefic
        # Venus: 3+8 lord — 8=dusthana; malefic
        # Sun: 6th lord — dusthana; malefic
        # Mercury: 4+7 lord — kendra lords (natural benefic); kendradhipati; malefic
        # Saturn: 11+12 lord — 12=dusthana; malefic
        "Jupiter": "neutral", "Mars": "benefic", "Moon": "benefic",
        "Venus": "malefic", "Sun": "malefic", "Mercury": "malefic", "Saturn": "malefic",
    },
}

def house_lords_for_lagna(lagna: str) -> dict[str, list[int]]:
    """Return {planet: [houses it lords]} for a given lagna (whole-sign).

    The deterministic basis for verifying FUNCTIONAL_NATURE_BY_LAGNA: a planet's
    functional nature is a function of which houses it lords from the lagna."""
    if lagna not in ZODIAC_SIGNS:
        return {}
    start = ZODIAC_SIGNS.index(lagna)
    lords: dict[str, list[int]] = {}
    for house in range(1, 13):
        sign = ZODIAC_SIGNS[(start + house - 1) % 12]
        ruler = SIGN_RULERS[sign]
        lords.setdefault(ruler, []).append(house)
    return lords


_KENDRA = {4, 7, 10}        # angular (excl. lagna, which is also a trikona)
_TRIKONA = {5, 9}           # trinal (excl. lagna)
_DUSTHANA = {6, 8, 12}      # malefic houses


def is_yogakaraka(houses: list[int]) -> bool:
    """A planet lording at least one kendra (4/7/10) AND one trikona (5/9) is yogakaraka."""
    hs = set(houses)
    return bool(hs & _KENDRA) and bool(hs & _TRIKONA)


# Dig Bala (directional strength) — planet strong in this house direction
DIG_BALA_HOUSES: dict[str, int] = {
    "Jupiter": 1, "Mercury": 1,  # Lagna (East)
    "Sun": 10, "Mars": 10,       # Midheaven (South)
    "Saturn": 7,                  # Descendant (West)
    "Moon": 4, "Venus": 4,        # IC (North)
}

# Ashtakavarga — benefic contribution tables (Bhinnashtakavarga).
# Each sub-dict: planet P contributes a benefic bindu to sign positions (1-12)
# when the planet under analysis is in that position relative to P's position.
# These are classical lookup offsets from BPHS Ch.66.
ASHTAKAVARGA_CONTRIBUTIONS: dict[str, dict[str, list[int]]] = {
    "Sun": {
        "Sun":     [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon":    [3, 6, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus":   [6, 7, 12],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun":     [3, 6, 7, 8, 10, 11],
        "Moon":    [1, 3, 6, 7, 10, 11],
        "Mars":    [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus":   [3, 4, 5, 7, 9, 10, 11],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [3, 6, 10, 11],
    },
    "Mars": {
        "Sun":     [3, 5, 6, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus":   [6, 8, 11, 12],
        "Saturn":  [1, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun":     [5, 6, 9, 11, 12],
        "Moon":    [2, 4, 6, 8, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun":     [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon":    [2, 5, 7, 9, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus":   [2, 5, 6, 9, 10, 11],
        "Saturn":  [3, 5, 6, 12],
        "Lagna":   [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun":     [8, 11, 12],
        "Moon":    [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars":    [3, 4, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn":  [3, 4, 5, 8, 9, 10, 11],
        "Lagna":   [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun":     [1, 2, 4, 7, 8, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus":   [6, 11, 12],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [1, 3, 4, 6, 10, 11],
    },
}
