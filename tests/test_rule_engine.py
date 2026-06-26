"""
Rule engine test suite — fixture-based, no real DB or API needed.

Each yoga/dosha test has both a PRESENT and ABSENT case.
Skipped tests document what needs to be built (aspect engine, all 12 lagnas).
"""
import pytest

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from services.rule_engine.dosha_detector import (
    detect_grahan_dosha, detect_kaal_sarp_dosha, detect_mangal_dosha,
    detect_pitra_dosha, detect_shrapit_dosha,
)
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_calculator import calculate_all_strengths, get_planet_strength
from services.rule_engine.yoga_detector import (
    detect_adhi_yoga, detect_budhaditya, detect_chandra_mangala,
    detect_gajakesari, detect_kaal_sarp, detect_panch_mahapurusha,
)
from utils.astro_constants import (
    FUNCTIONAL_NATURE_BY_LAGNA, SIGN_RULERS, ZODIAC_SIGNS,
    house_lords_for_lagna, is_yogakaraka,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _planet(name: str, longitude: float, sign: str, house: int, degree_in_sign: float | None = None) -> PlanetPosition:
    return PlanetPosition(
        planet=name, longitude=longitude, sign=sign, house=house,
        nakshatra="Ashwini", nakshatra_pada=1,
        degree_in_sign=degree_in_sign if degree_in_sign is not None else longitude % 30,
    )


def _planet_retro(name: str, longitude: float, sign: str, house: int) -> PlanetPosition:
    return PlanetPosition(
        planet=name, longitude=longitude, sign=sign, house=house,
        nakshatra="Ashwini", nakshatra_pada=1,
        degree_in_sign=longitude % 30, is_retrograde=True,
    )


def _make_chart(planets: dict | None = None, lagna: str = "Aries") -> NormalizedChart:
    """Build a minimal but valid NormalizedChart for testing.

    House signs are computed from lagna: house 1 = lagna sign, house 2 = next sign, etc.
    """
    start = ZODIAC_SIGNS.index(lagna)
    houses = {
        i + 1: HouseData(
            house_number=i + 1,
            sign=ZODIAC_SIGNS[(start + i) % 12],
            lord=SIGN_RULERS[ZODIAC_SIGNS[(start + i) % 12]],
            degree=0.0,
        )
        for i in range(12)
    }
    default_planets: dict[str, PlanetPosition] = {
        "Sun":     _planet("Sun",     10,  "Aries",       1),
        "Moon":    _planet("Moon",    40,  "Taurus",      2),
        "Mars":    _planet("Mars",    200, "Libra",       7),
        "Mercury": _planet("Mercury", 40,  "Taurus",      2),
        "Jupiter": _planet("Jupiter", 220, "Scorpio",     8),
        "Venus":   _planet("Venus",   100, "Cancer",      4),
        "Saturn":  _planet("Saturn",  250, "Sagittarius", 9),
        "Rahu":    _planet("Rahu",    130, "Leo",         5),
        "Ketu":    _planet("Ketu",    310, "Aquarius",    11),
    }
    if planets:
        default_planets.update(planets)
    return NormalizedChart(
        user_id="test",
        birth_data=BirthData(
            date="1990-01-01", time="06:00", latitude=13.0, longitude=77.6,
            timezone="Asia/Kolkata", place_name="Bangalore",
        ),
        lagna_sign=lagna, lagna_degree=0.0,
        moon_sign=default_planets["Moon"].sign,
        sun_sign=default_planets["Sun"].sign,
        nakshatra="Ashwini", nakshatra_pada=1,
        planets=default_planets, houses=houses,
        dasha=DashaData(
            maha_dasha_lord="Jupiter", maha_dasha_start="2020-01-01",
            maha_dasha_end="2036-01-01", antar_dasha_lord="Saturn",
            antar_dasha_start="2022-01-01", antar_dasha_end="2025-01-01",
        ),
    )


# ===========================================================================
# 1. YOGA DETECTION
# ===========================================================================

class TestGajakesariYoga:
    def test_present_same_house(self):
        # Moon and Jupiter in same house = distance 0 (kendra from self)
        chart = _make_chart({
            "Moon":    _planet("Moon",    40, "Taurus", 2),
            "Jupiter": _planet("Jupiter", 45, "Taurus", 2),
        })
        assert detect_gajakesari(chart)

    def test_present_seventh_house(self):
        # Moon house 1, Jupiter house 7 — mutual 7th = kendra
        chart = _make_chart({
            "Moon":    _planet("Moon",    0,  "Aries",  1),
            "Jupiter": _planet("Jupiter", 180, "Libra", 7),
        })
        assert detect_gajakesari(chart)

    def test_present_fourth_house(self):
        # Moon house 1, Jupiter house 4
        chart = _make_chart({
            "Moon":    _planet("Moon",    0,  "Aries",  1),
            "Jupiter": _planet("Jupiter", 90, "Cancer", 4),
        })
        assert detect_gajakesari(chart)

    def test_absent_non_kendra(self):
        # Moon house 1, Jupiter house 3 — not a kendra distance
        chart = _make_chart({
            "Moon":    _planet("Moon",    0,  "Aries",  1),
            "Jupiter": _planet("Jupiter", 60, "Gemini", 3),
        })
        assert not detect_gajakesari(chart)


class TestBudhadityaYoga:
    def test_present(self):
        chart = _make_chart({
            "Sun":     _planet("Sun",     10, "Aries", 1),
            "Mercury": _planet("Mercury", 15, "Aries", 1),
        })
        assert detect_budhaditya(chart)

    def test_absent_different_houses(self):
        chart = _make_chart({
            "Sun":     _planet("Sun",     10, "Aries",  1),
            "Mercury": _planet("Mercury", 45, "Taurus", 2),
        })
        assert not detect_budhaditya(chart)


class TestChandraMangalaYoga:
    def test_present_same_house(self):
        chart = _make_chart({
            "Moon": _planet("Moon", 40, "Taurus", 2),
            "Mars": _planet("Mars", 45, "Taurus", 2),
        })
        assert detect_chandra_mangala(chart)

    def test_present_kendra_from_moon(self):
        # Moon house 2, Mars house 5 — distance 3 = kendra
        chart = _make_chart({
            "Moon": _planet("Moon", 40, "Taurus", 2),
            "Mars": _planet("Mars", 130, "Leo",   5),
        })
        assert detect_chandra_mangala(chart)

    def test_absent(self):
        # Moon house 1, Mars house 3 — distance 2, not kendra
        chart = _make_chart({
            "Moon": _planet("Moon", 0,  "Aries",  1),
            "Mars": _planet("Mars", 60, "Gemini", 3),
        })
        assert not detect_chandra_mangala(chart)


class TestPanchMahapurushaYogas:
    # For Panch Mahapurusha: planet must be in own/exalted sign AND in a kendra (1,4,7,10).
    # With Aries lagna: house 1=Aries, 4=Cancer, 7=Libra, 10=Capricorn.

    def test_ruchaka_mars_own_sign_kendra(self):
        # Mars in Aries (own) in house 1 (kendra) with Aries lagna
        chart = _make_chart({"Mars": _planet("Mars", 10, "Aries", 1)}, lagna="Aries")
        assert "Ruchaka" in detect_panch_mahapurusha(chart)

    def test_ruchaka_mars_scorpio_kendra(self):
        # Mars in Scorpio (own) in house 7 with Taurus lagna
        # Taurus lagna: house 7 = Scorpio ✓
        chart = _make_chart({"Mars": _planet("Mars", 220, "Scorpio", 7)}, lagna="Taurus")
        assert "Ruchaka" in detect_panch_mahapurusha(chart)

    def test_ruchaka_absent_non_kendra(self):
        # Mars in Aries (own) but in house 3 — not kendra
        chart = _make_chart({"Mars": _planet("Mars", 10, "Aries", 3)}, lagna="Aquarius")
        assert "Ruchaka" not in detect_panch_mahapurusha(chart)

    def test_bhadra_mercury_virgo_kendra(self):
        # Mercury in Virgo (own) in house 1 with Virgo lagna
        chart = _make_chart({"Mercury": _planet("Mercury", 155, "Virgo", 1)}, lagna="Virgo")
        assert "Bhadra" in detect_panch_mahapurusha(chart)

    def test_bhadra_mercury_gemini_kendra(self):
        # Mercury in Gemini (own) in house 1 with Gemini lagna
        chart = _make_chart({"Mercury": _planet("Mercury", 65, "Gemini", 1)}, lagna="Gemini")
        assert "Bhadra" in detect_panch_mahapurusha(chart)

    def test_hamsa_jupiter_cancer_kendra(self):
        # Jupiter exalted in Cancer in house 4 with Aries lagna (house 4 = Cancer)
        chart = _make_chart({"Jupiter": _planet("Jupiter", 95, "Cancer", 4)}, lagna="Aries")
        assert "Hamsa" in detect_panch_mahapurusha(chart)

    def test_hamsa_jupiter_sagittarius_kendra(self):
        # Jupiter in Sagittarius (own) in house 1 with Sagittarius lagna
        chart = _make_chart({"Jupiter": _planet("Jupiter", 250, "Sagittarius", 1)}, lagna="Sagittarius")
        assert "Hamsa" in detect_panch_mahapurusha(chart)

    def test_malavya_venus_taurus_kendra(self):
        # Venus in Taurus (own) in house 1 with Taurus lagna
        chart = _make_chart({"Venus": _planet("Venus", 45, "Taurus", 1)}, lagna="Taurus")
        assert "Malavya" in detect_panch_mahapurusha(chart)

    def test_malavya_venus_libra_kendra(self):
        # Venus in Libra (own) in house 1 with Libra lagna
        chart = _make_chart({"Venus": _planet("Venus", 185, "Libra", 1)}, lagna="Libra")
        assert "Malavya" in detect_panch_mahapurusha(chart)

    def test_shasha_saturn_capricorn_kendra(self):
        # Saturn in Capricorn (own) in house 1 with Capricorn lagna
        chart = _make_chart({"Saturn": _planet("Saturn", 275, "Capricorn", 1)}, lagna="Capricorn")
        assert "Shasha" in detect_panch_mahapurusha(chart)

    def test_shasha_saturn_aquarius_kendra(self):
        # Saturn in Aquarius (own) in house 4 with Scorpio lagna (house 4 = Aquarius)
        chart = _make_chart({"Saturn": _planet("Saturn", 315, "Aquarius", 4)}, lagna="Scorpio")
        assert "Shasha" in detect_panch_mahapurusha(chart)

    def test_no_yoga_when_not_dignified(self):
        # Jupiter in Aries (neither own nor exalted) in kendra
        chart = _make_chart({"Jupiter": _planet("Jupiter", 10, "Aries", 1)}, lagna="Aries")
        assert "Hamsa" not in detect_panch_mahapurusha(chart)


class TestKaalSarpYoga:
    def test_present_all_planets_one_side(self):
        # Rahu house 1, Ketu house 7, all other planets in houses 2-6
        chart = _make_chart({
            "Rahu":    _planet("Rahu",    0,   "Aries",       1),
            "Ketu":    _planet("Ketu",    180, "Libra",       7),
            "Sun":     _planet("Sun",     30,  "Taurus",      2),
            "Moon":    _planet("Moon",    60,  "Gemini",      3),
            "Mars":    _planet("Mars",    90,  "Cancer",      4),
            "Mercury": _planet("Mercury", 120, "Leo",         5),
            "Jupiter": _planet("Jupiter", 150, "Virgo",       6),
            "Venus":   _planet("Venus",   155, "Virgo",       6),
            "Saturn":  _planet("Saturn",  160, "Virgo",       6),
        })
        assert detect_kaal_sarp(chart)

    def test_absent_planet_outside_arc(self):
        # Rahu house 1, Ketu house 7, Jupiter in house 9 (outside arc 1→7)
        chart = _make_chart({
            "Rahu":    _planet("Rahu",    0,   "Aries",       1),
            "Ketu":    _planet("Ketu",    180, "Libra",       7),
            "Sun":     _planet("Sun",     30,  "Taurus",      2),
            "Moon":    _planet("Moon",    60,  "Gemini",      3),
            "Mars":    _planet("Mars",    90,  "Cancer",      4),
            "Mercury": _planet("Mercury", 120, "Leo",         5),
            "Jupiter": _planet("Jupiter", 240, "Sagittarius", 9),
            "Venus":   _planet("Venus",   155, "Virgo",       6),
            "Saturn":  _planet("Saturn",  160, "Virgo",       6),
        })
        assert not detect_kaal_sarp(chart)


class TestAdhiYoga:
    def test_present(self):
        # Moon in house 1; Venus/Mercury/Jupiter in houses 6,7,8
        chart = _make_chart({
            "Moon":    _planet("Moon",    0,   "Aries",   1),
            "Venus":   _planet("Venus",   150, "Virgo",   6),
            "Mercury": _planet("Mercury", 180, "Libra",   7),
            "Jupiter": _planet("Jupiter", 210, "Scorpio", 8),
        })
        assert detect_adhi_yoga(chart)

    def test_absent_one_missing(self):
        # Jupiter not in 6/7/8 from Moon
        chart = _make_chart({
            "Moon":    _planet("Moon",    0,   "Aries",  1),
            "Venus":   _planet("Venus",   150, "Virgo",  6),
            "Mercury": _planet("Mercury", 180, "Libra",  7),
            "Jupiter": _planet("Jupiter", 30,  "Taurus", 2),
        })
        assert not detect_adhi_yoga(chart)


# ===========================================================================
# 2. DOSHA DETECTION
# ===========================================================================

class TestMangalDosha:
    @pytest.mark.parametrize("house", [1, 2, 4, 7, 8, 12])
    def test_present_in_dosha_houses(self, house):
        # Use Cancer lagna so we can easily place Mars in various houses
        lagna_signs = {1: "Aries", 2: "Taurus", 3: "Gemini", 4: "Cancer",
                       5: "Leo", 6: "Virgo", 7: "Libra", 8: "Scorpio",
                       9: "Sagittarius", 10: "Capricorn", 11: "Aquarius", 12: "Pisces"}
        mars_sign = ZODIAC_SIGNS[(ZODIAC_SIGNS.index("Aries") + house - 1) % 12]
        chart = _make_chart({"Mars": _planet("Mars", (house - 1) * 30 + 5, mars_sign, house)})
        assert detect_mangal_dosha(chart), f"Expected Mangal Dosha with Mars in house {house}"

    @pytest.mark.parametrize("house", [3, 5, 6, 9, 10, 11])
    def test_absent_in_non_dosha_houses(self, house):
        mars_sign = ZODIAC_SIGNS[(ZODIAC_SIGNS.index("Aries") + house - 1) % 12]
        chart = _make_chart({"Mars": _planet("Mars", (house - 1) * 30 + 5, mars_sign, house)})
        assert not detect_mangal_dosha(chart), f"Expected no Mangal Dosha with Mars in house {house}"


class TestPitraDosha:
    def test_present(self):
        chart = _make_chart({
            "Sun":  _planet("Sun",  10, "Aries", 1),
            "Rahu": _planet("Rahu", 15, "Aries", 1),
        })
        assert detect_pitra_dosha(chart)

    def test_absent(self):
        chart = _make_chart({
            "Sun":  _planet("Sun",  10,  "Aries", 1),
            "Rahu": _planet("Rahu", 130, "Leo",   5),
        })
        assert not detect_pitra_dosha(chart)


class TestShrapitDosha:
    def test_present(self):
        chart = _make_chart({
            "Saturn": _planet("Saturn", 130, "Leo", 5),
            "Rahu":   _planet("Rahu",   135, "Leo", 5),
        })
        assert detect_shrapit_dosha(chart)

    def test_absent(self):
        chart = _make_chart({
            "Saturn": _planet("Saturn", 250, "Sagittarius", 9),
            "Rahu":   _planet("Rahu",   130, "Leo",         5),
        })
        assert not detect_shrapit_dosha(chart)


class TestGrahanDosha:
    def test_present_sun_with_rahu(self):
        chart = _make_chart({
            "Sun":  _planet("Sun",  130, "Leo", 5),
            "Rahu": _planet("Rahu", 135, "Leo", 5),
        })
        assert detect_grahan_dosha(chart)

    def test_present_moon_with_ketu(self):
        chart = _make_chart({
            "Moon": _planet("Moon", 310, "Aquarius", 11),
            "Ketu": _planet("Ketu", 315, "Aquarius", 11),
        })
        assert detect_grahan_dosha(chart)

    def test_absent(self):
        chart = _make_chart({
            "Sun":  _planet("Sun",  10,  "Aries",   1),
            "Moon": _planet("Moon", 40,  "Taurus",  2),
            "Rahu": _planet("Rahu", 130, "Leo",     5),
            "Ketu": _planet("Ketu", 310, "Aquarius", 11),
        })
        assert not detect_grahan_dosha(chart)


class TestKaalSarpDosha:
    def test_present(self):
        chart = _make_chart({
            "Rahu":    _planet("Rahu",    0,   "Aries",  1),
            "Ketu":    _planet("Ketu",    180, "Libra",  7),
            "Sun":     _planet("Sun",     30,  "Taurus", 2),
            "Moon":    _planet("Moon",    60,  "Gemini", 3),
            "Mars":    _planet("Mars",    90,  "Cancer", 4),
            "Mercury": _planet("Mercury", 120, "Leo",    5),
            "Jupiter": _planet("Jupiter", 150, "Virgo",  6),
            "Venus":   _planet("Venus",   155, "Virgo",  6),
            "Saturn":  _planet("Saturn",  160, "Virgo",  6),
        })
        assert detect_kaal_sarp_dosha(chart)

    def test_absent(self):
        chart = _make_chart({
            "Rahu":    _planet("Rahu",    0,   "Aries",       1),
            "Ketu":    _planet("Ketu",    180, "Libra",       7),
            "Jupiter": _planet("Jupiter", 240, "Sagittarius", 9),  # outside arc
        })
        assert not detect_kaal_sarp_dosha(chart)


# ===========================================================================
# 3. PLANETARY STRENGTH
# ===========================================================================

class TestPlanetaryStrength:
    # --- Exaltation ---
    @pytest.mark.parametrize("planet,sign", [
        ("Sun", "Aries"), ("Moon", "Taurus"), ("Mars", "Capricorn"),
        ("Mercury", "Virgo"), ("Jupiter", "Cancer"), ("Venus", "Pisces"),
        ("Saturn", "Libra"),
    ])
    def test_exalted(self, planet, sign):
        assert get_planet_strength(planet, sign) == "exalted"

    # --- Debilitation ---
    @pytest.mark.parametrize("planet,sign", [
        ("Sun", "Libra"), ("Moon", "Scorpio"), ("Mars", "Cancer"),
        ("Mercury", "Pisces"), ("Jupiter", "Capricorn"), ("Venus", "Virgo"),
        ("Saturn", "Aries"),
    ])
    def test_debilitated(self, planet, sign):
        assert get_planet_strength(planet, sign) == "debilitated"

    # --- Own sign ---
    # Classical priority: exaltation > moolatrikona > own sign.
    # For planets whose own sign overlaps with MT/exaltation, use a degree past the MT range.
    # Mercury/Virgo = exaltation (not own-sign), so we test Mercury's OTHER own sign (Gemini).
    @pytest.mark.parametrize("planet,sign,degree", [
        ("Sun",     "Leo",         25.0),  # past MT range (0-20)
        ("Moon",    "Cancer",       5.0),  # Cancer is own sign, not MT/exaltation
        ("Mars",    "Aries",       15.0),  # past MT range (0-12)
        ("Mars",    "Scorpio",      5.0),  # own sign, no MT range
        ("Mercury", "Gemini",       5.0),  # own sign, no MT range (MT is Virgo)
        ("Jupiter", "Sagittarius", 12.0),  # past MT range (0-10)
        ("Jupiter", "Pisces",       5.0),  # own sign, no MT range
        ("Venus",   "Taurus",       5.0),  # own sign, no MT range (MT is Libra)
        ("Venus",   "Libra",       20.0),  # past MT range (0-15)
        ("Saturn",  "Capricorn",    5.0),  # own sign, no MT range (MT is Aquarius)
        ("Saturn",  "Aquarius",    25.0),  # past MT range (0-20)
    ])
    def test_own_sign(self, planet, sign, degree):
        result = get_planet_strength(planet, sign, degree)
        assert result == "own sign", f"{planet} in {sign} at {degree}° should be own sign, got {result}"

    # --- Moolatrikona (degree-dependent) ---
    # Mercury/Virgo is ALSO exaltation — exaltation check runs first, so Mercury/Virgo always = exalted.
    # Moon/Taurus is ALSO exaltation — same rule, always exalted regardless of degree.
    # Only test MT for planets where the MT sign is NOT also the exaltation sign.
    @pytest.mark.parametrize("planet,sign,degree", [
        ("Sun",     "Leo",         10.0),   # Sun MT: Leo 0-20 (exaltation is Aries — no conflict)
        ("Mars",    "Aries",        5.0),   # Mars MT: Aries 0-12 (exaltation is Capricorn — no conflict)
        ("Jupiter", "Sagittarius",  5.0),   # Jupiter MT: Sagittarius 0-10 (exaltation is Cancer — no conflict)
        ("Saturn",  "Aquarius",    10.0),   # Saturn MT: Aquarius 0-20 (exaltation is Libra — no conflict)
        ("Venus",   "Libra",       10.0),   # Venus MT: Libra 0-15 (exaltation is Pisces — no conflict)
        # Mercury MT is Virgo, but Virgo is also Mercury's exaltation — exaltation wins, tested below.
        # Moon MT is Taurus, but Taurus is also Moon's exaltation — exaltation wins, tested below.
    ])
    def test_moolatrikona(self, planet, sign, degree):
        result = get_planet_strength(planet, sign, degree)
        assert result == "moolatrikona", f"{planet} in {sign} at {degree}° should be moolatrikona, got {result}"

    def test_mercury_virgo_is_exalted_not_moolatrikona(self):
        # Virgo = Mercury exaltation; exaltation check runs before MT, so always exalted
        assert get_planet_strength("Mercury", "Virgo", 17.0) == "exalted"
        assert get_planet_strength("Mercury", "Virgo", 5.0) == "exalted"

    def test_moon_taurus_is_exalted_not_moolatrikona(self):
        # Taurus = Moon exaltation; always exalted regardless of degree
        assert get_planet_strength("Moon", "Taurus", 8.0) == "exalted"

    # Degree outside MT range falls back to own sign
    def test_sun_in_leo_outside_mt_range(self):
        # Sun in Leo at 25° — past MT range (0-20), should be own sign
        result = get_planet_strength("Sun", "Leo", 25.0)
        assert result == "own sign"

    # --- Friendly / Enemy / Neutral ---
    def test_sun_in_cancer_friendly(self):
        # Cancer ruled by Moon; Moon is a friend of Sun
        assert get_planet_strength("Sun", "Cancer") == "friendly sign"

    def test_sun_in_libra_is_debilitated(self):
        # Libra is debilitation for Sun — takes priority over enemy check
        assert get_planet_strength("Sun", "Libra") == "debilitated"

    def test_saturn_in_aries_is_debilitated(self):
        assert get_planet_strength("Saturn", "Aries") == "debilitated"

    def test_mercury_in_scorpio_neutral(self):
        # Scorpio ruled by Mars; Mars is NOT in Mercury's enemy list (only Moon is)
        # So Mercury in Scorpio = neutral sign (correctly)
        assert get_planet_strength("Mercury", "Scorpio") == "neutral sign"

    def test_jupiter_in_gemini_enemy(self):
        # Gemini ruled by Mercury; Mercury is enemy of Jupiter
        assert get_planet_strength("Jupiter", "Gemini") == "enemy sign"

    def test_neutral_sign(self):
        # Mars in Aquarius: Aquarius ruled by Saturn; Saturn is neutral to Mars
        result = get_planet_strength("Mars", "Aquarius")
        assert result == "neutral sign"


class TestCombustDetection:
    def test_mercury_combust(self):
        """Mercury within 6° of Sun should be flagged combust."""
        chart = _make_chart({
            "Sun":     _planet("Sun",     10, "Aries", 1, degree_in_sign=10),
            "Mercury": _planet("Mercury", 14, "Aries", 1, degree_in_sign=14),
        })
        strengths = calculate_all_strengths(chart)
        assert "combust" in strengths["Mercury"], f"Mercury should be combust, got: {strengths['Mercury']}"

    def test_mercury_not_combust_when_far(self):
        chart = _make_chart({
            "Sun":     _planet("Sun",     10, "Aries",  1, degree_in_sign=10),
            "Mercury": _planet("Mercury", 50, "Taurus", 2, degree_in_sign=20),
        })
        strengths = calculate_all_strengths(chart)
        assert "combust" not in strengths["Mercury"]

    def test_moon_never_combust(self):
        """Moon is never counted as combust (classical rule)."""
        chart = _make_chart({
            "Sun":  _planet("Sun",  10, "Aries", 1, degree_in_sign=10),
            "Moon": _planet("Moon", 13, "Aries", 1, degree_in_sign=13),
        })
        strengths = calculate_all_strengths(chart)
        assert "combust" not in strengths["Moon"]

    def test_rahu_ketu_never_combust(self):
        chart = _make_chart({
            "Sun":  _planet("Sun",  10, "Aries", 1),
            "Rahu": _planet("Rahu", 12, "Aries", 1),
            "Ketu": _planet("Ketu", 8,  "Aries", 1),
        })
        strengths = calculate_all_strengths(chart)
        assert "combust" not in strengths["Rahu"]
        assert "combust" not in strengths["Ketu"]


# ===========================================================================
# 4. ASPECT ENGINE — stubs documenting what needs to be built
# ===========================================================================

class TestAspects:
    def test_mars_special_aspects(self):
        """Mars in house 1 should aspect houses 4, 7, 8."""
        from services.rule_engine.aspect_engine import houses_aspected_by_planet
        chart = _make_chart({"Mars": _planet("Mars", 10, "Aries", 1)})
        aspects = houses_aspected_by_planet(chart, "Mars")
        assert 4 in aspects
        assert 7 in aspects
        assert 8 in aspects

    def test_jupiter_special_aspects(self):
        """Jupiter in house 1 should aspect houses 5, 7, 9."""
        from services.rule_engine.aspect_engine import houses_aspected_by_planet
        chart = _make_chart({"Jupiter": _planet("Jupiter", 10, "Aries", 1)})
        aspects = houses_aspected_by_planet(chart, "Jupiter")
        assert 5 in aspects
        assert 7 in aspects
        assert 9 in aspects

    def test_saturn_special_aspects(self):
        """Saturn in house 1 should aspect houses 3, 7, 10."""
        from services.rule_engine.aspect_engine import houses_aspected_by_planet
        chart = _make_chart({"Saturn": _planet("Saturn", 10, "Aries", 1)})
        aspects = houses_aspected_by_planet(chart, "Saturn")
        assert 3 in aspects
        assert 7 in aspects
        assert 10 in aspects

    def test_all_planets_seventh_aspect(self):
        """Every planet casts a full aspect on the 7th house from itself."""
        from services.rule_engine.aspect_engine import houses_aspected_by_planet
        chart = _make_chart()
        for planet_name, pos in chart.planets.items():
            seventh = ((pos.house - 1 + 6) % 12) + 1
            aspects = houses_aspected_by_planet(chart, planet_name)
            assert seventh in aspects, f"{planet_name} in house {pos.house} should aspect house {seventh}"

    def test_house_aspected_by_planet(self):
        """Given a house, return which planets aspect it."""
        from services.rule_engine.aspect_engine import planets_aspecting_house
        chart = _make_chart({"Jupiter": _planet("Jupiter", 10, "Aries", 1)})
        # Jupiter in house 1 aspects houses 5, 7, 9
        aspecting = planets_aspecting_house(chart, 7)
        assert "Jupiter" in aspecting

    def test_aspect_engine_in_rule_engine_result(self):
        """aspects_by_planet and planets_aspecting_house are populated in RuleEngineResult."""
        chart = _make_chart({"Mars": _planet("Mars", 10, "Aries", 1)})
        result = run_rule_engine(chart)
        assert "Mars" in result.aspects_by_planet
        assert 4 in result.aspects_by_planet["Mars"]
        assert "Mars" in result.planets_aspecting_house.get(4, [])

    def test_dig_bala_in_result(self):
        """Planets in their Dig Bala house appear in dig_bala_planets."""
        # Jupiter/Mercury strong in house 1; Sun/Mars strong in house 10
        chart = _make_chart({
            "Jupiter": _planet("Jupiter", 10, "Aries", 1),
            "Sun":     _planet("Sun",     280, "Capricorn", 10),
        })
        result = run_rule_engine(chart)
        assert "Jupiter" in result.dig_bala_planets
        assert "Sun" in result.dig_bala_planets
        assert "Moon" not in result.dig_bala_planets  # Moon strong in house 4, not placed there

    def test_functional_nature_in_result(self):
        """functional_nature is populated from FUNCTIONAL_NATURE_BY_LAGNA for known lagnas."""
        chart = _make_chart(lagna="Aries")
        result = run_rule_engine(chart)
        assert result.functional_nature.get("Saturn") == "malefic"
        assert result.functional_nature.get("Mars") == "benefic"   # lagna lord (1+8)


# ===========================================================================
# 5. FUNCTIONAL NATURE — verified for ALL 12 lagnas against classical invariants
# ===========================================================================

_VALID_NATURES = {"benefic", "malefic", "neutral", "yogakaraka"}
# The six universally-agreed yogakarakas (kendra+trikona lord).
_CANONICAL_YOGAKARAKAS = {
    "Taurus": "Saturn", "Cancer": "Mars", "Leo": "Mars",
    "Libra": "Saturn", "Capricorn": "Venus", "Aquarius": "Venus",
}


class TestFunctionalNature:
    def test_aries_lagna_functional_nature(self):
        nature = FUNCTIONAL_NATURE_BY_LAGNA.get("Aries", {})
        # Mars lords 1+8 — lagna lord, benefic (NOT yogakaraka)
        assert nature.get("Mars") == "benefic"
        assert nature.get("Saturn") == "malefic"   # 10th/11th lord
        assert nature.get("Jupiter") == "benefic"  # 9th/12th — trikona wins
        assert nature.get("Sun") == "benefic"      # 5th lord

    @pytest.mark.parametrize("lagna", ZODIAC_SIGNS)
    def test_all_lagnas_present_and_valid(self, lagna):
        """Every lagna has all 7 planets with a valid functional-nature value."""
        nature = FUNCTIONAL_NATURE_BY_LAGNA.get(lagna, {})
        for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
            assert nature.get(planet) in _VALID_NATURES, f"{lagna}/{planet} invalid: {nature.get(planet)}"

    @pytest.mark.parametrize("lagna", ZODIAC_SIGNS)
    def test_yogakaraka_invariant(self, lagna):
        """Exactly the six classical yogakarakas exist; the table marks them and no others."""
        nature = FUNCTIONAL_NATURE_BY_LAGNA.get(lagna, {})
        marked = {p for p, v in nature.items() if v == "yogakaraka"}
        expected = {_CANONICAL_YOGAKARAKAS[lagna]} if lagna in _CANONICAL_YOGAKARAKAS else set()
        assert marked == expected, f"{lagna}: yogakaraka mismatch (got {marked}, expected {expected})"

    @pytest.mark.parametrize("lagna", ZODIAC_SIGNS)
    def test_lagna_lord_never_malefic(self, lagna):
        """The lagna lord is always a friend — benefic or neutral, never malefic."""
        lords = house_lords_for_lagna(lagna)
        lagna_lord = next((p for p, hs in lords.items() if 1 in hs), None)
        nature = FUNCTIONAL_NATURE_BY_LAGNA.get(lagna, {})
        assert nature.get(lagna_lord) != "malefic", f"{lagna}: lagna lord {lagna_lord} marked malefic"

    @pytest.mark.parametrize("lagna", ZODIAC_SIGNS)
    def test_pure_dusthana_lord_is_malefic(self, lagna):
        """A planet lording only dusthana(s) (6/8/12) with no trikona/lagna is malefic."""
        lords = house_lords_for_lagna(lagna)
        nature = FUNCTIONAL_NATURE_BY_LAGNA.get(lagna, {})
        for planet, houses in lords.items():
            hs = set(houses)
            only_dusthana = hs & {6, 8, 12} and not (hs & {1, 5, 9}) and not (hs & {4, 7, 10})
            if only_dusthana:
                assert nature.get(planet) == "malefic", \
                    f"{lagna}: {planet} lords only dusthana {houses} but is {nature.get(planet)}"

    @pytest.mark.parametrize("lagna", ZODIAC_SIGNS)
    def test_table_yogakaraka_matches_derivation(self, lagna):
        """Every planet the table marks yogakaraka truly lords a kendra AND a trikona."""
        lords = house_lords_for_lagna(lagna)
        nature = FUNCTIONAL_NATURE_BY_LAGNA.get(lagna, {})
        for planet, value in nature.items():
            if value == "yogakaraka":
                assert is_yogakaraka(lords.get(planet, [])), \
                    f"{lagna}: {planet} marked yogakaraka but lords {lords.get(planet)}"


# ===========================================================================
# 6. RULE ENGINE INTEGRATION
# ===========================================================================

class TestRuleEngineIntegration:
    def test_house_lords_all_12_populated(self):
        chart = _make_chart(lagna="Aries")
        result = run_rule_engine(chart)
        assert len(result.house_lords) == 12
        assert result.house_lords[1] == "Mars"   # Aries lagna → house 1 = Aries → Mars
        assert result.house_lords[4] == "Moon"   # house 4 = Cancer → Moon
        assert result.house_lords[7] == "Venus"  # house 7 = Libra → Venus
        assert result.house_lords[10] == "Saturn" # house 10 = Capricorn → Saturn

    def test_planet_category_lists_populated(self):
        chart = _make_chart({
            "Jupiter": _planet("Jupiter", 10, "Aries", 1),   # kendra + trikona
            "Saturn":  _planet("Saturn",  200, "Libra", 7),  # kendra
            "Mars":    _planet("Mars",    90,  "Cancer", 4), # kendra
            "Sun":     _planet("Sun",     120, "Leo",    5), # not kendra/trikona/dusthana
            "Mercury": _planet("Mercury", 170, "Virgo",  6), # dusthana
        }, lagna="Aries")
        result = run_rule_engine(chart)
        assert "Jupiter" in result.kendra_planets
        assert "Jupiter" in result.trikona_planets
        assert "Saturn" in result.kendra_planets
        assert "Mercury" in result.dusthana_planets

    def test_retrograde_planets_detected(self):
        chart = _make_chart({
            "Saturn": _planet_retro("Saturn", 250, "Sagittarius", 9),
            "Mars":   _planet_retro("Mars",   10,  "Aries",       1),
        })
        result = run_rule_engine(chart)
        assert "Saturn" in result.retrograde_planets
        assert "Mars" in result.retrograde_planets
        assert "Sun" not in result.retrograde_planets

    def test_active_dasha_in_result(self):
        chart = _make_chart()
        result = run_rule_engine(chart)
        assert result.active_dasha["maha"] == "Jupiter"
        assert result.active_dasha["antar"] == "Saturn"
        assert "maha_end" in result.active_dasha

    def test_strengths_all_planets_present(self):
        chart = _make_chart()
        result = run_rule_engine(chart)
        for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"):
            assert planet in result.planet_strengths, f"{planet} missing from planet_strengths"

    def test_combust_flagged_in_engine(self):
        chart = _make_chart({
            "Sun":     _planet("Sun",     10, "Aries", 1, degree_in_sign=10),
            "Mercury": _planet("Mercury", 14, "Aries", 1, degree_in_sign=14),
        })
        result = run_rule_engine(chart)
        assert "combust" in result.planet_strengths.get("Mercury", "")

    def test_yoga_list_in_result(self):
        # Chart with Gajakesari (Moon-Jupiter same house) and Budhaditya (Sun-Mercury same house)
        chart = _make_chart({
            "Sun":     _planet("Sun",     10, "Aries", 1),
            "Mercury": _planet("Mercury", 15, "Aries", 1),
            "Moon":    _planet("Moon",    95, "Cancer", 4),
            "Jupiter": _planet("Jupiter", 90, "Cancer", 4),
        })
        result = run_rule_engine(chart)
        assert "Gajakesari" in result.yogas_present
        assert "Budhaditya" in result.yogas_present
