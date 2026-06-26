"""Tests for the outcome/signature engine (Phase G) and Jaimini karakas (Phase J)."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from models.intent import IntentCategory, IntentEntities, IntentResult
from services.assessment_engine import assess_topic
from services.outcome_engine import derive_outcome, format_outcome_for_prompt
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from services.significator_engine import get_significators
from utils.jaimini import amatyakaraka, atmakaraka
from utils.significations import life_area, professions_for, traits_for
from utils.astro_constants import ZODIAC_SIGNS


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=retro, degree_in_sign=lon % 30)


def _chart():
    planets = {
        "Sun": _p("Sun", 102.8, "Cancer", 4), "Moon": _p("Moon", 221.18, "Scorpio", 8),
        "Mars": _p("Mars", 231.9, "Scorpio", 8), "Mercury": _p("Mercury", 94.73, "Cancer", 4),
        "Jupiter": _p("Jupiter", 69.75, "Gemini", 3), "Venus": _p("Venus", 62.97, "Gemini", 3),
        "Saturn": _p("Saturn", 48.13, "Taurus", 2), "Rahu": _p("Rahu", 70.70, "Gemini", 3, True),
        "Ketu": _p("Ketu", 250.70, "Sagittarius", 9, True),
    }
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2001-07-29", time="23:45", latitude=18.5,
                                          longitude=73.8, timezone="Asia/Kolkata", place_name="Pune"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Scorpio", sun_sign="Cancer",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1], lord="", degree=0) for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Ketu", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Ketu", antar_dasha_start="", antar_dasha_end=""),
    )


def _outcome(topic):
    c = _chart()
    rules = run_rule_engine(c)
    st = compute_all_strengths(c)
    intent = IntentResult(intent=IntentCategory.TOPIC_READING, entities=IntentEntities(topics=[topic]))
    sig = get_significators(intent, c, rules, topic=topic)
    a = assess_topic(sig, st, rules, 0.6, chart=c)
    return derive_outcome(topic, sig, a, st, c, rules)


# --- Domain maps ---

def test_significations_maps():
    assert "engineering" in professions_for("Mars")
    assert "courageous" in traits_for("Mars")
    assert "career" in life_area(10)


# --- Career outcome ---

def test_career_outcome_has_fields_and_plain_language():
    out = _outcome("career")
    assert out.field_candidates                      # concrete fields named
    assert "engineering" in out.field_candidates     # Mars in own sign leads
    assert out.headline and out.trajectory_text
    assert out.strengths and out.challenges
    # Challenges must NOT describe an affliction with positive traits
    joined = " ".join(out.challenges).lower()
    assert "friction" in joined or "strain" in joined or "obstruct" in joined


def test_outcome_prompt_block_is_rewrite_material():
    out = _outcome("career")
    text = format_outcome_for_prompt(out)
    assert "Rewrite into" in text                    # instructs prose rewrite
    assert "career" in text


# --- Person (marriage) outcome ---

def test_marriage_outcome_describes_traits():
    out = _outcome("marriage")
    assert out.traits                                # spouse temperament present
    assert "spouse" in out.headline.lower()


# --- Jaimini karakas ---

def test_chara_karakas_by_degree():
    c = _chart()
    # Highest degree-in-sign among Sun-Saturn is Mars (~21.9), then Saturn (~18.13)
    assert atmakaraka(c) == "Mars"
    assert amatyakaraka(c) == "Saturn"
