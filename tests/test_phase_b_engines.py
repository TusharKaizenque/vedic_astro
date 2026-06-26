"""Tests for Phase B depth engines: conjunction, dispositor/argala, classification."""
from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.aspect_engine import aspect_quality
from services.rule_engine.conjunction_engine import (
    conjunction_influence, get_conjunctions, planets_conjunct,
)
from services.rule_engine.dispositor_engine import (
    analyze_house_chain, argala_on_house, bhavat_bhavam, dispositor_chain,
)
from utils.astro_constants import ZODIAC_SIGNS


def _planet(name, sign, house):
    idx = ZODIAC_SIGNS.index(sign)
    return PlanetPosition(
        planet=name, longitude=idx * 30 + 15, sign=sign, house=house,
        nakshatra="", nakshatra_pada=1, degree_in_sign=15.0,
    )


def _chart(planets, lagna="Aries"):
    start = ZODIAC_SIGNS.index(lagna)
    houses = {
        i: HouseData(house_number=i, sign=ZODIAC_SIGNS[(start + i - 1) % 12],
                     lord="", degree=0)
        for i in range(1, 13)
    }
    return NormalizedChart(
        user_id="t", birth_data=BirthData(
            date="2000-01-01", time="12:00", latitude=0.0, longitude=0.0,
            timezone="UTC", place_name="x"),
        lagna_sign=lagna, lagna_degree=0.0, moon_sign="Aries", sun_sign="Aries",
        nakshatra="", nakshatra_pada=1, planets=planets, houses=houses,
        dasha=DashaData(maha_dasha_lord="Sun", maha_dasha_start="", maha_dasha_end="",
                        antar_dasha_lord="Sun", antar_dasha_start="", antar_dasha_end=""),
    )


# --- Conjunction ---

def test_conjunction_detected():
    chart = _chart({
        "Jupiter": _planet("Jupiter", "Leo", 5),
        "Venus": _planet("Venus", "Leo", 5),
        "Mars": _planet("Mars", "Aries", 1),
    })
    conj = get_conjunctions(chart)
    assert 5 in conj
    assert set(conj[5].planets) == {"Jupiter", "Venus"}
    assert 1 not in conj  # Mars alone


def test_planets_conjunct_excludes_self():
    chart = _chart({
        "Sun": _planet("Sun", "Leo", 5),
        "Mercury": _planet("Mercury", "Leo", 5),
    })
    assert planets_conjunct(chart, "Sun") == ["Mercury"]


def test_conjunction_influence_benefic_vs_malefic():
    chart = _chart({
        "Saturn": _planet("Saturn", "Leo", 5),
        "Jupiter": _planet("Jupiter", "Leo", 5),       # benefic with Saturn
        "Mars": _planet("Mars", "Aries", 1),
        "Sun": _planet("Sun", "Aries", 1),             # malefic with Mars
    })
    assert conjunction_influence(chart, "Saturn") == "benefic"
    assert conjunction_influence(chart, "Mars") == "malefic"


def test_conjunction_influence_none_when_alone():
    chart = _chart({"Mars": _planet("Mars", "Aries", 1)})
    assert conjunction_influence(chart, "Mars") == "none"


# --- Aspect quality ---

def test_aspect_quality_functional_overrides_natural():
    # Saturn is a natural malefic but functional yogakaraka → benefic aspect
    assert aspect_quality("Saturn", "yogakaraka") == "benefic"
    assert aspect_quality("Jupiter", "malefic") == "malefic"


def test_aspect_quality_falls_back_to_natural():
    assert aspect_quality("Jupiter", "") == "benefic"
    assert aspect_quality("Mars", "") == "malefic"


# --- Dispositor / Argala / Bhavat-Bhavam ---

def test_dispositor_chain_terminates_in_own_sign():
    # Mars in Aries (own sign) → chain terminates at Mars
    chart = _chart({"Mars": _planet("Mars", "Aries", 1)})
    assert dispositor_chain(chart, "Mars") == ["Mars"]


def test_dispositor_chain_follows_lords():
    # Sun in Cancer → dispositor Moon; Moon in Taurus → dispositor Venus
    chart = _chart({
        "Sun": _planet("Sun", "Cancer", 4),
        "Moon": _planet("Moon", "Taurus", 2),
        "Venus": _planet("Venus", "Libra", 7),  # own sign, terminal
    })
    chain = dispositor_chain(chart, "Sun")
    assert chain[0] == "Sun"
    assert "Moon" in chain
    assert chain[-1] == "Venus"


def test_argala_supporting_and_obstructing():
    # Planet in 2nd from house 1 (house 2) gives argala; planet in 12th obstructs
    chart = _chart({
        "Jupiter": _planet("Jupiter", "Taurus", 2),    # 2nd from 1 → argala
        "Saturn": _planet("Saturn", "Pisces", 12),     # 12th from 1 → virodha
    })
    arg = argala_on_house(chart, 1)
    assert "Jupiter" in arg.supporting
    assert "Saturn" in arg.obstructing
    assert arg.net == "mixed"


def test_bhavat_bhavam():
    assert bhavat_bhavam(10) == 7   # 10th from 10th
    assert bhavat_bhavam(1) == 1
    assert bhavat_bhavam(7) == 1    # 7th from 7th


def test_topic_resolver_normalizes_freeform():
    from models.intent import IntentCategory, IntentEntities, IntentResult
    from services.significator_engine import _resolve_topic

    def mk(topics=None, retr=None, intent=IntentCategory.TOPIC_READING):
        return IntentResult(intent=intent, entities=IntentEntities(topics=topics or []),
                            retrieval_topics=retr or [])

    assert _resolve_topic(mk(["career"])) == "career"
    assert _resolve_topic(mk(["professional life"])) == "career"
    assert _resolve_topic(mk(["getting married"])) == "marriage"
    assert _resolve_topic(mk(["should I start a startup"])) == "business"
    assert _resolve_topic(mk([], ["my profession"])) == "career"
    assert _resolve_topic(mk(["wealth and money"])) == "wealth"
    # Unknown free-form falls back to intent default, never silently to house [1]
    assert _resolve_topic(mk(["xyzzy"])) == "career"  # TOPIC_READING default


def test_resolve_topics_multi():
    from models.intent import IntentCategory, IntentEntities, IntentResult
    from services.significator_engine import resolve_topics

    def mk(topics):
        return IntentResult(intent=IntentCategory.TOPIC_READING,
                            entities=IntentEntities(topics=topics))

    # Compound question → two distinct topics, order preserved
    assert resolve_topics(mk(["career", "marriage"])) == ["career", "marriage"]
    # Free-form compound
    assert resolve_topics(mk(["my profession", "getting married"])) == ["career", "marriage"]
    # De-duplicated
    assert resolve_topics(mk(["career", "job", "work"])) == ["career"]
    # Always at least one
    assert len(resolve_topics(mk([]))) >= 1


def test_assembler_matches_lord_in_house_by_lordship():
    from models.knowledge import ChunkType, KnowledgeChunk, RerankedChunk
    from services.reasoning_assembler import _find_chunk_for_factor
    from services.significator_engine import SignificatorFactor

    # A house-lord chunk with EMPTY planets_primary (keyed by lordship + placement)
    chunk = KnowledgeChunk(
        chunk_id="seventh_lord_in_5th", chunk_type=ChunkType.LORD_IN_HOUSE,
        content="7th lord in 5th house: love marriage.", planets_primary=[],
        houses_primary=[7, 5], topics=["marriage"],
    )
    rc = RerankedChunk(chunk=chunk, relevance_score=1.0, retrieval_rank=0)
    # Factor: Venus is the 7th lord, placed in the 5th house
    factor = SignificatorFactor(
        role="7th lord", planet="Venus", placed_house=5, sign="Leo",
        dignity="neutral sign", functional_nature="benefic", dig_bala=False,
        aspects_topic_house=False, kind="supporting", lords_house=7,
    )
    matched = _find_chunk_for_factor(factor, [rc])
    assert matched is not None and matched.chunk.chunk_id == "seventh_lord_in_5th"


def test_assembler_matches_planet_in_sign():
    from models.knowledge import ChunkType, KnowledgeChunk, RerankedChunk
    from services.reasoning_assembler import _find_chunk_for_factor
    from services.significator_engine import SignificatorFactor

    # planet_in_sign chunk keyed by planet + sign (no house)
    chunk = KnowledgeChunk(
        chunk_id="mars_in_scorpio", chunk_type=ChunkType.PLANET_IN_SIGN,
        content="Mars in Scorpio: intense, own sign.", planets_primary=["Mars"],
        houses_primary=[], signs=["Scorpio"], topics=["placement"],
    )
    rc = RerankedChunk(chunk=chunk, relevance_score=1.0, retrieval_rank=0)
    # Factor: Mars in Scorpio, but in a house with no planet_in_house chunk available
    factor = SignificatorFactor(
        role="karaka", planet="Mars", placed_house=8, sign="Scorpio",
        dignity="own sign", functional_nature="benefic", dig_bala=False,
        aspects_topic_house=False, kind="supporting",
    )
    matched = _find_chunk_for_factor(factor, [rc])
    assert matched is not None and matched.chunk.chunk_id == "mars_in_scorpio"


def test_analyze_house_chain_full():
    chart = _chart({
        "Saturn": _planet("Saturn", "Taurus", 2),
        "Venus": _planet("Venus", "Gemini", 3),
        "Mercury": _planet("Mercury", "Gemini", 3),
    })
    result = analyze_house_chain(chart, 10)   # Capricorn for Aries lagna → Saturn
    assert result.lord == "Saturn"
    assert result.lord_chain[0] == "Saturn"
    assert result.bhavat_bhavam_house == 7
