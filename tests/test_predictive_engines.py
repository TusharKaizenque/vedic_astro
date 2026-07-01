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


# ---------- Arudha Lagna ----------
def test_arudha_lagna_computation_and_tone():
    from services.arudha_analysis import build_arudha_reading
    from utils.arudha import arudha_pada
    # Aries lagna (idx0), lord Mars in Leo (idx4) → arudha = (2*4-0)%12 = 8 = Sagittarius.
    assert arudha_pada(0, 4) == 8
    planets = {"Mars": _p("Mars", 130, "Leo", 5), "Jupiter": _p("Jupiter", 250, "Sagittarius", 9),
               "Venus": _p("Venus", 250, "Sagittarius", 9), "Sun": _p("Sun", 130, "Leo", 5)}
    r = build_arudha_reading(_chart(planets))
    assert r.al_sign == "Sagittarius" and r.al_house_from_lagna == 9
    assert "Jupiter" in r.occupants and "esteemed" in r.tone


def test_arudha_pada_exception_rule():
    from utils.arudha import arudha_pada
    # If the pada lands in the house itself or the 7th, take the 10th from it.
    # House idx 0, lord idx 6 → raw = (12-0)%12 = 0 = same house → +9 → 9.
    assert arudha_pada(0, 6) == 9
    # House idx 0, lord idx 3 → raw = 6 = 7th from house → +9 → 3.
    assert arudha_pada(0, 3) == 3


# ---------- Bhrigu Bindu ----------
def test_bhrigu_bindu_midpoint():
    from services.special_points import bhrigu_bindu
    # Rahu 0° Aries, Moon 60° Gemini → midpoint 30° = 0° Taurus.
    planets = {"Rahu": _p("Rahu", 0.0, "Aries", 1), "Moon": _p("Moon", 60.0, "Gemini", 3)}
    bb = bhrigu_bindu(_chart(planets))
    assert bb is not None and abs(bb.longitude - 30.0) < 0.01
    assert bb.sign == "Taurus" and bb.house_from_lagna == 2
    assert bb.sign_lord == "Venus"


def test_bhrigu_bindu_none_without_nodes():
    from services.special_points import bhrigu_bindu
    assert bhrigu_bindu(_chart({"Moon": _p("Moon", 60.0, "Gemini", 3)})) is None
