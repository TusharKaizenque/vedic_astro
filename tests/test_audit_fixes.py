"""Regression tests for the astrological-correctness audit fixes."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.dosha_detector import detect_mangal_dosha, detect_pitra_dosha
from services.rule_engine.strength_calculator import calculate_all_strengths
from services.rule_engine.varga_engine import varga_sign
from services.rule_engine.yoga_detector import detect_dhana_yoga
from utils.astro_constants import NATURAL_ENEMIES, combustion_orb
from utils.nakshatras import nakshatra_of


def _p(name, lon, sign, house, retro=False):
    return PlanetPosition(planet=name, longitude=lon, sign=sign, house=house, nakshatra="",
                          nakshatra_pada=1, is_retrograde=retro, degree_in_sign=lon % 30)


def _chart(planets, lagna="Aries"):
    from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS
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


# --- D9 navamsa boundary bug ---

def test_d9_navamsa_at_sign_boundary():
    # Leo 0°00' (longitude exactly 120.0) → navamsa Aries (fixed sign starts from the 9th).
    assert varga_sign(120.0, "D9") == "Aries"
    # Cancer 0° (90.0) → navamsa Cancer (water/movable-ish: Cancer is movable → same sign).
    assert varga_sign(90.0, "D9") == "Cancer"


def test_d9_movable_fixed_dual_starts():
    assert varga_sign(1.0, "D9") == "Aries"        # Aries (movable) → same
    assert varga_sign(31.0, "D9") == "Capricorn"   # Taurus (fixed) → 9th
    assert varga_sign(61.0, "D9") == "Libra"       # Gemini (dual) → 5th


# --- Combustion per-planet orbs ---

def test_combustion_orbs_are_per_planet():
    assert combustion_orb("Mars") == 17.0
    assert combustion_orb("Mercury") == 14.0
    assert combustion_orb("Mercury", is_retrograde=True) == 12.0
    assert combustion_orb("Moon") == 12.0


def test_mars_combust_within_17_degrees():
    # Mars 15° from Sun → combust under the 17° orb (the old flat 6° wrongly missed this).
    chart = _chart({"Sun": _p("Sun", 10, "Aries", 1), "Mars": _p("Mars", 25, "Aries", 1)})
    assert "combust" in calculate_all_strengths(chart)["Mars"]


def test_mars_not_combust_beyond_orb():
    chart = _chart({"Sun": _p("Sun", 10, "Aries", 1), "Mars": _p("Mars", 40, "Taurus", 2)})
    assert "combust" not in calculate_all_strengths(chart)["Mars"]


# --- Moon natural enemies corrected ---

def test_moon_has_no_natural_enemies():
    assert NATURAL_ENEMIES["Moon"] == []


# --- Mangal Dosha multi-reference + cancellation (covered in test_rule_engine too) ---

def test_mangal_from_venus_reference():
    # Mars 3rd from lagna (clear), but 4th from Venus → Manglik via Venus.
    chart = _chart({
        "Mars": _p("Mars", 2 * 30 + 5, "Gemini", 3),
        "Moon": _p("Moon", 5, "Aries", 1),
        "Venus": _p("Venus", 11 * 30 + 5, "Pisces", 12),   # Mars (h3) is 4th from Venus (h12)
    })
    assert detect_mangal_dosha(chart)


# --- Pitra Dosha node-driven ---

def test_pitra_node_in_ninth():
    chart = _chart({"Ketu": _p("Ketu", 8 * 30 + 5, "Sagittarius", 9),
                    "Sun": _p("Sun", 5, "Aries", 1)})
    assert detect_pitra_dosha(chart)


def test_pitra_absent_without_node_affliction():
    chart = _chart({"Rahu": _p("Rahu", 4 * 30, "Leo", 5), "Ketu": _p("Ketu", 10 * 30, "Aquarius", 11),
                    "Sun": _p("Sun", 5, "Aries", 1)})
    assert not detect_pitra_dosha(chart)


# --- Dhana Yoga broadened (opposition / exchange) ---

def test_dhana_yoga_by_opposition():
    # Aries lagna: 2nd lord Venus (Taurus), 11th lord Saturn (Aquarius). Place them opposite.
    chart = _chart({"Venus": _p("Venus", 5, "Aries", 1), "Saturn": _p("Saturn", 6 * 30 + 5, "Libra", 7)})
    assert detect_dhana_yoga(chart)


def test_timing_question_leads_with_window():
    """A 'when …' question injects the ANSWER-FIRST timing directive; a quality question doesn't."""
    from services import prompt_builder
    from services.intent_classifier import is_timing_question
    from models.intent import IntentResult, IntentCategory

    assert is_timing_question("when will I get married")
    assert is_timing_question("what is a good time for marriage")
    assert not is_timing_question("how is my marriage")
    assert not is_timing_question("what is my spouse like")

    intent = IntentResult(intent=IntentCategory.TIMING_QUERY, requires_chart=True)
    timing_block = "[MARRIAGE TIMING]\n- Mar 2027 – Sep 2027 (Venus MD / Jupiter AD) [STRONG]: ..."

    # WHEN question + a timing block present → the ANSWER-FIRST directive is in the prompt.
    msgs = prompt_builder.build(
        "when will I get married", intent, None, None, None, [], None, [], [],
        marriage_timing=timing_block, timing_lead=True,
    )
    ctx = "\n".join(m["content"] for m in msgs)
    assert "ANSWER THE 'WHEN' FIRST" in ctx
    assert "VERY FIRST sentence" in ctx

    # Quality question (timing_lead False) → no answer-first directive even if a block exists.
    msgs2 = prompt_builder.build(
        "how is my marriage", intent, None, None, None, [], None, [], [],
        marriage_timing=timing_block, timing_lead=False,
    )
    assert "ANSWER THE 'WHEN' FIRST" not in "\n".join(m["content"] for m in msgs2)
