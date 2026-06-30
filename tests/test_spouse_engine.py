"""Tests for the Spouse Engine — multi-factor, individualized partner portrait."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from services.spouse_engine import (
    _arudha_idx, build_spouse_profile, format_spouse_profile_for_prompt,
)
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS
from utils.jaimini import darakaraka


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=retro, degree_in_sign=lon % 30)


def _chart(planets, lagna="Aries"):
    start = ZODIAC_SIGNS.index(lagna)
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=5.0, moon_sign="Aries", sun_sign="Aries",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(start + i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(start + i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


# Aries lagna; Venus has the lowest degree-in-sign (2.0) → Darakaraka = Venus.
_PLANETS_A = {
    "Sun": _p("Sun", 100.5, "Cancer", 4), "Moon": _p("Moon", 215.2, "Scorpio", 8),
    "Mars": _p("Mars", 231.9, "Scorpio", 8), "Mercury": _p("Mercury", 94.7, "Cancer", 4),
    "Jupiter": _p("Jupiter", 69.7, "Gemini", 3), "Venus": _p("Venus", 62.0, "Gemini", 3),
    "Saturn": _p("Saturn", 48.1, "Taurus", 2),
    "Rahu": _p("Rahu", 70.7, "Gemini", 3, True), "Ketu": _p("Ketu", 250.7, "Sagittarius", 9, True),
}


def test_darakaraka_is_lowest_degree_planet():
    assert darakaraka(_chart(_PLANETS_A)) == "Venus"


def _profile(planets, lagna="Aries"):
    chart = _chart(planets, lagna)
    rules = run_rule_engine(chart)
    strengths = compute_all_strengths(chart)
    return build_spouse_profile(chart, rules, strengths)


def test_profile_has_all_core_facets():
    p = _profile(_PLANETS_A)
    labels = " ".join(f.label for f in p.facets)
    assert "Inner nature" in labels          # Darakaraka
    assert "7th-house stamps" in labels       # occupants/aspectors
    assert "7th lord" in labels
    assert "Navamsa D9 7th" in labels
    assert "Upapada" in labels
    assert p.darakaraka == "Venus"
    assert p.profession_hints                 # non-empty


def test_inner_nature_grounded_in_darakaraka():
    p = _profile(_PLANETS_A)
    inner = next(f for f in p.facets if "Inner nature" in f.label)
    assert "Darakaraka = Venus" in inner.factor
    assert "refined" in inner.text or "aesthetic" in inner.text  # Venus archetype


def test_different_charts_give_different_darakaraka_and_profiles():
    # Make Saturn the lowest-degree planet instead of Venus → DK changes → portrait changes.
    planets_b = dict(_PLANETS_A)
    planets_b["Venus"] = _p("Venus", 75.0, "Gemini", 3)   # raise Venus degree
    planets_b["Saturn"] = _p("Saturn", 30.5, "Taurus", 2)  # Saturn lowest (0.5)
    pa, pb = _profile(_PLANETS_A), _profile(planets_b)
    assert pa.darakaraka != pb.darakaraka
    assert format_spouse_profile_for_prompt(pa) != format_spouse_profile_for_prompt(pb)


def test_arudha_formula_and_exception():
    # Normal: house 0 (Aries), lord at index 2 → 2nd-distance again → index 4.
    assert _arudha_idx(0, 2) == 4
    # Exception: lord in the house's own sign (dist 0) → arudha would be the house itself →
    # take the 10th from it → index 9.
    assert _arudha_idx(0, 0) == 9


def test_format_block_has_header_and_no_empty_when_facets():
    block = format_spouse_profile_for_prompt(_profile(_PLANETS_A))
    assert "SPOUSE PROFILE" in block and "Darakaraka" in block
