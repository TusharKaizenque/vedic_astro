"""Routing heuristics: life-overview vs topic, descriptive (person traits), timing backstop."""
import pytest

from models.intent import IntentCategory, IntentEntities, IntentResult
from services.intent_classifier import (
    _augment_timing, _augment_topics, is_descriptive_query, is_life_overview_query,
)


@pytest.mark.parametrize("q,expected", [
    ("what is my overall career outlook", False),   # 'overall' but topic named → not overview
    ("will I marry in the future", False),          # marriage topic present
    ("tell me about my life", True),
    ("overall reading please", True),
    ("what will I do in my life", True),
    ("who am i", True),
    ("how is my health", False),
    ("read my chart", True),
])
def test_life_overview_routing(q, expected):
    assert is_life_overview_query(q) is expected


@pytest.mark.parametrize("q,expected", [
    ("will my spouse be educated", True),
    ("what will my wife be like", True),
    ("when will I meet my wife", False),            # timing, not descriptive
    ("is my husband going to be wealthy", True),
    ("how is my career", False),                    # verdict, no person subject
    ("personality of my future spouse", True),
    ("describe my partner", True),
    ("what is my career like", False),
])
def test_descriptive_routing(q, expected):
    assert is_descriptive_query(q) is expected


def _fresh():
    return IntentResult(intent=IntentCategory.TOPIC_READING, entities=IntentEntities())


@pytest.mark.parametrize("q,transits,has_year", [
    ("when will I get married", True, False),
    ("what does 2027 hold for my career", True, True),
    ("tell me about my career", False, False),
    ("what happens in March next year", True, False),
    ("how is my career right now", False, False),
])
def test_timing_backstop(q, transits, has_year):
    r = _augment_timing(_fresh(), q)
    assert r.requires_transits is transits
    if has_year:
        assert any(tok.isdigit() for tok in r.entities.time_references)


@pytest.mark.parametrize("q,topic", [
    ("What will my spouse be like", "marriage"),     # classifier often misses this → defaulted to career
    ("describe my wife", "marriage"),
    ("how is my career", "career"),
    ("will I be wealthy", "wealth"),
    ("tell me about my children", "children"),
])
def test_topic_backstop_adds_missing_topic(q, topic):
    r = _augment_topics(_fresh(), q)
    assert topic in r.entities.topics


def test_topic_backstop_does_not_duplicate():
    r = _fresh()
    r.entities.topics = ["marriage"]
    out = _augment_topics(r, "about my spouse")
    assert out.entities.topics.count("marriage") == 1


def test_timing_backstop_preserves_existing_refs():
    r = _fresh()
    r.entities.time_references = ["2030"]
    out = _augment_timing(r, "what about 2027 too")
    assert "2030" in out.entities.time_references and "2027" in out.entities.time_references
