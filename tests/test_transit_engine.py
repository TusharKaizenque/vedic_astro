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


def test_double_transit_detected():
    # Aries lagna → 7th house = Libra. Transit Jupiter in Libra (conjoins 7th), Saturn in Aries
    # (its 7th aspect reaches Libra). Both hit the 7th → double transit.
    chart = _chart(moon_sign="Aries", lagna="Aries")
    rep = gochara_report(chart, {"Jupiter": "Libra", "Saturn": "Aries"}, "2026",
                         topic_houses=[7], dasha_lords=["Saturn"])
    assert rep.double_transit
    assert any("DOUBLE TRANSIT" in n for n in rep.notes)


def test_no_double_transit_when_only_one_hits():
    chart = _chart(moon_sign="Aries", lagna="Aries")
    # Jupiter in Libra hits the 7th; Saturn in Gemini does not (aspects 3rd/7th/10th from Gemini).
    rep = gochara_report(chart, {"Jupiter": "Libra", "Saturn": "Gemini"}, "2026", topic_houses=[7])
    assert not rep.double_transit


def test_transit_notes_carry_ashtakavarga_bindus():
    chart = _chart(moon_sign="Aries", lagna="Aries", saturn_sign="Capricorn")
    rep = gochara_report(chart, {"Saturn": "Taurus"}, "2026", topic_houses=[2])
    assert any("Ashtakavarga" in n and "bindus" in n for n in rep.notes)


def test_yoga_fructification_timing():
    from services.rule_engine.engine import run_rule_engine
    from services.rule_engine.yoga_analysis import format_yoga_timing_for_prompt
    from utils.astro_constants import SIGN_RULERS

    def _p(n, lon, sign, house):
        return PlanetPosition(planet=n, longitude=lon, sign=sign, house=house, nakshatra="",
                              nakshatra_pada=1, degree_in_sign=lon % 30)
    planets = {"Moon": _p("Moon", 100, "Cancer", 4), "Jupiter": _p("Jupiter", 95, "Cancer", 4),
               "Mars": _p("Mars", 8, "Aries", 1)}
    tree = {"dasha_periods": [{"name": "Jupiter", "antardasha": [
        {"name": "Moon", "start": "2027-01-01T00:00:00+00:00", "end": "2028-06-01T00:00:00+00:00"}]}]}
    chart = NormalizedChart(
        user_id="t", birth_data=BirthData(date="1990-01-01", time="10:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Cancer", sun_sign="Leo",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(i - 1) % 12]], degree=0) for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Jupiter", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Moon", antar_dasha_start="", antar_dasha_end=""),
        raw_prokerala_response=tree)
    r = run_rule_engine(chart)
    block = format_yoga_timing_for_prompt(chart, r.yoga_readings, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert "YOGA ACTIVATION TIMING" in block
    assert "Gajakesari" in block and "Jupiter mahadasha / Moon antardasha" in block
