"""Tests for the Phase-1 deterministic depth layer: planetary states + graded yoga analysis."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.planetary_states import (
    compute_planet_states, dignity_of, _baladi_avastha,
)
from services.rule_engine.yoga_analysis import analyze_yogas, format_yoga_analysis_for_prompt
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=retro, degree_in_sign=lon % 30)


def _chart(planets, lagna="Aries"):
    start = ZODIAC_SIGNS.index(lagna)
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="1990-01-01", time="10:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=0.0, moon_sign="Aries", sun_sign="Aries",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(start + i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(start + i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


# ---------- dignity ----------
def test_dignity_refinement():
    assert dignity_of("Jupiter", "Cancer", 5.0) == "exalted"
    assert dignity_of("Saturn", "Aries", 5.0) == "debilitated"
    assert dignity_of("Sun", "Leo", 10.0) == "moolatrikona"      # Leo 0-20 = MT
    assert dignity_of("Sun", "Leo", 25.0) == "own sign"          # beyond MT range = own
    assert dignity_of("Mars", "Cancer", 5.0) == "debilitated"    # Mars debilitates in Cancer
    assert dignity_of("Mars", "Gemini", 5.0) == "enemy sign"     # Mercury's sign, Mars's enemy


# ---------- baladi avastha (odd signs forward, even signs reversed) ----------
def test_baladi_avastha():
    assert _baladi_avastha("Aries", 3.0) == "Infant"     # odd sign, first portion
    assert _baladi_avastha("Aries", 15.0) == "Young"     # odd sign, middle = full strength
    assert _baladi_avastha("Taurus", 3.0) == "Dead"      # even sign reverses → first portion = Dead
    assert _baladi_avastha("Taurus", 15.0) == "Young"    # middle stays Young either way


# ---------- combustion ----------
def test_combustion_detected():
    # Mercury 1.5° from the Sun (orb 14°) → combust; Saturn far away → not.
    planets = {
        "Sun": _p("Sun", 130.0, "Leo", 5), "Mercury": _p("Mercury", 131.5, "Leo", 5),
        "Saturn": _p("Saturn", 200.0, "Libra", 7),
    }
    states = compute_planet_states(_chart(planets))
    assert states["Mercury"].combust and states["Mercury"].combust_orb == 1.5
    assert not states["Saturn"].combust


# ---------- planetary war (graha yuddha) ----------
def test_planetary_war():
    # Mars 10.2° and Saturn 10.8° in Aries, within 1° → war; lower-longitude Mars wins.
    planets = {
        "Sun": _p("Sun", 200.0, "Libra", 7),
        "Mars": _p("Mars", 10.2, "Aries", 1), "Saturn": _p("Saturn", 10.8, "Aries", 1),
    }
    states = compute_planet_states(_chart(planets))
    assert states["Mars"].war and states["Mars"].war_won
    assert states["Saturn"].war and not states["Saturn"].war_won
    assert states["Saturn"].war_with == "Mars"


# ---------- yoga grading ----------
def test_yoga_grading_strong_vs_weak():
    # Strong Gajakesari: exalted Jupiter (Cancer/4th kendra) + Moon in a kendra.
    strong = _chart({
        "Moon": _p("Moon", 100.0, "Cancer", 4), "Jupiter": _p("Jupiter", 95.0, "Cancer", 4),
    })
    r = analyze_yogas(strong, ["Gajakesari"], compute_planet_states(strong))
    assert r[0].name == "Gajakesari" and r[0].strength == "strong"
    assert "Jupiter" in r[0].participants and r[0].effect and r[0].source

    # Weakened Gajakesari: debilitated Jupiter (Capricorn/10th) + Moon — same yoga, graded down.
    weak = _chart({
        "Moon": _p("Moon", 280.0, "Capricorn", 10), "Jupiter": _p("Jupiter", 285.0, "Capricorn", 10),
    })
    r2 = analyze_yogas(weak, ["Gajakesari"], compute_planet_states(weak))
    assert r2[0].strength in ("weakened", "modest")


def test_adverse_yoga_flagged_and_sorted_last():
    ch = _chart({"Moon": _p("Moon", 100.0, "Cancer", 4), "Jupiter": _p("Jupiter", 95.0, "Cancer", 4)})
    readings = analyze_yogas(ch, ["Kemadruma", "Gajakesari"], compute_planet_states(ch))
    assert readings[0].name == "Gajakesari"          # beneficial first
    assert readings[-1].name == "Kemadruma" and readings[-1].adverse
    block = format_yoga_analysis_for_prompt(readings)
    assert "Gajakesari" in block and "Kemadruma" in block
