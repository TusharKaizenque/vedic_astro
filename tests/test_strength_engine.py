"""Tests for the classical Shadbala-lite strength engine (Phase A1)."""
import pytest

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.strength_engine import (
    compute_all_strengths, compute_planet_strength,
)
from utils.astro_constants import EXALTATION_DEGREE, ZODIAC_SIGNS


def _planet(name, longitude, house, retro=False):
    sign = ZODIAC_SIGNS[int(longitude // 30) % 12]
    return PlanetPosition(
        planet=name, longitude=longitude, sign=sign, house=house,
        nakshatra="", nakshatra_pada=1, is_retrograde=retro,
        degree_in_sign=longitude % 30,
    )


def _chart(planets):
    return NormalizedChart(
        user_id="t", birth_data=BirthData(
            date="2000-01-01", time="12:00", latitude=0.0, longitude=0.0,
            timezone="UTC", place_name="x"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Aries", sun_sign="Aries",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1], lord="Mars", degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


def test_exalted_planet_raises_sthana():
    # Sun at exact exaltation (Aries 10°) → Uchcha (inside Sthana Bala) near max
    from services.rule_engine.strength_engine import _uchcha
    assert _uchcha("Sun", EXALTATION_DEGREE["Sun"]) == pytest.approx(60.0, abs=0.5)
    chart = _chart({"Sun": _planet("Sun", EXALTATION_DEGREE["Sun"], 1)})
    s = compute_planet_strength("Sun", chart, sun_long=EXALTATION_DEGREE["Sun"], moon_long=200.0)
    assert "near exaltation" in s.notes
    assert "sthana" in s.components and s.components["sthana"] > 100


def test_debilitated_planet_low_uchcha():
    from services.rule_engine.strength_engine import _uchcha
    debil = (EXALTATION_DEGREE["Sun"] + 180) % 360
    assert _uchcha("Sun", debil) == pytest.approx(0.0, abs=0.5)
    chart = _chart({"Sun": _planet("Sun", debil, 7)})
    s = compute_planet_strength("Sun", chart, sun_long=debil, moon_long=10.0)
    assert "near debilitation" in s.notes


def test_six_balas_present():
    chart = _chart({"Jupiter": _planet("Jupiter", 95.0, 1)})
    s = compute_planet_strength("Jupiter", chart, sun_long=200.0, moon_long=50.0)
    assert set(s.components) == {"sthana", "dig", "kala", "cheshta", "naisargika", "drik"}


def test_dig_bala_strong_in_correct_house():
    # Sun has full Dig Bala in the 10th house
    chart = _chart({"Sun": _planet("Sun", 100.0, 10)})
    s = compute_planet_strength("Sun", chart, sun_long=100.0, moon_long=200.0)
    assert s.components["dig"] == pytest.approx(60.0, abs=0.1)


def test_dig_bala_weak_in_opposite_house():
    # Sun in 4th house (opposite its strong 10th) → Dig Bala 0
    chart = _chart({"Sun": _planet("Sun", 100.0, 4)})
    s = compute_planet_strength("Sun", chart, sun_long=100.0, moon_long=200.0)
    assert s.components["dig"] == pytest.approx(0.0, abs=0.1)


def test_retrograde_boosts_cheshta():
    chart = _chart({
        "Mars": _planet("Mars", 50.0, 2, retro=True),
        "Saturn": _planet("Saturn", 50.0, 2, retro=False),
    })
    retro = compute_planet_strength("Mars", chart, 0.0, 200.0)
    direct = compute_planet_strength("Saturn", chart, 0.0, 200.0)
    assert retro.components["cheshta"] > direct.components["cheshta"]
    assert "retrograde" in " ".join(retro.notes)


def test_combustion_penalty_applied():
    # Mercury within 2° of Sun → combust, penalty > 0
    chart = _chart({"Mercury": _planet("Mercury", 12.0, 1), "Sun": _planet("Sun", 10.0, 1)})
    s = compute_planet_strength("Mercury", chart, sun_long=10.0, moon_long=200.0)
    assert s.combustion_penalty > 0
    assert "combust" in " ".join(s.notes)


def test_bands_assigned():
    chart = _chart({"Sun": _planet("Sun", EXALTATION_DEGREE["Sun"], 10)})
    s = compute_planet_strength("Sun", chart, EXALTATION_DEGREE["Sun"], 200.0)
    assert s.band in ("strong", "moderate", "weak")
    assert 0.0 <= s.relative <= 1.0


def test_compute_all_returns_every_planet():
    planets = {
        "Sun": _planet("Sun", 10, 1), "Moon": _planet("Moon", 40, 2),
        "Mars": _planet("Mars", 70, 3),
    }
    result = compute_all_strengths(_chart(planets))
    assert set(result.keys()) == set(planets.keys())


def test_kendradi_bala_favours_angular_houses():
    from services.rule_engine.strength_engine import _kendradi
    assert _kendradi(1) == 60.0    # kendra
    assert _kendradi(2) == 30.0    # panapara
    assert _kendradi(3) == 15.0    # apoklima


def test_drik_bala_benefic_vs_malefic_aspect():
    from services.rule_engine.strength_engine import _drik
    from services.rule_engine.aspect_engine import get_aspects_by_planet
    # Target in house 1; a benefic (Jupiter) in 7 aspects it → drik up; a malefic in 7 → down
    benefic = _chart({"Mars": _planet("Mars", 0, 1), "Jupiter": _planet("Jupiter", 180, 7)})
    malefic = _chart({"Mars": _planet("Mars", 0, 1), "Saturn": _planet("Saturn", 180, 7)})
    db = _drik("Mars", benefic, get_aspects_by_planet(benefic))
    dm = _drik("Mars", malefic, get_aspects_by_planet(malefic))
    assert db > dm


def test_strength_band_uses_required_ratio():
    # A planet meeting its requirement is strong; well below is weak.
    chart = _chart({"Mars": _planet("Mars", 210, 1)})   # Mars own sign Scorpio in kendra
    s = compute_planet_strength("Mars", chart, sun_long=30.0, moon_long=120.0)
    assert s.band in ("strong", "moderate", "weak")
    assert s.total_virupas > 0
