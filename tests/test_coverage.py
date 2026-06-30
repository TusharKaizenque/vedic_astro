"""Tests for the coverage guarantee (every very-high signature must surface in the prose)."""
from services.chart_signatures import ChartSignature
from services.coverage import is_covered, missing_signatures


def _sig(label):
    return ChartSignature(key=label, label=label, polarity="boon",
                          confidence="very high", score=5.0, evidence=["a", "b"])


WEALTH = _sig("exceptional wealth & material abundance")
EMINENCE = _sig("rise to authority & public eminence")
MARRIAGE = _sig("friction or delay in marriage & partnership")
DELAY = _sig("success that arrives after delay & perseverance")
HEALTH = _sig("a constitution that needs steady care")


def test_covered_when_theme_keyword_present():
    assert is_covered("You have strong potential for wealth and material comfort.", WEALTH)


def test_not_covered_when_theme_absent():
    assert not is_covered("You are drawn to learning and quiet reflection.", WEALTH)


def test_eminence_matched_by_paraphrase():
    assert is_covered("You will rise to positions of leadership and public recognition.", EMINENCE)


def test_marriage_not_falsely_matched_by_delay_word():
    # The marriage label contains 'delay', but a text about delayed success (no relationship
    # words) must NOT count the marriage signature as covered.
    text = "Success comes gradually, after patient effort and some delay."
    assert not is_covered(text, MARRIAGE)


def test_delay_signature_matched_by_its_own_keywords():
    text = "Your success comes gradually, rewarding patience and perseverance."
    assert is_covered(text, DELAY)


def test_health_matched_by_constitution_fragment():
    assert is_covered("Your physical constitution needs steady care and rest.", HEALTH)


def test_missing_returns_only_uncovered():
    text = "You have great wealth and material abundance ahead."
    missing = missing_signatures(text, [WEALTH, EMINENCE, MARRIAGE])
    labels = [s.label for s in missing]
    assert WEALTH.label not in labels
    assert EMINENCE.label in labels and MARRIAGE.label in labels


def test_nothing_missing_when_all_covered():
    text = "Wealth flows to you, you rise to authority, and marriage brings partnership."
    assert missing_signatures(text, [WEALTH, EMINENCE, MARRIAGE]) == []
