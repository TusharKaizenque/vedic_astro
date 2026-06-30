"""
Golden-chart regression tests (Phase E2).

Locks in the full deterministic reasoning output for a known chart so any future change
that silently alters a verdict is caught. Runs the whole non-LLM pipeline — rule engine →
strengths → significators → assessment — with no DB, no retrieval, no network.

Chart: Aries lagna, 2001-07-29 23:45 Pune (the chart used throughout development).
"""
import pytest

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from models.intent import IntentCategory, IntentEntities, IntentResult
from services.assessment_engine import assess_topic
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from services.significator_engine import get_significators
from utils.astro_constants import ZODIAC_SIGNS


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house,
                          nakshatra="", nakshatra_pada=1, is_retrograde=retro,
                          degree_in_sign=lon % 30)


@pytest.fixture
def golden_chart():
    planets = {
        "Sun": _p("Sun", 102.8, "Cancer", 4),
        "Moon": _p("Moon", 221.18, "Scorpio", 8),
        "Mars": _p("Mars", 231.9, "Scorpio", 8),
        "Mercury": _p("Mercury", 94.73, "Cancer", 4),
        "Jupiter": _p("Jupiter", 69.75, "Gemini", 3),
        "Venus": _p("Venus", 62.97, "Gemini", 3),
        "Saturn": _p("Saturn", 48.13, "Taurus", 2),
        "Rahu": _p("Rahu", 70.70, "Gemini", 3, True),
        "Ketu": _p("Ketu", 250.70, "Sagittarius", 9, True),
    }
    houses = {i: HouseData(house_number=i, sign=ZODIAC_SIGNS[i - 1], lord="", degree=0)
              for i in range(1, 13)}
    return NormalizedChart(
        user_id="golden",
        birth_data=BirthData(date="2001-07-29", time="23:45", latitude=18.52,
                             longitude=73.85, timezone="Asia/Kolkata", place_name="Pune"),
        lagna_sign="Aries", lagna_degree=0.0, moon_sign="Scorpio", sun_sign="Cancer",
        nakshatra="", nakshatra_pada=1, planets=planets, houses=houses,
        dasha=DashaData(maha_dasha_lord="Ketu", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Ketu", antar_dasha_start="", antar_dasha_end=""),
    )


def _assess(chart, topic):
    rules = run_rule_engine(chart)
    strengths = compute_all_strengths(chart)
    intent = IntentResult(intent=IntentCategory.TOPIC_READING,
                          entities=IntentEntities(topics=[topic]))
    sig = get_significators(intent, chart, rules, topic=topic)
    return assess_topic(sig, strengths, rules, grounded_ratio=0.6, chart=chart)


def test_golden_career_verdict(golden_chart):
    a = _assess(golden_chart, "career")
    # Saturn (10th & 11th lord) is now ONE neutral primary factor (not double-counted as a
    # spurious afflicter), and the yoga boost is capped — so career lands MIXED with LOW
    # confidence (the main significator is neutral), just under the favourable threshold.
    assert a.direction == "mixed"
    assert a.confidence == "low"
    assert a.sav_primary_house == 30          # 10th house Sarvashtakavarga
    assert a.sav_band == "strong"
    assert [w.planet for w in a.dominant_supporting] == ["Sun", "Mars", "Jupiter"]
    assert [w.planet for w in a.dominant_afflicting] == ["Venus", "Mercury"]  # Saturn no longer here
    assert "Venus" in a.key_tension


def test_golden_career_margin_stable(golden_chart):
    a = _assess(golden_chart, "career")
    assert a.margin == pytest.approx(0.197, abs=0.001)


def test_golden_house_lord_not_double_counted(golden_chart):
    """Saturn rules the 10th AND 11th (both career houses) — it must appear as exactly ONE
    merged factor, never two, so its vote isn't double-weighted."""
    rules = run_rule_engine(golden_chart)
    intent = IntentResult(intent=IntentCategory.TOPIC_READING,
                          entities=IntentEntities(topics=["career"]))
    sig = get_significators(intent, golden_chart, rules, topic="career")
    saturn_factors = [f for f in sig.factors if f.planet == "Saturn"]
    assert len(saturn_factors) == 1
    assert "10th & 11th lord" in saturn_factors[0].role


def test_golden_is_deterministic(golden_chart):
    """Same chart + topic → byte-identical verdict every run."""
    a1 = _assess(golden_chart, "career")
    a2 = _assess(golden_chart, "career")
    assert a1.direction == a2.direction
    assert a1.margin == a2.margin
    assert a1.summary_line == a2.summary_line
    assert a1.sav_primary_house == a2.sav_primary_house


def test_golden_marriage_verdict(golden_chart):
    """Marriage uses the 7th house — distinct SAV from career's 10th."""
    rules = run_rule_engine(golden_chart)
    intent = IntentResult(intent=IntentCategory.TOPIC_READING,
                          entities=IntentEntities(topics=["marriage"]))
    sig = get_significators(intent, golden_chart, rules, topic="marriage")
    strengths = compute_all_strengths(golden_chart)
    a = assess_topic(sig, strengths, rules, grounded_ratio=0.6, chart=golden_chart)
    assert a.topic == "marriage"
    assert a.sav_primary_house == 19          # 7th house SAV (Libra) — weak
    assert a.direction in ("favourable", "mixed", "challenged")
    # Venus is the marriage karaka + 7th lord — it must be present as a (single, merged) factor.
    venus = [f for f in sig.factors if f.planet == "Venus"]
    assert len(venus) == 1 and "karaka" in venus[0].role and "7th" in venus[0].role


def test_golden_strengths_stable(golden_chart):
    """Full Shadbala ranking (ratio to required): Mars (own sign) & Moon strong; Sun weak."""
    strengths = compute_all_strengths(golden_chart)
    assert strengths["Mars"].band == "strong"      # own sign Scorpio
    assert strengths["Moon"].band == "strong"
    assert strengths["Sun"].band == "weak"          # night birth, low dig/kala
    assert strengths["Venus"].band == "moderate"
    # Mars is the strongest by ratio-to-required (relative), even if not by raw virupas.
    assert strengths["Mars"].relative == max(s.relative for s in strengths.values())
