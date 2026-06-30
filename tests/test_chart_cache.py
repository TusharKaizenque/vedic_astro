"""Cache-first chart generation: don't re-bill Prokerala for a chart we already have."""
import asyncio
from unittest.mock import patch

import pytest

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services import chart_service
from services.chart_service import _same_birth, _time_key, generate_and_save_chart
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS

_BD = BirthData(date="2003-06-30", time="19:30:00", latitude=21.017332,
                longitude=75.900742, timezone="Asia/Kolkata", place_name="Varangaon")


def _chart(birth: BirthData) -> NormalizedChart:
    return NormalizedChart(
        user_id="u", birth_data=birth, lagna_sign="Sagittarius", lagna_degree=0.0,
        moon_sign="Gemini", sun_sign="Gemini", nakshatra="Punarvasu", nakshatra_pada=2,
        planets={"Sun": PlanetPosition(planet="Sun", longitude=74.0, sign="Gemini", house=7,
                                       nakshatra="Ardra", nakshatra_pada=1, degree_in_sign=14.0)},
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[i - 1]], degree=0) for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Saturn", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Moon", antar_dasha_start="", antar_dasha_end=""),
    )


# --- _time_key / _same_birth ---

def test_time_key_normalizes_seconds():
    assert _time_key("19:30") == _time_key("19:30:00") == (19, 30, 0)
    assert _time_key("19:30:30") == (19, 30, 30)


def test_same_birth_true_for_equivalent_inputs():
    assert _same_birth(_BD, _BD.model_copy(update={"time": "19:30", "place_name": "Other"}))


@pytest.mark.parametrize("change", [
    {"time": "19:31"}, {"time": "19:30:30"}, {"date": "2003-07-01"},
    {"latitude": 22.0}, {"timezone": "UTC"},
])
def test_same_birth_false_when_relevant_field_differs(change):
    assert not _same_birth(_BD, _BD.model_copy(update=change))


# --- cache-first generation (no Prokerala call on a hit) ---

def _run(coro):
    return asyncio.run(coro)


def test_cache_hit_makes_no_prokerala_call():
    async def _boom(*a, **k):
        raise AssertionError("Prokerala was called on a cache hit")
    async def _existing(_uid):
        return _chart(_BD)
    with patch.object(chart_service, "get_chart", _existing), \
         patch.object(chart_service, "fetch_full_chart", _boom):
        chart = _run(generate_and_save_chart("u", _BD.model_copy(update={"time": "19:30"})))
    assert chart.lagna_sign == "Sagittarius"  # returned the cached chart, no API hit


def test_changed_birth_bypasses_cache_and_fetches():
    async def _sentinel(*a, **k):
        raise RuntimeError("FETCHED")
    async def _existing(_uid):
        return _chart(_BD)
    with patch.object(chart_service, "get_chart", _existing), \
         patch.object(chart_service, "fetch_full_chart", _sentinel):
        with pytest.raises(RuntimeError, match="FETCHED"):
            _run(generate_and_save_chart("u", _BD.model_copy(update={"time": "06:00"})))


def test_force_bypasses_cache_even_when_birth_matches():
    async def _sentinel(*a, **k):
        raise RuntimeError("FETCHED")
    async def _existing(_uid):
        return _chart(_BD)
    with patch.object(chart_service, "get_chart", _existing), \
         patch.object(chart_service, "fetch_full_chart", _sentinel):
        with pytest.raises(RuntimeError, match="FETCHED"):
            _run(generate_and_save_chart("u", _BD, force=True))
