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


# Prokerala (and other ephemerides) return nakshatra names in many spellings/transliterations.
# Map every variant to our canonical name so the lord / traits / pada lookups never silently
# fail on a benign spelling difference. Keys are "squashed" (lowercased, alphanumerics only).
def _squash(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


_NAK_ALIASES: dict[str, str] = {
    # canonical spellings (squashed) map to themselves
    **{_squash(n): n for n in NAKSHATRAS},
    # common transliteration / regional variants
    "aswini": "Ashwini", "ashvini": "Ashwini", "asvini": "Ashwini",
    "kritika": "Krittika", "krithika": "Krittika", "karthika": "Krittika", "krithikai": "Krittika",
    "mrigasira": "Mrigashira", "mrigashirsha": "Mrigashira", "mrugashira": "Mrigashira",
    "mrigshira": "Mrigashira", "makayiram": "Mrigashira",
    "aardra": "Ardra", "arudra": "Ardra", "thiruvathira": "Ardra",
    "punervasu": "Punarvasu", "punarpoosam": "Punarvasu",
    "pushyami": "Pushya", "pushyam": "Pushya", "poosam": "Pushya",
    "aslesha": "Ashlesha", "ashlesa": "Ashlesha", "ayilyam": "Ashlesha",
    "makha": "Magha", "makam": "Magha",
    "purvaphalguni": "Purva Phalguni", "poorvaphalguni": "Purva Phalguni",
    "pubba": "Purva Phalguni", "purvafalguni": "Purva Phalguni", "pooram": "Purva Phalguni",
    "uttaraphalguni": "Uttara Phalguni", "uttarafalguni": "Uttara Phalguni", "uthiram": "Uttara Phalguni",
    "hastha": "Hasta", "hastham": "Hasta",
    "chithra": "Chitra", "chithira": "Chitra", "chitta": "Chitra",
    "svati": "Swati", "swathi": "Swati", "chothi": "Swati",
    "visakha": "Vishakha", "vishaka": "Vishakha", "vishakam": "Vishakha", "visakam": "Vishakha",
    "anusham": "Anuradha", "anizham": "Anuradha",
    "jyeshta": "Jyeshtha", "jyestha": "Jyeshtha", "kettai": "Jyeshtha", "jeshta": "Jyeshtha",
    "moola": "Mula", "mool": "Mula", "moolam": "Mula",
    "purvashada": "Purva Ashadha", "poorvashada": "Purva Ashadha", "purvaashadha": "Purva Ashadha",
    "purvaashada": "Purva Ashadha", "pooradam": "Purva Ashadha", "purvashadha": "Purva Ashadha",
    "uttarashada": "Uttara Ashadha", "uttaraashadha": "Uttara Ashadha", "uttaraashada": "Uttara Ashadha",
    "uttaradam": "Uttara Ashadha", "uttarashadha": "Uttara Ashadha",
    "sravana": "Shravana", "shravan": "Shravana", "thiruvonam": "Shravana",
    "dhanishtha": "Dhanishta", "dhanista": "Dhanishta", "avittam": "Dhanishta",
    "shatabhishaj": "Shatabhisha", "satabhisha": "Shatabhisha", "shatabhishak": "Shatabhisha",
    "shatataraka": "Shatabhisha", "sadayam": "Shatabhisha", "satabhishaj": "Shatabhisha",
    "purvabhadra": "Purva Bhadrapada", "purvabhadrapada": "Purva Bhadrapada",
    "poorvabhadrapada": "Purva Bhadrapada", "pooruttathi": "Purva Bhadrapada",
    "uttarabhadra": "Uttara Bhadrapada", "uttarabhadrapada": "Uttara Bhadrapada",
    "uttarattathi": "Uttara Bhadrapada", "uthrattathi": "Uttara Bhadrapada",
    "revathi": "Revati", "revthi": "Revati",
}


def normalize_nakshatra(name: str) -> str:
    """Map any spelling/transliteration of a nakshatra to our canonical name ("" if unknown)."""
    if not name:
        return ""
    return _NAK_ALIASES.get(_squash(name), "")


# Classical significations per nakshatra: (ruling deity, symbol, vocational fields). Drawn from
# BPHS, the Taittiriya Brahmana deity assignments, and traditional vocational karaka readings.
# Used to give the janma-nakshatra (and a planet's nakshatra) a SPECIFIC, individual texture
# instead of a generic temperament line.
NAKSHATRA_PROFILE: dict[str, dict[str, str]] = {
    "Ashwini":          {"deity": "Ashwini Kumaras (celestial healers)", "symbol": "horse's head", "careers": "medicine & healing, emergency work, athletics, transport, pioneering ventures"},
    "Bharani":          {"deity": "Yama (lord of dharma & death)", "symbol": "yoni", "careers": "law & judgment, surgery/obstetrics, creative arts, work involving discipline and transformation"},
    "Krittika":         {"deity": "Agni (fire)", "symbol": "razor/flame", "careers": "leadership, military/defence, cutting-edge or fire-related work, criticism, cooking, metallurgy"},
    "Rohini":           {"deity": "Brahma (the creator)", "symbol": "ox-cart", "careers": "agriculture, luxury goods, arts & beauty, finance, real estate, anything that grows or nurtures"},
    "Mrigashira":       {"deity": "Soma (the moon)", "symbol": "deer's head", "careers": "research & exploration, writing, travel, sales, perfumery/textiles, curious seeking work"},
    "Ardra":            {"deity": "Rudra (storm)", "symbol": "teardrop", "careers": "research & analysis, engineering, pharmacology, work through crisis/transformation, technology"},
    "Punarvasu":        {"deity": "Aditi (mother of the gods)", "symbol": "quiver of arrows", "careers": "teaching, spirituality, hospitality, publishing, work involving renewal and return"},
    "Pushya":           {"deity": "Brihaspati (Jupiter, guru)", "symbol": "cow's udder", "careers": "counsel & priesthood, nourishing/caretaking work, public service, food, dependable institutions"},
    "Ashlesha":         {"deity": "the Nagas (serpents)", "symbol": "coiled serpent", "careers": "strategy, psychology, occult/research, medicine (toxins), negotiation, anything requiring penetration"},
    "Magha":            {"deity": "the Pitris (ancestors)", "symbol": "throne", "careers": "leadership & authority, tradition/heritage work, administration, ceremony, positions of rank"},
    "Purva Phalguni":   {"deity": "Bhaga (delight, fortune)", "symbol": "front legs of a bed", "careers": "arts & entertainment, hospitality, luxury, relationship/creative work, leisure industries"},
    "Uttara Phalguni":  {"deity": "Aryaman (patronage, contracts)", "symbol": "back legs of a bed", "careers": "service & contracts, philanthropy, marriage/partnership work, reliable professional roles"},
    "Hasta":            {"deity": "Savitr (the Sun's creative power)", "symbol": "hand", "careers": "skilled crafts, healing hands, commerce, design, anything dexterous or detail-handed"},
    "Chitra":           {"deity": "Tvashtar (cosmic architect)", "symbol": "bright jewel", "careers": "design & architecture, engineering, fashion, jewellery, visible creative brilliance"},
    "Swati":            {"deity": "Vayu (wind)", "symbol": "young shoot in wind", "careers": "trade & business, diplomacy, independent ventures, travel, flexible self-directed work"},
    "Vishakha":         {"deity": "Indra-Agni (power & fire)", "symbol": "triumphal archway", "careers": "goal-driven achievement, politics, research, anything demanding sustained ambition"},
    "Anuradha":         {"deity": "Mitra (friendship, alliances)", "symbol": "lotus", "careers": "organising & alliances, foreign work, devotional/disciplined pursuits, teamwork-based success"},
    "Jyeshtha":         {"deity": "Indra (king of the gods)", "symbol": "circular amulet", "careers": "command & protection, military/police, occult, positions of seniority earned through trial"},
    "Mula":             {"deity": "Nirriti (dissolution)", "symbol": "tied roots", "careers": "research to the root, medicine/herbs, philosophy, investigation, work involving endings & foundations"},
    "Purva Ashadha":    {"deity": "Apas (the waters)", "symbol": "fan/winnowing basket", "careers": "persuasion & debate, law, water/shipping trades, invigorating influential work"},
    "Uttara Ashadha":   {"deity": "the Vishvadevas (universal gods)", "symbol": "elephant tusk", "careers": "leadership with integrity, government, pioneering lasting institutions, ethical authority"},
    "Shravana":         {"deity": "Vishnu (the preserver)", "symbol": "ear / three footprints", "careers": "learning & teaching, media/communication, counselling, knowledge-keeping, connective work"},
    "Dhanishta":        {"deity": "the eight Vasus", "symbol": "drum", "careers": "music & rhythm, wealth/finance, real estate, group ventures, performance and timing-based work"},
    "Shatabhisha":      {"deity": "Varuna (cosmic waters & law)", "symbol": "empty circle", "careers": "healing & medicine, astrology/occult, technology, research into hidden things, independent work"},
    "Purva Bhadrapada": {"deity": "Aja Ekapada (one-footed goat)", "symbol": "front of a funeral cot", "careers": "spirituality with intensity, occult, research, work involving extremes and the unseen"},
    "Uttara Bhadrapada":{"deity": "Ahir Budhnya (serpent of the deep)", "symbol": "back of a funeral cot", "careers": "wisdom & counsel, charity, deep advisory work, patient long-term endeavours"},
    "Revati":           {"deity": "Pushan (nourisher, guide of journeys)", "symbol": "fish", "careers": "guidance & care, travel/foreign work, spirituality, art, nurturing and protective roles"},
}


def profile_of(name: str) -> dict[str, str]:
    """Classical significations (deity, symbol, careers) for a nakshatra ('' fields if unknown)."""
    canonical = name if name in NAKSHATRA_PROFILE else normalize_nakshatra(name)
    return NAKSHATRA_PROFILE.get(canonical, {})


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
    canonical = name if name in NAKSHATRAS else normalize_nakshatra(name)
    if canonical not in NAKSHATRAS:
        return ""
    return VIMSHOTTARI_ORDER[NAKSHATRAS.index(canonical) % 9]


def traits_of(name: str) -> str:
    if name in NAKSHATRA_TRAITS:
        return NAKSHATRA_TRAITS[name]
    return NAKSHATRA_TRAITS.get(normalize_nakshatra(name), "")
