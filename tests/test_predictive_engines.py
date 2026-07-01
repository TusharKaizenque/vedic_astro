"""Tests for Vargottama, Vimshopaka Bala, Putrakaraka, and the children-timing engine."""
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.children_timing import build_children_timing, children_significators
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.varga_engine import (
    vargottama_planets, vimshopaka_bala, vimshopaka_band,
)
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS
from utils.jaimini import putrakaraka

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _p(name, lon, sign, house, deg=None):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=False,
                          degree_in_sign=deg if deg is not None else lon % 30)


def _chart(planets, lagna="Aries", tree=None):
    start = ZODIAC_SIGNS.index(lagna)
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="1990-01-01", time="10:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=0.0, moon_sign="Cancer", sun_sign="Leo",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(start + i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(start + i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Jupiter", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Jupiter", antar_dasha_start="", antar_dasha_end=""),
        raw_prokerala_response=tree or {})


# ---------- Vargottama ----------
def test_vargottama_first_navamsa_of_movable_sign():
    # A planet at 1° Aries falls in the first navamsa (Aries) → same sign in D1 and D9.
    ch = _chart({"Sun": _p("Sun", 1.0, "Aries", 1)})
    assert "Sun" in vargottama_planets(ch)
    # A planet mid-Aries lands in a different navamsa → not vargottama.
    ch2 = _chart({"Sun": _p("Sun", 20.0, "Aries", 1)})
    assert "Sun" not in vargottama_planets(ch2)


# ---------- Vimshopaka Bala ----------
def test_vimshopaka_exalted_beats_debilitated():
    strong = _chart({"Sun": _p("Sun", 10.0, "Aries", 1)})       # Sun exalted in Aries
    weak = _chart({"Sun": _p("Sun", 190.0, "Libra", 7)})        # Sun debilitated in Libra
    s = vimshopaka_bala(strong)["Sun"]
    w = vimshopaka_bala(weak)["Sun"]
    assert s > w
    assert vimshopaka_band(s) in ("strong", "very strong")
    # Nodes are excluded (own no signs).
    ch = _chart({"Rahu": _p("Rahu", 100.0, "Cancer", 4), "Sun": _p("Sun", 10.0, "Aries", 1)})
    assert "Rahu" not in vimshopaka_bala(ch)


def test_vimshopaka_bands():
    assert vimshopaka_band(18) == "very strong"
    assert vimshopaka_band(12) == "strong"
    assert vimshopaka_band(7) == "moderate"
    assert vimshopaka_band(3) == "weak"


# ---------- Putrakaraka ----------
def test_putrakaraka_is_fifth_by_degree():
    # Degrees descending: Sun28 Moon25 Mars22 Merc18 Jup12 Ven8 Sat3 → 5th (index 4) = Jupiter.
    planets = {
        "Sun": _p("Sun", 0, "Aries", 1, 28), "Moon": _p("Moon", 0, "Taurus", 2, 25),
        "Mars": _p("Mars", 0, "Gemini", 3, 22), "Mercury": _p("Mercury", 0, "Cancer", 4, 18),
        "Jupiter": _p("Jupiter", 0, "Leo", 5, 12), "Venus": _p("Venus", 0, "Virgo", 6, 8),
        "Saturn": _p("Saturn", 0, "Libra", 7, 3),
    }
    assert putrakaraka(_chart(planets)) == "Jupiter"


# ---------- Children timing ----------
def test_children_significators_include_5th_lord_jupiter_putrakaraka():
    # Aries lagna → 5th house Leo, 5th lord Sun. Jupiter is the karaka.
    planets = {
        "Sun": _p("Sun", 130, "Leo", 5, 28), "Jupiter": _p("Jupiter", 95, "Cancer", 4, 5),
        "Moon": _p("Moon", 100, "Cancer", 4, 10), "Mars": _p("Mars", 8, "Aries", 1, 8),
    }
    ch = _chart(planets)
    sig = children_significators(ch, run_rule_engine(ch))
    assert "Sun" in sig            # 5th lord
    assert "Jupiter" in sig        # karaka of children


def test_children_timing_window_scored():
    planets = {"Sun": _p("Sun", 130, "Leo", 5, 28), "Jupiter": _p("Jupiter", 95, "Cancer", 4, 5),
               "Moon": _p("Moon", 100, "Cancer", 4, 10)}
    tree = {"dasha_periods": [{"name": "Jupiter", "antardasha": [
        {"name": "Sun", "start": "2027-01-01T00:00:00+00:00", "end": "2028-01-01T00:00:00+00:00"},
        {"name": "Mercury", "start": "2020-01-01T00:00:00+00:00", "end": "2021-01-01T00:00:00+00:00"},
    ]}]}
    ch = _chart(planets, tree=tree)
    windows = build_children_timing(ch, run_rule_engine(ch), NOW)
    by_ad = {w.antar_lord: w for w in windows}
    assert "Sun" in by_ad            # 5th-lord antardasha, upcoming → scored
    assert "Mercury" not in by_ad    # ended 2021 → excluded
    assert by_ad["Sun"].score >= 2
