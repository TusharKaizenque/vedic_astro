"""Tests for the Wealth Timing engine — dasha windows of Dhana (wealth) significators."""
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.engine import run_rule_engine
from services.wealth_timing import (
    build_wealth_timing, format_wealth_timing_for_prompt, wealth_significators,
)
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _p(name, lon, sign, house):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=False, degree_in_sign=lon % 30)


def _chart(dasha_periods):
    # Aries lagna → 2nd lord Venus, 11th lord Saturn, 9th lord Jupiter, 5th lord Sun.
    planets = {
        "Venus": _p("Venus", 35.0, "Taurus", 2), "Saturn": _p("Saturn", 305.0, "Aquarius", 11),
        "Jupiter": _p("Jupiter", 250.0, "Sagittarius", 9), "Sun": _p("Sun", 130.0, "Leo", 5),
        "Moon": _p("Moon", 5.0, "Aries", 1), "Mars": _p("Mars", 8.0, "Aries", 1),
        "Mercury": _p("Mercury", 65.0, "Gemini", 3),
    }
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Aries", sun_sign="Leo",
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
        {"name": "Saturn", "start": "2027-01-01T00:00:00+00:00", "end": "2028-06-01T00:00:00+00:00"},
        {"name": "Moon", "start": "2028-06-01T00:00:00+00:00", "end": "2029-06-01T00:00:00+00:00"},
    ],
}]


def test_significators_include_2nd_11th_lords_and_karakas():
    sig = wealth_significators(_chart(_DASHA), run_rule_engine(_chart(_DASHA)))
    assert "Venus" in sig and "Saturn" in sig      # 2nd & 11th lords (+ Venus karaka)
    assert "Jupiter" in sig                          # wealth karaka / 9th lord


def test_future_significator_window_scored_past_excluded():
    chart = _chart(_DASHA)
    windows = build_wealth_timing(chart, run_rule_engine(chart), NOW)
    by_ad = {w.antar_lord: w for w in windows}
    assert "Sun" not in by_ad                         # ended 2025-06 → excluded
    assert by_ad["Saturn"].score >= 2                  # Saturn = 11th lord (antar trigger)
    # Moon is the 4th lord (not a wealth significator) → only the Venus MD lifts it.
    assert by_ad["Moon"].score < by_ad["Saturn"].score


def test_format_block_present():
    block = format_wealth_timing_for_prompt(build_wealth_timing(_chart(_DASHA), run_rule_engine(_chart(_DASHA)), NOW), NOW)
    assert "WEALTH TIMING" in block and "antardasha" in block.lower()
