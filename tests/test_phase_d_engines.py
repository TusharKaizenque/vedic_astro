"""Tests for Phase D precision engines: varga (divisional charts) + Ashtakavarga."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.ashtakavarga_engine import (
    compute_bav, compute_sav, sav_band, sav_for_house,
)
from services.rule_engine.varga_engine import (
    sign_dignity, varga_agreement, varga_sign,
)
from utils.astro_constants import ZODIAC_SIGNS

# Classical fixed BAV totals per planet (BPHS) — a strong correctness invariant.
_BAV_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
               "Jupiter": 56, "Venus": 52, "Saturn": 39}


def _planet(name, longitude, house):
    return PlanetPosition(
        planet=name, longitude=longitude, sign=ZODIAC_SIGNS[int(longitude // 30) % 12],
        house=house, nakshatra="", nakshatra_pada=1, degree_in_sign=longitude % 30,
    )


def _full_chart():
    # Arbitrary but fixed positions for all 7 + nodes
    longs = {"Sun": 100, "Moon": 221, "Mars": 232, "Mercury": 95, "Jupiter": 70,
             "Venus": 63, "Saturn": 48, "Rahu": 71, "Ketu": 251}
    planets = {n: _planet(n, l, (int(l // 30) % 12) + 1) for n, l in longs.items()}
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Scorpio", sun_sign="Cancer",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1], lord="", degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Ketu", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Ketu", antar_dasha_start="", antar_dasha_end=""),
    )


# --- Ashtakavarga ---

def test_sav_total_is_337():
    sav = compute_sav(_full_chart())
    assert sum(sav) == 337   # classical invariant


def test_bav_totals_match_classical():
    bav = compute_bav(_full_chart())
    for planet, total in _BAV_TOTALS.items():
        assert sum(bav[planet]) == total, f"{planet} BAV total {sum(bav[planet])} != {total}"


def test_sav_band_thresholds():
    assert sav_band(31) == "strong"
    assert sav_band(28) == "average"
    assert sav_band(20) == "weak"


def test_sav_for_house_in_range():
    chart = _full_chart()
    for h in range(1, 13):
        b = sav_for_house(chart, h)
        assert 0 <= b <= 56


# --- Varga (divisional charts) ---

def test_navamsa_movable_sign_starts_same():
    # Aries 0-3.33 deg → D9 Aries (movable sign starts from itself)
    assert varga_sign(1.0, "D9") == "Aries"


def test_navamsa_fixed_sign_taurus_starts_capricorn():
    # Taurus 0-3.33 (longitude 30-33.33) → D9 Capricorn
    assert varga_sign(31.0, "D9") == "Capricorn"


def test_navamsa_dual_sign_gemini_starts_libra():
    # Gemini 0-3.33 (longitude 60-63.33) → D9 Libra
    assert varga_sign(61.0, "D9") == "Libra"


def test_dasamsa_odd_sign_starts_same():
    # Aries 0-3 deg → D10 Aries (odd sign starts from itself)
    assert varga_sign(1.0, "D10") == "Aries"


def test_dasamsa_even_sign_taurus_starts_ninth():
    # Taurus first dasamsa → 9th from Taurus = Capricorn
    assert varga_sign(31.0, "D10") == "Capricorn"


def test_unknown_varga_returns_empty():
    assert varga_sign(100.0, "D99") == ""


def test_sign_dignity():
    assert sign_dignity("Sun", "Aries") == "exalted"
    assert sign_dignity("Sun", "Libra") == "debilitated"
    assert sign_dignity("Venus", "Libra") == "own sign"


def test_varga_agreement():
    # Strong in D1, strong in varga → confirms
    assert varga_agreement("exalted", "own sign") == "confirms"
    # Strong in D1, weak in varga → contradicts
    assert varga_agreement("exalted", "debilitated") == "contradicts"
    # No varga info → neutral
    assert varga_agreement("exalted", "") == "neutral"
