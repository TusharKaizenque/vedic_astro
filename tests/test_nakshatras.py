"""Tests for the nakshatra (lunar-mansion) engine."""
from utils.chart_normalizer import _resolve_nakshatra
from utils.nakshatras import (
    NAKSHATRAS, nakshatra_index, nakshatra_lord, nakshatra_lord_by_name,
    nakshatra_of, normalize_nakshatra, pada_of, traits_of,
)


def test_27_nakshatras():
    assert len(NAKSHATRAS) == 27
    assert NAKSHATRAS[0] == "Ashwini"
    assert NAKSHATRAS[-1] == "Revati"


def test_index_and_name_at_boundaries():
    assert nakshatra_of(0.0) == "Ashwini"          # 0° = start of Ashwini
    assert nakshatra_of(13.0) == "Ashwini"         # still within first 13°20'
    assert nakshatra_of(13.34) == "Bharani"        # crossed into 2nd
    assert nakshatra_of(359.9) == "Revati"         # last nakshatra
    assert nakshatra_index(360.0) == 0             # wraps


def test_known_moon_position():
    # Moon at 221.18° (Scorpio) → Anuradha, pada 3, lord Saturn
    assert nakshatra_of(221.18) == "Anuradha"
    assert pada_of(221.18) == 3
    assert nakshatra_lord(221.18) == "Saturn"


def test_pada_range():
    # 4 padas of 3°20' across a 13°20' nakshatra
    assert pada_of(0.0) == 1
    assert pada_of(3.0) == 1
    assert pada_of(3.34) == 2
    assert pada_of(7.0) == 3
    assert pada_of(11.0) == 4


def test_nakshatra_lords_cycle_vimshottari():
    # Ashwini=Ketu, Bharani=Venus, Krittika=Sun ... 10th (Magha) restarts at Ketu
    assert nakshatra_lord_by_name("Ashwini") == "Ketu"
    assert nakshatra_lord_by_name("Bharani") == "Venus"
    assert nakshatra_lord_by_name("Krittika") == "Sun"
    assert nakshatra_lord_by_name("Magha") == "Ketu"     # 10th, cycle repeats
    assert nakshatra_lord_by_name("Revati") == "Mercury" # 27th


def test_traits_present_for_all():
    for n in NAKSHATRAS:
        assert traits_of(n), f"missing traits for {n}"


def test_normalize_canonical_roundtrip():
    # Every canonical name normalizes to itself.
    for n in NAKSHATRAS:
        assert normalize_nakshatra(n) == n


def test_normalize_prokerala_variants():
    # Common transliteration / regional spellings map to canonical names.
    cases = {
        "BHARANI": "Bharani", "Mrigasira": "Mrigashira", "Poorva Phalguni": "Purva Phalguni",
        "Uttaraphalguni": "Uttara Phalguni", "Jyeshta": "Jyeshtha", "Moola": "Mula",
        "Satabhisha": "Shatabhisha", "Uttara Bhadra": "Uttara Bhadrapada", "Revathi": "Revati",
        "Chothi": "Swati", "Kettai": "Jyeshtha", "Aslesha": "Ashlesha", "Dhanishtha": "Dhanishta",
    }
    for variant, canonical in cases.items():
        assert normalize_nakshatra(variant) == canonical, variant
    assert normalize_nakshatra("not a nakshatra") == ""
    assert normalize_nakshatra("") == ""


def test_lookups_tolerate_variants():
    # Lord / traits lookups no longer silently fail on a benign spelling difference.
    assert nakshatra_lord_by_name("Poorva Phalguni") == "Venus"
    assert nakshatra_lord_by_name("Jyeshta") == "Mercury"
    assert traits_of("Mrigasira") == traits_of("Mrigashira") != ""


def test_resolve_nakshatra_is_longitude_sourced():
    # Bharani pada 1 spans 13°20'–16°40'. A Moon at 14° → Bharani p1 regardless of what
    # name Prokerala supplies; a disagreeing provided name does NOT override the longitude.
    name, pada = _resolve_nakshatra("Moon", 14.0, "", 0)
    assert (name, pada) == ("Bharani", 1)
    # Provided pada/name are ignored when a real longitude is present (consistency guarantee).
    name, pada = _resolve_nakshatra("Moon", 14.0, "Krittika", 3)
    assert (name, pada) == ("Bharani", 1)
    # A normalised provided name that AGREES is fine.
    name, pada = _resolve_nakshatra("Moon", 14.0, "BHARANI", 1)
    assert (name, pada) == ("Bharani", 1)


def test_resolve_nakshatra_falls_back_without_longitude():
    # No usable longitude → fall back to Prokerala's (normalised) name + pada.
    name, pada = _resolve_nakshatra("Moon", 0.0, "Revathi", 4)
    assert (name, pada) == ("Revati", 4)
