"""Normalize Prokerala responses into the internal chart model."""

import logging
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from utils.astro_constants import SANSKRIT_TO_ENGLISH, SIGN_RULERS, ZODIAC_SIGNS
from utils.nakshatras import nakshatra_of, normalize_nakshatra, pada_of

logger = logging.getLogger(__name__)


def _num(value, default: float = 0.0) -> float:
    """Parse a possibly-string/None numeric Prokerala field without throwing."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y", "r", "retrograde")
    return bool(value)


def normalize_prokerala_response(raw: dict, user_id: str, birth_data: BirthData) -> NormalizedChart:
    # TODO: ASTROLOGY EXPERT REQUIRED — Verify all fields against live Prokerala responses.
    try:
        data = raw.get("data", raw)
        planets = _parse_planets(data)
        houses = _parse_houses(data)
        dasha = _parse_dasha(data)
        asc_sign, asc_longitude = _extract_ascendant(data)
        lagna = _get_lagna_sign(data, houses)  # raises loudly if indeterminable
        _assign_planet_houses(planets, lagna)
        moon = planets.get("Moon")
        sun = planets.get("Sun")
        # Minimum-viable-chart gate: a chart with no luminaries is unusable; fail loudly
        # rather than silently producing a degenerate reading.
        if moon is None and sun is None:
            raise ValueError("Chart has neither Moon nor Sun — unusable data")
        return NormalizedChart(
            user_id=user_id,
            birth_data=birth_data,
            lagna_sign=lagna,
            lagna_degree=asc_longitude % 30,
            moon_sign=moon.sign if moon else "Unknown",
            sun_sign=sun.sign if sun else "Unknown",
            # Janma nakshatra = the Moon's nakshatra (computed from longitude).
            nakshatra=(moon.nakshatra if moon and moon.nakshatra else
                       (nakshatra_of(moon.longitude) if moon else "")),
            nakshatra_pada=(moon.nakshatra_pada if moon and moon.nakshatra_pada else
                            (pada_of(moon.longitude) if moon else 1)),
            planets=planets,
            houses=houses,
            dasha=dasha,
            yogas_raw=data.get("yoga_details", []),
            divisional_charts=data.get("divisional_charts", {}),
            raw_prokerala_response=raw,
        )
    except Exception as exc:
        logger.exception("Failed to normalize Prokerala response")
        raise ValueError(f"Chart normalization failed: {exc}") from exc


def _resolve_nakshatra(
    planet: str, longitude: float, provided_name: str, provided_pada: int
) -> tuple[str, int]:
    """Single source of truth for a planet's nakshatra + pada.

    The nakshatra/pada are a pure deterministic function of the sidereal longitude (which
    Prokerala always supplies under ayanamsa=1), so we derive both from it — guaranteeing the
    name, pada, lord and every prompt block stay mutually consistent. Prokerala's own name is
    normalised and used only (a) to log a genuine disagreement and (b) as a fallback when the
    longitude is missing."""
    norm_provided = normalize_nakshatra(provided_name)
    if longitude:
        derived_name = nakshatra_of(longitude)
        derived_pada = pada_of(longitude)
        if norm_provided and norm_provided != derived_name:
            logger.warning(
                "Nakshatra mismatch for %s: Prokerala '%s' vs longitude-derived '%s' "
                "(%.4f°) — using longitude-derived for consistency.",
                planet, provided_name, derived_name, longitude,
            )
        return derived_name, derived_pada
    # No usable longitude — fall back to Prokerala's (normalised) values.
    return (norm_provided or provided_name or ""), (provided_pada or 1)


def _parse_planets(data: dict) -> dict[str, PlanetPosition]:
    result = {}
    source = data.get("planets", data.get("planet_position", {}))
    if isinstance(source, list):
        source = {str(item.get("name", "")).lower(): item for item in source}
    for raw_name in ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"):
        canonical = raw_name.title()
        item = source.get(raw_name, source.get(canonical, {}))
        if not item:
            continue
        rasi = item.get("rasi", item.get("sign", {}))
        sign = _normalize_sign(rasi.get("name", "") if isinstance(rasi, dict) else str(rasi))
        longitude = _num(item.get("longitude"))
        # If Prokerala omits the rasi, derive the sign from the sidereal longitude so the
        # planet still gets a valid sign (and therefore a whole-sign house).
        if sign not in ZODIAC_SIGNS and longitude:
            sign = ZODIAC_SIGNS[int(longitude // 30) % 12]
        # Nakshatra and pada are, by definition, a function of the sidereal longitude. We
        # derive BOTH from the (always-present) Prokerala longitude so the name, pada, lord,
        # and every downstream prompt block agree exactly — Prokerala's own name field is only
        # used to cross-check (and as a fallback if the longitude is somehow missing). This
        # also avoids feeding the LLM two different "locked" janma nakshatras for one planet.
        nak = item.get("nakshatra", {})
        provided_name = nak.get("name", "") if isinstance(nak, dict) else str(nak)
        provided_pada = _int(nak.get("pada")) if isinstance(nak, dict) else 0
        nak_name, nak_pada = _resolve_nakshatra(canonical, longitude, provided_name, provided_pada)
        result[canonical] = PlanetPosition(
            planet=canonical,
            longitude=longitude,
            sign=sign,
            house=_int(item.get("house")),
            nakshatra=nak_name,
            nakshatra_pada=nak_pada,
            is_retrograde=_truthy(item.get("isRetrograde", item.get("is_retrograde", False))),
            # Fall back to longitude-within-sign when no explicit in-sign degree is given.
            degree_in_sign=_num(item.get("degree", item.get("longitude_within_sign")), longitude % 30),
        )
    return result


def _parse_houses(data: dict) -> dict[int, HouseData]:
    source = data.get("houses", data.get("bhava", []))
    houses = {}
    for item in source or []:
        number = _int(item.get("number", item.get("house", 0)))
        sign_data = item.get("sign", {})
        raw_sign = sign_data.get("name", "") if isinstance(sign_data, dict) else str(sign_data)
        sign = _normalize_sign(raw_sign)
        if 1 <= number <= 12:
            houses[number] = HouseData(
                house_number=number, sign=sign, lord=SIGN_RULERS.get(sign, ""),
                degree=_num(item.get("degree")),
            )
    if not houses:
        asc_sign, _ = _extract_ascendant(data)
        # No silent Aries default: if the ascendant is unusable, leave houses empty so the
        # caller (_get_lagna_sign) raises loudly instead of fabricating an Aries chart.
        if asc_sign not in ZODIAC_SIGNS:
            logger.warning("No house data and no valid ascendant sign (%r); cannot build whole-sign houses", asc_sign)
            return houses
        start = ZODIAC_SIGNS.index(asc_sign)
        for offset in range(12):
            sign = ZODIAC_SIGNS[(start + offset) % 12]
            houses[offset + 1] = HouseData(
                house_number=offset + 1, sign=sign, lord=SIGN_RULERS[sign], degree=0
            )
    return houses


def _parse_dasha(data: dict) -> DashaData:
    periods = data.get("dasha_periods", data.get("dasha", []))

    if isinstance(periods, list) and periods:
        now = datetime.now(timezone.utc)

        def _parse_dt(value) -> datetime:
            s = str(value).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        def _in_range(item: dict) -> bool:
            try:
                return _parse_dt(item["start"]) <= now <= _parse_dt(item["end"])
            except Exception:
                return False

        maha = next((p for p in periods if _in_range(p)), None)
        if maha is None:
            logger.warning("No Mahadasha period covers the current date; defaulting to the last period")
            maha = periods[-1]
        antars = maha.get("antardasha", [])
        antar = next((a for a in antars if _in_range(a)), antars[-1] if antars else {})
        pratys = antar.get("pratyantardasha", [])
        praty = next((p for p in pratys if _in_range(p)), pratys[-1] if pratys else {})

        def _date(item: dict, key: str) -> str:
            return str(item.get(key, item.get(key.replace("_", ""), "")))

        return DashaData(
            maha_dasha_lord=str(maha.get("name", "")),
            maha_dasha_start=_date(maha, "start"),
            maha_dasha_end=_date(maha, "end"),
            antar_dasha_lord=str(antar.get("name", "")),
            antar_dasha_start=_date(antar, "start"),
            antar_dasha_end=_date(antar, "end"),
            pratyantara_dasha_lord=str(praty.get("name", "")) or None,
            pratyantara_dasha_start=_date(praty, "start") or None,
            pratyantara_dasha_end=_date(praty, "end") or None,
        )

    # Fallback: legacy dict format
    source = periods if isinstance(periods, dict) else {}
    current = source.get("current", source)
    maha = current.get("maha_dasha", current.get("mahaDasha", {}))
    antar = current.get("antar_dasha", current.get("antarDasha", {}))
    praty = current.get("pratyantar_dasha", current.get("pratyantarDasha", {}))

    def lord(value: dict) -> str:
        return str(value.get("lord", value.get("name", value.get("planet", ""))))

    def date(value: dict, key: str) -> str:
        return str(value.get(key, value.get(key.replace("_", ""), "")))

    return DashaData(
        maha_dasha_lord=lord(maha), maha_dasha_start=date(maha, "start_date"),
        maha_dasha_end=date(maha, "end_date"), antar_dasha_lord=lord(antar),
        antar_dasha_start=date(antar, "start_date"), antar_dasha_end=date(antar, "end_date"),
        pratyantara_dasha_lord=lord(praty) or None,
        pratyantara_dasha_start=date(praty, "start_date") or None,
        pratyantara_dasha_end=date(praty, "end_date") or None,
    )


def _extract_ascendant(data: dict) -> tuple[str, float]:
    """Prokerala returns the ascendant as a 'planet' named "Ascendant" inside the
    planet-position list (there is no separate ascendant/houses field). Return its
    (normalized_sign, longitude), falling back to an explicit ``ascendant`` field if present."""
    source = data.get("planets", data.get("planet_position", []))
    items = source if isinstance(source, list) else (source.values() if isinstance(source, dict) else [])
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).strip().lower() == "ascendant":
            rasi = item.get("rasi", item.get("sign", {}))
            sign = _normalize_sign(rasi.get("name", "") if isinstance(rasi, dict) else str(rasi))
            return sign, _num(item.get("longitude"))
    # Explicit ascendant field (other Prokerala endpoints / legacy shapes).
    asc = data.get("ascendant", {})
    if isinstance(asc, dict):
        rasi = asc.get("rasi", asc.get("sign", {}))
        sign = _normalize_sign(rasi.get("name", "") if isinstance(rasi, dict) else str(rasi))
        return sign, _num(asc.get("longitude"))
    return "", 0.0


def _normalize_sign(raw: str) -> str:
    """Convert Sanskrit/variant sign names to canonical English; log anything unrecognized."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw in SANSKRIT_TO_ENGLISH:
        return SANSKRIT_TO_ENGLISH[raw]
    titled = raw.title()
    if titled in ZODIAC_SIGNS:
        return titled
    if titled in SANSKRIT_TO_ENGLISH:
        return SANSKRIT_TO_ENGLISH[titled]
    logger.warning("Unrecognized sign name from Prokerala: %r", raw)
    return titled


def _assign_planet_houses(planets: dict[str, "PlanetPosition"], lagna: str) -> None:
    """Compute house number for each planet from its sign relative to lagna (whole-sign system)."""
    if lagna not in ZODIAC_SIGNS:
        return
    lagna_idx = ZODIAC_SIGNS.index(lagna)
    for pos in planets.values():
        if pos.house == 0 and pos.sign in ZODIAC_SIGNS:
            sign_idx = ZODIAC_SIGNS.index(pos.sign)
            pos.house = (sign_idx - lagna_idx) % 12 + 1


def _get_lagna_sign(data: dict, houses: dict[int, HouseData]) -> str:
    value, _ = _extract_ascendant(data)
    if value in ZODIAC_SIGNS:
        return value
    h1 = houses.get(1)
    if h1 and h1.sign in ZODIAC_SIGNS:
        return h1.sign
    # Lagna drives every house assignment — never guess it. Fail loudly.
    raise ValueError("Could not determine a valid lagna (ascendant) from the chart data")


def build_chart_summary(chart: NormalizedChart) -> str:
    """Authoritative, locked snapshot of the chart. Every placement and dasha date here is
    FIXED — the synthesis must never state a value that contradicts this block."""
    from utils.formatting import format_date
    from services.rule_engine.strength_calculator import get_planet_strength
    d = chart.dasha
    # Self-heal janma nakshatra for charts cached before nakshatra-from-longitude existed.
    moon = chart.planets.get("Moon")
    nak_name = chart.nakshatra or (nakshatra_of(moon.longitude) if moon else "")
    nak_pada = chart.nakshatra_pada or (pada_of(moon.longitude) if moon else 1)
    lines = [
        f"Birth: {chart.birth_data.date} {chart.birth_data.time} | {chart.birth_data.place_name}",
        f"Lagna (Ascendant): {chart.lagna_sign}",
        f"Janma Nakshatra (Moon's): {nak_name} pada {nak_pada}",
        "Planetary placements (sign | dignity | house | nakshatra) — FIXED, never restate differently:",
    ]
    for name, pos in chart.planets.items():
        retro = " | retrograde" if pos.is_retrograde else ""
        nak = f" | {pos.nakshatra}" if pos.nakshatra else ""
        # State the rasi dignity so the narrator never asserts a strength that contradicts it
        # (e.g. a debilitated planet must be flagged as such, even if a yoga later redeems it).
        # Rahu/Ketu get their sign-friendship dignity too (via the sign lord) — a minor but real
        # signal that would otherwise appear nowhere.
        dignity = f" | {get_planet_strength(name, pos.sign, pos.degree_in_sign)}"
        lines.append(f"  {name}: {pos.sign}{dignity} | house {pos.house}{nak}{retro}")
    if d.maha_dasha_lord:
        lines.append("Vimshottari dasha (FIXED dates — do NOT recompute or guess):")
        lines.append(
            f"  Mahadasha: {d.maha_dasha_lord} — runs {format_date(d.maha_dasha_start)} "
            f"to {format_date(d.maha_dasha_end)} (a multi-year period)"
        )
        if d.antar_dasha_lord:
            lines.append(
                f"  Antardasha (sub-period inside it): {d.antar_dasha_lord} — "
                f"{format_date(d.antar_dasha_start)} to {format_date(d.antar_dasha_end)}"
            )
    return "\n".join(lines)
