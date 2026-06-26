"""Tests for the transit (gochara) engine — D2. Pure logic, no network."""
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.transit_engine import (
    gochara_report, parse_transit_positions, resolve_transit_date,
)
from utils.astro_constants import ZODIAC_SIGNS


def _planet(name, sign):
    idx = ZODIAC_SIGNS.index(sign)
    return PlanetPosition(planet=name, longitude=idx * 30 + 10, sign=sign, house=1,
                          nakshatra="", nakshatra_pada=1, degree_in_sign=10.0)


def _chart(moon_sign="Aries", lagna="Aries", saturn_sign="Aries"):
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=18.5,
                                          longitude=73.8, timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=0.0, moon_sign=moon_sign, sun_sign="Leo",
        nakshatra="", nakshatra_pada=1,
        planets={"Saturn": _planet("Saturn", saturn_sign), "Moon": _planet("Moon", moon_sign)},
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1], lord="", degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Saturn", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Saturn", antar_dasha_start="", antar_dasha_end=""),
    )


# --- Date resolution ---

def test_resolve_explicit_year():
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    assert resolve_transit_date(["2027"], now).year == 2027


def test_resolve_next_year():
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    assert resolve_transit_date(["next year"], now).year == 2027


def test_resolve_fallback_to_now():
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    assert resolve_transit_date([], now) == now


# --- Position parsing ---

def test_parse_transit_positions_normalizes_sanskrit():
    raw = {"data": {"planets": [
        {"name": "Saturn", "rasi": {"name": "Vrischika"}},
        {"name": "Jupiter", "rasi": {"name": "Mithuna"}},
    ]}}
    pos = parse_transit_positions(raw)
    assert pos["Saturn"] == "Scorpio"
    assert pos["Jupiter"] == "Gemini"


# --- Gochara: Sade Sati ---

def test_sade_sati_detected_when_saturn_over_moon():
    # Natal Moon in Aries; transit Saturn in Aries → 1st from Moon → Sade Sati peak
    chart = _chart(moon_sign="Aries")
    report = gochara_report(chart, {"Saturn": "Aries"}, "2027")
    assert report.sade_sati is True
    assert "peak" in report.sade_sati_phase


def test_sade_sati_rising_when_saturn_12th_from_moon():
    # Moon in Aries; Saturn in Pisces → 12th from Moon → rising
    chart = _chart(moon_sign="Aries")
    report = gochara_report(chart, {"Saturn": "Pisces"}, "2027")
    assert report.sade_sati is True
    assert "rising" in report.sade_sati_phase


def test_no_sade_sati_when_saturn_favourable():
    # Moon in Aries; Saturn in Gemini → 3rd from Moon → favourable, no sade sati
    chart = _chart(moon_sign="Aries")
    report = gochara_report(chart, {"Saturn": "Gemini"}, "2027")
    assert report.sade_sati is False
    assert report.favourable >= 1


# --- Gochara: Jupiter favourable ---

def test_jupiter_favourable_from_moon():
    # Moon in Aries; Jupiter in Aquarius → 11th from Moon → favourable
    chart = _chart(moon_sign="Aries")
    report = gochara_report(chart, {"Jupiter": "Aquarius"}, "2027")
    assert report.favourable >= 1


# --- Gochara: dasha lord activation ---

def test_transit_over_dasha_lord_noted():
    # Saturn is the dasha lord, natal Saturn in Capricorn; transit Saturn in Capricorn
    chart = _chart(saturn_sign="Capricorn")
    report = gochara_report(chart, {"Saturn": "Capricorn"}, "2027", dasha_lords=["Saturn"])
    assert any("dasha lord" in n for n in report.notes)
