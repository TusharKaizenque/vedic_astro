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
    assert a.direction == "favourable"
    assert a.confidence == "moderate"
    assert a.sav_primary_house == 30          # 10th house Sarvashtakavarga
    assert a.sav_band == "strong"
    assert [w.planet for w in a.dominant_supporting] == ["Mars", "Sun", "Jupiter"]
    assert [w.planet for w in a.dominant_afflicting] == ["Venus", "Mercury", "Saturn"]
    assert "Mars" in a.key_tension and "Venus" in a.key_tension


def test_golden_career_margin_stable(golden_chart):
    a = _assess(golden_chart, "career")
    assert a.margin == pytest.approx(0.237, abs=0.001)


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
    a = _assess(golden_chart, "marriage")
    assert a.topic == "marriage"
    assert a.sav_primary_house == 19          # 7th house SAV (Libra) — weak
    assert a.direction in ("favourable", "mixed", "challenged")
    # Venus is the marriage karaka and should appear among the factors
    planets = {w.planet for w in a.dominant_supporting + a.dominant_afflicting}
    assert "Venus" in planets


def test_golden_strengths_stable(golden_chart):
    """Shadbala-lite ranking is stable: Venus/Jupiter strongest, Saturn weakest here."""
    strengths = compute_all_strengths(golden_chart)
    assert strengths["Venus"].band == "strong"
    assert strengths["Jupiter"].band == "strong"
    assert strengths["Saturn"].band == "weak"
    # Moon's debilitation is cancelled (neecha bhanga) — it is not the weakest
    assert strengths["Saturn"].total_virupas < strengths["Venus"].total_virupas
