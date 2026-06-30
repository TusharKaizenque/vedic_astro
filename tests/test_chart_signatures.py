"""Tests for the Chart Signature Engine — multi-factor, anti-generic life signatures."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.chart_signatures import (
    ChartSignature, _tension_note, detect_signatures, format_signatures_for_prompt,
    select_signatures,
)
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=retro, degree_in_sign=lon % 30)


def _chart(planets, lagna="Aries"):
    start = ZODIAC_SIGNS.index(lagna)
    return NormalizedChart(
        user_id="t", birth_data=BirthData(date="2000-01-01", time="12:00", latitude=0.0,
                                          longitude=0.0, timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=0.0, moon_sign="Aries", sun_sign="Aries",
        nakshatra="", nakshatra_pada=1, planets=planets,
        houses={i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(start + i - 1) % 12],
                             lord=SIGN_RULERS[ZODIAC_SIGNS[(start + i - 1) % 12]], degree=0)
                for i in range(1, 13)},
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


def _signatures(planets, lagna="Aries"):
    chart = _chart(planets, lagna)
    rules = run_rule_engine(chart)
    strengths = compute_all_strengths(chart)
    return detect_signatures(chart, rules, strengths)


# --- the core anti-generic invariant: a signature needs ≥2 corroborating factors ---

def test_every_emitted_signature_has_at_least_two_factors():
    sigs = _signatures({
        "Mars": _p("Mars", 7 * 30 + 5, "Scorpio", 8),   # Aries lagna lord in 8th dusthana
        "Moon": _p("Moon", 7 * 30 + 9, "Scorpio", 8),
        "Saturn": _p("Saturn", 7 * 30 + 18, "Scorpio", 8),
        "Ketu": _p("Ketu", 11 * 30, "Pisces", 12),
    })
    assert sigs, "expected at least one signature"
    for s in sigs:
        assert len(s.evidence) >= 2, f"{s.label} fired on a single factor: {s.evidence}"


def test_struggle_signature_fires_for_afflicted_lagna_and_dusthana_stack():
    sigs = _signatures({
        "Mars": _p("Mars", 7 * 30 + 5, "Scorpio", 8),   # lagna lord in dusthana
        "Moon": _p("Moon", 7 * 30 + 9, "Scorpio", 8),   # Moon in dusthana
        "Saturn": _p("Saturn", 5 * 30 + 2, "Virgo", 6),  # third dusthana occupant
    })
    labels = [s.label for s in sigs]
    assert any("struggle" in l for l in labels)


def test_spiritual_signature_fires_for_ketu_and_moksha_emphasis():
    sigs = _signatures({
        "Ketu": _p("Ketu", 11 * 30 + 5, "Pisces", 12),   # Ketu in 12th
        "Saturn": _p("Saturn", 11 * 30 + 2, "Pisces", 12),  # Saturn in 12th
        "Jupiter": _p("Jupiter", 7 * 30 + 1, "Scorpio", 8),  # planet in 8th → 2 in moksha houses
    })
    assert any("spiritual" in s.label for s in sigs)


def test_signatures_sorted_by_score_descending():
    sigs = _signatures({
        "Mars": _p("Mars", 7 * 30 + 5, "Scorpio", 8),
        "Moon": _p("Moon", 7 * 30 + 9, "Scorpio", 8),
        "Saturn": _p("Saturn", 5 * 30 + 2, "Virgo", 6),
        "Ketu": _p("Ketu", 11 * 30, "Pisces", 12),
    })
    scores = [s.score for s in sigs]
    assert scores == sorted(scores, reverse=True)


# --- selection + tension (pure, no chart needed) ---

def _sig(label, polarity, confidence, score):
    return ChartSignature(key=label, label=label, polarity=polarity,
                          confidence=confidence, score=score, evidence=["a", "b"])


def test_select_floors_at_three_when_few_strong():
    sigs = [_sig("x", "boon", "moderate", 2.0), _sig("y", "challenge", "moderate", 1.8),
            _sig("z", "neutral", "moderate", 1.5), _sig("w", "boon", "moderate", 1.2)]
    chosen = select_signatures(sigs)
    assert len(chosen) == 3  # floor of 3 even though none are high-confidence


def test_select_keeps_all_strong_up_to_limit():
    sigs = [_sig(f"s{i}", "boon", "very high", 6 - i * 0.1) for i in range(8)]
    assert len(select_signatures(sigs, limit=6)) == 6


def test_tension_note_present_when_boon_and_challenge_coexist():
    chosen = [_sig("eminence", "boon", "very high", 6.0),
              _sig("struggle", "challenge", "very high", 5.5)]
    note = _tension_note(chosen)
    assert "not a contradiction" in note
    assert "eminence" in note and "struggle" in note


def test_tension_note_absent_without_both_polarities():
    chosen = [_sig("eminence", "boon", "very high", 6.0),
              _sig("wealth", "boon", "high", 4.0)]
    assert _tension_note(chosen) == ""


def test_format_block_leads_with_signatures_header():
    block = format_signatures_for_prompt([_sig("exceptional wealth", "boon", "very high", 5.0)])
    assert "STANDOUT CHART SIGNATURES" in block
    assert "exceptional wealth" in block
