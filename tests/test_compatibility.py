"""Tests for the compatibility (Ashtakoot + Mangal) engine."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.compatibility import (
    _bhakoot, _gana, _nadi, _yoni, assess_compatibility, format_compatibility_for_prompt,
)
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS


# ── koota unit checks (indices: Ashwini=0 … Revati=26) ──

def test_nadi_same_group_is_zero_else_eight():
    assert _nadi(0, 5).score == 0.0     # Ashwini & Ardra are both Aadi
    assert _nadi(0, 1).score == 8.0     # Ashwini (Aadi) vs Bharani (Madhya)


def test_bhakoot_dosha_axes():
    assert _bhakoot("Aries", "Taurus").score == 0.0       # 2/12
    assert _bhakoot("Cancer", "Scorpio").score == 0.0     # 5/9
    assert _bhakoot("Aries", "Gemini").score == 7.0       # 3/11 — supportive


def test_yoni_same_and_mortal_enemy():
    # Ashwini=horse, Shatabhisha=horse → same → 4.
    assert _yoni(0, 23).score == 4.0
    # Bharani=elephant, Dhanishta=lion → mortal enemies → 0.
    assert _yoni(1, 22).score == 0.0


def test_gana_deva_deva_full_rakshasa_clash_low():
    assert _gana(0, 0).score == 6.0      # deva + deva
    assert _gana(10, 2).score <= 1.0     # manushya (P.Phalguni) + rakshasa (Krittika)


# ── integration ──

def _p(name, lon, sign, house):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=False, degree_in_sign=lon % 30)


def _chart(moon_lon, moon_sign, mars_house=3):
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign=moon_sign, sun_sign="Aries",
        nakshatra="", nakshatra_pada=1,
        planets={"Moon": _p("Moon", moon_lon, moon_sign, 1),
                 "Mars": _p("Mars", 0.0, ZODIAC_SIGNS[(mars_house - 1) % 12], mars_house),
                 "Venus": _p("Venus", 0.0, "Taurus", 2), "Sun": _p("Sun", 0.0, "Aries", 1)},
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


def test_assess_challenging_pair():
    # Moon ~100° = Pushya (Cancer); Moon ~220° = Anuradha (Scorpio): same Madhya Nadi + 5/9 Bhakoot.
    a = _chart(100.0, "Cancer")
    b = _chart(220.0, "Scorpio")
    rep = assess_compatibility(a, b)
    nadi = next(k for k in rep.kootas if k.name.startswith("Nadi"))
    bhakoot = next(k for k in rep.kootas if k.name.startswith("Bhakoot"))
    assert nadi.score == 0.0 and bhakoot.score == 0.0
    assert rep.total == round(sum(k.score for k in rep.kootas), 1)
    assert rep.verdict                       # non-empty
    assert any("Nadi" in c for c in rep.cautions)


def test_format_block_leads_with_verdict():
    rep = assess_compatibility(_chart(100.0, "Cancer"), _chart(40.0, "Taurus"))
    block = format_compatibility_for_prompt(rep)
    assert "COMPATIBILITY" in block and "Verdict:" in block and "Breakdown:" in block
