"""Tests for the expanded yoga library."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.yoga_detector import (
    detect_amala, detect_chatussagara, detect_durudhara, detect_guru_mangala,
    detect_maha_bhagya, detect_papa_kartari, detect_shakata, detect_shubha_kartari,
    detect_vasi, detect_vesi, find_parivartana,
)
from utils.astro_constants import ZODIAC_SIGNS


def _p(name, sign, house):
    idx = ZODIAC_SIGNS.index(sign)
    return PlanetPosition(planet=name, longitude=idx * 30 + 15, sign=sign, house=house,
                          nakshatra="", nakshatra_pada=1, degree_in_sign=15.0)


def _chart(planets, lagna="Aries", time="10:00"):
    start = ZODIAC_SIGNS.index(lagna)
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time=time, latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=0.0, moon_sign="Aries", sun_sign="Aries",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(start + i - 1) % 12], lord="", degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


def test_shubha_kartari_benefics_flank_lagna():
    chart = _chart({"Jupiter": _p("Jupiter", "Taurus", 2), "Venus": _p("Venus", "Pisces", 12)})
    assert detect_shubha_kartari(chart)
    assert not detect_papa_kartari(chart)


def test_papa_kartari_malefics_flank_lagna():
    chart = _chart({"Mars": _p("Mars", "Taurus", 2), "Saturn": _p("Saturn", "Pisces", 12)})
    assert detect_papa_kartari(chart)


def test_durudhara_planets_flank_moon():
    # Moon in house 1; planets in 2 and 12 (excl Sun/nodes)
    chart = _chart({"Moon": _p("Moon", "Aries", 1), "Jupiter": _p("Jupiter", "Taurus", 2),
                    "Venus": _p("Venus", "Pisces", 12)})
    assert detect_durudhara(chart)


def test_vesi_and_vasi_from_sun():
    # Sun house 1; Mars in 2 (vesi), Saturn in 12 (vasi)
    chart = _chart({"Sun": _p("Sun", "Aries", 1), "Mars": _p("Mars", "Taurus", 2),
                    "Saturn": _p("Saturn", "Pisces", 12)})
    assert detect_vesi(chart)
    assert detect_vasi(chart)


def test_shakata_moon_in_6_8_12_from_jupiter():
    # Jupiter house 1, Moon house 6 → 6th from Jupiter → Shakata
    chart = _chart({"Jupiter": _p("Jupiter", "Aries", 1), "Moon": _p("Moon", "Virgo", 6)})
    assert detect_shakata(chart)


def test_guru_mangala_conjunction():
    chart = _chart({"Jupiter": _p("Jupiter", "Leo", 5), "Mars": _p("Mars", "Leo", 5)})
    assert detect_guru_mangala(chart)


def test_amala_benefic_in_10th():
    chart = _chart({"Jupiter": _p("Jupiter", "Capricorn", 10), "Moon": _p("Moon", "Aries", 1)})
    assert detect_amala(chart)


def test_chatussagara_all_kendras():
    chart = _chart({"Sun": _p("Sun", "Aries", 1), "Moon": _p("Moon", "Cancer", 4),
                    "Mars": _p("Mars", "Libra", 7), "Saturn": _p("Saturn", "Capricorn", 10)})
    assert detect_chatussagara(chart)


def test_parivartana_sign_exchange():
    # Mars in Taurus (Venus's sign), Venus in Aries (Mars's sign) → mutual exchange
    chart = _chart({"Mars": _p("Mars", "Taurus", 2), "Venus": _p("Venus", "Aries", 1)})
    result = find_parivartana(chart)
    assert any("Parivartana" in r for r in result)


def test_maha_bhagya_day_birth_odd_signs():
    # Day birth (10:00), lagna/Sun/Moon all in odd signs (Aries, Leo, Sagittarius)
    chart = _chart({"Sun": _p("Sun", "Leo", 5), "Moon": _p("Moon", "Sagittarius", 9)},
                   lagna="Aries", time="10:00")
    assert detect_maha_bhagya(chart)
    # Night birth with the same odd signs → not Maha Bhagya
    chart_night = _chart({"Sun": _p("Sun", "Leo", 5), "Moon": _p("Moon", "Sagittarius", 9)},
                         lagna="Aries", time="23:00")
    assert not detect_maha_bhagya(chart_night)
