"""Normalize Prokerala responses into the internal chart model."""

import logging
from datetime import datetime, timezone

from models.chart import BirthData, DashaData, HouseData, NormalizedChart, PlanetPosition
from utils.astro_constants import SANSKRIT_TO_ENGLISH, SIGN_RULERS, ZODIAC_SIGNS

logger = logging.getLogger(__name__)


def normalize_prokerala_response(raw: dict, user_id: str, birth_data: BirthData) -> NormalizedChart:
    # TODO: ASTROLOGY EXPERT REQUIRED — Verify all fields against live Prokerala responses.
    try:
        data = raw.get("data", raw)
        planets = _parse_planets(data)
        houses = _parse_houses(data)
        dasha = _parse_dasha(data)
        lagna = _get_lagna_sign(data, houses)
        _assign_planet_houses(planets, lagna)
        moon = planets.get("Moon")
        sun = planets.get("Sun")
        return NormalizedChart(
            user_id=user_id,
            birth_data=birth_data,
            lagna_sign=lagna,
            lagna_degree=float(data.get("ascendant", {}).get("longitude", 0)),
            moon_sign=moon.sign if moon else "Unknown",
            sun_sign=sun.sign if sun else "Unknown",
            nakshatra=data.get("nakshatra", {}).get("name", moon.nakshatra if moon else ""),
            nakshatra_pada=int(data.get("nakshatra", {}).get("pada", moon.nakshatra_pada if moon else 1)),
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
        nak = item.get("nakshatra", {})
        result[canonical] = PlanetPosition(
            planet=canonical,
            longitude=float(item.get("longitude", 0)),
            sign=sign,
            house=int(item.get("house", 0)),
            nakshatra=nak.get("name", "") if isinstance(nak, dict) else str(nak),
            nakshatra_pada=int(nak.get("pada", 1)) if isinstance(nak, dict) else 1,
            is_retrograde=bool(item.get("isRetrograde", item.get("is_retrograde", False))),
            degree_in_sign=float(item.get("degree", item.get("longitude_within_sign", 0))),
        )
    return result


def _parse_houses(data: dict) -> dict[int, HouseData]:
    source = data.get("houses", data.get("bhava", []))
    houses = {}
    for item in source or []:
        number = int(item.get("number", item.get("house", 0)))
        sign_data = item.get("sign", {})
        sign = sign_data.get("name", "") if isinstance(sign_data, dict) else str(sign_data)
        if 1 <= number <= 12:
            houses[number] = HouseData(
                house_number=number, sign=sign, lord=SIGN_RULERS.get(sign, ""),
                degree=float(item.get("degree", 0)),
            )
    if not houses:
        asc = data.get("ascendant", {})
        rasi = asc.get("rasi", asc.get("sign", {})) if isinstance(asc, dict) else {}
        asc_sign = rasi.get("name", "Aries") if isinstance(rasi, dict) else str(rasi)
        start = ZODIAC_SIGNS.index(asc_sign) if asc_sign in ZODIAC_SIGNS else 0
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

        def _in_range(item: dict) -> bool:
            try:
                return (
                    datetime.fromisoformat(item["start"]) <= now
                    <= datetime.fromisoformat(item["end"])
                )
            except Exception:
                return False

        maha = next((p for p in periods if _in_range(p)), periods[-1])
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


def _normalize_sign(raw: str) -> str:
    """Convert Sanskrit sign names to English for internal consistency."""
    return SANSKRIT_TO_ENGLISH.get(raw, raw)


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
    asc = data.get("ascendant", {})
    rasi = asc.get("rasi", asc.get("sign", {})) if isinstance(asc, dict) else {}
    value = _normalize_sign(rasi.get("name", "") if isinstance(rasi, dict) else str(rasi))
    return value or houses[1].sign


def build_chart_summary(chart: NormalizedChart) -> str:
    lines = [
        f"Birth: {chart.birth_data.date} {chart.birth_data.time} | {chart.birth_data.place_name}",
        f"Lagna: {chart.lagna_sign} | Moon: {chart.moon_sign} | Sun: {chart.sun_sign}",
        f"Janma Nakshatra: {chart.nakshatra} Pada {chart.nakshatra_pada}",
        "Planetary Positions:",
    ]
    for name, pos in chart.planets.items():
        flags = f"{' (R)' if pos.is_retrograde else ''}{' | ' + pos.strength if pos.strength else ''}"
        lines.append(f"  {name}: {pos.sign}, House {pos.house}{flags}")
    lines.extend([
        f"Current Dasha: {chart.dasha.maha_dasha_lord} Mahadasha / "
        f"{chart.dasha.antar_dasha_lord} Antardasha",
        f"Maha period: {chart.dasha.maha_dasha_start} → {chart.dasha.maha_dasha_end}",
        f"Antar period: {chart.dasha.antar_dasha_start} → {chart.dasha.antar_dasha_end}",
    ])
    return "\n".join(lines)
