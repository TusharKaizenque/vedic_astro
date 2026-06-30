"""Tests for the whole-chart Life Overview synthesis."""
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.intent_classifier import is_life_overview_query
from services.life_overview import build_life_overview, format_life_overview_for_prompt
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from utils.astro_constants import ZODIAC_SIGNS


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=retro, degree_in_sign=lon % 30)


def _chart():
    planets = {
        "Sun": _p("Sun", 102.8, "Cancer", 4), "Moon": _p("Moon", 221.18, "Scorpio", 8),
        "Mars": _p("Mars", 231.9, "Scorpio", 8), "Mercury": _p("Mercury", 94.73, "Cancer", 4),
        "Jupiter": _p("Jupiter", 69.75, "Gemini", 3), "Venus": _p("Venus", 62.97, "Gemini", 3),
        "Saturn": _p("Saturn", 48.13, "Taurus", 2), "Rahu": _p("Rahu", 70.70, "Gemini", 3, True),
        "Ketu": _p("Ketu", 250.70, "Sagittarius", 9, True),
    }
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2001-07-29", time="23:45", latitude=18.5,
                                          longitude=73.8, timezone="Asia/Kolkata", place_name="Pune"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Scorpio", sun_sign="Cancer",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1], lord="", degree=0) for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Ketu", maha_dasha_start="2026-05-21T11:26:39",
                        maha_dasha_end="2033-05-21", antar_dasha_lord="Ketu",
                        antar_dasha_start="", antar_dasha_end=""),
    )


def test_detection():
    assert is_life_overview_query("how was my life until now?")
    assert is_life_overview_query("what will I do in my life?")
    assert is_life_overview_query("tell me about myself")
    assert not is_life_overview_query("what does my chart say about my career?")
    assert not is_life_overview_query("when will I get married?")


def test_overview_is_multidomain_and_surfaces_standout_themes():
    c = _chart()
    rules = run_rule_engine(c)
    st = compute_all_strengths(c)
    ov = build_life_overview(c, rules, st, datetime(2026, 6, 26, tzinfo=timezone.utc))
    # multiple domains surfaced, not one
    assert len(ov.prominent_domains) >= 3
    # dominant planets identified
    assert ov.dominant_planets
    # general standout themes are surfaced (whatever the chart emphasizes), 1-4 of them
    assert 1 <= len(ov.standout_themes) <= 4
    # they are general life themes, not a hardcoded category
    assert all(isinstance(t, str) and t for t in ov.standout_themes)


def test_overview_has_past_and_future_chapters():
    c = _chart()
    rules = run_rule_engine(c)
    st = compute_all_strengths(c)
    ov = build_life_overview(c, rules, st, datetime(2026, 6, 26, tzinfo=timezone.utc))
    phases = {ch.phase for ch in ov.chapters}
    assert "past" in phases       # "how was my life until now"
    assert "future" in phases     # "what will I do"
    # the prompt block renders the chapters
    text = format_life_overview_for_prompt(ov)
    assert "life chapters" in text


def test_overview_chapters_are_chronological():
    c = _chart()
    rules = run_rule_engine(c)
    st = compute_all_strengths(c)
    ov = build_life_overview(c, rules, st, datetime(2026, 6, 26, tzinfo=timezone.utc))
    years = [ch.start_year for ch in ov.chapters]
    assert years == sorted(years)
