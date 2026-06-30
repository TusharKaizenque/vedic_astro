"""Tests for the review-driven fixes: dasha projection, topic dedup, date formatting, karakas."""
from datetime import datetime

from models.intent import IntentCategory, IntentEntities, IntentResult
from services.dasha_projection import project_dasha
from services.significator_engine import resolve_topics
from utils.astro_constants import TOPIC_PLANET_MAP
from utils.formatting import format_date


# --- #1 Post-dasha projection ---

def test_projection_advances_antardasha_for_future():
    # Ketu maha 2026-05-21 → 2033. Mid-2027 is still Ketu maha but Venus antar.
    p = project_dasha("Ketu", "2026-05-21T11:26:39", datetime(2027, 7, 1), current_antar="Ketu")
    assert p.maha_lord == "Ketu"
    assert p.antar_lord == "Venus"
    assert p.is_future is True


def test_projection_current_period_not_flagged_future():
    p = project_dasha("Ketu", "2026-05-21T11:26:39", datetime(2026, 7, 1), current_antar="Ketu")
    assert p.antar_lord == "Ketu"
    assert p.is_future is False


def test_projection_advances_mahadasha_when_past_end():
    # Far future beyond the 7-year Ketu maha → next maha is Venus.
    p = project_dasha("Ketu", "2026-05-21T11:26:39", datetime(2034, 1, 1))
    assert p.maha_lord == "Venus"


def test_projection_handles_bad_input():
    assert project_dasha("Ketu", "not-a-date", datetime(2027, 1, 1)) is None


# --- #4 Date formatting ---

def test_format_date_iso_to_readable():
    assert format_date("2026-10-17T14:53:38+05:30") == "October 17, 2026"


def test_format_date_passthrough_on_garbage():
    assert format_date("sometime") == "sometime"
    assert format_date("") == ""


# --- #2/#6 Topic family dedup ---

def test_startup_resolves_to_single_professional_topic():
    intent = IntentResult(intent=IntentCategory.TIMING_QUERY,
                          entities=IntentEntities(topics=["career", "startup"]))
    topics = resolve_topics(intent)
    # career and business are the same family — only one survives
    assert topics == ["career"]
    assert "business" not in topics


def test_genuinely_distinct_topics_both_kept():
    intent = IntentResult(intent=IntentCategory.TOPIC_READING,
                          entities=IntentEntities(topics=["career", "marriage"]))
    assert resolve_topics(intent) == ["career", "marriage"]


def test_wealth_and_finance_dedup():
    intent = IntentResult(intent=IntentCategory.TOPIC_READING,
                          entities=IntentEntities(topics=["wealth", "finance"]))
    assert resolve_topics(intent) == ["wealth"]


# --- #7 Karaka corrections ---

def test_career_karakas_correct():
    # Saturn (primary) + Sun (secondary); Mars is NOT a career karaka.
    assert "Saturn" in TOPIC_PLANET_MAP["career"]
    assert "Sun" in TOPIC_PLANET_MAP["career"]
    assert "Mars" not in TOPIC_PLANET_MAP["career"]


def test_business_has_karakas():
    assert TOPIC_PLANET_MAP.get("business")
    assert "Mercury" in TOPIC_PLANET_MAP["business"]   # commerce karaka belongs here


# --- #8 Descriptive vs timing query detection ---

def test_descriptive_queries_detected():
    from services.intent_classifier import is_descriptive_query
    assert is_descriptive_query("how will my wife be?")        # person subject
    assert is_descriptive_query("what is my spouse like?")     # person subject
    assert is_descriptive_query("describe my career")          # explicit 'describe'
    # NOTE: "how will my married life be?" is now treated as a marriage VERDICT question
    # (no person subject, no explicit 'describe') — the prior broad rule wrongly suppressed
    # the verdict for every "how will my <topic> be" question. See test_intent_routing.
    assert not is_descriptive_query("how will my married life be?")


def test_timing_queries_not_descriptive():
    from services.intent_classifier import is_descriptive_query
    assert not is_descriptive_query("should I start a startup in 2027?")
    assert not is_descriptive_query("when will I get married?")
    assert not is_descriptive_query("what does my chart say about career?")
