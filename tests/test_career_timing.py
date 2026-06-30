"""Tests for the Career Timing engine — dasha windows of karma (career) significators."""
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.career_timing import (
    build_career_timing, career_significators, format_career_timing_for_prompt,
)
from services.rule_engine.engine import run_rule_engine
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _p(name, lon, sign, house):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=False, degree_in_sign=lon % 30)


def _chart(dasha_periods):
    # Aries lagna → 10th lord Saturn (Capricorn), 6th lord Mercury (Virgo). Sun = karaka.
    planets = {
        "Saturn": _p("Saturn", 280.0, "Capricorn", 10), "Sun": _p("Sun", 130.0, "Leo", 5),
        "Mercury": _p("Mercury", 160.0, "Virgo", 6), "Jupiter": _p("Jupiter", 250.0, "Sagittarius", 9),
        "Venus": _p("Venus", 35.0, "Taurus", 2), "Moon": _p("Moon", 65.0, "Gemini", 3),
        "Mars": _p("Mars", 8.0, "Aries", 1),
        "Rahu": _p("Rahu", 100.0, "Cancer", 4), "Ketu": _p("Ketu", 130.5, "Leo", 5),
    }
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Gemini", sun_sign="Leo",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Saturn", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Mercury", antar_dasha_start="", antar_dasha_end=""),
        raw_prokerala_response={"dasha_periods": dasha_periods},
    )


_DASHA = [{
    "name": "Saturn",
    "antardasha": [
        {"name": "Mercury", "start": "2024-01-01T00:00:00+00:00", "end": "2025-06-01T00:00:00+00:00"},
        {"name": "Sun", "start": "2027-01-01T00:00:00+00:00", "end": "2028-06-01T00:00:00+00:00"},
        {"name": "Ketu", "start": "2028-06-01T00:00:00+00:00", "end": "2029-06-01T00:00:00+00:00"},
    ],
}]


def test_significators_include_10th_lord_and_karakas():
    sig = career_significators(_chart(_DASHA), run_rule_engine(_chart(_DASHA)))
    assert "Saturn" in sig      # 10th lord + karma karaka
    assert "Sun" in sig          # authority karaka
    assert "Mercury" in sig      # 6th lord (service)


def test_future_significator_window_scored_past_excluded():
    chart = _chart(_DASHA)
    windows = build_career_timing(chart, run_rule_engine(chart), NOW)
    by_ad = {w.antar_lord: w for w in windows}
    assert "Mercury" not in by_ad                      # ended 2025-06 → excluded
    assert by_ad["Sun"].score >= 2                       # Sun = authority karaka (antar trigger)
    # Ketu (in the 5th, not aspecting the 10th, not a lord) → not a career significator.
    assert "Ketu" not in by_ad or by_ad["Ketu"].score < by_ad["Sun"].score


def test_format_block_present():
    block = format_career_timing_for_prompt(build_career_timing(_chart(_DASHA), run_rule_engine(_chart(_DASHA)), NOW), NOW)
    assert "CAREER TIMING" in block and "antardasha" in block.lower()
