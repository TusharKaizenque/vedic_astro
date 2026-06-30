"""Tests for the faithfulness verifier (anti-hallucination check)."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.faithfulness import verify_response
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS


def _p(name, sign, house):
    return PlanetPosition(planet=name, longitude=0.0, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=False, degree_in_sign=0.0)


def _chart():
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign="Sagittarius", lagna_degree=0.0, moon_sign="Gemini", sun_sign="Gemini",
        nakshatra="", nakshatra_pada=1,
        planets={"Jupiter": _p("Jupiter", "Cancer", 8), "Mars": _p("Mars", "Aquarius", 3),
                 "Mercury": _p("Mercury", "Gemini", 7), "Saturn": _p("Saturn", "Gemini", 7)},
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[i - 1]], degree=0) for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Saturn", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Moon", antar_dasha_start="", antar_dasha_end=""),
    )


def test_faithful_house_claim_passes():
    assert verify_response("Jupiter is situated in the 8th house.", _chart()) == []


def test_wrong_house_claim_flagged():
    cons = verify_response("Jupiter in the 5th house grants wisdom.", _chart())
    assert len(cons) == 1 and cons[0].planet == "Jupiter" and cons[0].kind == "house"


def test_wrong_sign_claim_flagged():
    cons = verify_response("Mars in Aries makes you bold.", _chart())
    assert len(cons) == 1 and cons[0].kind == "sign"


def test_correct_sign_claim_passes():
    assert verify_response("Mercury in Gemini sharpens the intellect.", _chart()) == []


def test_lordship_phrasing_not_flagged():
    # "lord of the 5th" is lordship, not a placement claim — must not be flagged.
    assert verify_response("Jupiter, the lord of the 5th house, is benefic.", _chart()) == []


def test_unknown_planet_in_text_ignored():
    # Planet not in the chart's planet set → no claim to verify.
    assert verify_response("Venus in the 2nd house brings comfort.", _chart()) == []


def test_duplicate_contradiction_reported_once():
    text = "Jupiter in the 5th house. Later, Jupiter in the 5th house again."
    assert len(verify_response(text, _chart())) == 1


def test_multiple_distinct_contradictions():
    cons = verify_response("Jupiter in the 5th house and Mars in Aries.", _chart())
    assert len(cons) == 2
