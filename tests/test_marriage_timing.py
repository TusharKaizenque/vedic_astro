"""Tests for the Marriage Timing engine — dasha windows of marriage significators."""
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.marriage_timing import (
    build_marriage_timing, format_marriage_timing_for_prompt, marriage_significators,
)
from services.rule_engine.engine import run_rule_engine
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _p(name, lon, sign, house):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=False, degree_in_sign=lon % 30)


def _chart(dasha_periods):
    planets = {
        "Sun": _p("Sun", 125.5, "Leo", 5), "Moon": _p("Moon", 30.3, "Taurus", 2),  # Moon deg 0.3 = DK
        "Mars": _p("Mars", 9.9, "Aries", 1), "Mercury": _p("Mercury", 140.7, "Leo", 5),
        "Jupiter": _p("Jupiter", 250.6, "Sagittarius", 9), "Venus": _p("Venus", 188.0, "Libra", 7),
        "Saturn": _p("Saturn", 300.8, "Aquarius", 11),
        "Rahu": _p("Rahu", 75.0, "Gemini", 3), "Ketu": _p("Ketu", 255.0, "Sagittarius", 9),
    }
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=5.0, moon_sign="Taurus", sun_sign="Leo",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Venus", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
        raw_prokerala_response={"dasha_periods": dasha_periods},
    )


_DASHA = [{
    "name": "Venus",
    "antardasha": [
        {"name": "Sun", "start": "2024-01-01T00:00:00+00:00", "end": "2025-06-01T00:00:00+00:00"},
        {"name": "Moon", "start": "2027-01-01T00:00:00+00:00", "end": "2028-06-01T00:00:00+00:00"},
        # Saturn here is in the 11th (aspects 1/5/8, NOT the 7th) and isn't a 2nd/7th lord,
        # karaka, DK, dispositor or UL lord → a genuine non-significator.
        {"name": "Saturn", "start": "2028-06-01T00:00:00+00:00", "end": "2029-01-01T00:00:00+00:00"},
    ],
}]


def test_significators_include_seventh_lord_venus_and_darakaraka():
    chart = _chart(_DASHA)
    sig = marriage_significators(chart, run_rule_engine(chart))
    assert "Venus" in sig          # 7th lord (Libra) + karaka
    assert "Moon" in sig           # Darakaraka


def test_past_window_excluded_and_future_scored():
    chart = _chart(_DASHA)
    windows = build_marriage_timing(chart, run_rule_engine(chart), NOW)
    by_ad = {w.antar_lord: w for w in windows}
    assert "Sun" not in by_ad                       # ended 2025-06, before NOW → excluded
    assert "Moon" in by_ad                           # future + Moon is the Darakaraka
    assert by_ad["Moon"].score >= 2                   # antar significator (Moon DK) + Venus MD
    assert by_ad["Moon"].start.year == 2027


def test_non_significator_window_scores_lower():
    chart = _chart(_DASHA)
    windows = build_marriage_timing(chart, run_rule_engine(chart), NOW)
    by_ad = {w.antar_lord: w for w in windows}
    # Saturn AD is not a significator → only the Venus mahadasha lifts it (score 1),
    # well below the Moon-DK antardasha window.
    assert by_ad["Saturn"].score == 1.0
    assert by_ad["Saturn"].score < by_ad["Moon"].score


def test_format_block_present():
    chart = _chart(_DASHA)
    block = format_marriage_timing_for_prompt(build_marriage_timing(chart, run_rule_engine(chart), NOW), NOW)
    assert "MARRIAGE TIMING" in block and "antardasha" in block.lower()
