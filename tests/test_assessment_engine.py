"""Tests for the deterministic assessment/verdict engine (Phase A2)."""
from services.assessment_engine import (
    TopicAssessment, _role_weight, assess_topic,
)
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.strength_engine import PlanetStrength
from services.significator_engine import (
    DashaActivation, SignificatorFactor, SignificatorResult,
)


def _factor(planet, role, kind):
    return SignificatorFactor(
        role=role, planet=planet, placed_house=10, sign="Capricorn",
        dignity="own sign", functional_nature="benefic", dig_bala=False,
        aspects_topic_house=False, kind=kind,
    )


def _strength(planet, relative, band):
    return PlanetStrength(planet=planet, total_virupas=relative * 300,
                          relative=relative, band=band)


def _sig(factors, yogas=None, doshas=None, maha="Sun", maha_sig=False):
    return SignificatorResult(
        topic="career", primary_houses=[10], karaka_planets=["Sun"],
        relevant_varga="D10", factors=factors,
        dasha_activation=DashaActivation(
            maha_lord=maha, antar_lord=maha, maha_end="2030", antar_end="2027",
            maha_is_significator=maha_sig, antar_is_significator=maha_sig,
            maha_functional_nature="benefic", antar_functional_nature="benefic",
            activation_strength="strong" if maha_sig else "weak"),
        relevant_yogas=yogas or [], relevant_doshas=doshas or [],
        planets_in_topic_houses={}, aspects_on_topic_houses={},
    )


def test_role_weight_hierarchy():
    assert _role_weight("10th lord + karaka") == 1.0
    assert _role_weight("karaka") == 0.8
    assert _role_weight("10th lord") == 1.0
    assert _role_weight("occupies 10th house") == 0.7
    assert _role_weight("aspects 11th house") == 0.5


def test_strong_support_yields_favourable():
    factors = [
        _factor("Jupiter", "10th lord", "supporting"),
        _factor("Sun", "karaka", "supporting"),
    ]
    strengths = {"Jupiter": _strength("Jupiter", 0.8, "strong"),
                 "Sun": _strength("Sun", 0.7, "strong")}
    a = assess_topic(_sig(factors), strengths, RuleEngineResult())
    assert a.direction == "favourable"
    assert a.support_score > a.afflict_score


def test_strong_affliction_yields_challenged():
    factors = [
        _factor("Saturn", "10th lord", "afflicting"),
        _factor("Mars", "occupies 10th house", "afflicting"),
    ]
    strengths = {"Saturn": _strength("Saturn", 0.8, "strong"),
                 "Mars": _strength("Mars", 0.7, "strong")}
    a = assess_topic(_sig(factors), strengths, RuleEngineResult())
    assert a.direction == "challenged"
    assert a.afflict_score > a.support_score


def test_balanced_yields_mixed():
    factors = [
        _factor("Jupiter", "10th lord", "supporting"),
        _factor("Saturn", "6th lord", "afflicting"),
    ]
    strengths = {"Jupiter": _strength("Jupiter", 0.6, "strong"),
                 "Saturn": _strength("Saturn", 0.6, "strong")}
    a = assess_topic(_sig(factors), strengths, RuleEngineResult())
    assert a.direction == "mixed"


def test_stronger_planet_wins_key_tension():
    factors = [
        _factor("Jupiter", "10th lord", "supporting"),
        _factor("Saturn", "6th lord", "afflicting"),
    ]
    strengths = {"Jupiter": _strength("Jupiter", 0.9, "strong"),
                 "Saturn": _strength("Saturn", 0.3, "weak")}
    a = assess_topic(_sig(factors), strengths, RuleEngineResult())
    assert "support is stronger" in a.key_tension


def test_yogas_boost_direction():
    factors = [_factor("Jupiter", "10th lord", "supporting"),
               _factor("Saturn", "6th lord", "afflicting")]
    strengths = {"Jupiter": _strength("Jupiter", 0.5, "moderate"),
                 "Saturn": _strength("Saturn", 0.5, "moderate")}
    plain = assess_topic(_sig(factors), strengths, RuleEngineResult())
    boosted = assess_topic(
        _sig(factors, yogas=["Raja Yoga", "Dharma Karmadhipati"]),
        strengths, RuleEngineResult())
    assert boosted.margin > plain.margin


def test_dasha_significator_activates_topic():
    factors = [_factor("Sun", "karaka", "supporting")]
    strengths = {"Sun": _strength("Sun", 0.7, "strong")}
    a = assess_topic(_sig(factors, maha="Sun", maha_sig=True), strengths, RuleEngineResult())
    assert a.timing_favours_now == "favourable"
    assert "Sun" in a.dasha_timing


def test_assessment_is_deterministic():
    factors = [_factor("Jupiter", "10th lord", "supporting"),
               _factor("Saturn", "6th lord", "afflicting")]
    strengths = {"Jupiter": _strength("Jupiter", 0.7, "strong"),
                 "Saturn": _strength("Saturn", 0.5, "moderate")}
    a1 = assess_topic(_sig(factors), strengths, RuleEngineResult())
    a2 = assess_topic(_sig(factors), strengths, RuleEngineResult())
    assert a1.direction == a2.direction
    assert a1.margin == a2.margin
    assert a1.summary_line == a2.summary_line
